from __future__ import annotations

from pathlib import Path

import pytest

from spec2lean.database import build_database, connect
from spec2lean.parsers.html import parse_html


@pytest.fixture
def html_source() -> Path:
    return Path(__file__).parent / "fixtures" / "specification.html"


@pytest.fixture
def html_database(tmp_path: Path, html_source: Path) -> Path:
    target = tmp_path / "specification.sqlite"
    build_database(
        target,
        language="synthetic",
        version="1.0",
        documents=[parse_html(html_source, "https://example.test/spec")],
    )
    return target


@pytest.fixture
def planner_database(tmp_path: Path) -> Path:
    source = Path(__file__).parent / "fixtures" / "planner_specification.html"
    target = tmp_path / "planner.sqlite"
    build_database(
        target,
        language="synthetic",
        version="1.0",
        documents=[parse_html(source, "https://example.test/planner-spec")],
    )
    return target
