use std::path::Path;

use rusqlite::{Connection, OpenFlags, Row};
use serde::Serialize;

use crate::ids::{NodeId, SpanId};

/// Row ceiling shared by every bounded query, matching the Python
/// `MAX_TOOL_ROWS`.
pub const MAX_TOOL_ROWS: i64 = 100;
/// Per-node exact-text ceiling, matching the Python `MAX_NODE_TEXT_CHARS`.
pub const MAX_NODE_TEXT_CHARS: usize = 24_000;

pub type Result<T> = std::result::Result<T, SpecDbError>;

#[derive(Debug)]
pub enum SpecDbError {
    Sqlite(rusqlite::Error),
    UnknownNode(String),
    OutOfRange(String),
    Schema(String),
}

impl std::fmt::Display for SpecDbError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Sqlite(error) => write!(f, "specification index error: {error}"),
            Self::UnknownNode(id) => write!(f, "unknown node: {id}"),
            Self::OutOfRange(detail) => write!(f, "{detail}"),
            Self::Schema(detail) => write!(f, "specification index is unusable: {detail}"),
        }
    }
}

impl std::error::Error for SpecDbError {}

impl From<rusqlite::Error> for SpecDbError {
    fn from(error: rusqlite::Error) -> Self {
        Self::Sqlite(error)
    }
}

/// The two official renditions Phase 1 indexes. An enum, not a string, so a
/// rendition the schema does not define cannot reach the pairing rules.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum SourceType {
    Html,
    Pdf,
}

impl SourceType {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Html => "html",
            Self::Pdf => "pdf",
        }
    }

    fn parse(value: &str) -> rusqlite::Result<Self> {
        match value {
            "html" => Ok(Self::Html),
            "pdf" => Ok(Self::Pdf),
            other => Err(rusqlite::Error::FromSqlConversionFailure(
                0,
                rusqlite::types::Type::Text,
                Box::new(SpecDbError::Schema(format!("unknown source type: {other}"))),
            )),
        }
    }
}

#[derive(Debug, Clone)]
pub struct NodeRow {
    pub node_id: NodeId,
    pub document_id: String,
    pub parent_id: Option<NodeId>,
    pub node_type: String,
    pub ordinal: i64,
    pub depth: i64,
    pub title: Option<String>,
    pub section_number: Option<String>,
    pub raw_text: String,
    pub page_start: Option<i64>,
    pub page_end: Option<i64>,
    pub html_anchor: Option<String>,
    pub metadata_json: String,
    pub source_type: SourceType,
    pub document_sha256: String,
    pub document_local_path: String,
    pub document_official_url: Option<String>,
}

impl NodeRow {
    fn from_row(row: &Row<'_>) -> rusqlite::Result<Self> {
        Ok(Self {
            node_id: NodeId::trusted(row.get("node_id")?),
            document_id: row.get("document_id")?,
            parent_id: row.get::<_, Option<String>>("parent_id")?.map(NodeId::trusted),
            node_type: row.get("node_type")?,
            ordinal: row.get("ordinal")?,
            depth: row.get("depth")?,
            title: row.get("title")?,
            section_number: row.get("section_number")?,
            raw_text: row.get("raw_text")?,
            page_start: row.get("page_start")?,
            page_end: row.get("page_end")?,
            html_anchor: row.get("html_anchor")?,
            metadata_json: row.get("metadata_json")?,
            source_type: SourceType::parse(&row.get::<_, String>("source_type")?)?,
            document_sha256: row.get("sha256").unwrap_or_default(),
            document_local_path: row.get("local_path").unwrap_or_default(),
            document_official_url: row.get("official_url").unwrap_or(None),
        })
    }
}

#[derive(Debug, Clone)]
pub struct SpanRow {
    pub span_id: SpanId,
    pub node_id: NodeId,
    pub ordinal: i64,
    pub page_number: Option<i64>,
    pub bbox: Option<[f64; 4]>,
    pub block_index: Option<i64>,
    pub line_index: Option<i64>,
    pub span_index: Option<i64>,
    pub dom_path: Option<String>,
    pub source_line_start: Option<i64>,
    pub source_line_end: Option<i64>,
    pub raw_text: String,
}

impl SpanRow {
    fn from_row(row: &Row<'_>) -> rusqlite::Result<Self> {
        let x0: Option<f64> = row.get("bbox_x0")?;
        let bbox = match x0 {
            Some(x0) => Some([
                x0,
                row.get::<_, Option<f64>>("bbox_y0")?.unwrap_or_default(),
                row.get::<_, Option<f64>>("bbox_x1")?.unwrap_or_default(),
                row.get::<_, Option<f64>>("bbox_y1")?.unwrap_or_default(),
            ]),
            None => None,
        };
        Ok(Self {
            span_id: SpanId::trusted(row.get("span_id")?),
            node_id: NodeId::trusted(row.get("node_id")?),
            ordinal: row.get("ordinal")?,
            page_number: row.get("page_number")?,
            bbox,
            block_index: row.get("block_index")?,
            line_index: row.get("line_index")?,
            span_index: row.get("span_index")?,
            dom_path: row.get("dom_path")?,
            source_line_start: row.get("source_line_start")?,
            source_line_end: row.get("source_line_end")?,
            raw_text: row.get("raw_text")?,
        })
    }
}

#[derive(Debug, Clone)]
pub struct XrefRow {
    pub reference_id: String,
    pub source_node_id: NodeId,
    pub ordinal: i64,
    pub kind: String,
    pub raw_text: String,
    pub target_reference_text: String,
    pub href: Option<String>,
    pub resolved_target_node_id: Option<NodeId>,
    pub resolution_status: String,
    pub candidate_count: i64,
}

#[derive(Debug, Clone)]
pub struct DefinitionRow {
    pub term: String,
    pub definition_text: String,
    pub structural_basis: String,
    pub node_id: NodeId,
}

#[derive(Debug, Clone)]
pub struct CorrelationRow {
    pub correlation_id: String,
    pub other_node_id: NodeId,
    pub basis: String,
    pub confidence: String,
}

#[derive(Debug, Clone)]
pub struct SearchHit {
    pub node: NodeRow,
    pub snippet: String,
}

const NODE_COLUMNS: &str =
    "n.*, d.source_type, d.sha256, d.local_path, d.official_url";

/// Read-only access to the Phase-1 index.
///
/// The database is a *file artifact*, not a live protocol, which is why the
/// parser that produces it can stay in Python while everything that consumes it
/// moves here: there is no IPC boundary between the two, only a SQLite file.
pub struct SpecDb {
    connection: Connection,
}

impl SpecDb {
    pub fn open(path: &Path) -> Result<Self> {
        let connection = Connection::open_with_flags(
            path,
            OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_URI,
        )?;
        Ok(Self { connection })
    }

    pub fn node_exists(&self, node_id: &NodeId) -> Result<bool> {
        Ok(self
            .connection
            .query_row("SELECT 1 FROM nodes WHERE node_id = ?1", [node_id], |_| Ok(()))
            .optional()?
            .is_some())
    }

    pub fn span_exists(&self, span_id: &SpanId) -> Result<bool> {
        Ok(self
            .connection
            .query_row(
                "SELECT 1 FROM source_spans WHERE span_id = ?1",
                [span_id],
                |_| Ok(()),
            )
            .optional()?
            .is_some())
    }

    pub fn node(&self, node_id: &NodeId) -> Result<NodeRow> {
        let sql = format!(
            "SELECT {NODE_COLUMNS} FROM nodes n JOIN documents d USING(document_id) \
             WHERE n.node_id = ?1"
        );
        self.connection
            .query_row(&sql, [node_id], NodeRow::from_row)
            .optional()?
            .ok_or_else(|| SpecDbError::UnknownNode(node_id.to_string()))
    }

    pub fn spans(&self, node_id: &NodeId) -> Result<Vec<SpanRow>> {
        let mut statement = self
            .connection
            .prepare("SELECT * FROM source_spans WHERE node_id = ?1 ORDER BY ordinal")?;
        let rows = statement.query_map([node_id], SpanRow::from_row)?;
        collect(rows)
    }

    pub fn spans_by_id(&self, span_ids: &[SpanId]) -> Result<Vec<SpanRow>> {
        if span_ids.is_empty() {
            return Ok(Vec::new());
        }
        let placeholders = (1..=span_ids.len())
            .map(|index| format!("?{index}"))
            .collect::<Vec<_>>()
            .join(",");
        let sql = format!("SELECT * FROM source_spans WHERE span_id IN ({placeholders})");
        let mut statement = self.connection.prepare(&sql)?;
        let params = rusqlite::params_from_iter(span_ids.iter());
        let rows = statement.query_map(params, SpanRow::from_row)?;
        collect(rows)
    }

    pub fn children(&self, node_id: &NodeId, limit: i64) -> Result<Vec<NodeRow>> {
        bounded_limit(limit)?;
            // `nodes_parent_order` is (document_id, parent_id, ordinal), so a
            // query that omits the leading column can only scan it, and then
            // has to sort. Naming `document_id` turns the scan into a seek and
            // makes the ordering free. A node's document is fetched by primary
            // key, which is one point lookup; `parent_id` is a self-reference
            // and `UNIQUE(document_id, parent_id, ordinal)` scopes the pair to
            // one document, so this narrows nothing.
        let sql = format!(
            "SELECT {NODE_COLUMNS} FROM nodes n JOIN documents d USING(document_id) \
             WHERE n.document_id = (SELECT document_id FROM nodes WHERE node_id = ?1) \
               AND n.parent_id = ?1 ORDER BY n.ordinal, n.node_id LIMIT ?2"
        );
        let mut statement = self.connection.prepare(&sql)?;
        let rows = statement.query_map(
            rusqlite::params![node_id, limit],
            NodeRow::from_row,
        )?;
        collect(rows)
    }

    pub fn ancestors(&self, node_id: &NodeId, limit: i64) -> Result<Vec<NodeRow>> {
        bounded_limit(limit)?;
        let sql = format!(
            "WITH RECURSIVE ancestors(node_id, parent_id, distance) AS (
                 SELECT node_id, parent_id, 0 FROM nodes WHERE node_id = ?1
                 UNION ALL
                 SELECT n.node_id, n.parent_id, a.distance + 1
                 FROM nodes n JOIN ancestors a ON n.node_id = a.parent_id
             )
             SELECT {NODE_COLUMNS} FROM ancestors a
             JOIN nodes n ON n.node_id = a.node_id JOIN documents d USING(document_id)
             ORDER BY a.distance DESC LIMIT ?2"
        );
        let mut statement = self.connection.prepare(&sql)?;
        let rows = statement.query_map(rusqlite::params![node_id, limit], NodeRow::from_row)?;
        collect(rows)
    }

    pub fn subtree(&self, node_id: &NodeId, max_depth: i64, limit: i64) -> Result<Vec<NodeRow>> {
        if !(0..=8).contains(&max_depth) {
            return Err(SpecDbError::OutOfRange(
                "maxDepth must be between 0 and 8".into(),
            ));
        }
        bounded_limit(limit)?;
        let sql = format!(
            "WITH RECURSIVE tree(node_id, distance, path) AS (
                 SELECT node_id, 0, printf('%08d', ordinal) FROM nodes WHERE node_id = ?1
                 UNION ALL
                 SELECT n.node_id, t.distance + 1, t.path || '/' || printf('%08d', n.ordinal)
                 FROM nodes n JOIN tree t ON n.parent_id = t.node_id WHERE t.distance < ?2
             )
             SELECT {NODE_COLUMNS} FROM tree t JOIN nodes n USING(node_id)
             JOIN documents d USING(document_id) ORDER BY t.path, n.node_id LIMIT ?3"
        );
        let mut statement = self.connection.prepare(&sql)?;
        let rows = statement.query_map(
            rusqlite::params![node_id, max_depth, limit],
            NodeRow::from_row,
        )?;
        collect(rows)
    }

    pub fn search(&self, query: &str, limit: i64) -> Result<Vec<SearchHit>> {
        bounded_limit(limit)?;
        let tokens: Vec<String> = query
            .split_whitespace()
            .map(|token| format!("\"{}\"", token.replace('"', "\"\"")))
            .collect();
        if tokens.is_empty() {
            return Err(SpecDbError::OutOfRange(
                "search query must be non-empty".into(),
            ));
        }
        let expression = tokens.join(" AND ");
        let sql = format!(
            "SELECT {NODE_COLUMNS}, snippet(nodes_fts, 2, '[', ']', ' … ', 32) AS snippet,
                    bm25(nodes_fts, 8.0, 1.0, 0.5) AS rank
             FROM nodes_fts JOIN nodes n ON n.node_id = nodes_fts.node_id
             JOIN documents d USING(document_id) WHERE nodes_fts MATCH ?1
             ORDER BY rank, n.node_id LIMIT ?2"
        );
        let mut statement = self.connection.prepare(&sql)?;
        let rows = statement.query_map(rusqlite::params![expression, limit], |row| {
            Ok((NodeRow::from_row(row)?, row.get::<_, String>("snippet")?))
        })?;
        let mut result = Vec::new();
        for row in rows {
            let (node, snippet) = row?;
            result.push(SearchHit { node, snippet });
        }
        Ok(result)
    }

    pub fn xrefs(&self, node_id: &NodeId) -> Result<Vec<XrefRow>> {
        let mut statement = self.connection.prepare(
            "SELECT * FROM cross_references
             WHERE source_node_id = ?1 OR resolved_target_node_id = ?2
             ORDER BY source_node_id, ordinal LIMIT ?3",
        )?;
        let rows = statement.query_map(
            rusqlite::params![node_id, node_id, MAX_TOOL_ROWS],
            |row| {
                Ok(XrefRow {
                    reference_id: row.get("reference_id")?,
                    source_node_id: NodeId::trusted(row.get("source_node_id")?),
                    ordinal: row.get("ordinal")?,
                    kind: row.get("kind")?,
                    raw_text: row.get("raw_text")?,
                    target_reference_text: row.get("target_reference_text")?,
                    href: row.get("href")?,
                    resolved_target_node_id: row
                        .get::<_, Option<String>>("resolved_target_node_id")?
                        .map(NodeId::trusted),
                    resolution_status: row.get("resolution_status")?,
                    candidate_count: row.get("candidate_count")?,
                })
            },
        )?;
        collect(rows)
    }

    /// Definitions matching a term. Phase 3 requires a query; Phase 2 allows
    /// browsing the whole index, so the query is optional here and the
    /// non-empty rule is enforced by the caller that needs it.
    pub fn definitions_matching(
        &self,
        query: Option<&str>,
        limit: i64,
    ) -> Result<Vec<DefinitionRow>> {
        bounded_limit(limit)?;
        let read = |row: &Row<'_>| {
            Ok(DefinitionRow {
                term: row.get("term")?,
                definition_text: row.get("definition_text")?,
                structural_basis: row.get("structural_basis")?,
                node_id: NodeId::trusted(row.get("node_id")?),
            })
        };
        let normalized = query
            .map(crate::text::normalize_text)
            .map(|value| value.to_lowercase())
            .filter(|value| !value.is_empty());
        match normalized {
            Some(normalized) => {
                let mut statement = self.connection.prepare(
                    "SELECT t.term, d.definition_text, d.structural_basis, d.node_id
                     FROM definitions d JOIN terms t USING(term_id)
                     WHERE t.normalized_term LIKE ?1
                     ORDER BY t.normalized_term, d.node_id LIMIT ?2",
                )?;
                let rows = statement
                    .query_map(rusqlite::params![format!("%{normalized}%"), limit], read)?;
                collect(rows)
            }
            None => {
                let mut statement = self.connection.prepare(
                    "SELECT t.term, d.definition_text, d.structural_basis, d.node_id
                     FROM definitions d JOIN terms t USING(term_id)
                     ORDER BY t.normalized_term, d.node_id LIMIT ?1",
                )?;
                let rows = statement.query_map(rusqlite::params![limit], read)?;
                collect(rows)
            }
        }
    }

    pub fn definitions(&self, query: &str, limit: i64) -> Result<Vec<DefinitionRow>> {
        if crate::text::normalize_text(query).is_empty() {
            return Err(SpecDbError::OutOfRange(
                "definition query must be non-empty".into(),
            ));
        }
        self.definitions_matching(Some(query), limit)
    }

    /// Every chapter/section/subsection, HTML rendition first, then shallowest.
    ///
    /// The ordering is load-bearing: scope resolution prefers the HTML
    /// rendition and the least deeply nested heading when several match.
    pub fn headings(&self) -> Result<Vec<NodeRow>> {
        let sql = format!(
            "SELECT {NODE_COLUMNS} FROM nodes n JOIN documents d USING(document_id)
             WHERE n.node_type IN ('chapter', 'section', 'subsection')
             ORDER BY CASE d.source_type WHEN 'html' THEN 0 ELSE 1 END, n.depth, n.node_id"
        );
        let mut statement = self.connection.prepare(&sql)?;
        let rows = statement.query_map([], NodeRow::from_row)?;
        collect(rows)
    }

    /// `(node_type, raw_text)` for a node and its whole subtree, unbounded.
    ///
    /// Used only to decide whether a heading's subtree actually mentions an
    /// instruction; never returned to a model.
    pub fn descendant_texts(&self, node_id: &NodeId) -> Result<Vec<(String, String)>> {
        let mut statement = self.connection.prepare(
            "WITH RECURSIVE tree(node_id) AS (
                 SELECT node_id FROM nodes WHERE node_id = ?1
                 UNION ALL SELECT n.node_id FROM nodes n JOIN tree t ON n.parent_id = t.node_id
             ) SELECT node_type, raw_text FROM nodes JOIN tree USING(node_id)",
        )?;
        let rows = statement.query_map([node_id], |row| Ok((row.get(0)?, row.get(1)?)))?;
        collect(rows)
    }

    /// Node identity, type, and text for a node and its whole subtree.
    ///
    /// Scope resolution uses the identity to distinguish evidence in a
    /// section's content from the instruction spelling repeated by its heading.
    pub fn descendant_texts_with_ids(
        &self,
        node_id: &NodeId,
    ) -> Result<Vec<(NodeId, String, String)>> {
        let mut statement = self.connection.prepare(
            "WITH RECURSIVE tree(node_id) AS (
                 SELECT node_id FROM nodes WHERE node_id = ?1
                 UNION ALL SELECT n.node_id FROM nodes n JOIN tree t ON n.parent_id = t.node_id
             ) SELECT node_id, node_type, raw_text FROM nodes JOIN tree USING(node_id)",
        )?;
        let rows = statement.query_map([node_id], |row| {
            Ok((NodeId::trusted(row.get(0)?), row.get(1)?, row.get(2)?))
        })?;
        collect(rows)
    }

    /// Heading children of a node, in document order.
    pub fn heading_children(&self, node_id: &NodeId) -> Result<Vec<NodeRow>> {
        // The same unusable index as `children`; the same fix.
        let sql = format!(
            "SELECT {NODE_COLUMNS} FROM nodes n JOIN documents d USING(document_id)
             WHERE n.document_id = (SELECT document_id FROM nodes WHERE node_id = ?1)
               AND n.parent_id = ?1 AND n.node_type IN ('chapter', 'section', 'subsection')
             ORDER BY n.ordinal, n.node_id"
        );
        let mut statement = self.connection.prepare(&sql)?;
        let rows = statement.query_map([node_id], NodeRow::from_row)?;
        collect(rows)
    }

    /// Document roots, one per indexed rendition.
    pub fn root_nodes(&self) -> Result<Vec<NodeId>> {
        let mut statement = self
            .connection
            .prepare("SELECT node_id FROM nodes WHERE parent_id IS NULL ORDER BY document_id, node_id")?;
        let rows = statement.query_map([], |row| Ok(NodeId::trusted(row.get(0)?)))?;
        collect(rows)
    }

    pub fn correlated(&self, node_id: &NodeId) -> Result<Vec<CorrelationRow>> {
        let mut statement = self.connection.prepare(
            "SELECT correlation_id, basis, confidence,
                    CASE WHEN left_node_id = ?1 THEN right_node_id ELSE left_node_id END AS other_node_id
             FROM node_correlations WHERE left_node_id = ?2 OR right_node_id = ?3
             ORDER BY correlation_id LIMIT ?4",
        )?;
        let rows = statement.query_map(
            rusqlite::params![node_id, node_id, node_id, MAX_TOOL_ROWS],
            |row| {
                Ok(CorrelationRow {
                    correlation_id: row.get("correlation_id")?,
                    other_node_id: NodeId::trusted(row.get("other_node_id")?),
                    basis: row.get("basis")?,
                    confidence: row.get("confidence")?,
                })
            },
        )?;
        collect(rows)
    }

    /// The nearest ancestor-or-self chapter/section/subsection, used to label
    /// every evidence fragment with where it came from.
    pub fn section(&self, node_id: &NodeId) -> Result<(Option<String>, Option<String>)> {
        let row = self
            .connection
            .query_row(
                "WITH RECURSIVE lineage(node_id, parent_id, distance) AS (
                     SELECT node_id, parent_id, 0 FROM nodes WHERE node_id = ?1
                     UNION ALL SELECT n.node_id, n.parent_id, l.distance + 1
                     FROM nodes n JOIN lineage l ON n.node_id = l.parent_id
                 )
                 SELECT n.section_number, n.title FROM lineage l JOIN nodes n USING(node_id)
                 WHERE n.node_type IN ('chapter', 'section', 'subsection')
                 ORDER BY l.distance LIMIT 1",
                [node_id],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()?;
        Ok(row.unwrap_or((None, None)))
    }

    pub fn nearest_anchor(&self, node_id: &NodeId) -> Result<Option<String>> {
        Ok(self
            .connection
            .query_row(
                "WITH RECURSIVE lineage(node_id, parent_id, distance) AS (
                     SELECT node_id, parent_id, 0 FROM nodes WHERE node_id = ?1
                     UNION ALL SELECT n.node_id, n.parent_id, l.distance + 1
                     FROM nodes n JOIN lineage l ON n.node_id = l.parent_id
                 ) SELECT n.html_anchor FROM lineage l JOIN nodes n USING(node_id)
                   WHERE n.html_anchor IS NOT NULL ORDER BY l.distance LIMIT 1",
                [node_id],
                |row| row.get::<_, Option<String>>(0),
            )
            .optional()?
            .flatten())
    }

    /// The digest that pins a plan to the exact index it was built against.
    pub fn semantic_digest(&self) -> Result<String> {
        self.connection
            .query_row(
                "SELECT semantic_digest FROM builds WHERE status = 'COMPLETE' \
                 ORDER BY created_at DESC LIMIT 1",
                [],
                |row| row.get::<_, Option<String>>(0),
            )
            .optional()?
            .flatten()
            .filter(|digest| !digest.is_empty())
            .ok_or_else(|| {
                SpecDbError::Schema("Phase 1 database has no completed semantic digest".into())
            })
    }

    pub fn specification(&self) -> Result<(String, String)> {
        self.connection
            .query_row(
                "SELECT language, version FROM specifications LIMIT 1",
                [],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()?
            .ok_or_else(|| {
                SpecDbError::Schema("Phase 1 database has no specification identity".into())
            })
    }
}

fn bounded_limit(limit: i64) -> Result<()> {
    if (1..=MAX_TOOL_ROWS).contains(&limit) {
        Ok(())
    } else {
        Err(SpecDbError::OutOfRange(format!(
            "limit must be between 1 and {MAX_TOOL_ROWS}"
        )))
    }
}

fn collect<T>(rows: rusqlite::MappedRows<'_, impl FnMut(&Row<'_>) -> rusqlite::Result<T>>) -> Result<Vec<T>> {
    let mut result = Vec::new();
    for row in rows {
        result.push(row?);
    }
    Ok(result)
}

/// Character-wise truncation. Slicing by bytes would split a multi-byte
/// character and panic; the specification text is full of them.
pub fn truncate_chars(value: &str, limit: usize) -> (String, bool) {
    if value.chars().count() <= limit {
        return (value.to_string(), false);
    }
    (value.chars().take(limit).collect(), true)
}

use rusqlite::OptionalExtension;

/// One node ranked by how close its text is to a query vector.
#[derive(Debug, Clone)]
pub struct SemanticHit {
    pub node: NodeRow,
    pub similarity: f32,
}

/// What an index knows about its own embeddings, if it has any.
#[derive(Debug, Clone)]
pub struct EmbeddingBuild {
    pub model: String,
    pub dim: usize,
    pub node_count: i64,
}

impl SpecDb {
    /// The embedding build this index carries, or `None` if it was built
    /// without one. Every index answers this — a semantic search against a
    /// lexical-only index should say so rather than return nothing.
    pub fn embedding_build(&self) -> Result<Option<EmbeddingBuild>> {
        let exists: i64 = self.connection.query_row(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='embedding_builds'",
            [],
            |row| row.get(0),
        )?;
        if exists == 0 {
            return Ok(None);
        }
        let mut statement = self
            .connection
            .prepare("SELECT model, dim, node_count FROM embedding_builds LIMIT 1")?;
        let mut rows = statement.query([])?;
        match rows.next()? {
            Some(row) => Ok(Some(EmbeddingBuild {
                model: row.get(0)?,
                dim: row.get::<_, i64>(1)? as usize,
                node_count: row.get(2)?,
            })),
            None => Ok(None),
        }
    }

    /// Nodes most similar to `query`, best first.
    ///
    /// Brute force over every stored vector. A specification index holds
    /// hundreds to low thousands of nodes, so this is a few milliseconds of
    /// arithmetic, and it keeps the index one SQLite file with no extension to
    /// load and no second store to keep in step.
    pub fn semantic_search(&self, query: &[f32], limit: i64) -> Result<Vec<SemanticHit>> {
        bounded_limit(limit)?;
        if self.embedding_build()?.is_none() || query.is_empty() {
            return Ok(Vec::new());
        }
        let mut statement = self
            .connection
            .prepare("SELECT node_id, vector FROM embeddings")?;
        let mut rows = statement.query([])?;
        let mut scored: Vec<(f32, NodeId)> = Vec::new();
        while let Some(row) = rows.next()? {
            let node_id: String = row.get(0)?;
            let blob: Vec<u8> = row.get(1)?;
            let Some(similarity) = cosine(query, &blob) else {
                continue;
            };
            scored.push((similarity, NodeId::trusted(node_id)));
        }
        // Descending by similarity; ties by node id so a run is reproducible.
        scored.sort_by(|left, right| {
            right
                .0
                .partial_cmp(&left.0)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| left.1.as_str().cmp(right.1.as_str()))
        });
        scored.truncate(limit as usize);

        let mut hits = Vec::with_capacity(scored.len());
        for (similarity, node_id) in scored {
            hits.push(SemanticHit {
                node: self.node(&node_id)?,
                similarity,
            });
        }
        Ok(hits)
    }
}

/// Cosine similarity between a query and a stored little-endian float32 vector.
///
/// Stored vectors are normalised at build time and queries are normalised when
/// they are embedded, so this is a dot product — but the norms are applied
/// anyway, because an index built by an older writer that did not normalise
/// would otherwise rank by magnitude.
fn cosine(query: &[f32], blob: &[u8]) -> Option<f32> {
    if blob.len() != query.len() * 4 {
        return None;
    }
    let mut dot = 0f32;
    let mut norm = 0f32;
    for (index, chunk) in blob.chunks_exact(4).enumerate() {
        let value = f32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]);
        dot += value * query[index];
        norm += value * value;
    }
    let query_norm: f32 = query.iter().map(|value| value * value).sum();
    if norm == 0.0 || query_norm == 0.0 {
        return None;
    }
    Some(dot / (norm.sqrt() * query_norm.sqrt()))
}
