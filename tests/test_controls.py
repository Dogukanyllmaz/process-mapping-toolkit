from pathlib import Path

import pytest

from procmap import controls, mermaid
from procmap.cli import main
from procmap.model import ModelError, load, parse

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def codes(findings, step=None):
    return {f.code for f in findings if step is None or f.step == step}


@pytest.fixture
def as_is():
    return load(EXAMPLES / "purchase-request-as-is.yaml")


@pytest.fixture
def to_be():
    return load(EXAMPLES / "purchase-request-to-be.yaml")


def test_as_is_finds_every_gap(as_is):
    findings = controls.check(as_is)
    assert "PC03" in codes(findings, "W1")   # fixed person
    assert "PC03" in codes(findings, "F1")
    assert "PC04" in codes(findings, "P2")   # initiator approves
    assert "PC06" in codes(findings, "A3")   # same role approves twice
    assert "PC07" in codes(findings, "W2")   # manual re-entry
    assert "PC07" in codes(findings, "P3")
    assert "PC08" in codes(findings, "P3")   # dead end
    assert "PC09" in codes(findings, "X1")   # unreachable
    assert "PC01" in codes(findings, "A1")   # no SLA
    assert "PC02" in codes(findings, "P1")   # SLA without escalation
    assert "PC05" in codes(findings)         # A1 -> A2 -> A3 -> W1


def test_to_be_is_clean(to_be):
    assert controls.check(to_be) == []


def test_findings_are_sorted_by_severity(as_is):
    severities = [f.severity for f in controls.check(as_is)]
    assert severities == sorted(severities, key=["high", "medium", "low"].index)


def test_chain_limit_is_configurable(as_is):
    assert "PC05" not in codes(controls.check(as_is, max_chain=10))


def test_mermaid_has_lanes_edges_and_highlights(as_is):
    findings = controls.check(as_is)
    by_step = {}
    for f in findings:
        if f.step:
            by_step.setdefault(f.step, []).append(f.code)
    text = mermaid.render(as_is, by_step)
    assert text.startswith("flowchart LR")
    assert 'subgraph L0["Requester"]' in text
    assert "D1 --> P1" in text
    assert "class " in text and "W1" in text.split("class ")[-1]


def test_unknown_next_step_is_rejected():
    with pytest.raises(ModelError, match="does not exist"):
        parse({"code": "X", "name": "x", "lanes": ["A"],
               "steps": [{"id": "S", "name": "s", "type": "start", "lane": "A", "next": "missing"}]})


def test_undeclared_lane_is_rejected():
    with pytest.raises(ModelError, match="lane"):
        parse({"code": "X", "name": "x", "lanes": ["A"],
               "steps": [{"id": "S", "name": "s", "type": "start", "lane": "B"}]})


def test_check_exit_code(capsys):
    assert main(["check", str(EXAMPLES / "purchase-request-as-is.yaml")]) == 1
    assert main(["check", str(EXAMPLES / "purchase-request-to-be.yaml")]) == 0


def test_report_writes_markdown(tmp_path):
    out = tmp_path / "report.md"
    assert main(["report", str(EXAMPLES / "purchase-request-as-is.yaml"), "-o", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "```mermaid" in text and "| high | PC03 |" in text
