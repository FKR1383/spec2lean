"""Generic, specification-scoped shared Lean core materialization."""

from .models import FrozenSharedCore, MissingSharedAbstraction, SharedRequirement
from .requirements import collect_shared_requirements, relevant_dependency_ids
from .runner import ensure_shared_core
from .store import load_core, load_current_core
from .validation import validate_core_artifact

__all__ = [
    "FrozenSharedCore",
    "MissingSharedAbstraction",
    "SharedRequirement",
    "collect_shared_requirements",
    "ensure_shared_core",
    "load_core",
    "load_current_core",
    "relevant_dependency_ids",
    "validate_core_artifact",
]
