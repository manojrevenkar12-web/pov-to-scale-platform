"""Run the lab over a seed split, write results, and generate the reports from them.

pts lab sim --split dev        # tune against these seeds as often as needed
pts lab sim --split heldout    # once; writes results/HELDOUT.lock
pts lab report [--check]       # README block, reports/RESULTS.md, dashboard data
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from datetime import UTC, datetime
from typing import Any

from .. import ROOT, config
from .sim import DESIGNS, METRICS, Design, year

LOCK = ROOT / "results" / "HELDOUT.lock"
START, END = "<!-- results:start -->", "<!-- results:end -->"


class LabError(Exception):
    pass


def config_hash() -> str:
    h = hashlib.sha256()
    for name in ("lab", "platform", "promotion", "pricing"):
        h.update((config.CONFIG / f"{name}.yaml").read_bytes())
    return h.hexdigest()


def stat(xs: list[float]) -> dict[str, float]:
    mean = statistics.fmean(xs)
    ci = 1.96 * statistics.stdev(xs) / math.sqrt(len(xs)) if len(xs) > 1 else 0.0
    return {"mean": round(mean, 2), "ci95": round(ci, 2)}


def run(split: str) -> dict[str, Any]:
    cfg = config.load("lab")
    if split not in ("dev", "heldout"):
        raise LabError("split must be dev or heldout")
    if split == "heldout":
        if LOCK.exists():
            raise LabError(f"the held-out split already ran ({LOCK.relative_to(ROOT)}); it runs once")
        if set(cfg["seeds"]["heldout"]) & set(cfg["seeds"]["dev"]):
            raise LabError("a seed is in both splits")
    seeds = cfg["seeds"][split]
    designs = []
    for d in DESIGNS:
        per_seed = [year(s, d, cfg) for s in seeds]
        designs.append(
            {
                "design": d.value,
                "label": d.label,
                "metrics": {k: stat([r[k] for r in per_seed]) for k in per_seed[0]},
            }
        )
    result = {
        "split": split,
        "seeds": seeds,
        "engagements_per_year": cfg["year"]["engagements"],
        "config_sha256": config_hash(),
        "metrics": [{"key": k, "label": lbl, "unit": u, "better": b} for k, lbl, u, b in METRICS],
        "designs": designs,
    }
    out = ROOT / "results" / f"{split}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    if split == "heldout":
        LOCK.write_text(
            f"held-out split ran {datetime.now(UTC).isoformat(timespec='seconds')}\n"
            f"config sha256 {result['config_sha256']}\nseeds {seeds}\n"
        )
    return result


def _num(x: float) -> str:
    if abs(x) >= 100:
        return f"{x:,.0f}"
    s = f"{x:.1f}"
    return s[:-2] if s.endswith(".0") else s


def table(r: dict[str, Any]) -> str:
    ds = r["designs"]
    lines = [
        f"**{r['split']} split** · {len(r['seeds'])} simulated years × {r['engagements_per_year']} client engagements"
        f" · mean per year ± 95% interval · settings sha256 `{r['config_sha256'][:12]}`",
        "",
        "| Per year | " + " | ".join(d["label"] for d in ds) + " |",
        "|---|" + "---:|" * len(ds),
    ]
    for m in r["metrics"]:
        cells = []
        for d in ds:
            s = d["metrics"][m["key"]]
            cell = f"{_num(s['mean'])} ± {_num(s['ci95'])}"
            cells.append(f"**{cell}**" if d["design"] == Design.platform.value else cell)
        unit = "" if m["unit"] == "per year" else f" ({m['unit']})"
        lines.append(f"| {m['label']}{unit} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _load(split: str) -> dict[str, Any] | None:
    p = ROOT / "results" / f"{split}.json"
    return json.loads(p.read_text()) if p.exists() else None


def report(check: bool = False) -> list[str]:
    dev = _load("dev")
    if dev is None:
        raise LabError("run `pts lab sim --split dev` first")
    h = config_hash()
    if dev["config_sha256"] != h:
        raise LabError("results/dev.json was made with different settings; rerun the dev split")
    held = _load("heldout")
    if held is not None:
        if held["config_sha256"] != h:
            raise LabError("settings changed after the held-out split ran; its numbers no longer describe them")
        if not LOCK.exists():
            raise LabError("results/heldout.json exists without results/HELDOUT.lock")
    main = held or dev
    block = table(main)
    if held:
        op = {d["design"]: d["metrics"] for d in dev["designs"]}
        block += (
            f"\nThe dev split ({len(dev['seeds'])} years) agrees: the platform has "
            f"{_num(op['platform']['isolation']['mean'])} isolation incidents and "
            f"€{_num(op['platform']['overrun_keur']['mean'])}k unapproved overspend a year, against "
            f"{_num(op['ad_hoc']['isolation']['mean'])} and €{_num(op['ad_hoc']['overrun_keur']['mean'])}k "
            "for hand-built environments.\n"
        )
    readme = (ROOT / "README.md").read_text()
    if START not in readme or END not in readme:
        raise LabError("README.md needs the results markers")
    i, j = readme.index(START) + len(START), readme.index(END)
    files = {
        "README.md": readme[:i] + "\n" + block + readme[j:],
        "reports/RESULTS.md": _report_md(dev, held),
        "dashboard/public/data/results.json": json.dumps({"dev": dev, "heldout": held}, indent=2) + "\n",
    }
    stale = []
    for rel, text in files.items():
        p = ROOT / rel
        if p.exists() and p.read_text() == text:
            continue
        if check:
            stale.append(rel)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
    if stale:
        raise LabError(f"generated files are stale: {', '.join(stale)}; run `pts lab report`")
    return list(files)


def _report_md(dev: dict[str, Any], held: dict[str, Any] | None) -> str:
    out = [
        "# Lab results\n",
        "Generated by `pts lab report` from `results/*.json`. Do not edit by hand; CI regenerates it and fails "
        "on any difference.\n",
        "Every rate behind these numbers is an assumption in `config/lab.yaml`. The lab compares designs on the "
        "same luck; it does not measure any real firm's engagements.\n",
    ]
    if held:
        out += ["## Held-out years (run once, locked)\n", table(held)]
    out += ["## Dev years\n", table(dev)]
    main = held or dev
    by = {d["design"]: d["metrics"] for d in main["designs"]}
    out += [
        "## Reading the ablations\n",
        f"- **Without budgets** the platform keeps isolation and the promotion gate but lets runaway agents and "
        f"leaked keys spend: €{_num(by['platform_no_budgets']['overrun_keur']['mean'])}k unapproved a year.",
        f"- **Without the promotion gate** {_num(by['platform_no_gate']['bad_in_prod']['mean'])} regressed releases "
        f"a year reach production instead of {_num(by['platform']['bad_in_prod']['mean'])}; the gate costs "
        f"{_num(by['platform']['gate_stops']['mean'])} stopped promotions and about a week each.",
        f"- **What the platform costs:** {_num(by['platform']['blocked_days']['mean'])} days a year in which a PoV "
        "waited for its owner to raise a budget, and running the platform itself (included in engineer time).",
        "",
    ]
    return "\n".join(out)
