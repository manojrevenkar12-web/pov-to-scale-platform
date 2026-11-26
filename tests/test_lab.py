from pts import config
from pts.lab import sim
from pts.lab.world import draw


def cfg():
    c = config.load("lab")
    c["year"]["engagements"] = 40
    return c


def test_same_seed_same_year():
    c = cfg()
    assert sim.year(3, sim.Design.platform, c) == sim.year(3, sim.Design.platform, c)


def test_every_design_sees_the_same_engagements():
    c = cfg()
    a, b = draw(5, c, 7), draw(5, c, 7)
    assert a.request == b.request and a.usage == b.usage and a.releases["scaled"][0] == b.releases["scaled"][0]


def test_platform_blocks_what_reaches_azure_elsewhere():
    c = cfg()
    plat, adhoc = sim.year(2, sim.Design.platform, c), sim.year(2, sim.Design.ad_hoc, c)
    assert plat["violations"] == 0 and plat["policy_blocks"] == adhoc["violations"]
    assert plat["isolation"] == 0 and plat["security"] == 0 and plat["idle_keur"] == 0


def test_budgets_stop_runaway_spend_but_cost_some_waiting():
    c = cfg()
    c["engagement"]["runaway"] = 1.0
    with_b, without = sim.year(4, sim.Design.platform, c), sim.year(4, sim.Design.no_budgets, c)
    assert with_b["overrun_keur"] == 0 and without["overrun_keur"] > 0
    assert with_b["blocked_days"] > 0 and without["blocked_days"] == 0


def test_the_gate_keeps_regressions_out_of_production():
    c = cfg()
    c["release"]["bad"] = 1.0  # every first attempt is bad
    gated, ungated = sim.year(6, sim.Design.platform, c), sim.year(6, sim.Design.no_gate, c)
    assert ungated["bad_in_prod"] >= gated["bad_in_prod"]
    assert gated["gate_stops"] > 0 and ungated["gate_stops"] == 0


def test_ablations_change_only_their_part():
    c = cfg()
    p, nb, ng = (sim.year(8, d, c) for d in (sim.Design.platform, sim.Design.no_budgets, sim.Design.no_gate))
    for k in ("violations", "isolation", "security", "env_days", "idle_keur"):
        assert p[k] == nb[k] == ng[k]
    assert p["bad_in_prod"] == nb["bad_in_prod"] and p["overrun_keur"] == ng["overrun_keur"]
