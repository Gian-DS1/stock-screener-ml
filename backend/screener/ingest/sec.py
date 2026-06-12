"""Cliente HTTP compartido para SEC EDGAR con throttling (límite oficial: 10 req/s)."""
import threading
import time

import requests

from screener.config import settings

_MIN_INTERVAL = 0.12  # ~8 req/s, margen bajo el límite de la SEC
_lock = threading.Lock()
_last_request = 0.0

_session = requests.Session()


def sec_get(url: str, max_retries: int = 3) -> requests.Response:
    global _last_request
    headers = {"User-Agent": settings.sec_user_agent, "Accept-Encoding": "gzip, deflate"}
    for attempt in range(max_retries):
        with _lock:
            wait = _MIN_INTERVAL - (time.monotonic() - _last_request)
            if wait > 0:
                time.sleep(wait)
            _last_request = time.monotonic()
        resp = _session.get(url, headers=headers, timeout=30)
        if resp.status_code == 429 or resp.status_code >= 500:
            time.sleep(2.0 * (attempt + 1))
            continue
        return resp
    resp.raise_for_status()
    return resp
