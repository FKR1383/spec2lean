__version__ = "0.2.0"
PARSER_VERSION = "phase1-1"
INDEX_SCHEMA_VERSION = 1
PAGE_TEXT_FORMAT_VERSION = 1
PLAN_SCHEMA_VERSION = 1
PLANNER_AGENT = "spec2lean-planner"
PLANNER_MODEL_ID = "openai/gpt-5.3-codex-spark"
PLANNER_REASONING_EFFORT = "low"

NODE_TYPES = {
    "document",
    "chapter",
    "section",
    "subsection",
    "paragraph",
    "definition",
    "table",
    "code_block",
    "syntax_block",
    "list",
    "note",
    "example",
    "footnote",
    "caption",
    "generic",
}

HEADING_TYPES = {"chapter", "section", "subsection"}
REFERENCE_STATUSES = {"RESOLVED", "AMBIGUOUS", "UNRESOLVED"}

UNIT_KINDS = {
    "ARCHITECTURE",
    "STATE_MODEL",
    "TYPE_SYSTEM",
    "EXECUTION_MODEL",
    "OPERAND_MODEL",
    "MEMORY_MODEL",
    "ABI",
    "INSTRUCTION_FAMILY",
    "INSTRUCTION",
    "DIRECTIVE",
    "SPECIAL_REGISTER",
    "OTHER",
}

# Edges point from a prerequisite unit to a unit that depends on it.
DEPENDENCY_TYPES = {
    "USES_STATE_MODEL",
    "USES_TYPE_SYSTEM",
    "USES_EXECUTION_MODEL",
    "USES_OPERAND_MODEL",
    "USES_MEMORY_MODEL",
    "USES_INSTRUCTION",
    "REQUIRES",
}

DEPENDENCY_ORIGINS = {"EXPLICIT", "INFERRED"}
