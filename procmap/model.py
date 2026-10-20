"""Process definition model: a small, readable YAML format for As-Is / To-Be workflows."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

STEP_TYPES = {"start", "task", "approval", "system", "decision", "end"}
ASSIGNEE_TYPES = {"initiator", "role", "manager_of", "field", "person", "system"}


@dataclass
class Assignee:
    type: str
    value: str = ""

    def label(self) -> str:
        return {
            "initiator": "initiator",
            "role": self.value,
            "manager_of": f"manager of {self.value}",
            "field": f"person in field '{self.value}'",
            "person": f"fixed person {self.value}",
            "system": "system",
        }.get(self.type, self.value)


@dataclass
class Step:
    id: str
    name: str
    type: str
    lane: str
    next: list[str] = field(default_factory=list)
    assignee: Assignee | None = None
    sla_hours: float | None = None
    escalation: bool = False
    manual_reentry: bool = False  # data typed again into another system


@dataclass
class Process:
    code: str
    name: str
    lanes: list[str]
    steps: list[Step]
    default_sla_hours: float | None = None

    def step(self, step_id: str) -> Step:
        for s in self.steps:
            if s.id == step_id:
                return s
        raise KeyError(step_id)

    @property
    def by_id(self) -> dict[str, Step]:
        return {s.id: s for s in self.steps}


class ModelError(ValueError):
    pass


def _parse_next(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    return [str(x) for x in raw]


def load(path: str | Path) -> Process:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return parse(data)


def parse(data: dict) -> Process:
    lanes = list(data.get("lanes", []))
    steps: list[Step] = []
    for raw in data.get("steps", []):
        assignee = None
        if "assignee" in raw:
            a = raw["assignee"]
            assignee = Assignee(type=a["type"], value=str(a.get("value", "")))
        steps.append(
            Step(
                id=str(raw["id"]),
                name=raw["name"],
                type=raw.get("type", "task"),
                lane=raw.get("lane", lanes[0] if lanes else ""),
                next=_parse_next(raw.get("next")),
                assignee=assignee,
                sla_hours=raw.get("sla_hours"),
                escalation=bool(raw.get("escalation", False)),
                manual_reentry=bool(raw.get("manual_reentry", False)),
            )
        )
    process = Process(
        code=data["code"],
        name=data["name"],
        lanes=lanes,
        steps=steps,
        default_sla_hours=data.get("default_sla_hours"),
    )
    validate(process)
    return process


def validate(process: Process) -> None:
    ids = [s.id for s in process.steps]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ModelError(f"duplicate step ids: {sorted(duplicates)}")
    known = set(ids)
    for s in process.steps:
        if s.type not in STEP_TYPES:
            raise ModelError(f"{s.id}: unknown step type '{s.type}'")
        if s.lane not in process.lanes:
            raise ModelError(f"{s.id}: lane '{s.lane}' is not declared")
        if s.assignee and s.assignee.type not in ASSIGNEE_TYPES:
            raise ModelError(f"{s.id}: unknown assignee type '{s.assignee.type}'")
        for target in s.next:
            if target not in known:
                raise ModelError(f"{s.id}: next step '{target}' does not exist")
    if not any(s.type == "start" for s in process.steps):
        raise ModelError("process has no start step")
