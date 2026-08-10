# Spec2Lean Evidence for VS Code

This extension keeps the normal Lean editor intact and opens a synchronized
evidence panel beside it. CodeLens links above mapped declarations show the
semantic claims and hash-verified official source fragments used by the
Spec2Lean run.

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

Feedback does **not** approve a human gate and does not promote artifacts.
Existing source bundles without PDF page/bounding-box metadata remain usable
through their HTML evidence; the extension never invents missing PDF boxes.
