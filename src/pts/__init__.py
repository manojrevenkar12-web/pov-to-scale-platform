"""pov-to-scale-platform: engagements, policy, promotion gate, budgets, lab."""

import os
from pathlib import Path

# The repository root (config/, engagements/, runbooks/). In the container image it is /app (PTS_ROOT).
ROOT = Path(os.environ.get("PTS_ROOT", Path(__file__).resolve().parents[2]))
CONFIG = ROOT / "config"
