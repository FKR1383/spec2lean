use std::collections::{BTreeMap, BTreeSet};

use serde_json::{Value, json};
use spec2lean_specdb::{
    NodeId, NodeRow, SourceType, SpanId, SpanRow, SpecDb, SpecDbError, canonical_json,
    normalize_text, stable_id,
};

use crate::ledger::ExposureLedger;
use crate::model::{Diagnostic, DiagnosticCode as Code, Role, Tier};
use crate::render::span_public;
use crate::scope::EvidenceScope;

/// Both official renditions are required only when Phase 2 attached both to the
/// unit — never as a blanket rule.
pub fn required_official_renditions(
    db: &SpecDb,
    scope: &EvidenceScope,
) -> Result<BTreeSet<SourceType>, SpecDbError> {
    let mut present = BTreeSet::new();
    for node_id in scope.unit_source_node_ids() {
        if db.node_exists(&node_id)? {
            present.insert(db.node(&node_id)?.source_type);
        }
    }
    let both = BTreeSet::from([SourceType::Html, SourceType::Pdf]);
    Ok(if both.is_subset(&present) {
        both
    } else {
        BTreeSet::new()
    })
}

/// Grouped source nodes must be adjacent siblings of one document.
fn canonical_nodes(
    db: &SpecDb,
    node_ids: &[NodeId],
    path: &str,
    diagnostics: &mut Vec<Diagnostic>,
) -> Result<(Vec<NodeId>, Vec<NodeRow>), SpecDbError> {
    let mut rows = Vec::with_capacity(node_ids.len());
    for node_id in node_ids {
        rows.push(db.node(node_id)?);
    }
    if rows.len() <= 1 {
        return Ok((node_ids.to_vec(), rows));
    }
    let documents: BTreeSet<&String> = rows.iter().map(|row| &row.document_id).collect();
    let parents: BTreeSet<Option<&NodeId>> = rows.iter().map(|row| row.parent_id.as_ref()).collect();
    if documents.len() != 1 || parents.len() != 1 {
        diagnostics.push(Diagnostic::new(
            Code::NoncontiguousNodes,
            "a grouped evidence item must use adjacent sibling nodes from one document",
            path,
        ));
        return Ok((node_ids.to_vec(), rows));
    }
    rows.sort_by(|left, right| {
        (left.ordinal, left.node_id.as_str()).cmp(&(right.ordinal, right.node_id.as_str()))
    });
    let ordinals: Vec<i64> = rows.iter().map(|row| row.ordinal).collect();
    let contiguous = ordinals
        .iter()
        .enumerate()
        .all(|(index, ordinal)| *ordinal == ordinals[0] + index as i64);
    if !contiguous {
        diagnostics.push(Diagnostic::new(
            Code::NoncontiguousNodes,
            "grouped source nodes must be contiguous",
            path,
        ));
    }
    Ok((
        rows.iter().map(|row| row.node_id.clone()).collect(),
        rows,
    ))
}

/// Selected spans must exist, belong to the selected nodes, be contiguous
/// within each node, and cover every selected node.
fn span_rows(
    db: &SpecDb,
    node_ids: &[NodeId],
    span_ids: &[SpanId],
    path: &str,
    diagnostics: &mut Vec<Diagnostic>,
) -> Result<Vec<SpanRow>, SpecDbError> {
    if span_ids.is_empty() {
        return Ok(Vec::new());
    }
    let found = db.spans_by_id(span_ids)?;
    let known: BTreeSet<&SpanId> = found.iter().map(|row| &row.span_id).collect();
    for (index, span_id) in span_ids.iter().enumerate() {
        if !known.contains(span_id) {
            diagnostics.push(Diagnostic::new(
                Code::InventedSourceSpan,
                format!("source span does not exist: {span_id}"),
                format!("{path}[{index}]"),
            ));
        }
    }
    let allowed: BTreeSet<&NodeId> = node_ids.iter().collect();
    for row in &found {
        if !allowed.contains(&row.node_id) {
            diagnostics.push(Diagnostic::new(
                Code::SpanNodeMismatch,
                format!(
                    "span {} does not belong to the selected source nodes",
                    row.span_id
                ),
                path,
            ));
        }
    }
    let node_order: BTreeMap<&NodeId, usize> = node_ids
        .iter()
        .enumerate()
        .map(|(index, node_id)| (node_id, index))
        .collect();
    let mut ordered: Vec<SpanRow> = found
        .into_iter()
        .filter(|row| allowed.contains(&row.node_id))
        .collect();
    ordered.sort_by_key(|row| {
        (
            node_order.get(&row.node_id).copied().unwrap_or(usize::MAX),
            row.ordinal,
            row.span_id.as_str().to_string(),
        )
    });

    let mut by_node: BTreeMap<&NodeId, Vec<i64>> = BTreeMap::new();
    for row in &ordered {
        by_node.entry(&row.node_id).or_default().push(row.ordinal);
    }
    for (node_id, ordinals) in &by_node {
        let contiguous = ordinals
            .iter()
            .enumerate()
            .all(|(index, ordinal)| *ordinal == ordinals[0] + index as i64);
        if !contiguous {
            diagnostics.push(Diagnostic::new(
                Code::NoncontiguousSpans,
                format!("selected spans are not contiguous in {node_id}"),
                path,
            ));
        }
    }
    let missing: Vec<String> = node_ids
        .iter()
        .filter(|node_id| !by_node.contains_key(node_id))
        .map(NodeId::to_string)
        .collect();
    if !missing.is_empty() {
        diagnostics.push(Diagnostic::new(
            Code::SpanNodeCoverage,
            format!(
                "when sourceSpanIds are used, at least one span is required for every source node: {missing:?}"
            ),
            path,
        ));
    }
    Ok(ordered)
}

fn bbox(spans: &[SpanRow]) -> Option<[f64; 4]> {
    let boxes: Vec<[f64; 4]> = spans.iter().filter_map(|row| row.bbox).collect();
    let pages: BTreeSet<i64> = spans.iter().filter_map(|row| row.page_number).collect();
    if boxes.is_empty() || pages.len() != 1 {
        return None;
    }
    Some([
        boxes.iter().map(|b| b[0]).fold(f64::INFINITY, f64::min),
        boxes.iter().map(|b| b[1]).fold(f64::INFINITY, f64::min),
        boxes.iter().map(|b| b[2]).fold(f64::NEG_INFINITY, f64::max),
        boxes.iter().map(|b| b[3]).fold(f64::NEG_INFINITY, f64::max),
    ])
}

/// Join selected spans, inserting a newline at node boundaries and at line
/// breaks within a node. Public so Phase 6 can re-derive an evidence record's
/// exact text from the index and compare.
pub fn span_text(spans: &[SpanRow]) -> String {
    let mut pieces = String::new();
    let mut previous: Option<&SpanRow> = None;
    for row in spans {
        if let Some(previous) = previous {
            // A newline at every node boundary, and at every line break within
            // a node — the two cases the Python implementation spelled apart.
            let crossed_node = previous.node_id != row.node_id;
            let crossed_line =
                row.line_index.is_some() && row.line_index != previous.line_index;
            if crossed_node || crossed_line {
                pieces.push('\n');
            }
        }
        pieces.push_str(&row.raw_text);
        previous = Some(row);
    }
    pieces
}

fn fragment(db: &SpecDb, row: &NodeRow, selected: &[SpanRow]) -> Result<Value, SpecDbError> {
    let (section_number, section_title) = db.section(&row.node_id)?;
    let spans = if selected.is_empty() {
        db.spans(&row.node_id)?
    } else {
        selected.to_vec()
    };
    Ok(json!({
        "sourceNodeId": row.node_id,
        "nodeType": row.node_type,
        "sectionNumber": section_number,
        "sectionTitle": section_title,
        "htmlAnchor": if row.source_type == SourceType::Html {
            db.nearest_anchor(&row.node_id)?
        } else {
            None
        },
        "pageStart": row.page_start,
        "pageEnd": row.page_end,
        "sourceSpans": spans.iter().map(span_public).collect::<Vec<_>>(),
    }))
}

pub struct SelectionInput<'a> {
    pub node_ids: &'a [NodeId],
    pub span_ids: &'a [SpanId],
    pub role: Role,
    pub tier: Tier,
    pub rationale: &'a str,
}

/// Rebuild one evidence record entirely from Phase 1.
///
/// Nothing the model wrote reaches the record except the role, the tier, and
/// the rationale: exact text, spans, pages, anchors, hashes, and bounding boxes
/// are all reconstructed here.
pub fn build_evidence_record(
    db: &SpecDb,
    scope: &EvidenceScope,
    selection: &SelectionInput<'_>,
    selection_basis: &BTreeMap<NodeId, Vec<String>>,
) -> Result<Result<Value, Vec<Diagnostic>>, SpecDbError> {
    let mut diagnostics = Vec::new();
    let (node_ids, rows) = canonical_nodes(db, selection.node_ids, "$.sourceNodeIds", &mut diagnostics)?;
    let spans = span_rows(db, &node_ids, selection.span_ids, "$.sourceSpanIds", &mut diagnostics)?;
    if !diagnostics.is_empty() {
        return Ok(Err(diagnostics));
    }

    let mut spans_by_node: BTreeMap<&NodeId, Vec<SpanRow>> = BTreeMap::new();
    for span in &spans {
        spans_by_node
            .entry(&span.node_id)
            .or_default()
            .push(span.clone());
    }
    let mut fragments = Vec::with_capacity(rows.len());
    for row in &rows {
        let selected = spans_by_node
            .get(&row.node_id)
            .cloned()
            .unwrap_or_default();
        fragments.push(fragment(db, row, &selected)?);
    }

    let exact_text = if spans.is_empty() {
        rows.iter()
            .map(|row| row.raw_text.as_str())
            .collect::<Vec<_>>()
            .join("\n")
    } else {
        span_text(&spans)
    };

    let document = &rows[0];
    let provenance_spans = if spans.is_empty() {
        let mut all = Vec::new();
        for row in &rows {
            all.extend(db.spans(&row.node_id)?);
        }
        all
    } else {
        spans.clone()
    };

    let pages: BTreeSet<i64> = provenance_spans
        .iter()
        .filter_map(|row| row.page_number)
        .collect();
    let sections: BTreeSet<(Option<String>, Option<String>)> = fragments
        .iter()
        .map(|item| {
            (
                item["sectionNumber"].as_str().map(str::to_string),
                item["sectionTitle"].as_str().map(str::to_string),
            )
        })
        .collect();
    let anchors: BTreeSet<String> = fragments
        .iter()
        .filter_map(|item| item["htmlAnchor"].as_str().map(str::to_string))
        .collect();

    let identity = json!({
        "sourceDatabaseDigest": scope.source_database_digest,
        "sourceNodeIds": node_ids,
        "sourceSpanIds": spans.iter().map(|row| row.span_id.clone()).collect::<Vec<_>>(),
        "role": selection.role,
        "tier": selection.tier,
    });
    let (section_number, section_title) = if sections.len() == 1 {
        sections.into_iter().next().unwrap_or((None, None))
    } else {
        (None, None)
    };

    Ok(Ok(json!({
        "evidenceId": stable_id("evidence", &[&canonical_json(&identity)], 32),
        "unitId": scope.unit.get("unitId"),
        "role": selection.role,
        "tier": selection.tier,
        "rationale": normalize_text(selection.rationale),
        "sourceNodeId": node_ids[0],
        "sourceNodeIds": node_ids,
        "sourceSpanIds": spans.iter().map(|row| row.span_id.clone()).collect::<Vec<_>>(),
        "sourceType": document.source_type.as_str(),
        "sectionNumber": section_number,
        "sectionTitle": section_title,
        "exactText": exact_text,
        "documentId": document.document_id,
        "documentSha256": document.document_sha256,
        "sourcePath": document.document_local_path,
        "officialUrl": document.document_official_url,
        "htmlAnchor": if anchors.len() == 1 { anchors.into_iter().next() } else { None },
        "pdfPage": if pages.len() == 1 { pages.into_iter().next() } else { None },
        "bbox": bbox(&provenance_spans).map(|value| value.to_vec()),
        "selectionBasis": node_ids
            .iter()
            .map(|node_id| json!({
                "sourceNodeId": node_id,
                "basis": selection_basis.get(node_id).cloned().unwrap_or_default(),
            }))
            .collect::<Vec<_>>(),
        "provenance": fragments,
    })))
}

/// Whether two evidence records plausibly describe the same passage.
///
/// Phase 1 records HTML/PDF correlations; where it has none, an identical
/// section number is the next best structural evidence. Without either, "the
/// same passage in both renditions" is unverified, and the pairing rule would
/// be satisfied by any two unrelated passages carrying the same labels.
fn paired(db: &SpecDb, left: &Value, right: &Value) -> Result<bool, SpecDbError> {
    // A shared section number alone is too weak — a whole chapter carries one —
    // so the structural kind must match too: the same passage in two renditions
    // is a syntax block in both, or a note in both.
    let section = |item: &Value| item["sectionNumber"].as_str().map(str::to_string);
    let kind = |item: &Value| item["provenance"][0]["nodeType"].as_str().map(str::to_string);
    if let (Some(left_section), Some(right_section)) = (section(left), section(right))
        && left_section == right_section
        && kind(left).is_some()
        && kind(left) == kind(right)
    {
        return Ok(true);
    }
    let nodes = |item: &Value| -> Vec<NodeId> {
        item["sourceNodeIds"]
            .as_array()
            .map(Vec::as_slice)
            .unwrap_or_default()
            .iter()
            .filter_map(Value::as_str)
            .filter_map(|value| NodeId::parse(value).ok())
            .collect()
    };
    let right_nodes: BTreeSet<String> = nodes(right).iter().map(NodeId::to_string).collect();
    for node_id in nodes(left) {
        for correlation in db.correlated(&node_id)? {
            if right_nodes.contains(&correlation.other_node_id.to_string()) {
                return Ok(true);
            }
        }
    }
    Ok(false)
}

fn rendition_diagnostics(
    db: &SpecDb,
    records: &[Value],
    required: &BTreeSet<SourceType>,
    path: &str,
) -> Result<Vec<Diagnostic>, SpecDbError> {
    if required.is_empty() {
        return Ok(Vec::new());
    }
    let mut diagnostics = Vec::new();
    let present: BTreeSet<&str> = records
        .iter()
        .filter_map(|item| item["sourceType"].as_str())
        .collect();
    let missing: Vec<&str> = required
        .iter()
        .map(|value| value.as_str())
        .filter(|value| !present.contains(value))
        .collect();
    if !missing.is_empty() {
        diagnostics.push(Diagnostic::new(
            Code::MissingSourceRendition,
            format!(
                "this unit has official HTML and PDF sources; evidence is missing: {}",
                missing.join(", ")
            ),
            path,
        ));
    }
    // Keyed on the wire strings so ordering matches the Python `sorted()`.
    let mut grouped: BTreeMap<(&str, &str), Vec<&Value>> = BTreeMap::new();
    for item in records {
        let (Some(role), Some(tier), Some(source_type)) = (
            item["role"].as_str(),
            item["tier"].as_str(),
            item["sourceType"].as_str(),
        ) else {
            continue;
        };
        if required.iter().any(|value| value.as_str() == source_type) {
            grouped.entry((role, tier)).or_default().push(item);
        }
    }
    for ((role, tier), members) in grouped {
        let source_types: BTreeSet<&str> = members
            .iter()
            .filter_map(|item| item["sourceType"].as_str())
            .collect();
        let missing: Vec<&str> = required
            .iter()
            .map(|value| value.as_str())
            .filter(|value| !source_types.contains(value))
            .collect();
        if !missing.is_empty() {
            diagnostics.push(Diagnostic::new(
                Code::UnpairedSourceRendition,
                format!(
                    "{tier} {role} evidence must include corresponding HTML and PDF selections; missing: {}",
                    missing.join(", ")
                ),
                path,
            ));
            continue;
        }
        // Both renditions are present; they must actually correspond. The rule
        // says to use the matching passages, not to add an unrelated citation
        // to satisfy it.
        let html: Vec<&&Value> = members
            .iter()
            .filter(|item| item["sourceType"].as_str() == Some("html"))
            .collect();
        let pdf: Vec<&&Value> = members
            .iter()
            .filter(|item| item["sourceType"].as_str() == Some("pdf"))
            .collect();
        let mut any_pair = false;
        for left in &html {
            for right in &pdf {
                if paired(db, left, right)? {
                    any_pair = true;
                }
            }
        }
        if !any_pair {
            diagnostics.push(Diagnostic::new(
                Code::UnrelatedSourceRendition,
                format!(
                    "no {tier} {role} HTML selection corresponds to a PDF one; the renditions must \
                     be the same passage, related by section number or by an indexed correlation"
                ),
                path,
            ));
        }
    }
    Ok(diagnostics)
}

/// Validate a submission and, if it is clean, reconstruct the whole bundle.
///
/// Ported field-for-field from the Python validator: the diagnostic codes,
/// messages, paths, and ordering are the model's feedback channel, so changing
/// them silently would change retriever behaviour.
pub fn validate_submission(
    db: &SpecDb,
    scope: &EvidenceScope,
    ledger: &ExposureLedger,
    submission: &Value,
) -> Result<Result<Value, Vec<Diagnostic>>, SpecDbError> {
    let mut diagnostics: Vec<Diagnostic> = Vec::new();
    let Some(object) = submission.as_object() else {
        return Ok(Err(vec![Diagnostic::root(
            Code::ExpectedObject,
            "submission must be an object",
        )]));
    };
    let unit_id = scope.unit.get("unitId").and_then(Value::as_str).unwrap_or("");

    let mut unexpected: Vec<&String> = object
        .keys()
        .filter(|key| !matches!(key.as_str(), "unitId" | "selections"))
        .collect();
    unexpected.sort();
    for key in unexpected {
        diagnostics.push(Diagnostic::new(
            Code::UnexpectedField,
            format!("semantic or unsupported submission field is not allowed: {key}"),
            format!("$.{key}"),
        ));
    }
    if object.get("unitId").and_then(Value::as_str) != Some(unit_id) {
        diagnostics.push(Diagnostic::new(
            Code::WrongUnit,
            format!("submission unit must be {unit_id}"),
            "$.unitId",
        ));
    }
    let Some(raw_selections) = object.get("selections").and_then(Value::as_array) else {
        diagnostics.push(Diagnostic::new(
            Code::ExpectedArray,
            "$.selections must be an array",
            "$.selections",
        ));
        return Ok(Err(diagnostics));
    };
    if raw_selections.is_empty() {
        diagnostics.push(Diagnostic::new(
            Code::EmptyEvidence,
            "at least one evidence selection is required",
            "$.selections",
        ));
    }

    let mut records: Vec<Value> = Vec::new();
    let mut seen: BTreeSet<(Vec<String>, Vec<String>)> = BTreeSet::new();

    for (index, raw) in raw_selections.iter().enumerate() {
        let path = format!("$.selections[{index}]");
        let Some(selection) = raw.as_object() else {
            diagnostics.push(Diagnostic::new(
                Code::InvalidSelection,
                "selection must be an object",
                &path,
            ));
            continue;
        };
        let mut unexpected: Vec<&String> = selection
            .keys()
            .filter(|key| {
                !matches!(
                    key.as_str(),
                    "sourceNodeIds" | "sourceSpanIds" | "role" | "tier" | "rationale"
                )
            })
            .collect();
        unexpected.sort();
        for key in unexpected {
            diagnostics.push(Diagnostic::new(
                Code::UnexpectedField,
                format!("unsupported selection field: {key}"),
                format!("{path}.{key}"),
            ));
        }

        let Some(raw_nodes) = selection.get("sourceNodeIds").and_then(Value::as_array) else {
            diagnostics.push(Diagnostic::new(
                Code::InvalidSourceNodes,
                "sourceNodeIds must be a non-empty array",
                format!("{path}.sourceNodeIds"),
            ));
            continue;
        };
        if raw_nodes.is_empty() {
            diagnostics.push(Diagnostic::new(
                Code::InvalidSourceNodes,
                "sourceNodeIds must be a non-empty array",
                format!("{path}.sourceNodeIds"),
            ));
            continue;
        }
        if !raw_nodes.iter().all(Value::is_string) {
            diagnostics.push(Diagnostic::new(
                Code::InvalidSourceNode,
                "every source node ID must be a string",
                format!("{path}.sourceNodeIds"),
            ));
            continue;
        }
        let node_strings: Vec<&str> = raw_nodes.iter().filter_map(Value::as_str).collect();
        if node_strings.iter().collect::<BTreeSet<_>>().len() != node_strings.len() {
            diagnostics.push(Diagnostic::new(
                Code::DuplicateSourceNode,
                "sourceNodeIds contains a duplicate",
                format!("{path}.sourceNodeIds"),
            ));
        }

        let raw_spans = match selection.get("sourceSpanIds") {
            None => Vec::new(),
            Some(Value::Array(items)) if items.iter().all(Value::is_string) => items
                .iter()
                .filter_map(Value::as_str)
                .collect::<Vec<&str>>(),
            Some(_) => {
                diagnostics.push(Diagnostic::new(
                    Code::InvalidSourceSpans,
                    "sourceSpanIds must be an array of strings",
                    format!("{path}.sourceSpanIds"),
                ));
                continue;
            }
        };
        if raw_spans.iter().collect::<BTreeSet<_>>().len() != raw_spans.len() {
            diagnostics.push(Diagnostic::new(
                Code::DuplicateSourceSpan,
                "sourceSpanIds contains a duplicate",
                format!("{path}.sourceSpanIds"),
            ));
        }

        // A malformed identifier is reported with the same code as one that
        // simply does not exist: from the model's side both mean "you did not
        // get that from Phase 1".
        let mut node_ids = Vec::new();
        let mut invented = false;
        for raw in &node_strings {
            match NodeId::parse(raw) {
                Ok(node_id) if db.node_exists(&node_id)? => node_ids.push(node_id),
                _ => {
                    invented = true;
                    diagnostics.push(Diagnostic::new(
                        Code::InventedSourceNode,
                        format!("source node does not exist: {raw}"),
                        format!("{path}.sourceNodeIds"),
                    ));
                }
            }
        }
        for node_id in &node_ids {
            if !ledger.is_selectable(node_id) {
                diagnostics.push(Diagnostic::new(
                    Code::NodeNotExposed,
                    format!(
                        "source node was not exposed with exact text in this session: {node_id}"
                    ),
                    format!("{path}.sourceNodeIds"),
                ));
            } else if raw_spans.is_empty() && ledger.is_truncated(node_id) {
                // Selecting the whole node would put text into the bundle that
                // this session never saw, attributed as though it had.
                diagnostics.push(Diagnostic::new(
                    Code::NodeTextTruncated,
                    format!(
                        "only part of {node_id} was shown; name the spans you mean, or read it \
                         in full with spec_show first"
                    ),
                    format!("{path}.sourceNodeIds"),
                ));
            }
        }
        let mut span_ids = Vec::new();
        for raw in &raw_spans {
            match SpanId::parse(raw) {
                Ok(span_id) => {
                    if !ledger.is_span_exposed(&span_id) {
                        diagnostics.push(Diagnostic::new(
                            Code::SpanNotExposed,
                            format!("source span was not exposed in this session: {span_id}"),
                            format!("{path}.sourceSpanIds"),
                        ));
                    }
                    span_ids.push(span_id);
                }
                Err(_) => diagnostics.push(Diagnostic::new(
                    Code::InventedSourceSpan,
                    format!("source span does not exist: {raw}"),
                    format!("{path}.sourceSpanIds"),
                )),
            }
        }

        let role = selection
            .get("role")
            .and_then(|value| serde_json::from_value::<Role>(value.clone()).ok());
        if role.is_none() {
            diagnostics.push(Diagnostic::new(
                Code::InvalidRole,
                format!("invalid evidence role: {}", selection.get("role").unwrap_or(&Value::Null)),
                format!("{path}.role"),
            ));
        }
        let tier = selection
            .get("tier")
            .and_then(|value| serde_json::from_value::<Tier>(value.clone()).ok());
        if tier.is_none() {
            diagnostics.push(Diagnostic::new(
                Code::InvalidTier,
                format!("invalid evidence tier: {}", selection.get("tier").unwrap_or(&Value::Null)),
                format!("{path}.tier"),
            ));
        }
        let rationale = selection.get("rationale").and_then(Value::as_str);
        if rationale.is_none_or(|value| normalize_text(value).is_empty()) {
            diagnostics.push(Diagnostic::new(
                Code::EmptyRationale,
                "relevance rationale must be non-empty",
                format!("{path}.rationale"),
            ));
        }

        let (Some(role), Some(tier), Some(rationale)) = (role, tier, rationale) else {
            continue;
        };
        if invented {
            continue;
        }

        let mut local: Vec<Diagnostic> = Vec::new();
        let (canonical, _) = canonical_nodes(
            db,
            &node_ids,
            &format!("{path}.sourceNodeIds"),
            &mut local,
        )?;
        let spans = span_rows(
            db,
            &canonical,
            &span_ids,
            &format!("{path}.sourceSpanIds"),
            &mut local,
        )?;
        let had_local = !local.is_empty();
        diagnostics.append(&mut local);

        let key = (
            canonical.iter().map(NodeId::to_string).collect::<Vec<_>>(),
            spans
                .iter()
                .map(|row| row.span_id.to_string())
                .collect::<Vec<_>>(),
        );
        if !seen.insert(key) {
            diagnostics.push(Diagnostic::new(
                Code::DuplicateEvidence,
                "identical source evidence was selected more than once",
                &path,
            ));
            continue;
        }
        if had_local {
            continue;
        }

        let basis: BTreeMap<NodeId, Vec<String>> = canonical
            .iter()
            .map(|node_id| (node_id.clone(), ledger.basis(node_id)))
            .collect();
        let selected_span_ids: Vec<SpanId> =
            spans.iter().map(|row| row.span_id.clone()).collect();
        let input = SelectionInput {
            node_ids: &canonical,
            span_ids: &selected_span_ids,
            role,
            tier,
            rationale,
        };
        match build_evidence_record(db, scope, &input, &basis)? {
            Ok(record) => {
                if record["exactText"].as_str().unwrap_or_default().is_empty() {
                    diagnostics.push(Diagnostic::new(
                        Code::EmptyEvidenceText,
                        "selected evidence resolves to empty Phase-1 text",
                        &path,
                    ));
                } else {
                    records.push(record);
                }
            }
            Err(mut errors) => diagnostics.append(&mut errors),
        }
    }

    if !records.is_empty()
        && !records
            .iter()
            .any(|item| item["tier"].as_str() == Some(Tier::Core.as_str()))
    {
        diagnostics.push(Diagnostic::new(
            Code::MissingCoreEvidence,
            "a valid bundle requires at least one CORE item",
            "$.selections",
        ));
    }
    diagnostics.extend(rendition_diagnostics(
        db,
        &records,
        &required_official_renditions(db, scope)?,
        "$.selections",
    )?);
    let ids: Vec<&str> = records
        .iter()
        .filter_map(|item| item["evidenceId"].as_str())
        .collect();
    if ids.iter().collect::<BTreeSet<_>>().len() != ids.len() {
        diagnostics.push(Diagnostic::new(
            Code::DuplicateEvidenceId,
            "evidence IDs must be unique",
            "$.selections",
        ));
    }
    if !diagnostics.is_empty() {
        return Ok(Err(diagnostics));
    }

    records.sort_by(|left, right| {
        let key = |item: &Value| {
            (
                item["tier"].as_str().unwrap_or_default().to_string(),
                item["evidenceId"].as_str().unwrap_or_default().to_string(),
            )
        };
        // CORE before SUPPORTING, then by evidence ID.
        let (left_tier, left_id) = key(left);
        let (right_tier, right_id) = key(right);
        let rank = |tier: &str| if tier == Tier::Core.as_str() { 0 } else { 1 };
        (rank(&left_tier), left_id).cmp(&(rank(&right_tier), right_id))
    });

    Ok(Ok(json!({
        "schemaVersion": 1,
        "phase": "RETRIEVE_EVIDENCE",
        "planRunId": scope.plan_run_id,
        "language": scope.language,
        "version": scope.version,
        "sourceDatabaseDigest": scope.source_database_digest,
        "unit": scope.unit,
        "evidence": records,
    })))
}
