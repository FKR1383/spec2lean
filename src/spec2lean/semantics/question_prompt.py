from __future__ import annotations

import json
from typing import Any

from .questions import OpenQuestionScope


def build_open_question_prompt(
    scope: OpenQuestionScope,
    bundle: dict[str, Any],
    failure: dict[str, Any],
    *,
    runtime_available: bool,
) -> str:
    runtime_rule = (
        "A trusted execute_probe tool is configured and may be used for a concrete case after the database check."
        if runtime_available else
        "No runtime-probe adapter is configured; do not select RUNTIME."
    )
    official_types = {
        item.get("sourceType") for item in bundle.get("evidence", [])
        if isinstance(item, dict)
    } & {"html", "pdf"}
    dual_source_rule = (
        "This unit has official HTML and PDF renditions. For every DATABASE answer, use "
        "spec_correlated as needed, read both exact passages, and submit one as sourceNodeIds/"
        "sourceSpanIds and the other as counterpartSourceNodeIds/counterpartSourceSpanIds.\n"
        if official_types == {"html", "pdf"} else ""
    )
    return f"""You are the Spec2Lean Open Question Handler for one failed Phase-4 unit.

Resolve every supplied question and finish with open_questions_submit_questions. Work in this order:
1. Call open_questions_get_current_evidence once to read the immutable current bundle.
2. For each question, search the canonical Phase-1 database first using a question-specific
   spec_search or spec_definitions call. Read promising nodes with spec_show/subtree.
3. If Phase 1 contains the missing rule, select DATABASE and cite newly discovered exact nodes.
   Do not re-select evidence already present in the bundle.
4. Only when the database check does not answer the question, you may use websearch/webfetch,
   the configured runtime probe, or your own explicit reasoning. Prefer authoritative internet
   sources over runtime observations, and runtime observations over unsupported reasoning.
5. INTERNET requires the exact URL and a short supporting excerpt. RUNTIME requires a probeId
   returned by execute_probe. LLM_REASONING is a non-normative assumption, never an official fact.
6. When evidence does not determine an answer, decide a reasonable modeling assumption and select
   LLM_REASONING. Choose the simplest interpretation consistent with the known constraints and the
   current unit's scope. State the actual decision and why it is reasonable; "unknown" or a request
   for more evidence is not a decision. Do not contradict existing evidence or claim your choice is
   specified by an unavailable source.
7. If the specification permits several behaviors, choose an allowed behavior for this model. If
   choosing a concrete behavior would invent details outside the unit's scope, describe an explicit
   abstract input or dependency and its known constraints. This is a modeling choice, not a claim
   that the specification supplies those details. Preserve all behavior actually specified.
8. Resolve every question using evidence or a recorded assumption in this session. Do not submit
   UNRESOLVED just because evidence is unavailable. If submission diagnostics ask for a decision,
   correct the answer and resubmit within this session.
9. Assign the semantic role needed by the answer (including OPERATION or ALGORITHM when deciding
   core behavior). Give a concise answer and rationale so the Extractor can use the decision.

All INTERNET, RUNTIME, and LLM_REASONING results are deterministically flagged non-normative and
must later become ASSUMPTION claims. Database selections remain canonical Phase-1 evidence.
{dual_source_rule}
{runtime_rule}

Deterministic question scope:
{json.dumps(scope.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)}

The current Phase-3 evidence bundle is available only through
open_questions_get_current_evidence so it is not duplicated in this command-line prompt.

Initial insufficient-evidence artifact:
{json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True)}
"""
