const app = document.querySelector('#app');
const state = { runs: [], run: null, unit: null, tab: 'lean', declaration: null, claim: null, evidence: null, source: null, codeQuery: '', codeDocument: 'unit', copyStatus: '' };

const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const fmtDate = value => value ? new Intl.DateTimeFormat(undefined,{dateStyle:'medium',timeStyle:'short'}).format(new Date(value)) : 'Unknown time';
const fmtDuration = ms => ms == null ? '—' : ms < 1000 ? `${ms} ms` : `${(ms/1000).toFixed(1)} s`;
const id = value => encodeURIComponent(value);
const badge = (value, extra='') => `<span class="badge ${esc(String(value||'').toLowerCase())} ${extra}">${esc(String(value||'UNKNOWN').replaceAll('_',' '))}</span>`;
const status = value => `<span class="status ${esc(value||'PENDING')}">${esc(value||'PENDING')}</span>`;
const safeUrl = value => { try { const url=new URL(value); return ['http:','https:'].includes(url.protocol)?url.href:null; } catch { return null; } };

async function api(path) {
  const response = await fetch(path);
  const value = await response.json().catch(()=>({error:`HTTP ${response.status}`}));
  if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
  return value;
}

function shell(content, crumb='Runs', searchable=false) {
  app.innerHTML = `<div class="shell"><header class="topbar">
    <div class="brand" data-action="home"><span class="brand-icon">S2L</span><span>Spec2Lean</span></div>
    <div class="crumb">${esc(crumb)}</div><div class="top-spacer"></div>
    ${searchable ? `<div class="search"><input id="global-search" autocomplete="off" placeholder="Search this run…" aria-label="Search active run"><div id="search-results" class="search-results hidden"></div></div>`:''}
  </header>${content}</div>`;
  app.querySelector('[data-action="home"]').onclick = showHome;
  if (searchable) setupSearch();
}

function errorView(error) {
  shell(`<div class="error-page"><div><div class="mark">!</div><h2>Artifact view unavailable</h2><p>${esc(error.message||error)}</p><button class="back" data-retry>← Back to runs</button></div></div>`);
  app.querySelector('[data-retry]').onclick = showHome;
}

async function showHome() {
  state.run = state.unit = state.declaration = state.claim = state.evidence = state.source = null;
  try {
    state.runs = await api('/api/runs');
    const cards = state.runs.map(run => {
      const pct = run.requested ? Math.round(100*run.completed/run.requested) : 0;
      return `<article class="run-card" data-run="${esc(run.runId)}"><div class="run-head"><div><div class="run-title">${esc(run.language)} ${esc(run.version)}</div><div class="run-subtitle">${esc(run.planRunId||run.runId)}</div></div>${status(run.status)}</div>
        <div class="scope">${esc((run.requestedNames||[]).join(', ') || run.scope?.mode || 'No resolved units')}</div>
        <div class="run-foot"><span><b>${run.completed} / ${run.requested}</b> complete${run.failed?` · ${run.failed} failed`:''}</span><time>${esc(fmtDate(run.updatedAt||run.createdAt))}</time></div><progress class="progress" value="${pct}" max="100" aria-label="${pct}% complete"></progress></article>`;
    }).join('');
    shell(`<main class="page"><section class="hero"><div><div class="eyebrow">V1 Artifact Explorer</div><h1>Follow generated code back to its source.</h1><p class="lede">Inspect Lean declarations, semantic claims, exact evidence, and official specification provenance—without opening artifact files.</p></div><div class="count">${state.runs.length} pipeline run${state.runs.length===1?'':'s'}</div></section>
      ${cards?`<section class="run-grid">${cards}</section>`:`<div class="empty"><h2>No pipeline runs yet</h2><p>Completed and partial runs will appear here when their run manifests are available.</p></div>`}</main>`);
    app.querySelectorAll('[data-run]').forEach(node => node.onclick=()=>openRun(node.dataset.run));
  } catch(error) { errorView(error); }
}

function stageValue(value) {
  if (typeof value === 'object' && value) return value.status || value.outcome || value.disposition || 'RECORDED';
  return value || 'NOT_STARTED';
}
function phaseCell(label,value) { const actual=stageValue(value); return `<div class="phase-cell"><small>${label}</small><span>${esc(actual.replaceAll('_',' '))}</span></div>`; }

async function openRun(runId) {
  try {
    state.run = await api(`/api/runs/${id(runId)}`); state.unit=null;
    const layers = state.run.layers.map(layer=>`<section class="layer"><div class="layer-label">Layer ${esc(layer.layer)}${layer.unplanned?' · recovered from run manifest':''}</div>${layer.units.map(unit=>`<div class="unit-row" data-unit="${esc(unit.unitId)}"><div class="unit-name"><span class="unit-state ${['FAIL','FAILED'].includes(unit.status)?'bad':''}">${['FAIL','FAILED'].includes(unit.status)?'×':unit.status==='PASS'?'✓':'○'}</span>${esc(unit.name)}</div>
      ${phaseCell('Evidence',unit.stages.evidence)}${phaseCell('Semantics',unit.stages.semantics)}${phaseCell('Translate',unit.stages.translate)}${phaseCell('Check',unit.stages.check)}${phaseCell('Repair',unit.stages.troubleshoot)}<span class="arrow">›</span></div>`).join('')}</section>`).join('');
    const sidebar = `<aside class="run-sidebar"><button class="back" data-back>← All runs</button><div class="eyebrow">${esc(state.run.status)}</div><h2 class="sidebar-title">${esc(state.run.language)} ${esc(state.run.version)}</h2><div class="sidebar-id">${esc(state.run.runId)}</div>
      <div class="summary-box"><div class="summary-number">${state.run.completed} / ${state.run.requested}</div><div class="summary-label">requested units complete</div></div>
      <div class="stage-key"><div><i class="dot good"></i> Artifacts available / passed</div><div><i class="dot bad"></i> Failed or broken</div><div><i class="dot"></i> Not reached / optional</div></div></aside>`;
    shell(`<div class="overview">${sidebar}<main class="overview-main"><header class="section-head"><div><div class="eyebrow">Processing order</div><h1>Run overview</h1></div>${status(state.run.status)}</header>${state.run.error?`<div class="warning">${esc(state.run.error)}</div>`:''}${layers||'<div class="empty">No planned units are available for this run.</div>'}</main></div>`,`${state.run.language.toUpperCase()} ${state.run.version}`,true);
    app.querySelector('[data-back]').onclick=showHome;
    app.querySelectorAll('[data-unit]').forEach(node=>node.onclick=()=>openUnit(node.dataset.unit));
  } catch(error) { errorView(error); }
}

async function openUnit(unitId, focus={}) {
  try {
    state.unit = await api(`/api/runs/${id(state.run.runId)}/units/${id(unitId)}`);
    state.tab = focus.tab || 'lean'; state.declaration = focus.declaration || null; state.claim=focus.claim||null; state.evidence=focus.evidence||null; state.source=null; state.copyStatus='';
    if (!state.claim && state.evidence) state.claim=state.unit.evidence.find(e=>e.evidenceId===state.evidence)?.usedByClaims?.[0]||null;
    if (!state.declaration && state.claim) state.declaration=state.unit.claims.find(c=>c.claimId===state.claim)?.declarations?.[0]||null;
    if (!state.declaration && state.evidence) state.declaration=state.unit.evidence.find(e=>e.evidenceId===state.evidence)?.implementedByDeclarations?.[0]||null;
    if (!state.declaration) state.declaration = state.unit.lean.declarations.find(d=>d.origin==='UNIT_DECLARATION'&&['OPERATION','EXECUTION'].includes(d.role))?.declaration || state.unit.lean.declarations.find(d=>d.origin==='UNIT_DECLARATION')?.declaration || state.unit.lean.declarations[0]?.declaration || null;
    selectDeclaration(state.declaration, false);
    renderUnitShell();
    if (state.evidence) await selectEvidence(state.evidence);
  } catch(error) { errorView(error); }
}

function renderUnitShell() {
  const u=state.unit.unit;
  const tabs=['overview','lean','semantics','evidence','checks','pipeline','raw'];
  const labels={overview:'Overview',lean:'Claims & Evidence',semantics:'Semantics',evidence:'All Evidence',checks:'Checks',pipeline:'Pipeline',raw:'Artifact / Raw'};
  const header=`<div class="detail-shell"><header class="unit-header"><div class="unit-heading"><button class="back" data-back-run>←</button><h1>${esc(u.name)}</h1>${status(u.status)}<span class="meta">${esc(state.unit.language.toUpperCase())} ${esc(state.unit.version)} · ${esc(state.unit.planRunId)}</span></div><nav class="tabs">${tabs.map(tab=>`<button class="tab ${state.tab===tab?'active':''}" data-tab="${tab}">${labels[tab]}</button>`).join('')}</nav></header><main class="detail-content" id="tab-content"></main></div>`;
  shell(header,`${state.run.language.toUpperCase()} ${state.run.version} / ${u.name}`,true);
  app.querySelector('[data-back-run]').onclick=()=>openRun(state.run.runId);
  app.querySelectorAll('[data-tab]').forEach(node=>node.onclick=()=>{state.tab=node.dataset.tab;renderUnitShell();});
  renderTab();
}

function renderTab() {
  const target=app.querySelector('#tab-content');
  if (state.tab==='lean') renderTrace(target);
  else if (state.tab==='overview') renderOverview(target);
  else if (state.tab==='semantics') renderSemantics(target);
  else if (state.tab==='evidence') renderEvidenceIndex(target);
  else if (state.tab==='checks') renderChecks(target);
  else if (state.tab==='pipeline') renderPipeline(target);
  else renderRaw(target);
}

function selectDeclaration(name, rerender=true) {
  state.declaration=name;
  const declaration=state.unit?.lean.declarations.find(d=>d.declaration===name);
  if (declaration?.sourceDocumentId) state.codeDocument=declaration.sourceDocumentId;
  const claimIds=declaration?.claims||[];
  if (!claimIds.includes(state.claim)) state.claim=claimIds[0]||null;
  const claim=state.unit?.claims.find(c=>c.claimId===state.claim);
  if (!(claim?.evidenceIds||[]).includes(state.evidence)) { state.evidence=claim?.evidenceIds?.[0]||null; state.source=null; }
  if (rerender) { renderTab(); if(state.evidence) selectEvidence(state.evidence); }
}
function selectClaim(claimId) {
  state.claim=claimId; const claim=state.unit.claims.find(c=>c.claimId===claimId);
  if (!(claim?.declarations||[]).includes(state.declaration)) {
    state.declaration=claim?.declarations?.[0]||state.declaration;
    const declaration=state.unit.lean.declarations.find(d=>d.declaration===state.declaration);
    if(declaration?.sourceDocumentId)state.codeDocument=declaration.sourceDocumentId;
  }
  state.evidence=claim?.evidenceIds?.[0]||null; state.source=null; renderTab(); if(state.evidence) selectEvidence(state.evidence);
}
async function selectEvidence(evidenceId) {
  state.evidence=evidenceId; state.source=null; renderTraceSelection();
  try { state.source=await api(`/api/runs/${id(state.run.runId)}/units/${id(state.unit.unit.unitId)}/evidence/${id(evidenceId)}`); }
  catch(error) { state.source={error:error.message}; }
  renderTraceSelection();
}

function leanHighlight(line) {
  let value=esc(line);
  const comment=value.indexOf('--');
  let tail=''; if(comment>=0){tail=`<span class="comment">${value.slice(comment)}</span>`;value=value.slice(0,comment);}
  value=value.replace(/(&quot;.*?&quot;)/g,'<span class="str">$1</span>')
    .replace(/\b(namespace|end|def|abbrev|structure|inductive|instance|theorem|lemma|by|let|if|then|else|fun|match|with|where|true|false)\b/g,'<span class="kw">$1</span>')
    .replace(/\b(Nat|UInt\d*|Bool|Prop|Type|String)\b/g,'<span class="type">$1</span>');
  return value+tail;
}
function codeDocuments(){return state.unit?.lean.documents||[{documentId:'unit',label:'Unit',origin:'UNIT_DECLARATION',source:state.unit?.lean.source||'',filename:state.unit?.lean.filename,declarations:state.unit?.lean.declarations||[]}];}
function activeCodeDocument(){return codeDocuments().find(item=>item.documentId===state.codeDocument)||codeDocuments()[0]||{source:'',declarations:[]};}
async function copyLeanSource(){
  const source=activeCodeDocument().source||'';
  try { await navigator.clipboard.writeText(source); state.copyStatus='Copied exact Lean source'; }
  catch { state.copyStatus='Clipboard access was unavailable'; }
  const result=app.querySelector('#copy-status'); if(result)result.textContent=state.copyStatus;
}
function renderCode() {
  const document=activeCodeDocument(); const declarations=document.declarations||[];
  return document.source.split('\n').map((line,index)=>{
    const n=index+1; const declaration=declarations.find(d=>n>=d.startLine&&n<=d.endLine); const start=declaration?.startLine===n;
    const hit=state.codeQuery && line.toLowerCase().includes(state.codeQuery.toLowerCase());
    const mappingClass=declaration?(declaration.mapped?'mapped':'unmapped'):'';
    const marker=declaration?.mapped?`${declaration.claims.length} claim${declaration.claims.length===1?'':'s'}`:'unmapped';
    return `<div class="code-line ${mappingClass} ${declaration?.declaration===state.declaration?'selected':''} ${hit?'search-hit':''}" ${declaration?`data-declaration="${esc(declaration.declaration)}"`:''}><span class="line-no" aria-hidden="true">${n}</span><span class="line-code">${leanHighlight(line)||' '}</span>${start?`<span class="claim-gutter ${declaration.mapped?'':'unmapped'}" aria-hidden="true">${esc(marker)}</span>`:'<span aria-hidden="true"></span>'}</div>`;
  }).join('');
}
function claimCards() {
  const declaration=state.unit.lean.declarations.find(d=>d.declaration===state.declaration);
  const claims=(declaration?.claims||[]).map(id=>state.unit.claims.find(c=>c.claimId===id)).filter(Boolean);
  if(!declaration) return '<div class="pane-empty">Select a declaration to see its recorded semantic mapping.</div>';
  if(!claims.length) return '<div class="pane-empty"><b>No semantic claim mapping recorded.</b><br>This declaration has no claim relationship for the selected unit.</div>';
  const selected=claims.find(claim=>claim.claimId===state.claim);
  const reverse=selected?`<div class="reverse trace-reverse"><h4>Lean declarations implementing this claim</h4><div class="pill-list">${(selected.declarationMappings||[]).map(item=>`<button class="pill button ${item.origin==='SHARED_CORE_DECLARATION'?'shared':''}" data-nav-declaration="${esc(item.declaration)}">${esc(item.declaration.split('.').pop())} · ${item.origin==='SHARED_CORE_DECLARATION'?'shared core':'unit'}</button>`).join('')||'<span class="pill">none</span>'}</div></div>`:'';
  return `<div class="cards">${claims.map(claim=>`<article class="claim-card ${claim.claimId===state.claim?'selected':''}" data-claim="${esc(claim.claimId)}"><div class="card-top">${badge(claim.kind)}<span class="card-id">${esc(claim.claimId)}</span></div><div class="card-text">${esc(claim.statement)}</div><div class="card-foot"><span>${claim.evidenceIds?.length||0} evidence items</span><span>→</span></div></article>`).join('')}</div>${reverse}`;
}
function evidencePane() {
  const claim=state.unit.claims.find(c=>c.claimId===state.claim);
  if(!claim) return '<div class="pane-empty">Choose a claim to reveal exact supporting evidence and provenance.</div>';
  const items=(claim.evidenceIds||[]).map(id=>state.unit.evidence.find(e=>e.evidenceId===id)||{evidenceId:id,broken:true});
  const selected=items.find(e=>e.evidenceId===state.evidence);
  return `<div class="cards">${items.map(item=>`<article class="evidence-card ${item.evidenceId===state.evidence?'selected':''}" data-evidence="${esc(item.evidenceId)}"><div class="card-top">${badge(item.broken?'BROKEN':item.tier)}${badge(item.role)}${badge(item.sourceType)}<span class="card-id">${esc(item.evidenceId)}</span></div><div class="card-text">${esc(item.broken?'Referenced evidence is missing from the Phase-3 bundle.':item.exactText)}</div><div class="card-foot"><span>${esc(item.sectionNumber||'No section')}</span><span>→</span></div></article>`).join('')}</div>${selected?renderEvidenceDetail(selected,claim):''}`;
}
function renderEvidenceDetail(item,claim) {
  const src=state.source;
  const p=src?.preview||{}; const node=src?.sourceNodes?.[0]||{};
  const location=p.type==='pdf'?`Page ${p.page||'—'}${p.bbox?` · bbox ${p.bbox.map(x=>x==null?'—':Number(x).toFixed(1)).join(', ')}`:''}`:`Anchor #${p.anchor||'—'} · line ${p.sourceLineStart||'—'}`;
  const spans=[...(item.sourceSpanIds||[]),...(node.sourceSpans||[]).map(span=>span.span_id||span.spanId).filter(Boolean)].filter((value,index,all)=>all.indexOf(value)===index);
  return `<div class="evidence-detail"><div class="eyebrow">Source provenance</div><div class="chain"><div class="chain-node"><b>Lean</b>${esc(state.declaration?.split('.').pop()||'—')}</div><span class="chain-arrow">›</span><div class="chain-node"><b>Claim</b>${esc(claim.claimId)}</div><span class="chain-arrow">›</span><div class="chain-node"><b>Evidence</b>${esc(item.evidenceId)}</div><span class="chain-arrow">›</span><div class="chain-node"><b>Source</b>${esc(item.sourceNodeId||'missing')}</div></div>
    <blockquote class="evidence-quote">${esc(item.exactText||'Exact text unavailable')}</blockquote>
    ${src?.error?`<div class="warning">${esc(src.error)}</div>`:state.evidence===item.evidenceId&&!src?'<div class="pane-empty"><div class="spinner"></div>Resolving Phase-1 source…</div>':`<div class="source-block"><div class="source-head"><span>${badge(item.sourceType)} Official source</span><span>${esc(location)}</span></div><div class="source-body"><dl class="kv"><dt>Document</dt><dd>${safeUrl(node.official_url||item.officialUrl)?`<a class="source-link" href="${esc(safeUrl(node.official_url||item.officialUrl))}" target="_blank" rel="noreferrer">${esc(node.document_title||item.sourcePath?.split('/').pop()||'Official specification')} ↗</a>`:esc(node.document_title||item.sourcePath?.split('/').pop()||'—')}<br><small>${esc(node.document_id||'')}</small></dd><dt>Section</dt><dd>${esc(item.sectionNumber||node.section_number||'—')} · ${esc(item.sectionTitle||node.title||'—')}</dd><dt>Node</dt><dd>${esc(item.sourceNodeId||'—')}</dd><dt>Source span</dt><dd>${esc(spans.join(', ')||'—')}</dd><dt>${p.type==='pdf'?'Page / bbox':'Anchor / DOM'}</dt><dd>${esc(p.type==='pdf'?location:`#${p.anchor||'—'} · ${p.domPath||'—'} · lines ${p.sourceLineStart||'—'}–${p.sourceLineEnd||'—'}`)}</dd></dl></div>${p.type==='pdf'&&p.imageUrl?`<img class="pdf-preview" src="${esc(p.imageUrl)}" alt="PDF page ${esc(p.page)} with selected evidence highlighted">`:''}</div>`}
    <div class="reverse"><h4>Used by claims</h4><div class="pill-list">${(item.usedByClaims||[]).map(x=>`<button class="pill button" data-nav-claim="${esc(x)}">${esc(x)}</button>`).join('')||'<span class="pill">none</span>'}</div></div><div class="reverse"><h4>Implemented by declarations</h4><div class="pill-list">${(item.implementationMappings||[]).map(x=>`<button class="pill button ${x.origin==='SHARED_CORE_DECLARATION'?'shared':''}" data-nav-declaration="${esc(x.declaration)}">${esc(x.declaration.split('.').pop())} · ${x.origin==='SHARED_CORE_DECLARATION'?'shared core':'unit'}</button>`).join('')||'<span class="pill">none</span>'}</div></div></div>`;
}
function renderTrace(target) {
  const documents=codeDocuments(); const active=activeCodeDocument();
  target.innerHTML=`<div class="trace-grid"><section class="pane"><header class="pane-head code-pane-head"><span class="pane-title">Generated Lean</span><div class="code-actions"><div class="code-search"><input id="code-search" placeholder="Find in code" value="${esc(state.codeQuery)}"></div><button class="copy-source" data-copy-source>Copy source</button><span id="copy-status" class="copy-status" aria-live="polite">${esc(state.copyStatus)}</span></div></header><div class="code-documents">${documents.map(item=>`<button class="code-document ${item.documentId===active.documentId?'active':''} ${item.origin==='SHARED_CORE_DECLARATION'?'shared':''}" data-code-document="${esc(item.documentId)}">${item.origin==='SHARED_CORE_DECLARATION'?'Shared core':'Unit'} · ${esc(item.filename||'unavailable')}</button>`).join('')}</div><div class="pane-body"><div class="code">${active.source?renderCode():'<div class="pane-empty">Lean translation is not available for this partial run.</div>'}</div></div></section>
    <section class="pane"><header class="pane-head"><span class="pane-title">Semantic claims</span><span class="pane-count">${state.unit.claims.length}</span></header><div class="pane-body" id="claim-pane">${claimCards()}</div></section>
    <section class="pane"><header class="pane-head"><span class="pane-title">Evidence & source</span><span class="pane-count">${state.unit.evidence.length}</span></header><div class="pane-body" id="evidence-pane">${evidencePane()}</div></section></div>`;
  bindTrace();
}
function renderTraceSelection(){ if(state.tab!=='lean')return; const cp=app.querySelector('#claim-pane'),ep=app.querySelector('#evidence-pane'); if(cp)cp.innerHTML=claimCards();if(ep)ep.innerHTML=evidencePane();bindTrace(); }
function bindTrace(){
  app.querySelectorAll('[data-declaration]').forEach(node=>node.onclick=()=>selectDeclaration(node.dataset.declaration));
  app.querySelectorAll('[data-claim]').forEach(node=>node.onclick=()=>selectClaim(node.dataset.claim));
  app.querySelectorAll('[data-evidence]').forEach(node=>node.onclick=()=>selectEvidence(node.dataset.evidence));
  app.querySelectorAll('[data-nav-claim]').forEach(node=>node.onclick=()=>selectClaim(node.dataset.navClaim));
  app.querySelectorAll('[data-nav-declaration]').forEach(node=>node.onclick=()=>selectDeclaration(node.dataset.navDeclaration));
  app.querySelectorAll('[data-code-document]').forEach(node=>node.onclick=()=>{const document=codeDocuments().find(item=>item.documentId===node.dataset.codeDocument);state.codeDocument=node.dataset.codeDocument;state.copyStatus='';selectDeclaration(document?.declarations?.find(item=>item.mapped)?.declaration||document?.declarations?.[0]?.declaration||null);});
  const copy=app.querySelector('[data-copy-source]'); if(copy)copy.onclick=copyLeanSource;
  const search=app.querySelector('#code-search'); if(search)search.oninput=()=>{state.codeQuery=search.value;const code=app.querySelector('.code');if(code)code.innerHTML=renderCode();bindTrace();};
}

function renderOverview(target){
  const u=state.unit; const primary=u.lean.declarations.filter(d=>d.mapped&&['OPERATION','EXECUTION'].includes(d.role)); const mapped=u.lean.declarations.filter(d=>d.mapped); const shared=mapped.filter(d=>d.origin==='SHARED_CORE_DECLARATION');
  target.innerHTML=`<div class="content-page"><div class="eyebrow">${esc(u.unit.status)}</div><h2>${esc(u.unit.name)} at a glance</h2>${u.warnings.map(w=>`<div class="warning">Broken reference: ${esc(w.source)} → ${esc(w.target)}</div>`).join('')}
  <div class="section-grid"><section class="semantic-section"><h3>Generated Lean</h3><div class="summary-number">${mapped.length}</div><p class="summary-label">mapped declarations (${mapped.length-shared.length} unit · ${shared.length} shared core)</p>${primary.map(d=>`<div class="pill ${d.origin==='SHARED_CORE_DECLARATION'?'shared':''}">${esc(d.localName)} · ${esc(d.role)} · ${d.origin==='SHARED_CORE_DECLARATION'?'shared core':'unit'}</div>`).join('')}</section>
  <section class="semantic-section"><h3>Semantic grounding</h3><div class="summary-number">${u.claims.length}</div><p class="summary-label">claims supported by ${u.evidence.length} exact evidence items</p><div class="pill-list">${[...new Set(u.claims.map(c=>c.kind))].map(x=>badge(x)).join('')}</div></section>
  <section class="semantic-section"><h3>Phase 6</h3>${u.checks?status(u.checks.status):'<p class="summary-label">Checks have not completed.</p>'}<p class="summary-label">Build · Coverage · Traceability</p></section></div></div>`;
}

function renderStructured(value){
  if(value==null)return '';
  if(Array.isArray(value))return `<ul class="structured">${value.map(v=>`<li>${renderStructured(v)}</li>`).join('')}</ul>`;
  if(typeof value==='object')return `<ul class="structured">${Object.entries(value).map(([k,v])=>k==='evidenceIds'?`<li><b>Evidence</b><div class="pill-list">${(v||[]).map(e=>`<button class="pill button" data-semantic-evidence="${esc(e)}">${esc(e)}</button>`).join('')}</div></li>`:`<li><b>${esc(k.replace(/([A-Z])/g,' $1'))}</b> ${typeof v==='object'?renderStructured(v):esc(v)}</li>`).join('')}</ul>`;
  return esc(value);
}
function renderSemantics(target){
  const semantics=state.unit.semantics;
  if(!semantics){target.innerHTML='<div class="content-page"><div class="empty">Phase-4 semantics are not available for this unit.</div></div>';return;}
  const labels={identity:'Identity',operation:'Operation',inputs:'Inputs / operands',result:'Result',typeRules:'Type rules',branches:'Branches',edgeCases:'Edge cases',stateEffects:'State effects',predication:'Predication',restrictions:'Restrictions',sourceFacts:'Source facts',derivedInterpretations:'Derived interpretations',dependencies:'Design dependencies',assumptions:'Assumptions'};
  const sections=Object.entries(labels).filter(([key])=>semantics[key]!=null&&(Array.isArray(semantics[key])?semantics[key].length:true)).map(([key,label])=>`<section class="semantic-section"><h3>${label}</h3>${renderStructured(semantics[key])}</section>`).join('');
  target.innerHTML=`<div class="content-page"><div class="eyebrow">Phase 4</div><h2>Structured semantics</h2><p class="lede">A friendly projection of categories present in the semantic artifact.</p><div class="section-grid">${sections}</div></div>`;
  app.querySelectorAll('[data-semantic-evidence]').forEach(node=>node.onclick=()=>{const evidence=node.dataset.semanticEvidence;const item=state.unit.evidence.find(e=>e.evidenceId===evidence);state.tab='lean';state.evidence=evidence;state.claim=item?.usedByClaims?.[0]||state.claim;state.declaration=item?.implementedByDeclarations?.[0]||state.declaration;renderUnitShell();selectEvidence(evidence);});
}
function renderEvidenceIndex(target){
  const grouped=Object.groupBy?Object.groupBy(state.unit.evidence,e=>e.tier||'OTHER'):state.unit.evidence.reduce((a,e)=>((a[e.tier||'OTHER']??=[]).push(e),a),{});
  target.innerHTML=`<div class="content-page"><div class="eyebrow">Phase 3 input boundary</div><h2>Evidence supplied to semantics</h2><div class="evidence-groups">${Object.entries(grouped).map(([tier,items])=>`<section><h3 class="group-title">${badge(tier)} <span>${items.length} items</span></h3><div class="section-grid">${items.map(item=>`<article class="evidence-card" data-index-evidence="${esc(item.evidenceId)}"><div class="card-top">${badge(item.role)}<span class="card-id">${esc(item.evidenceId)}</span></div><div class="card-text">${esc(item.exactText)}</div><div class="card-foot"><span>${esc(item.sectionNumber||'')}</span><span>${item.usedByClaims?.length||0} claims</span></div></article>`).join('')}</div></section>`).join('')||'<div class="empty">No Phase-3 evidence is available.</div>'}</div></div>`;
  app.querySelectorAll('[data-index-evidence]').forEach(node=>node.onclick=()=>{state.tab='lean';state.evidence=node.dataset.indexEvidence;const ev=state.unit.evidence.find(e=>e.evidenceId===state.evidence);state.claim=ev?.usedByClaims?.[0]||null;state.declaration=ev?.implementedByDeclarations?.[0]||state.declaration;renderUnitShell();selectEvidence(state.evidence);});
}
function navigationPills(navigation){
  if(!navigation)return '';
  const declarations=(navigation.declarations||[]).map(value=>`<button class="pill button" data-check-declaration="${esc(value)}">code · ${esc(value.split('.').pop())}</button>`);
  const claims=(navigation.claims||[]).map(value=>`<button class="pill button" data-check-claim="${esc(value)}">${esc(value)}</button>`);
  const evidence=(navigation.evidence||[]).map(value=>`<button class="pill button" data-check-evidence="${esc(value)}">${esc(value)}</button>`);
  const all=[...declarations,...claims,...evidence];
  return all.length?`<div class="pill-list diagnostic-navigation">${all.join('')}</div>`:'';
}
function checkItems(items){
  return (items||[]).map(item=>`<div class="check-detail-item"><pre class="raw">${esc(JSON.stringify(Object.fromEntries(Object.entries(item).filter(([key])=>key!=='navigation')),null,2))}</pre>${navigationPills(item.navigation)}</div>`).join('');
}
function checkDetails(label,data){
  if(!data)return `<section class="check-card"><h3>${label}</h3><div class="check-status">—</div><p class="summary-label">Not available</p></section>`;
  const details=label==='Build'?data.diagnostics:label==='Coverage'?{covered:data.covered,uncovered:data.uncovered}:{validMappings:data.validMappings,brokenMappings:data.brokenMappings};
  const items=Array.isArray(details)?details:(details&&typeof details==='object'?Object.values(details).flatMap(value=>Array.isArray(value)?value:[]):[]);
  return `<section class="check-card"><h3>${label}</h3><div class="check-status ${String(data.status).toLowerCase()}">${data.status==='PASS'?'✓':'×'} ${esc(data.status)}</div>${label==='Build'?`<p class="summary-label">${esc(data.leanVersion||'Lean compiler')} · ${fmtDuration(data.durationMs)}</p>`:''}<details><summary>View ${label.toLowerCase()} details</summary>${checkItems(items)||`<pre class="raw">${esc(JSON.stringify(details,null,2))}</pre>`}</details></section>`;
}
function navigateRecorded(kind,value){
  state.tab='lean';
  if(kind==='declaration')selectDeclaration(value,false);
  if(kind==='claim'){
    state.claim=value;const claim=state.unit.claims.find(item=>item.claimId===value);
    if(!(claim?.declarations||[]).includes(state.declaration))state.declaration=claim?.declarations?.[0]||null;
    const declaration=state.unit.lean.declarations.find(item=>item.declaration===state.declaration);if(declaration?.sourceDocumentId)state.codeDocument=declaration.sourceDocumentId;
    state.evidence=claim?.evidenceIds?.[0]||null;state.source=null;
  }
  if(kind==='evidence'){
    state.evidence=value;const evidence=state.unit.evidence.find(item=>item.evidenceId===value);
    state.claim=evidence?.usedByClaims?.[0]||null;state.declaration=evidence?.implementedByDeclarations?.[0]||null;
    const declaration=state.unit.lean.declarations.find(item=>item.declaration===state.declaration);if(declaration?.sourceDocumentId)state.codeDocument=declaration.sourceDocumentId;
  }
  renderUnitShell();if(state.evidence)selectEvidence(state.evidence);
}
function bindCheckNavigation(){
  app.querySelectorAll('[data-check-declaration]').forEach(node=>node.onclick=()=>navigateRecorded('declaration',node.dataset.checkDeclaration));
  app.querySelectorAll('[data-check-claim]').forEach(node=>node.onclick=()=>navigateRecorded('claim',node.dataset.checkClaim));
  app.querySelectorAll('[data-check-evidence]').forEach(node=>node.onclick=()=>navigateRecorded('evidence',node.dataset.checkEvidence));
}
function renderChecks(target){const c=state.unit.checks;const recorded=stageValue(state.unit.unit.stages.check);const changed=c&&['PASS','FAIL'].includes(recorded)&&recorded!==c.status;target.innerHTML=`<div class="content-page"><div class="eyebrow">Phase 6</div><h2>Deterministic checks</h2>${changed?`<div class="warning">This run recorded Check = ${esc(recorded)}. The plan's current shared check artifact is ${esc(c.status)}, so it may have been updated by a later resumed run.</div>`:''}${c?`<div class="check-grid">${checkDetails('Build',c.build)}${checkDetails('Coverage',c.coverage)}${checkDetails('Traceability',c.traceability)}</div>`:'<div class="empty">Phase-6 checks have not completed for this unit.</div>'}</div>`;bindCheckNavigation();}
function renderPipeline(target){
  const repairs=state.unit.repairs;
  target.innerHTML=`<div class="content-page"><div class="eyebrow">Artifact metadata</div><h2>Pipeline timeline</h2><div class="timeline">${state.unit.timeline.map(x=>`<div class="timeline-item"><b>${esc(x.phase)}</b><small>${esc(x.status)} · ${fmtDuration(x.durationMs)}</small></div>`).join('')}</div><h2>Troubleshooter history</h2>${repairs.length?repairs.map((r,i)=>`<section class="repair-card"><div class="card-top">${badge(`Repair ${i+1}`)}${badge(r.reason)}${badge('Current Lean = after')}</div><p>${esc(r.changes?.map(x=>x.description).join(' ')||'Compiler-guided repair recorded.')}</p><div class="pill-list">${(r.changes||[]).flatMap(x=>x.affectedDeclarations||[]).map(x=>`<span class="pill">${esc(x)}</span>`).join('')}</div><details><summary>Hashes and diagnostics</summary><pre class="raw">${esc(JSON.stringify({hashes:r.hashes,diagnostics:r.diagnostics},null,2))}</pre></details></section>`).join(''):'<div class="empty">Troubleshooter was not used for this unit.</div>'}</div>`;
}
function renderRaw(target){target.innerHTML=`<div class="content-page"><div class="eyebrow">Debugging</div><h2>Raw artifacts</h2><p class="lede">The normalized views remain authoritative projections; raw JSON is available here for low-level inspection.</p><details open><summary>Phase 4 / 5 / 6 artifacts</summary><pre class="raw">${esc(JSON.stringify(state.unit.raw,null,2))}</pre></details></div>`;}

function setupSearch(){
  const input=app.querySelector('#global-search'),results=app.querySelector('#search-results'); if(!input||!state.run)return;
  let timer; input.oninput=()=>{clearTimeout(timer);if(!input.value.trim()){results.classList.add('hidden');return;}timer=setTimeout(async()=>{try{const items=await api(`/api/runs/${id(state.run.runId)}/search?q=${encodeURIComponent(input.value)}`);results.innerHTML=items.map((x,i)=>`<div class="search-result" data-search-index="${i}"><small>${esc(x.type)}</small><span>${esc(x.label)}</span></div>`).join('')||'<div class="pane-empty">No matches</div>';results.classList.remove('hidden');results.querySelectorAll('[data-search-index]').forEach(node=>node.onclick=()=>{const x=items[Number(node.dataset.searchIndex)];openUnit(x.unitId,{tab:x.type==='evidence'?'evidence':'lean',declaration:x.type==='declaration'?x.id:null,claim:x.type==='claim'?x.id:null,evidence:x.type==='evidence'?x.id:null});});}catch(e){results.innerHTML=`<div class="pane-empty">${esc(e.message)}</div>`;results.classList.remove('hidden');}},220);};
}

document.addEventListener('keydown',event=>{if(event.key==='Escape')app.querySelector('#search-results')?.classList.add('hidden');if((event.ctrlKey||event.metaKey)&&event.key==='k'){event.preventDefault();app.querySelector('#global-search')?.focus();}});

(async()=>{try{const config=await api('/api/config');await showHome();if(config.initialRun)await openRun(config.initialRun);}catch(error){errorView(error);}})();
