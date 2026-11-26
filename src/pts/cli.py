"""pts: the platform's command line.

pts check                         policy on every engagement + static Terraform checks
pts render-all [--check]          address ranges and Terraform variables from engagements/*.yaml
pts slo-rules [--check]           Prometheus burn-rate rules from config/slo.yaml
pts gate --stage scaled --metrics m.json [--current-eval 0.88]
pts agent "PoV for client Northwind ..." --owner you@example.com --cost-center RB-1
pts triage alert.json [--metrics gateway.prom]
pts lab sim --split dev|heldout
pts lab report [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import ROOT, agent, gate, policy, render, slo, triage
from .engagement import load_all

ENGAGEMENTS = ROOT / "engagements"
IPAM = ROOT / "infra" / "ipam.json"
TFVARS = ROOT / "infra" / "terraform" / "envs" / "lab" / "engagements.auto.tfvars.json"
SLO_RULES = ROOT / "deploy" / "prometheus" / "slo-rules.yaml"
APPS = ROOT / "deploy" / "argocd" / "engagements.json"


def _write_or_check(path: Path, text: str, check: bool) -> bool:
    if path.exists() and path.read_text() == text:
        return True
    if check:
        print(f"stale: {path.relative_to(ROOT)}", file=sys.stderr)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    print(f"wrote {path.relative_to(ROOT)}")
    return True


def cmd_check(a: argparse.Namespace) -> int:
    es = load_all(ENGAGEMENTS)
    today = date.fromisoformat(a.today) if a.today else date.today()
    bad = 0
    for e in es:
        for f in policy.check(e, [o for o in es if o is not e], today=today):
            print(f"{e.id}: {f}")
            bad += f.severity == policy.ERROR
    for f in policy.check_terraform(ROOT / "infra" / "terraform"):
        print(f)
        bad += 1
    print(f"{len(es)} engagements, {bad} errors", file=sys.stderr)
    return 1 if bad else 0


def cmd_render_all(a: argparse.Namespace) -> int:
    existing = json.loads(IPAM.read_text()) if IPAM.exists() else {}
    es = load_all(ENGAGEMENTS)
    _, ipam_json, tf_json = render.render_all(es, existing)
    ok = _write_or_check(IPAM, ipam_json, a.check) & _write_or_check(TFVARS, tf_json, a.check)
    ok &= _write_or_check(APPS, render.argocd_apps(es), a.check)
    return 0 if ok else 1


def cmd_slo(a: argparse.Namespace) -> int:
    return 0 if _write_or_check(SLO_RULES, slo.render(), a.check) else 1


def cmd_gate(a: argparse.Namespace) -> int:
    if a.prometheus:
        try:
            m = gate.from_prometheus(a.prometheus, a.engagement)
        except ValueError as err:
            print(f"FAIL {err}")
            return 1
    else:
        m = gate.Metrics(**json.loads(Path(a.metrics).read_text()))
    d = gate.evaluate(a.stage, m, a.current_eval)
    for c in d.checks:
        print(f"{'ok  ' if c.ok else 'FAIL'} {c.name:13} {c.detail}")
    print(f"promote to {a.stage}: {'yes' if d.promote else 'no'}")
    return 0 if d.promote else 1


def cmd_agent(a: argparse.Namespace) -> int:
    es = load_all(ENGAGEMENTS)
    alloc = json.loads(IPAM.read_text()) if IPAM.exists() else {}
    extract = agent.llm_extractor(a.gateway, a.gateway_engagement) if a.gateway else agent.rules_extractor
    p = agent.propose(a.request, a.owner, a.cost_center, es, alloc, date.today(), extract)
    print(p.pr_body())
    if p.ok and a.write:
        for rel, text in agent.files(p).items():
            (ROOT / rel).write_text(text)
            print(f"wrote {rel}; run `pts render-all` and open the pull request")
    return 0 if p.ok else 1


def cmd_triage(a: argparse.Namespace) -> int:
    payload = json.loads(Path(a.alert).read_text())
    alerts = payload.get("alerts", [payload])
    metrics = Path(a.metrics).read_text() if a.metrics else ""
    for al in alerts:
        print(triage.triage(al, metrics).markdown())
    return 0


def cmd_lab(a: argparse.Namespace) -> int:
    from .lab import run

    try:
        if a.lab_cmd == "sim":
            r = run.run(a.split)
            p = {d["design"]: d["metrics"] for d in r["designs"]}["platform"]
            print(
                f"{a.split}: {len(r['seeds'])} years; platform isolation incidents "
                f"{p['isolation']['mean']}, unapproved overspend €{p['overrun_keur']['mean']}k"
            )
        else:
            for f in run.report(a.check):
                print(f"{'checked' if a.check else 'wrote'} {f}")
    except run.LabError as err:
        print(f"lab: {err}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pts", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--today")
    c.set_defaults(fn=cmd_check)
    r = sub.add_parser("render-all")
    r.add_argument("--check", action="store_true")
    r.set_defaults(fn=cmd_render_all)
    s = sub.add_parser("slo-rules")
    s.add_argument("--check", action="store_true")
    s.set_defaults(fn=cmd_slo)
    g = sub.add_parser("gate")
    g.add_argument("--stage", required=True, choices=["pilot", "scaled"])
    src = g.add_mutually_exclusive_group(required=True)
    src.add_argument("--metrics", help="JSON file with the observation window's metrics")
    src.add_argument("--prometheus", help="Prometheus URL to read them from")
    g.add_argument("--engagement", help="engagement id (with --prometheus)")
    g.add_argument("--current-eval", type=float)
    g.set_defaults(fn=cmd_gate)
    ag = sub.add_parser("agent")
    ag.add_argument("request")
    ag.add_argument("--owner", required=True)
    ag.add_argument("--cost-center", required=True)
    ag.add_argument("--gateway", help="AI gateway URL; without it the request is read with rules")
    ag.add_argument("--gateway-engagement", default="rb-knowledge-agents-scaled")
    ag.add_argument("--write", action="store_true", help="write engagements/<id>.yaml for the pull request")
    ag.set_defaults(fn=cmd_agent)
    t = sub.add_parser("triage")
    t.add_argument("alert")
    t.add_argument("--metrics")
    t.set_defaults(fn=cmd_triage)
    lab = sub.add_parser("lab")
    labsub = lab.add_subparsers(dest="lab_cmd", required=True)
    ls = labsub.add_parser("sim")
    ls.add_argument("--split", required=True, choices=["dev", "heldout"])
    lr = labsub.add_parser("report")
    lr.add_argument("--check", action="store_true")
    lab.set_defaults(fn=cmd_lab)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
