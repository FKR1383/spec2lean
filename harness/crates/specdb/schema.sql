PRAGMA foreign_keys = ON;
PRAGMA journal_mode = DELETE;

CREATE TABLE specifications (
    specification_id TEXT PRIMARY KEY,
    language TEXT NOT NULL COLLATE NOCASE,
    version TEXT NOT NULL,
    title TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(language, version)
);

CREATE TABLE builds (
    build_id TEXT PRIMARY KEY,
    specification_id TEXT NOT NULL REFERENCES specifications(specification_id),
    parser_version TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    semantic_digest TEXT,
    status TEXT NOT NULL
);

CREATE TABLE documents (
    document_id TEXT PRIMARY KEY,
    specification_id TEXT NOT NULL REFERENCES specifications(specification_id),
    source_type TEXT NOT NULL CHECK(source_type IN ('pdf', 'html')),
    title TEXT NOT NULL,
    official_url TEXT,
    local_path TEXT NOT NULL,
    sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
    byte_size INTEGER NOT NULL,
    parser_version TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    page_count INTEGER,
    source_text_chars INTEGER NOT NULL,
    indexed_text_chars INTEGER NOT NULL DEFAULT 0,
    parser_stats_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(specification_id, source_type, sha256)
);

CREATE TABLE pages (
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL CHECK(page_number >= 1),
    width REAL NOT NULL,
    height REAL NOT NULL,
    raw_text TEXT NOT NULL,
    source_text_chars INTEGER NOT NULL,
    PRIMARY KEY(document_id, page_number)
);

CREATE TABLE nodes (
    node_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES nodes(node_id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    source_key TEXT NOT NULL,
    node_type TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
    depth INTEGER NOT NULL CHECK(depth >= 0),
    title TEXT,
    normalized_title TEXT,
    section_number TEXT,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    html_anchor TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(document_id, source_key),
    UNIQUE(document_id, parent_id, ordinal),
    CHECK((page_start IS NULL AND page_end IS NULL) OR
          (page_start >= 1 AND page_end >= page_start))
);

CREATE INDEX nodes_parent_order ON nodes(document_id, parent_id, ordinal);
CREATE INDEX nodes_section_number ON nodes(document_id, section_number);
CREATE INDEX nodes_anchor ON nodes(document_id, html_anchor);
CREATE INDEX nodes_type ON nodes(document_id, node_type);

CREATE TABLE source_spans (
    span_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    page_number INTEGER,
    bbox_x0 REAL,
    bbox_y0 REAL,
    bbox_x1 REAL,
    bbox_y1 REAL,
    block_index INTEGER,
    line_index INTEGER,
    span_index INTEGER,
    dom_path TEXT,
    source_line_start INTEGER,
    source_line_end INTEGER,
    raw_text TEXT NOT NULL,
    UNIQUE(node_id, ordinal)
);

CREATE INDEX source_spans_page ON source_spans(document_id, page_number);
CREATE INDEX source_spans_dom ON source_spans(document_id, dom_path);

CREATE TABLE cross_references (
    reference_id TEXT PRIMARY KEY,
    source_node_id TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    kind TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    target_reference_text TEXT NOT NULL,
    href TEXT,
    resolved_target_node_id TEXT REFERENCES nodes(node_id),
    resolution_status TEXT NOT NULL CHECK(resolution_status IN ('RESOLVED', 'AMBIGUOUS', 'UNRESOLVED')),
    candidate_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE(source_node_id, ordinal)
);

CREATE INDEX cross_references_status ON cross_references(resolution_status);

CREATE TABLE terms (
    term_id TEXT PRIMARY KEY,
    specification_id TEXT NOT NULL REFERENCES specifications(specification_id),
    term TEXT NOT NULL,
    normalized_term TEXT NOT NULL,
    UNIQUE(specification_id, normalized_term)
);

CREATE TABLE definitions (
    definition_id TEXT PRIMARY KEY,
    term_id TEXT NOT NULL REFERENCES terms(term_id),
    node_id TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    definition_text TEXT NOT NULL,
    structural_basis TEXT NOT NULL,
    UNIQUE(node_id, ordinal)
);

CREATE TABLE term_occurrences (
    term_id TEXT NOT NULL REFERENCES terms(term_id),
    node_id TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    PRIMARY KEY(term_id, node_id, role, ordinal)
);

CREATE TABLE node_correlations (
    correlation_id TEXT PRIMARY KEY,
    left_node_id TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    right_node_id TEXT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    basis TEXT NOT NULL,
    confidence TEXT NOT NULL,
    UNIQUE(left_node_id, right_node_id)
);

CREATE TABLE validation_runs (
    validation_id TEXT PRIMARY KEY,
    build_id TEXT NOT NULL REFERENCES builds(build_id),
    created_at TEXT NOT NULL,
    ok INTEGER NOT NULL,
    report_json TEXT NOT NULL
);

CREATE VIRTUAL TABLE nodes_fts USING fts5(
    node_id UNINDEXED,
    title,
    raw_text,
    normalized_text,
    tokenize = 'unicode61 remove_diacritics 2'
);
