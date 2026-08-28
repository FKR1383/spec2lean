from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..util import canonical_json, normalize_text, stable_id
from .models import evidence_bundle_hash


QUESTION_SCHEMA_VERSION = 1
QUESTION_MODEL = "openai/gpt-5.6-sol"
QUESTION_REASONING = "medium"
QUESTION_AGENT = "spec2lean-open-question-handler"
QUESTION_SOURCES = ("DATABASE", "INTERNET", "RUNTIME", "LLM_REASONING", "UNRESOLVED")


@dataclass(frozen=True, slots=True)
class OpenQuestionScope:
    plan_run_id: str
    language: str
    version: str
    source_database_digest: str
    unit: dict[str, Any]
    evidence_bundle_hash: str
    semantic_run_id: str
    questions: tuple[dict[str, str], ...]
    run_id: str
    created_at: str

    @classmethod
    def from_inputs(
        cls,
        plan: dict[str, Any],
        bundle: dict[str, Any],
        failure: dict[str, Any],
        *,
        created_at: str,
    ) -> OpenQuestionScope:
        if failure.get("outcome") != "INSUFFICIENT_EVIDENCE":
            raise ValueError("open-question handling requires an INSUFFICIENT_EVIDENCE artifact")
        if failure.get("planRunId") != plan.get("planRunId"):
            raise ValueError("semantic failure does not match the Phase-2 plan")
        if failure.get("unit") != bundle.get("unit"):
            raise ValueError("semantic failure does not match the Phase-3 evidence unit")
        current_hash = evidence_bundle_hash(bundle)
        if failure.get("evidenceBundleHash") != current_hash:
            raise ValueError("semantic failure does not reference the current evidence bundle")
        aspects = (failure.get("failure") or {}).get("missingAspects")
        if not isinstance(aspects, list) or not aspects:
            raise ValueError("semantic failure has no missing aspects")
        normalized = [normalize_text(item) for item in aspects if isinstance(item, str)]
        if len(normalized) != len(aspects) or any(not item for item in normalized):
            raise ValueError("semantic failure contains an invalid missing aspect")
        if len(set(normalized)) != len(normalized):
            raise ValueError("semantic failure contains duplicate missing aspects")
        unit = dict(bundle["unit"])
        questions = tuple(
            {
                "questionId": stable_id("question", unit["unitId"], aspect, length=32),
                "aspect": aspect,
            }
            for aspect in normalized
        )
        run_id = stable_id(
            "question-run",
            plan["planRunId"],
            unit["unitId"],
            failure["runId"],
            current_hash,
            canonical_json(questions),
        )
        return cls(
            plan_run_id=str(plan["planRunId"]),
            language=str(plan["language"]),
            version=str(plan["version"]),
            source_database_digest=str(plan["sourceDatabaseDigest"]),
            unit=unit,
            evidence_bundle_hash=current_hash,
            semantic_run_id=str(failure["runId"]),
            questions=questions,
            run_id=run_id,
            created_at=created_at,
        )

    @property
    def unit_id(self) -> str:
        return str(self.unit["unitId"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": QUESTION_SCHEMA_VERSION,
            "planRunId": self.plan_run_id,
            "language": self.language,
            "version": self.version,
            "sourceDatabaseDigest": self.source_database_digest,
            "unit": dict(self.unit),
            "evidenceBundleHash": self.evidence_bundle_hash,
            "semanticRunId": self.semantic_run_id,
            "questions": [dict(item) for item in self.questions],
            "runId": self.run_id,
            "createdAt": self.created_at,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> OpenQuestionScope:
        return cls(
            plan_run_id=value["planRunId"],
            language=value["language"],
            version=value["version"],
            source_database_digest=value["sourceDatabaseDigest"],
            unit=dict(value["unit"]),
            evidence_bundle_hash=value["evidenceBundleHash"],
            semantic_run_id=value["semanticRunId"],
            questions=tuple(dict(item) for item in value["questions"]),
            run_id=value["runId"],
            created_at=value["createdAt"],
        )


def resolution_record(
    scope: OpenQuestionScope,
    *,
    question_id: str,
    source_kind: str,
    role: str,
    statement: str,
    rationale: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    normalized_statement = normalize_text(statement)
    normalized_rationale = normalize_text(rationale)
    identity = {
        "questionId": question_id,
        "sourceKind": source_kind,
        "role": role,
        "statement": normalized_statement,
        "rationale": normalized_rationale,
        "provenance": provenance,
    }
    return {
        "resolutionId": stable_id("resolution", canonical_json(identity), length=32),
        "unitId": scope.unit_id,
        "questionId": question_id,
        "sourceKind": source_kind,
        "role": role,
        "statement": normalized_statement,
        "rationale": normalized_rationale,
        "nonNormative": True,
        "provenance": provenance,
    }
