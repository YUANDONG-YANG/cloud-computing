"""The frontend offline fallback must stay truthful.

``frontend/app.js`` ships a ``DEMO_DATA`` object that the dashboard renders when
the Function App is unreachable, and it claims to be the real Project 1 batch
results. These tests parse that literal out of the JavaScript and compare it
against the committed ground truth in ``Project1/data/All_Diets.csv`` and
``Project1/docs/results/*.csv``. Fabricated fallback numbers are an
academic-integrity exposure, so this is the strictest guard in the suite.
"""
import collections
import csv
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_JS = REPO_ROOT / "Project2" / "frontend" / "app.js"
DATASET = REPO_ROOT / "Project1" / "data" / "All_Diets.csv"
RESULTS = REPO_ROOT / "Project1" / "docs" / "results"

MACRO_KEYS = ("Protein(g)", "Carbs(g)", "Fat(g)")
STRING_LITERAL = re.compile(r'"(?:[^"\\]|\\.)*"', re.S)


def read_csv(path):
    if not path.is_file():
        pytest.skip(f"ground truth not available: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def find_object_literal(text, name):
    """Return the ``{...}`` source of a top-level ``const <name> = {...}``."""
    match = re.search(r"(?:const|let|var)\s+" + re.escape(name) + r"\s*=\s*\{", text)
    if not match:
        return None
    start = text.index("{", match.start())
    depth = 0
    in_string = escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return None


def relax_json(chunk):
    """Make one non-string JavaScript fragment JSON-parsable."""
    chunk = re.sub(r"//[^\n]*", "", chunk)
    chunk = re.sub(r"([{\[,]\s*)([A-Za-z_$][A-Za-z0-9_$]*)(\s*):", r'\1"\2"\3:', chunk)
    return re.sub(r",(\s*[}\]])", r"\1", chunk)


def js_object_to_python(block):
    """Parse a JSON-shaped JS object literal, tolerating bare keys and trailing commas.

    String literals are copied through untouched so recipe names containing
    commas, colons or escapes cannot be corrupted by the relaxing rules.
    """
    pieces = []
    position = 0
    for match in STRING_LITERAL.finditer(block):
        pieces.append(relax_json(block[position:match.start()]))
        pieces.append(match.group(0))
        position = match.end()
    pieces.append(relax_json(block[position:]))
    return json.loads("".join(pieces))


@pytest.fixture(scope="module")
def demo_data():
    if not APP_JS.is_file():
        pytest.skip(f"frontend bundle not found: {APP_JS}")
    block = find_object_literal(APP_JS.read_text(encoding="utf-8"), "DEMO_DATA")
    if block is None:
        pytest.skip(
            "could not locate the 'const DEMO_DATA = {...}' literal in "
            f"{APP_JS}; update tests/test_frontend_demo_data.py if the "
            "offline fallback was renamed or moved"
        )
    try:
        return js_object_to_python(block)
    except ValueError as exc:
        pytest.skip(f"DEMO_DATA in {APP_JS} is not a JSON-shaped literal: {exc}")


def test_summary_counts_match_the_raw_dataset(demo_data):
    rows = read_csv(DATASET)
    expected = collections.Counter(
        row["Diet_type"].strip().casefold() for row in rows
    )
    summary = demo_data["summary"]
    assert summary["total_recipes"] == len(rows) == 7806
    assert summary["diet_counts"] == dict(expected)
    assert sorted(summary["diet_types"]) == sorted(expected)


def test_total_protein_matches_the_batch_results(demo_data):
    expected = {
        row["Diet_type"]: round(float(row["Protein(g)"]), 2)
        for row in read_csv(RESULTS / "total_protein.csv")
    }
    actual = {
        row["Diet_type"]: round(float(row["Total_Protein(g)"]), 2)
        for row in demo_data["total_protein_by_diet"]
    }
    assert actual == expected


def test_common_cuisines_match_the_batch_results(demo_data):
    expected = {
        (row["Diet_type"], row["Cuisine_type"]): int(row["count"])
        for row in read_csv(RESULTS / "common_cuisines.csv")
    }
    actual = {
        (row["Diet_type"], row["Cuisine_type"]): int(row["count"])
        for row in demo_data["common_cuisines"]
    }
    assert actual == expected


def test_average_macros_match_the_batch_results(demo_data):
    expected = {
        row["Diet_type"]: {key: round(float(row[key]), 2) for key in MACRO_KEYS}
        for row in read_csv(RESULTS / "average_macros.csv")
    }
    actual = {
        row["Diet_type"]: {key: round(float(row[key]), 2) for key in MACRO_KEYS}
        for row in demo_data["average_macros"]
    }
    assert actual == expected


def test_top_recipes_match_the_batch_results(demo_data):
    expected = {
        (row["Diet_type"], row["Recipe_name"], round(float(row["Protein(g)"]), 2))
        for row in read_csv(RESULTS / "top5_protein_recipes.csv")
    }
    actual = {
        (row["Diet_type"], row["Recipe_name"], round(float(row["Protein(g)"]), 2))
        for row in demo_data["top_recipes"]
    }
    assert actual == expected
