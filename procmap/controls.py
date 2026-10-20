"""Control checks: find the flow and internal-control gaps an auditor looks for in a workflow."""
from __future__ import annotations

from dataclasses import dataclass

from .model import Process

HUMAN = {"task", "approval"}


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str  # high / medium / low
    step: str | None
    message: str


@dataclass(frozen=True)
class Rule:
    code: str
    title: str
    severity: str
    why: str


RULES = {
    r.code: r
    for r in [
        Rule("PC01", "No SLA", "medium",
             "A human step without its own SLA cannot be measured or escalated."),
        Rule("PC02", "No escalation", "medium",
             "An SLA without escalation is a number nobody acts on."),
        Rule("PC03", "Hard-coded assignee", "high",
             "A step bound to a named person stops when that person leaves or is absent, "
             "and bypasses role-based access control."),
        Rule("PC04", "Self-approval possible", "high",
             "The initiator can approve their own request: segregation-of-duties breach."),
        Rule("PC05", "Long approval chain", "medium",
             "Many consecutive approvals dilute accountability and add waiting time."),
        Rule("PC06", "Repeated approver", "medium",
             "The same role approves twice in a row: the second approval adds delay, not control."),
        Rule("PC07", "Manual re-entry", "medium",
             "Data typed again into another system: error risk and no traceable link."),
        Rule("PC08", "Dead end", "high",
             "A non-end step with no outgoing path leaves instances stuck forever."),
        Rule("PC09", "Unreachable step", "low",
             "A step that cannot be reached from the start is dead design."),
    ]
}


def check(process: Process, max_chain: int = 3) -> list[Finding]:
    findings: list[Finding] = []
    steps = process.by_id

    def add(code: str, step: str | None, message: str) -> None:
        findings.append(Finding(code, RULES[code].severity, step, message))

    for s in process.steps:
        if s.type in HUMAN:
            own_sla = s.sla_hours is not None
            if not own_sla:
                default = process.default_sla_hours
                add("PC01", s.id, f"'{s.name}' has no SLA"
                    + (f" (falls back to the platform default of {default} h)" if default else ""))
            elif not s.escalation:
                add("PC02", s.id, f"'{s.name}' has an SLA of {s.sla_hours} h but no escalation")

            if s.assignee and s.assignee.type == "person":
                add("PC03", s.id, f"'{s.name}' is assigned to a fixed person")

            if s.type == "approval" and s.assignee and s.assignee.type == "initiator":
                add("PC04", s.id, f"'{s.name}' is approved by the initiator")

        if s.manual_reentry:
            add("PC07", s.id, f"'{s.name}' re-keys data into another system")

        if s.type != "end" and not s.next:
            add("PC08", s.id, f"'{s.name}' has no outgoing path")

        # repeated approver: approval -> approval with the same assignee
        if s.type == "approval" and s.assignee:
            for target in s.next:
                t = steps[target]
                if t.type == "approval" and t.assignee == s.assignee:
                    add("PC06", t.id, f"'{t.name}' repeats the approval of '{s.name}' ({s.assignee.label()})")

    # long approval chains along any path
    longest = _longest_approval_chain(process)
    if longest and len(longest) > max_chain:
        add("PC05", longest[0],
            f"{len(longest)} consecutive approvals: {' -> '.join(longest)} (limit {max_chain})")

    # reachability
    start = [s.id for s in process.steps if s.type == "start"]
    seen: set[str] = set()
    stack = list(start)
    while stack:
        sid = stack.pop()
        if sid in seen:
            continue
        seen.add(sid)
        stack.extend(steps[sid].next)
    for s in process.steps:
        if s.id not in seen:
            add("PC09", s.id, f"'{s.name}' cannot be reached from the start")

    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(findings, key=lambda f: (order[f.severity], f.code, f.step or ""))


def _longest_approval_chain(process: Process) -> list[str]:
    steps = process.by_id
    memo: dict[str, list[str]] = {}

    def chain_from(sid: str, visiting: frozenset[str]) -> list[str]:
        if sid in memo:
            return memo[sid]
        s = steps[sid]
        if s.type != "approval" or sid in visiting:
            return []
        best: list[str] = []
        for target in s.next:
            candidate = chain_from(target, visiting | {sid})
            if len(candidate) > len(best):
                best = candidate
        memo[sid] = [sid] + best
        return memo[sid]

    longest: list[str] = []
    for s in process.steps:
        c = chain_from(s.id, frozenset())
        if len(c) > len(longest):
            longest = c
    return longest


def summary(process: Process, findings: list[Finding]) -> dict[str, int]:
    human = [s for s in process.steps if s.type in HUMAN]
    return {
        "steps": len(process.steps),
        "human_steps": len(human),
        "approvals": sum(1 for s in human if s.type == "approval"),
        "findings": len(findings),
        "high": sum(1 for f in findings if f.severity == "high"),
    }
