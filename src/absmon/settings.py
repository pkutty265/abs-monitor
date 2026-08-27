"""Runtime settings. SEC requires a descriptive User-Agent with contact info."""
from __future__ import annotations
import os
from pathlib import Path

SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "abs-monitor research contact@example.com")
DATA_DIR = Path(os.environ.get("ABSMON_DATA_DIR", "data"))
RAW_DIR = DATA_DIR / "raw"
PARSED_DIR = DATA_DIR / "parsed"
# SEC fair-access limit is 10 req/s; stay well under it.
MIN_SECONDS_BETWEEN_REQUESTS = 0.15
