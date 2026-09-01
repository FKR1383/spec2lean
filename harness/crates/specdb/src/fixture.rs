//! A synthetic Phase-1 index, built in-process for tests.
//!
//! Keeps the Rust test suite self-contained: no Python, no PyMuPDF, no
//! generated file checked into the repository. The schema is the Phase-1 schema
//! verbatim, so the queries under test are the real ones.

use std::path::Path;

use rusqlite::Connection;

pub const SCHEMA_SQL: &str = include_str!("../schema.sql");

/// Two official renditions of one tiny specification, so the HTML/PDF pairing
/// rules have something to bite on.
pub fn build(path: &Path) -> rusqlite::Result<()> {
    let connection = Connection::open(path)?;
    connection.execute_batch(SCHEMA_SQL)?;
    let long_text = "x".repeat(25_000);
    connection.execute_batch(
        &r#"
INSERT INTO specifications VALUES
  ('spec:synthetic', 'synthetic', '1.0', 'Synthetic ISA', '2026-01-01T00:00:00Z');

INSERT INTO builds VALUES
  ('build:1', 'spec:synthetic', 'test', 1, '2026-01-01T00:00:00Z',
   'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd', 'COMPLETE');

INSERT INTO documents VALUES
  ('doc:html', 'spec:synthetic', 'html', 'Synthetic ISA (HTML)', 'https://example.test/spec',
   '/fixtures/spec.html',
   'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
   100, 'test', 1, NULL, 100, 100, '{}', '2026-01-01T00:00:00Z'),
  ('doc:pdf', 'spec:synthetic', 'pdf', 'Synthetic ISA (PDF)', 'https://example.test/spec.pdf',
   '/fixtures/spec.pdf',
   'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
   200, 'test', 1, 4, 100, 100, '{}', '2026-01-01T00:00:00Z');

-- HTML rendition
INSERT INTO nodes VALUES
  ('node:html-root',   'doc:html', NULL,             'k1', 'document',  0, 0, 'Synthetic ISA', 'synthetic isa', NULL,  '',                        '',                      NULL, NULL, NULL,        '{}'),
  ('node:html-ch1',    'doc:html', 'node:html-root', 'k2', 'chapter',   0, 1, 'Add',           'add',           '1',   '1. Add',                  '1. add',                NULL, NULL, 'add',       '{}'),
  ('node:html-syntax', 'doc:html', 'node:html-ch1',  'k3', 'syntax_block', 0, 2, NULL,         NULL,            NULL,  'add.type d, a, b;',       'add.type d, a, b;',     NULL, NULL, NULL,        '{}'),
  ('node:html-def',    'doc:html', 'node:html-ch1',  'k4', 'definition',   1, 2, NULL,         NULL,            NULL,  'predicate: a one-bit value.', 'predicate: a one-bit value.', NULL, NULL, 'predicate', '{}'),
  ('node:html-note',   'doc:html', 'node:html-ch1',  'k5', 'note',         2, 2, NULL,         NULL,            NULL,  'Note: overflow wraps.',   'note: overflow wraps.', NULL, NULL, NULL,        '{}');

-- A second, differently numbered chapter that defines the same spelling. Two
-- distinct sections claiming one instruction is ambiguity; two *renditions* of
-- one section are not.
INSERT INTO nodes VALUES
  ('node:html-ch2',     'doc:html', 'node:html-root', 'k7', 'chapter',      1, 1, 'Add', 'add', '2', '2. Add', '2. add', NULL, NULL, 'add2', '{}'),
  ('node:html-syntax2', 'doc:html', 'node:html-ch2',  'k8', 'syntax_block', 0, 2, NULL,  NULL,  NULL, 'add.type d, a, b;', 'add.type d, a, b;', NULL, NULL, NULL, '{}');

-- PDF rendition
INSERT INTO nodes VALUES
  ('node:pdf-root',   'doc:pdf', NULL,            'p1', 'document',     0, 0, 'Synthetic ISA', 'synthetic isa', NULL, '',                  '',                  NULL, NULL, NULL, '{}'),
  ('node:pdf-ch1',    'doc:pdf', 'node:pdf-root', 'p2', 'chapter',      0, 1, 'Add',           'add',           '1',  '1. Add',            '1. add',            1,    2,    NULL, '{}'),
  ('node:pdf-syntax', 'doc:pdf', 'node:pdf-ch1',  'p3', 'syntax_block', 0, 2, NULL,            NULL,            NULL, 'add.type d, a, b;', 'add.type d, a, b;', 2,    2,    NULL, '{}');

-- A node longer than the 24,000-character display limit, so a session can be
-- shown part of it and then try to select the whole thing.
INSERT INTO nodes VALUES
  ('node:html-long', 'doc:html', 'node:html-ch1', 'k6', 'paragraph', 3, 2, NULL, NULL, NULL,
   'LONGTEXT', 'longtext', NULL, NULL, NULL, '{}');

INSERT INTO source_spans VALUES
  ('span:html-syntax-0', 'node:html-syntax', 'doc:html', 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '/html/body/pre', 12, 12, 'add.type d, a, b;'),
  ('span:html-def-0',    'node:html-def',    'doc:html', 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '/html/body/dl',  20, 20, 'predicate: a one-bit value.'),
  ('span:html-syntax2-0','node:html-syntax2','doc:html', 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '/html/body/pre2', 50, 50, 'add.type d, a, b;'),
  ('span:html-note-0',   'node:html-note',   'doc:html', 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '/html/body/div', 30, 30, 'Note: overflow wraps.'),
  ('span:pdf-syntax-0',  'node:pdf-syntax',  'doc:pdf',  0, 2,    10.0, 20.0, 90.0, 30.0, 1,    0,    0,    NULL,             NULL, NULL, 'add.type d, '),
  ('span:pdf-syntax-1',  'node:pdf-syntax',  'doc:pdf',  1, 2,    10.0, 30.0, 95.0, 40.0, 1,    1,    0,    NULL,             NULL, NULL, 'a, b;');

INSERT INTO source_spans VALUES
  ('span:html-long-0', 'node:html-long', 'doc:html', 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '/html/body/p', 40, 40, 'LONGTEXT');

INSERT INTO cross_references VALUES
  ('ref:1', 'node:html-note', 0, 'section', 'see Chapter 1', '1', '#add', 'node:html-ch1', 'RESOLVED', 1);

INSERT INTO terms VALUES ('term:predicate', 'spec:synthetic', 'predicate', 'predicate');
INSERT INTO definitions VALUES
  ('def:1', 'term:predicate', 'node:html-def', 0, 'A one-bit value used to guard execution.', 'html-definition-list');

INSERT INTO node_correlations VALUES
  ('corr:1', 'node:html-syntax', 'node:pdf-syntax', 'exact-text', 'HIGH');

INSERT INTO nodes_fts (node_id, title, raw_text, normalized_text)
  SELECT node_id, COALESCE(title, ''), raw_text, normalized_text FROM nodes;
"#
        .replace("LONGTEXT", &long_text),
    )?;
    Ok(())
}
