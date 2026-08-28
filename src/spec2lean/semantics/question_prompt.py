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
    return f"""You are the Spec2Lean Open Question Handler for one failed Phase-4 unit.

Resolve every supplied question and finish with open_questions_submit_questions. Work in this order:
1. For each question, search the canonical Phase-1 database first using a question-specific
   spec_search or spec_definitions call. Read promising nodes with spec_show/subtree.
2. If Phase 1 contains the missing rule, select DATABASE and cite newly discovered exact nodes.
   Do not re-select evidence already present in the bundle.
3. Only when the database check does not answer the question, you may use websearch/webfetch,
   the configured runtime probe, or your own explicit reasoning. Prefer authoritative internet
   sources over runtime observations, and runtime observations over unsupported reasoning.
4. INTERNET requires the exact URL and a short supporting excerpt. RUNTIME requires a probeId
   returned by execute_probe. LLM_REASONING is a non-normative assumption, never an official fact.
5. If no defensible answer exists, select UNRESOLVED. Never hide uncertainty merely to continue.
6. Assign the semantic evidence role that the answer supports. Give a concise answer and rationale.

All INTERNET, RUNTIME, and LLM_REASONING results are deterministically flagged non-normative and
must later become ASSUMPTION claims. Database selections remain canonical Phase-1 evidence.
{runtime_rule}

Deterministic question scope:
{json.dumps(scope.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)}

Current Phase-3 evidence bundle:
{json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True)}

Initial insufficient-evidence artifact:
{json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True)}
"""
