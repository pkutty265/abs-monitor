"""Rate-limited, disk-caching HTTP client for sec.gov / data.sec.gov."""
from __future__ import annotations
import hashlib
import logging
import time
from pathlib import Path
from typing import Optional

import requests

from absmon import settings

log = logging.getLogger(__name__)


class EdgarClient:
    def __init__(self, user_agent: str = settings.SEC_USER_AGENT, cache_dir: Path = settings.RAW_DIR):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        })
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_request = 0.0

    def _throttle(self) -> None:
        wait = settings.MIN_SECONDS_BETWEEN_REQUESTS - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def get_bytes(self, url: str, cache_path: Optional[Path] = None, retries: int = 3) -> bytes:
        """GET with disk cache. cache_path is relative to cache_dir; defaults to a url hash."""
        if cache_path is None:
            cache_path = Path("_urlcache") / (hashlib.sha1(url.encode()).hexdigest() + ".bin")
        full = self.cache_dir / cache_path
        if full.exists():
            return full.read_bytes()

        for attempt in range(retries):
            self._throttle()
            resp = self.session.get(url, timeout=60)
            if resp.status_code == 200:
                full.parent.mkdir(parents=True, exist_ok=True)
                full.write_bytes(resp.content)
                return resp.content
            if resp.status_code in (403, 429, 503):
                # 403 from SEC almost always means throttling or a bad User-Agent.
                backoff = 2 ** attempt
                log.warning("HTTP %s on %s; sleeping %ss", resp.status_code, url, backoff)
                time.sleep(backoff)
                continue
            resp.raise_for_status()
        raise RuntimeError(f"Failed to fetch {url} after {retries} attempts")

    def get_json(self, url: str, cache_path: Optional[Path] = None) -> dict:
        import json
        return json.loads(self.get_bytes(url, cache_path))
