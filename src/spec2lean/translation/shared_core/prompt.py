from __future__ import annotations

import json
from typing import Any

from ..models import DECLARATION_ROLES
from .models import SharedRequirement


def build_core_prompt(
    plan: dict[str, Any],
    requirements: tuple[SharedRequirement, ...],
    parent_manifest: dict[str, Any] | None,
) -> str:
    scope = {
        "language": plan["language"],
        "version": plan["version"],
        "sourceDatabaseDigest": plan["sourceDatabaseDigest"],
        "dependencyIds": [item.dependency_id for item in requirements],
        "parentCoreRunId": (parent_manifest or {}).get("coreRunId"),
        "leanNamespace": (parent_manifest or {}).get("leanNamespace"),
    }
    declaration_roles = ", ".join(DECLARATION_ROLES)
    return f"""You are the generic Spec2Lean Phase-5 Shared-Core Materializer.

Choose one clear, composable Lean 4 representation for every supplied shared semantic dependency.
The mechanism is specification-independent: do not assume any particular language, instruction set,
execution model, concept name, or globally preferred Lean representation.

First call shared_core_get_context exactly once. It contains the authoritative shared requirements,
their Phase-4 claims, and any accepted parent core. Then call shared_core_submit_core with one complete
candidate.

Rules:
- Phase-4 semantic requirements decide what concepts mean; you decide only how this specification's
  current shared concepts are represented in Lean.
- Keep the core minimal. Include shared declarations and genuinely common infrastructure only. Do not
  move unit-specific behavior into the core.
- Record every concept by its supplied dependencyId and the exact public/supporting Lean declarations
  that implement it. Do not invent dependency IDs or semantic claim IDs.
- Map every named Lean declaration using one of these roles: {declaration_roles}. Semantic
  declarations cite only the supplied claimRefs that the declaration itself implements. Never copy
  every claim of a shared concept onto every declaration merely to satisfy coverage. A purely Lean
  IMPLEMENTATION_HELPER may instead support a mapped semantic declaration through
  supportsDeclarations, preserving the exact helper-to-declaration-to-claim chain.
- If a parent exists, return source beginning with the complete parent source byte-for-byte and append
  only new definitions. Preserve every existing concept/declaration mapping exactly; add each missing
  abstraction once. Put every appended declaration below the exact leanNamespace supplied in the
  context. New root cores are placed in their isolated namespace deterministically after submission.
- Prefer interfaces that permit consistent pure unit semantics and shared evaluation/execution
  infrastructure when the supplied semantics support that boundary. Do not force it otherwise.
- Keep representations compact and internally coherent. Derive classifications and boundary flags from
  their authoritative values instead of accepting contradictory parallel parameters. When several
  operations share execution context, prefer one small typed context over long unrelated parameter lists.
- Do not turn source statements into unconstrained Prop parameters and then merely conjoin them unless
  the accepted semantics genuinely expose those propositions as inputs to a relational model.
- Use readable Lean 4 with no sorry, admit, axioms, constants, unsafe, or partial declarations.
- Use only the two shared_core tools. If submission diagnostics reject the candidate, correct it in
  this same bounded session.

Deterministic scope (do not reproduce it as metadata):
{json.dumps(scope, ensure_ascii=False, indent=2, sort_keys=True)}
"""
