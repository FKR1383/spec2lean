//! JSON views handed to the model.
//!
//! These deliberately reproduce the shapes the Python implementation emitted,
//! so prompts, transcripts, and downstream phases stay comparable across the
//! two implementations while the port is in progress.

use serde_json::{Value, json};
use spec2lean_specdb::{
    MAX_NODE_TEXT_CHARS, NodeRow, SpanRow, SpecDb, SpecDbError, truncate_chars,
};

/// The evidence-phase node summary: adds `sourceType` and `pageEnd` over the
/// planning summary, and optionally the exact text.
pub fn node_summary(row: &NodeRow, include_text: bool) -> Value {
    let mut value = json!({
        "nodeId": row.node_id,
        "nodeType": row.node_type,
        "title": row.title,
        "sectionNumber": row.section_number,
        "sourceType": row.source_type.as_str(),
        "htmlAnchor": row.html_anchor,
        "pageStart": row.page_start,
        "pageEnd": row.page_end,
    });
    if include_text {
        let (text, truncated) = truncate_chars(&row.raw_text, MAX_NODE_TEXT_CHARS);
        value["exactText"] = json!(text);
        value["textTruncated"] = json!(truncated);
    }
    value
}

/// The narrower planning summary, used by `spec_ancestors` and `spec_search`.
pub fn planning_summary(row: &NodeRow) -> Value {
    json!({
        "nodeId": row.node_id,
        "nodeType": row.node_type,
        "title": row.title,
        "sectionNumber": row.section_number,
        "htmlAnchor": row.html_anchor,
        "pageStart": row.page_start,
        "sourceType": row.source_type.as_str(),
    })
}

pub fn span_public(span: &SpanRow) -> Value {
    json!({
        "spanId": span.span_id,
        "ordinal": span.ordinal,
        "exactText": span.raw_text,
        "page": span.page_number,
        "bbox": span.bbox.map(|bbox| bbox.to_vec()),
        "blockIndex": span.block_index,
        "lineIndex": span.line_index,
        "spanIndex": span.span_index,
        "domPath": span.dom_path,
        "sourceLineStart": span.source_line_start,
        "sourceLineEnd": span.source_line_end,
    })
}

/// Full node detail: exact text, every span, and document provenance.
pub fn show(db: &SpecDb, row: &NodeRow) -> Result<Value, SpecDbError> {
    let spans = db.spans(&row.node_id)?;
    let mut value = node_summary(row, true);
    value["metadata"] = serde_json::from_str(&row.metadata_json).unwrap_or_else(|_| json!({}));
    value["sourceSpans"] = json!(spans.iter().map(span_public).collect::<Vec<_>>());
    value["document"] = json!({
        "documentId": row.document_id,
        "sha256": row.document_sha256,
        "localPath": row.document_local_path,
        "officialUrl": row.document_official_url,
    });
    Ok(value)
}
