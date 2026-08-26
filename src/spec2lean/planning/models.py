from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ScopeMode(StrEnum):
    EXACT_INSTRUCTIONS = "EXACT_INSTRUCTIONS"
    INSTRUCTION_FAMILY = "INSTRUCTION_FAMILY"
    SOURCE_SUBTREE = "SOURCE_SUBTREE"
    FULL_SPECIFICATION = "FULL_SPECIFICATION"


@dataclass(frozen=True, slots=True)
class PlanningRequest:
    language: str
    version: str
    mode: ScopeMode
    instructions: tuple[str, ...] = ()
    family: str | None = None
    source_node_id: str | None = None

    def __post_init__(self) -> None:
        if not self.language.strip() or not self.version.strip():
            raise ValueError("language and version must be non-empty")
        populated = sum(
            (
                bool(self.instructions),
                self.family is not None,
                self.source_node_id is not None,
                self.mode == ScopeMode.FULL_SPECIFICATION,
            )
        )
        if populated != 1:
            raise ValueError("a planning request must contain exactly one typed scope selector")
        if self.mode == ScopeMode.EXACT_INSTRUCTIONS:
            if not self.instructions or any(not item.strip() for item in self.instructions):
                raise ValueError("EXACT_INSTRUCTIONS requires at least one non-empty instruction")
            normalized = tuple(item.strip() for item in self.instructions)
            if len(set(normalized)) != len(normalized):
                raise ValueError("exact instruction requests cannot contain duplicates")
            object.__setattr__(self, "instructions", normalized)
        elif self.mode == ScopeMode.INSTRUCTION_FAMILY:
            if not self.family or not self.family.strip():
                raise ValueError("INSTRUCTION_FAMILY requires a non-empty family")
            object.__setattr__(self, "family", self.family.strip())
        elif self.mode == ScopeMode.SOURCE_SUBTREE:
            if not self.source_node_id or not self.source_node_id.startswith("node:"):
                raise ValueError("SOURCE_SUBTREE requires a node:<phase-1-node-id>")

    @classmethod
    def exact(cls, language: str, version: str, instructions: list[str]) -> PlanningRequest:
        return cls(language, version, ScopeMode.EXACT_INSTRUCTIONS, tuple(instructions))

    @classmethod
    def family_request(cls, language: str, version: str, family: str) -> PlanningRequest:
        return cls(language, version, ScopeMode.INSTRUCTION_FAMILY, family=family)

    @classmethod
    def subtree(cls, language: str, version: str, node_id: str) -> PlanningRequest:
        return cls(language, version, ScopeMode.SOURCE_SUBTREE, source_node_id=node_id)

    @classmethod
    def full(cls, language: str, version: str) -> PlanningRequest:
        return cls(language, version, ScopeMode.FULL_SPECIFICATION)

    def to_dict(self) -> dict[str, Any]:
        scope: dict[str, Any] = {"mode": self.mode.value}
        if self.mode == ScopeMode.EXACT_INSTRUCTIONS:
            scope["instructions"] = list(self.instructions)
        elif self.mode == ScopeMode.INSTRUCTION_FAMILY:
            scope["family"] = self.family
        elif self.mode == ScopeMode.SOURCE_SUBTREE:
            scope["sourceNodeId"] = self.source_node_id
        return {
            "schemaVersion": 1,
            "language": self.language,
            "version": self.version,
            "scope": scope,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PlanningRequest:
        scope = value.get("scope")
        if not isinstance(scope, dict):
            raise ValueError("request.scope must be an object")
        try:
            mode = ScopeMode(scope.get("mode"))
        except ValueError as exc:
            raise ValueError(f"unknown planning scope mode: {scope.get('mode')!r}") from exc
        return cls(
            language=str(value.get("language", "")),
            version=str(value.get("version", "")),
            mode=mode,
            instructions=tuple(scope.get("instructions", ())),
            family=scope.get("family"),
            source_node_id=scope.get("sourceNodeId"),
        )
