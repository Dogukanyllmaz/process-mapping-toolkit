# procmap: process mapping & control-gap checker

Describe a workflow in a short YAML file; get a **swimlane map** and a list of the
**internal-control gaps** an auditor would raise, with severity and the reason behind each rule.

Workflows that grow over years tend to collect the same handful of problems: approvals with no SLA,
steps bound to a named person, the same role approving twice, data typed again into the ERP.
Encoding them as rules turns a manual review of many workflows into one repeatable command.

## Example

[`examples/purchase-request-as-is.yaml`](examples/purchase-request-as-is.yaml) is a fictional As-Is
purchase request process:

```bash
python -m procmap check examples/purchase-request-as-is.yaml
```

```
HIGH   PC03 F1     'Spend approval' is assigned to a fixed person
HIGH   PC03 W1     'Warehouse stock check' is assigned to a fixed person
HIGH   PC04 P2     'Requester confirms the offer' is approved by the initiator
HIGH   PC08 P3     'Create purchase order in ERP by hand' has no outgoing path
MEDIUM PC01 A1     'Manager approval' has no SLA (falls back to the platform default of 1 h)
...
MEDIUM PC05 A1     4 consecutive approvals: A1 -> A2 -> A3 -> W1 (limit 3)
MEDIUM PC06 A3     'Technical approval (second pass)' repeats the approval of 'Technical approval' (Technical manager)
MEDIUM PC07 W2     'Issue from stock and key the slip into the ERP' re-keys data into another system
LOW    PC09 X1     'Old cancellation branch' cannot be reached from the start
19 finding(s)
```

The [To-Be redesign](examples/purchase-request-to-be.yaml) of the same process passes with **0 findings**.
Full reports with the rendered maps:
[As-Is](examples/purchase-request-as-is.report.md) · [To-Be](examples/purchase-request-to-be.report.md).

## Control rules

| Code | Rule | Severity | Why it matters |
|---|---|---|---|
| PC01 | No SLA | medium | A human step without its own SLA cannot be measured or escalated. |
| PC02 | No escalation | medium | An SLA without escalation is a number nobody acts on. |
| PC03 | Hard-coded assignee | high | Work stops when that person leaves or is absent; bypasses role-based access. |
| PC04 | Self-approval possible | high | The initiator approves their own request: segregation-of-duties breach. |
| PC05 | Long approval chain | medium | Many consecutive approvals dilute accountability and add waiting time. |
| PC06 | Repeated approver | medium | The same role approving twice adds delay, not control. |
| PC07 | Manual re-entry | medium | Data typed again into another system: error risk, no traceable link. |
| PC08 | Dead end | high | A non-end step with no outgoing path leaves instances stuck. |
| PC09 | Unreachable step | low | Dead design that still has to be maintained. |

## Process format

```yaml
code: PR-TOBE
name: Purchase request (To-Be)
default_sla_hours: 1            # optional platform default, reported by PC01
lanes: [Requester, Line management, System, Finance]
steps:
  - {id: S0, name: Request opened, type: start, lane: Requester, next: S1}
  - id: A1
    name: Manager approval
    type: approval              # start | task | approval | system | decision | end
    lane: Line management
    assignee: {type: manager_of, value: requester}   # initiator | role | manager_of | field | person | system
    sla_hours: 16
    escalation: true
    next: [F1]
  - id: W2
    name: Key the slip into the ERP
    type: task
    lane: Warehouse
    manual_reentry: true
    next: E1
```

The loader validates the model (unknown step types, undeclared lanes, links to missing steps) before any check runs.

## Usage

```bash
pip install -e .[test]

procmap map    process.yaml                 # Mermaid swimlane diagram
procmap check  process.yaml --max-chain 3   # findings; exit code 1 on any high-severity finding
procmap report process.yaml -o report.md    # Markdown report: stats, map with findings highlighted, rules

pytest
```

Because `check` fails on high-severity findings, it can run in CI to stop a workflow change that
re-introduces a fixed assignee or a self-approval.
