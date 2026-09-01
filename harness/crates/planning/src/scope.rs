use std::collections::{BTreeMap, BTreeSet};
use std::sync::LazyLock;

use regex::Regex;
use serde_json::{Value, json};
use spec2lean_specdb::{NodeId, NodeRow, SourceType, SpecDb, SpecDbError, normalize_text, stable_id};

use crate::request::{PlanningRequest, Selector};

pub const MAX_FAMILY_CANDIDATES: usize = 200;

#[derive(Debug)]
pub enum ScopeError {
    Db(SpecDbError),
    Identity(String),
    Unresolvable(String),
    TooBroad(String),
}

impl std::fmt::Display for ScopeError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Db(error) => write!(f, "{error}"),
            Self::Identity(detail) | Self::Unresolvable(detail) | Self::TooBroad(detail) => {
                f.write_str(detail)
            }
        }
    }
}

impl std::error::Error for ScopeError {}

impl From<SpecDbError> for ScopeError {
    fn from(error: SpecDbError) -> Self {
        Self::Db(error)
    }
}

static MNEMONIC: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"[@A-Za-z_{}][@A-Za-z0-9_.{}]*").expect("valid"));
static SUFFIX_TERM: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\{\.[A-Za-z0-9_]+\}|\.[A-Za-z0-9_]+").expect("valid"));
static ALTERNATIVES: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\.([A-Za-z][A-Za-z0-9_]*)\s*=\s*\{([^}]*)\}").expect("valid")
});
static WORD: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[a-z0-9]+").expect("valid"));
static ALTERNATIVE_ITEM: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\.[A-Za-z0-9_]+").expect("valid"));

/// Mnemonics named by a heading title, lower-cased.
///
/// Specification headings are commonly `Integer Arithmetic Instructions: add`,
/// so the part after the last colon is what names the instruction.
pub fn title_mnemonics(title: Option<&str>) -> Vec<String> {
    let Some(title) = title else {
        return Vec::new();
    };
    let tail = match title.rsplit_once(':') {
        Some((_, tail)) => tail.trim(),
        None => title.trim(),
    };
    MNEMONIC
        .find_iter(tail)
        .map(|found| found.as_str().to_lowercase())
        .collect()
}

/// Whether a syntax block accepts an exact spelling such as `add.sat.s32`.
///
/// Specifications write syntax as a form plus finite alternatives, e.g.
/// `add{.sat}.type` with `.type = {.u32, .s32}`. Deciding membership means
/// expanding the form; a substring test would match spellings the
/// specification never defines.
pub fn syntax_accepts(instruction: &str, mnemonic: &str, syntax_text: &str) -> bool {
    let mut definitions: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for capture in ALTERNATIVES.captures_iter(syntax_text) {
        let name = capture[1].to_lowercase();
        let choices: Vec<String> = ALTERNATIVE_ITEM
            .find_iter(&capture[2])
            .map(|found| found.as_str().to_lowercase())
            .collect();
        definitions.insert(name, choices);
    }
    let pattern = match Regex::new(&format!(
        r"(?i)(?:^|[^A-Za-z0-9_.]){}((?:(?:\{{\.[A-Za-z0-9_]+\}})|(?:\.[A-Za-z0-9_]+))+)",
        regex::escape(mnemonic)
    )) {
        Ok(pattern) => pattern,
        Err(_) => return false,
    };
    let wanted = instruction.to_lowercase();
    for capture in pattern.captures_iter(syntax_text) {
        let mut expansions = vec![mnemonic.to_lowercase()];
        for term in SUFFIX_TERM.find_iter(&capture[1]) {
            let term = term.as_str();
            let optional = term.starts_with('{');
            let name = term.trim_matches(['{', '}'])[1..].to_lowercase();
            let mut choices = definitions
                .get(&name)
                .cloned()
                .unwrap_or_else(|| vec![format!(".{name}")]);
            choices.sort();
            if optional {
                choices.insert(0, String::new());
            }
            expansions = expansions
                .iter()
                .flat_map(|prefix| {
                    choices
                        .iter()
                        .map(move |choice| format!("{prefix}{choice}"))
                })
                .collect();
        }
        if expansions.contains(&wanted) {
            return true;
        }
    }
    false
}

/// Sort key that orders `1.10` after `1.9` rather than lexically.
fn section_order(section: Option<&str>) -> (u8, Vec<i64>, String) {
    match section {
        Some(section) if section.split('.').all(|part| part.chars().all(|c| c.is_ascii_digit()) && !part.is_empty()) => (
            0,
            section.split('.').filter_map(|part| part.parse().ok()).collect(),
            String::new(),
        ),
        other => (1, Vec::new(), other.unwrap_or_default().to_string()),
    }
}

/// A planning unit: a name and the Phase-1 nodes that define it.
pub fn unit(name: &str, node_ids: &[NodeId]) -> Value {
    let mut sources: Vec<String> = node_ids.iter().map(NodeId::to_string).collect();
    sources.sort();
    sources.dedup();
    let mut parts: Vec<&str> = vec![];
    let folded = name.to_lowercase();
    parts.push(&folded);
    parts.extend(sources.iter().map(String::as_str));
    json!({
        "unitId": stable_id("unit", &parts, 24),
        "name": name,
        "sourceNodeIds": sources,
    })
}

/// The deterministic result of resolving a request against the index.
#[derive(Debug, Clone)]
pub struct ResolvedScope {
    pub request: PlanningRequest,
    pub candidate_units: Vec<Value>,
    pub context_node_ids: Vec<String>,
    pub root_node_ids: Vec<String>,
    /// Units the model must preserve exactly, for modes where the request
    /// named them. Empty when the model may select a subset.
    pub exact_unit_ids: Vec<String>,
}

impl ResolvedScope {
    pub fn candidate_by_id(&self) -> BTreeMap<&str, &Value> {
        self.candidate_units
            .iter()
            .filter_map(|unit| Some((unit.get("unitId")?.as_str()?, unit)))
            .collect()
    }

    pub fn to_json(&self) -> Value {
        json!({
            "schemaVersion": 1,
            "request": self.request.to_json(),
            "candidateUnits": self.candidate_units,
            "contextNodeIds": self.context_node_ids,
            "rootNodeIds": self.root_node_ids,
            "exactUnitIds": self.exact_unit_ids,
        })
    }
}

pub struct ScopeResolver<'a> {
    db: &'a SpecDb,
}

impl<'a> ScopeResolver<'a> {
    pub fn new(db: &'a SpecDb) -> Self {
        Self { db }
    }

    pub fn resolve(&self, request: &PlanningRequest) -> Result<ResolvedScope, ScopeError> {
        // A plan built against the wrong specification is meaningless, and
        // every node ID in it would point somewhere unrelated.
        let (language, version) = self.db.specification()?;
        if !language.eq_ignore_ascii_case(&request.language) || version != request.version {
            return Err(ScopeError::Identity(format!(
                "database contains {language} {version}, not {} {}",
                request.language, request.version
            )));
        }
        match &request.selector {
            Selector::ExactInstructions(instructions) => self.exact(request, instructions),
            Selector::InstructionFamily(family) => self.family(request, family),
            Selector::SourceSubtree(node_id) => self.subtree(request, node_id),
            Selector::FullSpecification => self.full(request),
        }
    }

    fn exact(
        &self,
        request: &PlanningRequest,
        instructions: &[String],
    ) -> Result<ResolvedScope, ScopeError> {
        let mut units = Vec::new();
        let mut roots: Vec<NodeId> = Vec::new();
        for instruction in instructions {
            let node_ids = self.exact_instruction_nodes(instruction)?;
            if node_ids.is_empty() {
                return Err(ScopeError::Unresolvable(format!(
                    "exact instruction could not be resolved: {instruction}"
                )));
            }
            units.push(unit(instruction, &node_ids));
            roots.extend(node_ids);
        }
        let exact_ids = units
            .iter()
            .filter_map(|item| item.get("unitId")?.as_str().map(str::to_string))
            .collect();
        let mut unique_roots: Vec<String> = Vec::new();
        for node_id in &roots {
            let value = node_id.to_string();
            if !unique_roots.contains(&value) {
                unique_roots.push(value);
            }
        }
        Ok(ResolvedScope {
            request: request.clone(),
            context_node_ids: self.context_nodes(&roots)?,
            candidate_units: units,
            root_node_ids: unique_roots,
            exact_unit_ids: exact_ids,
        })
    }

    /// Headings whose subtree actually defines the requested spelling.
    fn exact_instruction_nodes(&self, instruction: &str) -> Result<Vec<NodeId>, ScopeError> {
        let wanted = instruction.to_lowercase();
        let mut matches: Vec<(usize, String, NodeRow)> = Vec::new();
        for row in self.db.headings()? {
            for mnemonic in title_mnemonics(row.title.as_deref()) {
                if wanted == mnemonic || wanted.starts_with(&format!("{mnemonic}.")) {
                    matches.push((mnemonic.len(), mnemonic, row.clone()));
                }
            }
        }
        if matches.is_empty() {
            return Ok(Vec::new());
        }
        // Prefer the longest mnemonic: `add.cc` beats `add` for `add.cc.u32`.
        let longest = matches.iter().map(|(length, _, _)| *length).max().unwrap_or(0);
        let headings: Vec<(String, NodeRow)> = matches
            .into_iter()
            .filter(|(length, _, _)| *length == longest)
            .map(|(_, mnemonic, row)| (mnemonic, row))
            .collect();

        let literal = Regex::new(&format!(
            r"(?i)(?:^|[^A-Za-z0-9_.]){}(?:[^A-Za-z0-9_.]|$)",
            regex::escape(instruction)
        ))
        .map_err(|error| ScopeError::Unresolvable(error.to_string()))?;

        let mut confirmed: Vec<NodeRow> = Vec::new();
        for (mnemonic, row) in headings {
            let descendants = self.db.descendant_texts(&row.node_id)?;
            let spelled_out = descendants
                .iter()
                .any(|(_, text)| literal.is_match(text));
            let by_syntax = descendants
                .iter()
                .any(|(node_type, _)| node_type == "syntax_block")
                && syntax_accepts(
                    instruction,
                    &mnemonic,
                    &descendants
                        .iter()
                        .map(|(_, text)| text.as_str())
                        .collect::<Vec<_>>()
                        .join("\n"),
                );
            if spelled_out || by_syntax {
                confirmed.push(row);
            }
        }
        if confirmed.is_empty() {
            return Ok(Vec::new());
        }
        // Keep the most specific logical section, and every rendition of it.
        let deepest = confirmed
            .iter()
            .map(|row| row.depth)
            .max()
            .unwrap_or_default();
        confirmed.retain(|row| row.depth == deepest);
        let best_section = confirmed[0].section_number.clone();
        let best_tail = title_mnemonics(confirmed[0].title.as_deref());
        let mut selected: Vec<NodeId> = confirmed
            .iter()
            .filter(|row| {
                row.section_number == best_section
                    && title_mnemonics(row.title.as_deref()) == best_tail
            })
            .map(|row| row.node_id.clone())
            .collect();
        selected.sort();
        selected.dedup();
        Ok(selected)
    }

    fn family(&self, request: &PlanningRequest, family: &str) -> Result<ResolvedScope, ScopeError> {
        let roots = self.family_roots(family)?;
        if roots.is_empty() {
            return Err(ScopeError::Unresolvable(format!(
                "instruction family could not be resolved: {family}"
            )));
        }
        let mut units = self.child_units(&roots)?;
        if units.is_empty() {
            units = vec![unit(family, &roots)];
        }
        if units.len() > MAX_FAMILY_CANDIDATES {
            return Err(ScopeError::TooBroad(format!(
                "family scope produced {} candidates; maximum is {MAX_FAMILY_CANDIDATES}",
                units.len()
            )));
        }
        let sources = unit_sources(&units);
        Ok(ResolvedScope {
            request: request.clone(),
            context_node_ids: self.context_nodes(&sources)?,
            candidate_units: units,
            root_node_ids: roots.iter().map(NodeId::to_string).collect(),
            // A family request names a region, not a unit list: the planner may
            // legitimately select a subset of the candidates.
            exact_unit_ids: Vec::new(),
        })
    }

    fn family_roots(&self, family: &str) -> Result<Vec<NodeId>, ScopeError> {
        let wanted = normalize_text(family).to_lowercase();
        let significant: Vec<String> = WORD
            .find_iter(&wanted)
            .map(|found| found.as_str().to_string())
            .filter(|word| !matches!(word.as_str(), "the" | "a" | "an"))
            .collect();
        let mut scored: Vec<(i64, NodeRow)> = Vec::new();
        for row in self.db.headings()? {
            let Some(title) = row.title.as_deref() else {
                continue;
            };
            let title = normalize_text(title).to_lowercase();
            if !significant.iter().all(|word| title.contains(word.as_str())) {
                continue;
            }
            let score = if title == wanted { 1000 } else { 0 } + significant.len() as i64 * 10
                - (title.len() as i64 - wanted.len() as i64).abs();
            scored.push((score, row));
        }
        if scored.is_empty() {
            return Ok(Vec::new());
        }
        let best = scored.iter().map(|(score, _)| *score).max().unwrap_or(0);
        let winner = scored
            .iter()
            .find(|(score, _)| *score == best)
            .map(|(_, row)| row)
            .expect("a best exists");
        let key = (
            winner.section_number.clone(),
            winner
                .title
                .as_deref()
                .map(|title| normalize_text(title).to_lowercase()),
        );
        // Every rendition of the winning section, not just the first.
        let mut roots: Vec<NodeId> = scored
            .iter()
            .filter(|(_, row)| {
                (
                    row.section_number.clone(),
                    row.title
                        .as_deref()
                        .map(|title| normalize_text(title).to_lowercase()),
                ) == key
            })
            .map(|(_, row)| row.node_id.clone())
            .collect();
        roots.sort();
        roots.dedup();
        Ok(roots)
    }

    fn subtree(
        &self,
        request: &PlanningRequest,
        node_id: &NodeId,
    ) -> Result<ResolvedScope, ScopeError> {
        if !self.db.node_exists(node_id)? {
            return Err(ScopeError::Unresolvable(format!(
                "source subtree node does not exist: {node_id}"
            )));
        }
        let roots = self.correlated_nodes(node_id)?;
        let mut units = self.child_units(&roots)?;
        if units.is_empty() {
            let row = self.db.node(node_id)?;
            let name = row.title.clone().unwrap_or_else(|| node_id.to_string());
            units = vec![unit(&name, &roots)];
        }
        let sources = unit_sources(&units);
        let exact_ids = units
            .iter()
            .filter_map(|item| item.get("unitId")?.as_str().map(str::to_string))
            .collect();
        Ok(ResolvedScope {
            request: request.clone(),
            context_node_ids: self.context_nodes(&sources)?,
            candidate_units: units,
            root_node_ids: roots.iter().map(NodeId::to_string).collect(),
            exact_unit_ids: exact_ids,
        })
    }

    fn full(&self, request: &PlanningRequest) -> Result<ResolvedScope, ScopeError> {
        let roots = self.db.root_nodes()?;
        let mut units = self.child_units(&roots)?;
        if units.is_empty() {
            units = vec![unit("full specification", &roots)];
        }
        let sources = unit_sources(&units);
        let exact_ids = units
            .iter()
            .filter_map(|item| item.get("unitId")?.as_str().map(str::to_string))
            .collect();
        Ok(ResolvedScope {
            request: request.clone(),
            context_node_ids: self.context_nodes(&sources)?,
            candidate_units: units,
            root_node_ids: roots.iter().map(NodeId::to_string).collect(),
            exact_unit_ids: exact_ids,
        })
    }

    /// One candidate unit per heading child, merging the HTML and PDF
    /// renditions of the same logical section into a single unit.
    fn child_units(&self, roots: &[NodeId]) -> Result<Vec<Value>, ScopeError> {
        let mut rows: Vec<NodeRow> = Vec::new();
        for root in roots {
            rows.extend(self.db.heading_children(root)?);
        }
        let mut grouped: BTreeMap<(Option<String>, String), Vec<NodeRow>> = BTreeMap::new();
        for row in rows {
            let label = row
                .title
                .clone()
                .unwrap_or_else(|| row.node_id.to_string());
            let key = (row.section_number.clone(), normalize_text(&label).to_lowercase());
            grouped.entry(key).or_default().push(row);
        }
        let mut keys: Vec<&(Option<String>, String)> = grouped.keys().collect();
        keys.sort_by(|left, right| {
            (section_order(left.0.as_deref()), &left.1)
                .cmp(&(section_order(right.0.as_deref()), &right.1))
        });
        let mut units = Vec::new();
        for key in keys {
            let group = &grouped[key];
            let title = group[0]
                .title
                .clone()
                .unwrap_or_else(|| group[0].node_id.to_string());
            let names = title_mnemonics(Some(&title));
            // `Integer Arithmetic: add, sub` names two mnemonics; a plain
            // heading names itself.
            let name = if title.contains(':') && !names.is_empty() {
                names.join(", ")
            } else {
                title
            };
            let node_ids: Vec<NodeId> = group.iter().map(|row| row.node_id.clone()).collect();
            units.push(unit(&name, &node_ids));
        }
        Ok(units)
    }

    fn correlated_nodes(&self, node_id: &NodeId) -> Result<Vec<NodeId>, ScopeError> {
        let mut related: BTreeSet<NodeId> = BTreeSet::from([node_id.clone()]);
        for row in self.db.correlated(node_id)? {
            related.insert(row.other_node_id);
        }
        Ok(related.into_iter().collect())
    }

    /// Nodes the planner is allowed to treat as already-known context: the
    /// units' own nodes, their ancestry, explicit cross-references, and
    /// correlated renditions.
    fn context_nodes(&self, roots: &[NodeId]) -> Result<Vec<String>, ScopeError> {
        let mut result: BTreeSet<String> = BTreeSet::new();
        for node_id in roots {
            result.insert(node_id.to_string());
            for row in self.db.ancestors(node_id, 30)? {
                result.insert(row.node_id.to_string());
            }
            for row in self.db.xrefs(node_id)? {
                result.insert(row.source_node_id.to_string());
                if let Some(target) = row.resolved_target_node_id {
                    result.insert(target.to_string());
                }
            }
            for related in self.correlated_nodes(node_id)? {
                result.insert(related.to_string());
            }
        }
        Ok(result.into_iter().collect())
    }
}

fn unit_sources(units: &[Value]) -> Vec<NodeId> {
    units
        .iter()
        .filter_map(|unit| unit.get("sourceNodeIds")?.as_array())
        .flatten()
        .filter_map(Value::as_str)
        .filter_map(|value| NodeId::parse(value).ok())
        .collect()
}

/// Renditions are compared by source type in a few places.
pub fn is_html(row: &NodeRow) -> bool {
    row.source_type == SourceType::Html
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mnemonics_come_from_the_part_after_the_last_colon() {
        assert_eq!(
            title_mnemonics(Some("Integer Arithmetic Instructions: add")),
            vec!["add".to_string()]
        );
        assert_eq!(
            title_mnemonics(Some("Instructions: add, sub")),
            vec!["add".to_string(), "sub".to_string()]
        );
        assert_eq!(title_mnemonics(Some("Introduction")), vec!["introduction"]);
        assert!(title_mnemonics(None).is_empty());
    }

    #[test]
    fn syntax_forms_expand_their_finite_alternatives() {
        let syntax = "add{.sat}.type d, a, b;\n.type = { .u32, .s32 }\n";
        // Spelled out by expansion, not by substring.
        assert!(syntax_accepts("add.u32", "add", syntax));
        assert!(syntax_accepts("add.sat.s32", "add", syntax));
        // The bare mnemonic is not itself a legal spelling of the form.
        assert!(!syntax_accepts("add", "add", syntax));
        // A type the specification never lists.
        assert!(!syntax_accepts("add.f64", "add", syntax));
        // A different mnemonic entirely.
        assert!(!syntax_accepts("sub.u32", "add", syntax));
    }

    #[test]
    fn section_numbers_sort_numerically_not_lexically() {
        let mut sections = vec![Some("1.10"), Some("1.9"), Some("2"), None, Some("A.1")];
        sections.sort_by_key(|value| section_order(*value));
        assert_eq!(sections, vec![Some("1.9"), Some("1.10"), Some("2"), None, Some("A.1")]);
    }

    #[test]
    fn unit_ids_are_stable_and_independent_of_node_order() {
        let a = NodeId::parse("node:a").unwrap();
        let b = NodeId::parse("node:b").unwrap();
        let first = unit("add", &[a.clone(), b.clone()]);
        let second = unit("add", &[b, a]);
        assert_eq!(first, second);
        assert!(first["unitId"].as_str().unwrap().starts_with("unit:"));
    }
}
