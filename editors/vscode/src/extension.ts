import { createHash, randomBytes } from "node:crypto"
import { execFile } from "node:child_process"
import { access, readFile } from "node:fs/promises"
import { isAbsolute, relative, resolve, sep } from "node:path"
import { promisify } from "node:util"

import * as vscode from "vscode"

import type {
  Evidence,
  EvidenceEntry,
  EvidenceManifest,
  EvidenceViewModel,
  IndexedManifest,
} from "./types.js"

const execFileAsync = promisify(execFile)

function sha256(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex")
}

function inside(root: string, candidate: string): boolean {
  const relation = relative(root, candidate)
  return relation === "" || (!relation.startsWith(`..${sep}`) && relation !== ".." && !isAbsolute(relation))
}

async function repositoryRoot(): Promise<string | undefined> {
  const configured = vscode.workspace
    .getConfiguration("spec2lean")
    .get<string>("repositoryRoot", "")
    .trim()
  const candidates = configured.length > 0
    ? [configured]
    : (vscode.workspace.workspaceFolders ?? []).map((folder) => folder.uri.fsPath)
  for (const candidate of candidates) {
    try {
      await Promise.all([
        access(resolve(candidate, "spec2lean")),
        access(resolve(candidate, "engine/orchestrator/package.json")),
      ])
      return candidate
    } catch {
      // Continue searching other workspace roots.
    }
  }
  return undefined
}

async function runCli(root: string, args: string[]): Promise<string> {
  const { stdout, stderr } = await execFileAsync(resolve(root, "spec2lean"), args, {
    cwd: root,
    timeout: 120_000,
    maxBuffer: 4 * 1024 * 1024,
  })
  if (stderr.trim().length > 0) console.warn(stderr)
  return stdout
}

class ManifestIndex {
  private manifests: IndexedManifest[] = []
  private root: string | undefined
  private readonly changeEmitter = new vscode.EventEmitter<void>()

  readonly onDidChange = this.changeEmitter.event

  async refresh(): Promise<void> {
    const root = await repositoryRoot()
    this.root = root
    if (root === undefined) {
      this.manifests = []
      this.changeEmitter.fire()
      return
    }
    const files = await vscode.workspace.findFiles(
      new vscode.RelativePattern(root, "runs/*/traceability/evidence-*.json"),
    )
    const loaded: IndexedManifest[] = []
    for (const uri of files) {
      try {
        const manifest = JSON.parse(await readFile(uri.fsPath, "utf8")) as EvidenceManifest
        if ((manifest.schemaVersion === 1 || manifest.schemaVersion === 2) && manifest.manifestType === "spec2lean_evidence_manifest") {
          loaded.push({
            manifestPath: relative(root, uri.fsPath).split(sep).join("/"),
            manifest,
          })
        }
      } catch (error) {
        console.warn(`Cannot load Spec2Lean evidence manifest ${uri.fsPath}`, error)
      }
    }
    this.manifests = loaded.sort((left, right) =>
      left.manifestPath.localeCompare(right.manifestPath),
    )
    this.changeEmitter.fire()
  }

  forDocument(document: vscode.TextDocument): IndexedManifest | undefined {
    if (this.root === undefined || !inside(this.root, document.uri.fsPath)) return undefined
    const documentPath = relative(this.root, document.uri.fsPath).split(sep).join("/")
    const documentSha256 = sha256(Buffer.from(document.getText(), "utf8"))
    const rank = (indexed: IndexedManifest): number =>
      (indexed.manifest.diagnostics.pdfAlignment?.matched ?? 0) * 1_000_000 +
      indexed.manifest.entries.reduce((sum, entry) => sum + entry.evidence.length, 0)
    const preferred = (matches: IndexedManifest[]): IndexedManifest | undefined =>
      matches
        .filter(({ manifest }) => manifest.leanDocument.sha256 === documentSha256)
        .sort((left, right) => rank(right) - rank(left))[0]
    return preferred(this.manifests.filter(({ manifest }) => manifest.leanDocument.path === documentPath))
      ?? preferred(this.manifests.filter(({ manifest }) =>
        documentPath.endsWith(`/lean/${manifest.leanDocument.path.split("/").at(-1) ?? ""}`),
      ))
  }

  entryAt(document: vscode.TextDocument, zeroBasedLine: number): {
    indexed: IndexedManifest
    entry: EvidenceEntry
  } | undefined {
    const indexed = this.forDocument(document)
    if (indexed === undefined) return undefined
    const line = zeroBasedLine + 1
    const entry = indexed.manifest.entries.find((candidate) =>
      line >= candidate.leanRange.startLine && line <= candidate.leanRange.endLine,
    )
    return entry === undefined ? undefined : { indexed, entry }
  }
}

class EvidenceCodeLensProvider implements vscode.CodeLensProvider {
  private readonly changeEmitter = new vscode.EventEmitter<void>()
  readonly onDidChangeCodeLenses = this.changeEmitter.event

  constructor(private readonly index: ManifestIndex) {
    index.onDidChange(() => this.changeEmitter.fire())
  }

  provideCodeLenses(document: vscode.TextDocument): vscode.CodeLens[] {
    const indexed = this.index.forDocument(document)
    if (indexed === undefined) return []
    return indexed.manifest.entries
      .filter((entry) => entry.semanticIds.length > 0 || entry.evidence.length > 0)
      .map((entry) => new vscode.CodeLens(
        new vscode.Range(entry.leanRange.startLine - 1, 0, entry.leanRange.startLine - 1, 0),
        {
          command: "spec2lean.showEvidence",
          title: `$(references) Spec2Lean: ${entry.claims.length} claims · ${entry.evidence.length} sources`,
          arguments: [indexed.manifestPath, entry.entryId],
          tooltip: `Show hash-bound source evidence for ${entry.declarationName}`,
        },
      ))
  }
}

function htmlExcerpt(raw: string): string {
  return raw
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, " ")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim()
}

async function sourceExcerpt(root: string, evidence: Evidence): Promise<string | undefined> {
  if (evidence.quotation !== undefined) return evidence.quotation
  if (evidence.sourceKind !== "HTML") return undefined
  const start = evidence.locator.startLine
  const end = evidence.locator.endLine
  if (start === undefined || end === undefined || end < start || end - start > 200) return undefined
  const data = await readFile(resolve(root, evidence.documentPath), "utf8")
  return htmlExcerpt(data.split(/\r?\n/).slice(start - 1, end).join("\n"))
}

class EvidencePanel {
  private panel: vscode.WebviewPanel | undefined
  private current: { indexed: IndexedManifest; entry: EvidenceEntry } | undefined

  constructor(private readonly extensionUri: vscode.Uri) {}

  isOpen(): boolean {
    return this.panel !== undefined
  }

  async show(indexed: IndexedManifest, entry: EvidenceEntry, preserveFocus = false): Promise<void> {
    const root = await repositoryRoot()
    if (root === undefined) throw new Error("Spec2Lean repository root was not found")
    if (this.panel === undefined) {
      this.panel = vscode.window.createWebviewPanel(
        "spec2leanEvidence",
        "Spec2Lean Evidence",
        { viewColumn: vscode.ViewColumn.Beside, preserveFocus },
        {
          enableScripts: true,
          retainContextWhenHidden: true,
          localResourceRoots: [vscode.Uri.file(root), vscode.Uri.joinPath(this.extensionUri, "dist")],
        },
      )
      this.panel.onDidDispose(() => { this.panel = undefined })
      this.panel.webview.onDidReceiveMessage((message: unknown) => {
        void this.handleMessage(message)
      })
      this.panel.webview.html = this.shell(this.panel.webview)
    } else if (!preserveFocus) {
      this.panel.reveal(vscode.ViewColumn.Beside, false)
    }
    this.current = { indexed, entry }
    this.panel.title = `Evidence: ${entry.declarationName}`
    await this.postCurrent(root)
  }

  private async postCurrent(root: string): Promise<void> {
    if (this.panel === undefined || this.current === undefined) return
    const { indexed, entry } = this.current
    const evidence = await Promise.all(entry.evidence.map(async (item) => {
      const absolute = resolve(root, item.documentPath)
      if (!inside(root, absolute)) {
        return {
          ...item,
          sourceUri: "",
          sourceVerified: false,
          sourceProblem: "Source path escapes the repository",
        }
      }
      try {
        const data = await readFile(absolute)
        const actual = sha256(data)
        return {
          ...item,
          sourceUri: this.panel?.webview.asWebviewUri(vscode.Uri.file(absolute)).toString() ?? "",
          sourceVerified: actual === item.documentSha256,
          sourceProblem: actual === item.documentSha256 ? undefined : "SHA-256 mismatch",
          excerpt: await sourceExcerpt(root, item),
        }
      } catch (error) {
        return {
          ...item,
          sourceUri: "",
          sourceVerified: false,
          sourceProblem: error instanceof Error ? error.message : String(error),
        }
      }
    }))
    const model: EvidenceViewModel = {
      manifestPath: indexed.manifestPath,
      runId: indexed.manifest.runId,
      unit: indexed.manifest.unit,
      leanPath: indexed.manifest.leanDocument.path,
      entry,
      evidence,
    }
    await this.panel.webview.postMessage({ type: "show", model })
  }

  private async handleMessage(message: unknown): Promise<void> {
    if (typeof message !== "object" || message === null || this.current === undefined) return
    const value = message as Record<string, unknown>
    if (value.type === "openSource" && typeof value.evidenceId === "string") {
      const evidence = this.current.entry.evidence.find((item) => item.evidenceId === value.evidenceId)
      const root = await repositoryRoot()
      if (evidence === undefined || root === undefined) return
      const absolute = resolve(root, evidence.documentPath)
      if (!inside(root, absolute)) {
        await vscode.window.showErrorMessage("The evidence path escapes the Spec2Lean repository.")
        return
      }
      const uri = vscode.Uri.file(absolute)
      if (evidence.sourceKind === "HTML" && evidence.locator.startLine !== undefined) {
        const document = await vscode.workspace.openTextDocument(uri)
        const editor = await vscode.window.showTextDocument(document, vscode.ViewColumn.Beside)
        const line = Math.max(0, evidence.locator.startLine - 1)
        editor.selection = new vscode.Selection(line, 0, line, 0)
        editor.revealRange(new vscode.Range(line, 0, line, 0), vscode.TextEditorRevealType.InCenter)
      } else {
        await vscode.commands.executeCommand("vscode.open", uri)
      }
      return
    }
    if (value.type === "feedback") {
      if (!vscode.workspace.isTrusted) {
        await vscode.window.showWarningMessage("Trust this workspace before recording Spec2Lean feedback.")
        return
      }
      const decision = typeof value.decision === "string" ? value.decision : ""
      const comment = typeof value.comment === "string" ? value.comment.trim() : ""
      if (!new Set(["CONFIRM_MAPPING", "REQUEST_CHANGE", "QUESTION"]).has(decision) || comment.length === 0) {
        await vscode.window.showErrorMessage("Choose a feedback decision and enter a comment.")
        return
      }
      let reviewer = vscode.workspace.getConfiguration("spec2lean").get<string>("reviewer", "").trim()
      if (reviewer.length === 0) {
        reviewer = (await vscode.window.showInputBox({
          title: "Spec2Lean reviewer identity",
          prompt: "This identity will be stored in the immutable feedback record.",
          ignoreFocusOut: true,
        }))?.trim() ?? ""
      }
      if (reviewer.length === 0) return
      const root = await repositoryRoot()
      if (root === undefined) return
      try {
        const output = await runCli(root, [
          "traceability", "feedback",
          "--manifest", this.current.indexed.manifestPath,
          "--entry", this.current.entry.entryId,
          "--decision", decision,
          "--reviewer", reviewer,
          "--comment", comment,
        ])
        const match = output.match(/\{[\s\S]*\}\s*$/)
        const result = match === null ? undefined : JSON.parse(match[0]) as { outputPath?: string }
        await vscode.window.showInformationMessage(
          `Spec2Lean feedback recorded${result?.outputPath === undefined ? "" : `: ${result.outputPath}`}. No gate was approved.`,
        )
        await this.panel?.webview.postMessage({ type: "feedbackRecorded", outputPath: result?.outputPath })
      } catch (error) {
        await vscode.window.showErrorMessage(`Could not record Spec2Lean feedback: ${String(error)}`)
      }
    }
  }

  private shell(webview: vscode.Webview): string {
    const nonce = randomBytes(16).toString("hex")
    const pdfJsUri = webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, "dist/vendor/pdf.mjs"))
    const pdfWorkerUri = webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, "dist/vendor/pdf.worker.mjs"))
    const csp = [
      "default-src 'none'",
      `img-src ${webview.cspSource} data:`,
      `style-src ${webview.cspSource} 'unsafe-inline'`,
      `script-src 'nonce-${nonce}' ${webview.cspSource}`,
      `worker-src ${webview.cspSource} blob:`,
      `connect-src ${webview.cspSource}`,
      `font-src ${webview.cspSource}`,
    ].join("; ")
    return `<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="${csp}">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Spec2Lean Evidence</title>
  <style>
    :root { color-scheme: light dark; }
    body { margin: 0; color: var(--vscode-foreground); background: var(--vscode-editor-background); font-family: var(--vscode-font-family); }
    header { position: sticky; top: 0; z-index: 2; padding: 12px 16px; border-bottom: 1px solid var(--vscode-panel-border); background: var(--vscode-editor-background); }
    main { display: grid; grid-template-columns: minmax(260px, 0.8fr) minmax(360px, 1.4fr); min-height: calc(100vh - 65px); }
    aside, section { padding: 14px 16px; overflow: auto; }
    aside { border-right: 1px solid var(--vscode-panel-border); }
    h1 { margin: 0 0 4px; font-size: 16px; }
    h2 { font-size: 13px; margin: 18px 0 8px; text-transform: uppercase; letter-spacing: .04em; color: var(--vscode-descriptionForeground); }
    .meta { color: var(--vscode-descriptionForeground); font-size: 12px; }
    .card { border: 1px solid var(--vscode-panel-border); border-radius: 4px; padding: 10px; margin: 8px 0; }
    .classification { font-size: 10px; font-weight: 700; letter-spacing: .04em; }
    .SOURCE_FACT { color: var(--vscode-testing-iconPassed); }
    .OPEN_QUESTION, .ASSUMPTION { color: var(--vscode-editorWarning-foreground); }
    button, select, textarea { font: inherit; }
    button { color: var(--vscode-button-foreground); background: var(--vscode-button-background); border: 0; padding: 6px 10px; cursor: pointer; }
    button.secondary { color: var(--vscode-button-secondaryForeground); background: var(--vscode-button-secondaryBackground); }
    button.evidence { width: 100%; text-align: left; margin: 4px 0; }
    button.evidence.active { outline: 2px solid var(--vscode-focusBorder); }
    .verified { color: var(--vscode-testing-iconPassed); }
    .problem { color: var(--vscode-errorForeground); }
    pre { white-space: pre-wrap; word-break: break-word; background: var(--vscode-textCodeBlock-background); padding: 12px; }
    #pdfWrap { position: relative; display: inline-block; max-width: 100%; }
    #pdfCanvas { max-width: 100%; height: auto; }
    #pdfBox { display: none; position: absolute; box-sizing: border-box; border: 3px solid var(--vscode-editorError-foreground); background: color-mix(in srgb, var(--vscode-editorError-foreground) 18%, transparent); pointer-events: none; }
    textarea { width: 100%; min-height: 90px; box-sizing: border-box; color: var(--vscode-input-foreground); background: var(--vscode-input-background); border: 1px solid var(--vscode-input-border); padding: 8px; }
    select { width: 100%; margin-bottom: 8px; color: var(--vscode-dropdown-foreground); background: var(--vscode-dropdown-background); padding: 6px; }
    .empty { padding: 30px; color: var(--vscode-descriptionForeground); }
    @media (max-width: 800px) { main { grid-template-columns: 1fr; } aside { border-right: 0; border-bottom: 1px solid var(--vscode-panel-border); } }
  </style>
</head>
<body>
  <header><h1 id="title">Spec2Lean Evidence</h1><div id="subtitle" class="meta">Select a mapped Lean declaration.</div></header>
  <main id="content" hidden>
    <aside>
      <h2>Semantic claims</h2><div id="claims"></div>
      <h2>Official evidence</h2><div id="evidenceList"></div>
      <h2>Human feedback</h2>
      <select id="decision" aria-label="Feedback decision">
        <option value="QUESTION">Question</option>
        <option value="REQUEST_CHANGE">Request change</option>
        <option value="CONFIRM_MAPPING">Confirm mapping</option>
      </select>
      <textarea id="comment" placeholder="Explain the evidence or mapping issue..."></textarea>
      <p><button id="submitFeedback">Record feedback</button></p>
      <div id="feedbackStatus" class="meta"></div>
    </aside>
    <section>
      <div id="sourceMeta" class="meta"></div>
      <div id="htmlView"><pre id="excerpt"></pre></div>
      <div id="pdfView" hidden><div id="pdfWrap"><canvas id="pdfCanvas"></canvas><div id="pdfBox"></div></div></div>
      <p><button id="openSource" class="secondary">Open source file</button></p>
    </section>
  </main>
  <div id="empty" class="empty">Move to a mapped Lean declaration or use its CodeLens.</div>
  <script type="module" nonce="${nonce}">
    import * as pdfjsLib from ${JSON.stringify(pdfJsUri.toString())};
    pdfjsLib.GlobalWorkerOptions.workerSrc = ${JSON.stringify(pdfWorkerUri.toString())};
    const vscode = acquireVsCodeApi();
    let model;
    let selectedEvidence;
    const byId = (id) => document.getElementById(id);
    const text = (node, value) => { node.textContent = value ?? ''; };
    function renderModel(next) {
      model = next;
      byId('content').hidden = false;
      byId('empty').hidden = true;
      text(byId('title'), next.entry.declarationName);
      text(byId('subtitle'), next.unit + ' · ' + next.entry.declarationKind + ' · Lean lines ' + next.entry.leanRange.startLine + '–' + next.entry.leanRange.endLine);
      const claims = byId('claims'); claims.replaceChildren();
      for (const claim of next.entry.claims) {
        const card = document.createElement('div'); card.className = 'card';
        const label = document.createElement('div'); label.className = 'classification ' + claim.classification; text(label, claim.classification + ' · ' + claim.semanticId);
        const statement = document.createElement('div'); text(statement, claim.statement);
        card.append(label, statement); claims.append(card);
      }
      if (next.entry.claims.length === 0) text(claims, 'No structured semantic claim is linked.');
      const list = byId('evidenceList'); list.replaceChildren();
      for (const evidence of next.evidence) {
        const button = document.createElement('button'); button.className = 'evidence secondary';
        button.dataset.evidenceId = evidence.evidenceId;
        text(button, (evidence.sourceVerified ? '✓ ' : '⚠ ') + evidence.evidenceId);
        button.addEventListener('click', () => selectEvidence(evidence)); list.append(button);
      }
      if (next.evidence.length === 0) text(list, 'No official fragment is linked.');
      if (next.evidence[0]) void selectEvidence(next.evidence[0]);
    }
    async function selectEvidence(evidence) {
      selectedEvidence = evidence;
      for (const button of document.querySelectorAll('button.evidence')) button.classList.toggle('active', button.dataset.evidenceId === evidence.evidenceId);
      const locator = evidence.locator;
      const location = [locator.section && '§' + locator.section, locator.heading, locator.page && 'page ' + locator.page, locator.startLine && 'lines ' + locator.startLine + '–' + (locator.endLine ?? locator.startLine)].filter(Boolean).join(' · ');
      text(byId('sourceMeta'), evidence.sourceKind + ' · ' + location + ' · ' + (evidence.sourceVerified ? 'SHA-256 verified' : evidence.sourceProblem ?? 'unverified'));
      byId('sourceMeta').className = 'meta ' + (evidence.sourceVerified ? 'verified' : 'problem');
      if (evidence.sourceKind === 'PDF' && evidence.locator.page && evidence.sourceUri) {
        byId('htmlView').hidden = true; byId('pdfView').hidden = false;
        try {
          const pdf = await pdfjsLib.getDocument(evidence.sourceUri).promise;
          const page = await pdf.getPage(evidence.locator.page);
          const viewport = page.getViewport({ scale: 1.5 });
          const canvas = byId('pdfCanvas'); const context = canvas.getContext('2d');
          canvas.width = viewport.width; canvas.height = viewport.height;
          await page.render({ canvasContext: context, viewport }).promise;
          const box = byId('pdfBox'); const bounds = evidence.locator.bbox;
          if (bounds) {
            box.style.display = 'block'; box.style.left = (bounds[0] * 100) + '%'; box.style.top = (bounds[1] * 100) + '%'; box.style.width = (bounds[2] * 100) + '%'; box.style.height = (bounds[3] * 100) + '%';
          } else box.style.display = 'none';
        } catch (error) {
          byId('pdfView').hidden = true; byId('htmlView').hidden = false; text(byId('excerpt'), 'PDF rendering failed: ' + String(error));
        }
      } else {
        byId('pdfView').hidden = true; byId('htmlView').hidden = false;
        text(byId('excerpt'), evidence.excerpt ?? evidence.quotation ?? 'No exact excerpt is available for this locator.');
      }
    }
    byId('openSource').addEventListener('click', () => { if (selectedEvidence) vscode.postMessage({ type: 'openSource', evidenceId: selectedEvidence.evidenceId }); });
    byId('submitFeedback').addEventListener('click', () => vscode.postMessage({ type: 'feedback', decision: byId('decision').value, comment: byId('comment').value }));
    window.addEventListener('message', (event) => {
      if (event.data.type === 'show') renderModel(event.data.model);
      if (event.data.type === 'feedbackRecorded') { text(byId('feedbackStatus'), 'Recorded: ' + (event.data.outputPath ?? 'review artifact')); byId('comment').value = ''; }
    });
  </script>
</body>
</html>`
  }
}

async function runForDocument(root: string, document: vscode.TextDocument): Promise<string | undefined> {
  const documentPath = relative(root, document.uri.fsPath).split(sep).join("/")
  const files = await vscode.workspace.findFiles(new vscode.RelativePattern(root, "runs/*/run.json"))
  for (const uri of files) {
    try {
      const run = JSON.parse(await readFile(uri.fsPath, "utf8")) as {
        runId?: string
        artifactRoot?: string
        leanModuleName?: string
      }
      if (
        typeof run.runId === "string" &&
        typeof run.artifactRoot === "string" &&
        typeof run.leanModuleName === "string" &&
        documentPath.startsWith(`${run.artifactRoot}/lean/`) &&
        new RegExp(
          `^${run.leanModuleName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?:Proofs)?-v\\d+\\.lean$`,
        ).test(documentPath.split("/").at(-1) ?? "")
      ) return run.runId
    } catch {
      // Ignore malformed or unrelated run records.
    }
  }
  return undefined
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const index = new ManifestIndex()
  const panel = new EvidencePanel(context.extensionUri)
  await index.refresh()

  context.subscriptions.push(
    vscode.languages.registerCodeLensProvider(
      [{ language: "lean4", scheme: "file" }, { pattern: "**/*.lean", scheme: "file" }],
      new EvidenceCodeLensProvider(index),
    ),
    vscode.commands.registerCommand(
      "spec2lean.showEvidence",
      async (manifestPath?: string, entryId?: string) => {
        const editor = vscode.window.activeTextEditor
        const located = manifestPath === undefined || entryId === undefined
          ? editor === undefined ? undefined : index.entryAt(editor.document, editor.selection.active.line)
          : undefined
        if (located !== undefined) {
          await panel.show(located.indexed, located.entry)
          return
        }
        if (manifestPath !== undefined && entryId !== undefined) {
          const root = await repositoryRoot()
          if (root === undefined) return
          const absolute = resolve(root, manifestPath)
          if (!inside(root, absolute)) {
            await vscode.window.showErrorMessage("The evidence manifest path escapes the Spec2Lean repository.")
            return
          }
          const manifest = JSON.parse(await readFile(absolute, "utf8")) as EvidenceManifest
          const entry = manifest.entries.find((candidate) => candidate.entryId === entryId)
          if (entry !== undefined) await panel.show({ manifestPath, manifest }, entry)
          return
        }
        await vscode.window.showInformationMessage("No Spec2Lean evidence mapping exists at the current Lean position.")
      },
    ),
    vscode.commands.registerCommand("spec2lean.refreshEvidence", async () => {
      await index.refresh()
      await vscode.window.showInformationMessage("Spec2Lean evidence manifests refreshed.")
    }),
    vscode.commands.registerCommand("spec2lean.buildEvidenceManifest", async () => {
      if (!vscode.workspace.isTrusted) {
        await vscode.window.showWarningMessage("Trust this workspace before running the Spec2Lean CLI.")
        return
      }
      const root = await repositoryRoot()
      const editor = vscode.window.activeTextEditor
      if (root === undefined || editor === undefined) {
        await vscode.window.showErrorMessage("Open a candidate Lean file inside a Spec2Lean workspace first.")
        return
      }
      const runId = await runForDocument(root, editor.document)
      if (runId === undefined) {
        await vscode.window.showErrorMessage("No Spec2Lean run owns the current candidate Lean file.")
        return
      }
      await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: `Building evidence manifest for ${runId}`,
      }, async () => {
        const documentArgs = /Proofs(?:-v\d+)?\.lean$/.test(editor.document.fileName)
          ? ["--document", "proofs"]
          : []
        try {
          await runCli(root, ["traceability", "build", "--run", runId, ...documentArgs, "--pdf-boxes"])
        } catch (error) {
          await runCli(root, ["traceability", "build", "--run", runId, ...documentArgs])
          await vscode.window.showWarningMessage(
            `PDF box extraction was unavailable; the HTML evidence manifest was still built. ${String(error)}`,
          )
        }
        await index.refresh()
      })
      await vscode.commands.executeCommand("spec2lean.showEvidence")
    }),
    vscode.window.onDidChangeTextEditorSelection(async (event) => {
      if (!panel.isOpen()) return
      if (!vscode.workspace.getConfiguration("spec2lean").get<boolean>("autoRevealEvidence", true)) return
      const located = index.entryAt(event.textEditor.document, event.selections[0]?.active.line ?? 0)
      if (located !== undefined) await panel.show(located.indexed, located.entry, true)
    }),
  )
}

export function deactivate(): void {}
