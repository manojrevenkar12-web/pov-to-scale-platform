from datetime import date

import pytest

from pts import ROOT
from pts.engagement import Engagement, load_all

TODAY = date(2026, 11, 26)


@pytest.fixture
def samples() -> list[Engagement]:
    return load_all(ROOT / "engagements")


def make(**over) -> Engagement:
    base = dict(
        id="test-pov",
        client="acme-test",
        owner="owner@example.com",
        cost_center="RB-TEST-1",
        stage="pov",
        classification="internal",
        region="germanywestcentral",
        start=date(2026, 11, 20),
        expires=date(2027, 1, 30),
        budget_eur=10000,
        models=[{"model": "gpt-4o-mini", "tokens_per_minute": 50000}],
    )
    base.update(over)
    return Engagement.model_validate(base)
