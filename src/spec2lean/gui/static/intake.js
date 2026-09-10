let specificationPoll;

async function mutate(path, options) {
  return api(path, {...options, headers: {'X-Spec2Lean-Token': state.config.csrfToken, ...options.headers}});
}

async function showSpecifications() {
  history.replaceState(null, '', '#specifications');
  clearTimeout(specificationPoll);
  try {
    const specifications = await api('/api/specifications');
    shell(`<main class="page"><section class="hero"><div><div class="eyebrow">Your workspace</div><h1>Specifications</h1><p class="lede">Upload a document, choose your units, and follow its progress from source to Lean.</p></div><button class="primary" data-new>+ New specification</button></section>
      <section class="run-grid">${specifications.map(item => `<button class="run-card specification-card" data-specification="${esc(item.id)}"><div class="run-head"><div class="run-title">${esc(item.title)}</div>${status(item.status)}</div><p>${esc(item.request.language)} · ${esc(item.request.version)} · ${item.pageCount} pages</p><div class="scope">${esc(scopeSummary(item.request.scope))}</div><div class="run-foot">${esc(fmtDate(item.updatedAt))}</div></button>`).join('') || '<div class="empty"><h2>Start with a PDF</h2><p>Your imported specifications will appear here, including ones prepared from the CLI.</p></div>'}</section></main>`, 'Specifications');
    app.querySelector('[data-new]').onclick = showNewSpecification;
    app.querySelectorAll('[data-specification]').forEach(node => node.onclick = () => showSpecification(node.dataset.specification));
  } catch (error) { errorView(error); }
}

function scopeSummary(scope) {
  return scope.instructions?.join(', ') || scope.family || scope.sourceNodeId || 'Full specification';
}

function showNewSpecification() {
  history.replaceState(null, '', '#new');
  shell(`<main class="page intake-page"><div class="eyebrow">New specification</div><h1>Start with your document.</h1><p class="lede">Add a PDF and choose what to formalize. Spec2Lean saves the source, records its provenance, and prepares the index.</p>
    <form id="intake-form" class="intake-form">
      <label class="upload-box"><b>Specification PDF</b><span>Choose a PDF with selectable text · up to 256 MiB</span><input name="pdf" type="file" accept=".pdf,application/pdf" required><span id="file-summary"></span></label>
      <div class="form-grid"><label>Specification identifier<input name="language" placeholder="e.g. tilelink" required maxlength="100" pattern="[A-Za-z0-9]([A-Za-z0-9._]|-)*"><small>A short name using letters, numbers, dots, underscores or hyphens.</small></label><label>Version<input name="version" placeholder="e.g. 1.9.3" required maxlength="100" pattern="[A-Za-z0-9]([A-Za-z0-9._]|-)*"></label>
      <label>Document title <span class="optional">optional</span><input name="title" placeholder="Use the title from the PDF" maxlength="500"></label><label>Publisher <span class="optional">optional</span><input name="publisher" placeholder="Organization or author" maxlength="500"></label></div>
      <label>Source URL <span class="optional">optional</span><input name="sourceUrl" type="url" placeholder="https://example.org/specification.pdf"><small>Recorded for provenance alongside your uploaded file.</small></label>
      <label>What should be formalized?<select name="scope"><option value="EXACT_INSTRUCTIONS">Specific units</option><option value="INSTRUCTION_FAMILY">A family of units</option><option value="SOURCE_SUBTREE">An existing indexed section</option><option value="FULL_SPECIFICATION">Full specification</option></select></label>
      <label id="scope-value-label"><span id="scope-value-title">Desired units</span><textarea name="scopeValue" rows="4" required placeholder="Get, PutFullData, PutPartialData"></textarea><small id="scope-value-hint">Use exact names from the specification, separated by commas or new lines.</small></label>
      <label class="checkbox-label"><input type="checkbox" name="buildIndex" checked><span>Build the Phase 1 index after upload<small>Parses and indexes the PDF locally. Later formalization phases use your configured model runtime.</small></span></label>
      <div id="intake-error" class="warning hidden" role="alert"></div><div id="upload-status" role="status" aria-live="polite"></div>
      <div class="form-actions"><button class="primary" type="submit">Upload and prepare</button><button class="secondary" type="button" data-cancel>Cancel</button></div>
    </form></main>`, 'New specification');
  const form = app.querySelector('#intake-form');
  const input = form.elements.pdf;
  input.onchange = () => { const file = input.files[0]; app.querySelector('#file-summary').textContent = file ? `${file.name} · ${(file.size / 1048576).toFixed(1)} MiB` : ''; };
  form.elements.scope.onchange = () => {
    const mode = form.elements.scope.value;
    const hidden = mode === 'FULL_SPECIFICATION';
    app.querySelector('#scope-value-label').classList.toggle('hidden', hidden);
    form.elements.scopeValue.required = !hidden;
    const descriptions = {
      EXACT_INSTRUCTIONS: ['Desired units', 'Get, PutFullData, PutPartialData', 'Use exact names from the specification, separated by commas or new lines.'],
      INSTRUCTION_FAMILY: ['Family', 'e.g. integer arithmetic', 'Describe a family defined by the specification.'],
      SOURCE_SUBTREE: ['Indexed section', 'node:…', 'Paste a node ID from an existing Phase 1 index for this document.']
    };
    if (descriptions[mode]) {
      const [title, placeholder, hint] = descriptions[mode];
      app.querySelector('#scope-value-title').textContent = title;
      form.elements.scopeValue.placeholder = placeholder;
      app.querySelector('#scope-value-hint').textContent = hint;
    }
  };
  app.querySelector('[data-cancel]').onclick = showSpecifications;
  form.onsubmit = async event => {
    event.preventDefault();
    const errorBox = app.querySelector('#intake-error');
    const uploadStatus = app.querySelector('#upload-status');
    const submit = form.querySelector('[type="submit"]');
    errorBox.classList.add('hidden');
    const buildIndex = form.elements.buildIndex.checked;
    try {
      const file = input.files[0];
      if (!file || !file.size || file.size > state.config.maxPdfBytes) throw new Error('Choose a non-empty PDF no larger than 256 MiB.');
      const mode = form.elements.scope.value;
      const value = form.elements.scopeValue.value.trim();
      const scope = {mode};
      if (mode === 'EXACT_INSTRUCTIONS') scope.instructions = value.split(/[,\n]/).map(x => x.trim()).filter(Boolean);
      if (mode === 'INSTRUCTION_FAMILY') scope.family = value;
      if (mode === 'SOURCE_SUBTREE') scope.sourceNodeId = value;
      const metadata = {filename: file.name, title: form.elements.title.value.trim(), publisher: form.elements.publisher.value.trim(), sourceUrl: form.elements.sourceUrl.value.trim(),
        request: {language: form.elements.language.value.trim(), version: form.elements.version.value.trim(), scope}};
      submit.disabled = true;
      uploadStatus.textContent = 'Uploading and validating your PDF…';
      const record = await mutate('/api/specifications', {method: 'POST', headers: {'Content-Type': 'application/pdf', 'X-Spec2Lean-Metadata': encodeURIComponent(JSON.stringify(metadata))}, body: file});
      await showSpecification(record.id);
      if (buildIndex) await startSpecification(record.id, 'index');
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.classList.remove('hidden');
      uploadStatus.textContent = '';
      submit.disabled = false;
    }
  };
}

async function startSpecification(specificationId, until) {
  const errorBox = app.querySelector('#job-error');
  const runtime = app.querySelector('#job-runtime')?.value || 'rust-harness';
  const indexMode = app.querySelector('#job-mode')?.value || 'lexical';
  app.querySelectorAll('[data-start]').forEach(node => node.disabled = true);
  try {
    await mutate(`/api/specifications/${id(specificationId)}/start`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({until, runtime, indexMode})});
    await showSpecification(specificationId);
  } catch (error) {
    if (errorBox) { errorBox.textContent = error.message; errorBox.classList.remove('hidden'); }
    app.querySelectorAll('[data-start]').forEach(node => node.disabled = false);
  }
}

async function showSpecification(specificationId) {
  history.replaceState(null, '', `#specifications/${specificationId}`);
  clearTimeout(specificationPoll);
  try {
    const record = await api(`/api/specifications/${id(specificationId)}`);
    if (location.hash !== `#specifications/${specificationId}`) return;
    const busy = ['RUNNING', 'QUEUED'].includes(record.status);
    const labels = {PREPARED: 'Source saved. Ready to build Phase 1.', INDEXED: 'Phase 1 is ready. Continue with your requested units.', COMPLETE: `Completed through ${record.untilPhase || 'the requested phase'}.`, FAILED: 'The job stopped. Review the error, then retry.', INTERRUPTED: 'The job was interrupted. Continue from saved artifacts.', RUNNING: 'Processing your specification…', QUEUED: 'Starting the pipeline…'};
    shell(`<main class="page intake-page"><button class="back" data-specs>← Specifications</button><div class="eyebrow">${esc(record.request.language)} · ${esc(record.request.version)}</div><h1>${esc(record.title)}</h1><div class="card-top">${status(record.status)}<span>${record.pageCount} pages${record.sourceReused ? ' · existing source reused' : ''}</span></div><p class="lede" role="status">${esc(labels[record.status] || record.status)}</p>
      <section class="semantic-section"><h3>Requested scope</h3><p>${esc(scopeSummary(record.request.scope))}</p></section>
      <div id="job-error" class="warning ${record.error ? '' : 'hidden'}" role="alert">${esc(record.error)}</div>
      <div class="form-grid job-options"><label>Model runtime<select id="job-runtime" ${busy ? 'disabled' : ''}><option value="rust-harness">Rust harness</option><option value="opencode" ${record.runtime === 'opencode' ? 'selected' : ''}>OpenCode</option></select></label><label>Search mode<select id="job-mode" ${busy ? 'disabled' : ''}><option value="lexical">Lexical (local)</option><option value="semantic" ${record.indexMode === 'semantic' ? 'selected' : ''}>Semantic (embedding model)</option></select></label></div>
      <p class="form-hint">Full pipeline execution uses your configured runtime and model credentials. Keep the GUI server running while a job is active.</p>
      <div class="form-actions"><button class="secondary" data-start="index" ${busy ? 'disabled' : ''}>Build Phase 1</button><button class="primary" data-start="troubleshoot" ${busy ? 'disabled' : ''}>${record.pipelineRunId ? 'Continue pipeline' : 'Run full pipeline'}</button>${record.pipelineRunId ? '<button class="secondary" data-run>View run artifacts →</button>' : ''}</div>
      <details ${busy || record.error ? 'open' : ''}><summary>Progress log</summary><pre class="raw job-log">${esc(record.log || 'Progress will appear here when the pipeline starts.')}</pre></details>
      ${record.indexAttempts?.length ? `<details><summary>Indexing history</summary><ul>${record.indexAttempts.map(attempt => `<li>${esc(fmtDate(attempt.startedAt))} · ${esc(attempt.indexMode)} · ${esc(attempt.status)}${attempt.error ? ` — ${esc(attempt.error)}` : ''}</li>`).join('')}</ul></details>` : ''}
      <details><summary>Source metadata and CLI</summary><dl class="kv"><dt>Source manifest</dt><dd>${esc(record.sourceManifest)}</dd><dt>Saved request</dt><dd>${esc(record.requestPath)}</dd><dt>SHA-256</dt><dd>${esc(record.sha256)}</dd><dt>Source URL</dt><dd>${esc(record.sourceUrl || 'Not supplied')}</dd></dl><p>Continue from the terminal:</p><pre class="raw">${esc(record.nextCommand)}</pre></details></main>`, 'Specification');
    app.querySelector('[data-specs]').onclick = showSpecifications;
    app.querySelectorAll('[data-start]').forEach(node => node.onclick = () => startSpecification(specificationId, node.dataset.start));
    if (record.pipelineRunId) app.querySelector('[data-run]').onclick = () => openRun(record.pipelineRunId);
    if (busy) specificationPoll = setTimeout(() => showSpecification(specificationId), 1500);
  } catch (error) { errorView(error); }
}
