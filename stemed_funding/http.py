"""Small HTTPS helpers with retries (standard library only)."""
import json
import time
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USER_AGENT = "STEMEd-Funding/1.0 (+https://github.com/JLib271/stemed-funding)"


def _send(req: Request, tries: int, timeout: int) -> bytes:
    last = None
    for attempt in range(tries):
        try:
            with urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except HTTPError as exc:
            last = exc
            if exc.code not in (429, 500, 502, 503, 504):
                raise
            wait = int(exc.headers.get("Retry-After") or 0) or 2 ** attempt * 3
        except (URLError, TimeoutError) as exc:
            last = exc
            wait = 2 ** attempt * 3
        time.sleep(min(wait, 60))
    raise RuntimeError(f"Giving up on {req.full_url}: {last}")


def get_json(url: str, tries: int = 4, timeout: int = 60) -> dict:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    return json.loads(_send(req, tries, timeout))


def post_json(url: str, body: dict, tries: int = 4, timeout: int = 60) -> dict:
    req = Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                  headers={"User-Agent": USER_AGENT, "Accept": "application/json",
                           "Content-Type": "application/json"})
    return json.loads(_send(req, tries, timeout))


def stamp(value: Optional[str]) -> str:
    """Grants.gov '2027-01-20-00-00-00' -> '2027-01-20'."""
    return (value or "")[:10]
