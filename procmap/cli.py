"""Command line: procmap map|check|report <process.yaml>."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import controls, mermaid
from .model import ModelError, load


def _report(path: Path, max_chain: int) -> str:
    process = load(path)
    findings = controls.check(process, max_chain=max_chain)
    stats = controls.summary(process, findings)
    by_step: dict[str, list[str]] = {}
    for f in findings:
        if f.step:
            by_step.setdefault(f.step, []).append(f.code)

    out = [
        f"# {process.code}: {process.name}",
        "",
        f"{stats['steps']} steps · {stats['human_steps']} human steps · {stats['approvals']} approvals · "
        f"**{stats['findings']} findings ({stats['high']} high)**",
        "",
        "## Map",
        "",
        "Steps with findings are outlined in red.",
        "",
        "```mermaid",
        mermaid.render(process, by_step).rstrip(),
        "```",
        "",
        "## Findings",
        "",
    ]
    if findings:
        out += ["| Severity | Code | Step | Finding |", "|---|---|---|---|"]
        out += [f"| {f.severity} | {f.code} | {f.step or '-'} | {f.message} |" for f in findings]
        out += ["", "## Rules triggered", ""]
        for code in sorted({f.code for f in findings}):
            rule = controls.RULES[code]
            out.append(f"- **{code} {rule.title}:** {rule.why}")
    else:
        out.append("No findings.")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="procmap", description="Map workflows and check them for control gaps.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("map", "print a Mermaid swimlane diagram"),
        ("check", "list control findings; exit code 1 if any high-severity finding"),
        ("report", "write a Markdown report with map and findings"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("process", type=Path)
        p.add_argument("--max-chain", type=int, default=3, help="max consecutive approvals (default 3)")
        if name == "report":
            p.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.command == "map":
            sys.stdout.write(mermaid.render(load(args.process)))
            return 0
        if args.command == "check":
            process = load(args.process)
            findings = controls.check(process, max_chain=args.max_chain)
            for f in findings:
                print(f"{f.severity.upper():6} {f.code} {f.step or '-':6} {f.message}")
            print(f"{len(findings)} finding(s)")
            return 1 if any(f.severity == "high" for f in findings) else 0
        text = _report(args.process, args.max_chain)
        if args.output:
            args.output.write_text(text, encoding="utf-8")
            print(f"written: {args.output}")
        else:
            sys.stdout.write(text)
        return 0
    except ModelError as e:
        print(f"model error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
