# Spec2Lean Evidence for VS Code

From the repository root, the simplest development launch is:

```bash
./spec2lean gui candidates/ptx/9.3/units/or-b16/lean/OrB16-v2.lean
```

This packages and force-installs the local extension as a VSIX on the active
VS Code server, then opens the repository plus the requested Lean file in a
normal new window. It works with Remote VS Code CLIs that do not support
`--extensionDevelopmentPath`.

Run that command in the environment where the repository lives. In a local
checkout it installs into local VS Code; in an SSH/container checkout it
installs into that active VS Code Server. The VSIX is platform-independent and
contains no native runtime dependency. The launcher requires the `code` CLI,
Node/npm dependencies already installed under `editors/vscode`, and VS Code
1.95 or newer.

This extension keeps the normal Lean editor intact and opens a synchronized
evidence panel beside it. CodeLens links above every discovered declaration
show semantic claims, reviewed project-design provenance, and hash-verified
official source fragments. An unmapped declaration gets a visible warning
CodeLens instead of being silently hidden.

CodeLens is deliberately hidden if the open Lean buffer no longer matches the
SHA-256 recorded in the manifest. Refresh or rebuild the manifest instead of
reviewing stale evidence.

## Development

```bash
cd editors/vscode
npm install
npm run check
```

PDF box generation uses the local `pdftotext -bbox` command from Poppler. If
Poppler is unavailable, the extension still builds and displays the
hash-verified HTML evidence and reports that PDF alignment was skipped.

Open this directory itself in VS Code and press `F5`. The committed launch
configuration starts a second window titled `[Extension Development Host]` and
opens the Spec2Lean repository in that second window. Open a candidate Lean
mapping there. New agentic-loop runs already contain their evidence manifest;
the `Spec2Lean: Build Evidence Manifest for Current Run` command is a migration
fallback for older runs. Use a CodeLens or move the cursor while the evidence
panel is open. If that exact command is absent from the Command Palette, the
current window is not the Extension Development Host.

The panel supports:

- semantic claim classification and statement display;
- SHA-256 verification before showing a local source;
- official HTML excerpts and exact line/anchor metadata;
- PDF page rendering through bundled PDF.js;
- normalized PDF bounding-box overlays when coordinates exist;
- immutable human feedback records through the deterministic Spec2Lean CLI.
- automatic refresh when a run writes a new content-addressed manifest.

Feedback does **not** approve a human gate and does not promote artifacts.
Existing source bundles without PDF page/bounding-box metadata remain usable
through their HTML evidence; the extension never invents missing PDF boxes.
