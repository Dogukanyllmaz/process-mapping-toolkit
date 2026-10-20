"""Render a process as a Mermaid swimlane flowchart (one subgraph per lane)."""
from __future__ import annotations

from .model import Process, Step

SHAPES = {
    "start": ("([", "])"),
    "end": ("([", "])"),
    "decision": ("{", "}"),
    "system": ("[[", "]]"),
    "approval": ("[/", "/]"),
    "task": ("[", "]"),
}


def _node(step: Step) -> str:
    left, right = SHAPES[step.type]
    label = step.name.replace('"', "'")
    if step.assignee and step.type in {"task", "approval"}:
        label += f"<br/><small>{step.assignee.label()}</small>"
    return f'{step.id}{left}"{label}"{right}'


def render(process: Process, findings_by_step: dict[str, list[str]] | None = None) -> str:
    findings_by_step = findings_by_step or {}
    lines = ["flowchart LR", f"    %% {process.code}: {process.name}"]
    for i, lane in enumerate(process.lanes):
        lines.append(f'    subgraph L{i}["{lane}"]')
        lines.append("        direction LR")
        for step in process.steps:
            if step.lane == lane:
                lines.append(f"        {_node(step)}")
        lines.append("    end")
    for step in process.steps:
        for target in step.next:
            lines.append(f"    {step.id} --> {target}")
    flagged = [sid for sid, codes in findings_by_step.items() if codes]
    if flagged:
        lines.append("    classDef finding stroke:#d33,stroke-width:3px")
        lines.append(f"    class {','.join(flagged)} finding")
    return "\n".join(lines) + "\n"
