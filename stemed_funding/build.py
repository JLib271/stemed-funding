"""Collect every opportunity and write the website, feeds, and calendar.

    python -m stemed_funding --out output --previous https://<owner>.github.io/<repo>
    python -m stemed_funding --validate      # only check opportunities/*.yml

Output (all static, served by GitHub Pages):
    index.html            searchable list
    opportunities.json    everything listed; also tells the next run when each was first seen
    feeds/new.xml         RSS of newly listed opportunities
    feeds/deadlines.ics   calendar of every dated deadline (subscribe in Google, Outlook, Apple)
"""
import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional
from urllib.request import Request, urlopen

from . import classify, curated, feeds, grantsgov
from .disciplines import DISCIPLINES
from .http import USER_AGENT

ROOT = Path(__file__).resolve().parent.parent
SPONSOR_TYPES = ["Federal", "Foundation", "Society or association", "State or regional"]
STATUS_LABELS = {
    "open": "Open", "forecast": "Forecast", "upcoming": "Upcoming", "rolling": "Rolling",
    "between-cycles": "Between cycles", "passed": "Deadline passed", "paused": "Paused",
    "invitation": "By invitation", "no-open-call": "No open call",
}


def load_config(name: str) -> dict:
    return json.loads((ROOT / "config" / name).read_text(encoding="utf-8"))


def load_previous(previous: Optional[str]) -> List[dict]:
    """Items from the last published opportunities.json (a URL or a local path). A missing
    or unreadable file just means a fresh start, e.g. on the very first run."""
    if not previous:
        return []
    try:
        if previous.startswith(("http://", "https://")):
            url = previous.rstrip("/") + "/opportunities.json"
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=60) as resp:
                data = json.load(resp)
        else:
            data = json.loads(Path(previous).read_text(encoding="utf-8"))
        return data.get("items", [])
    except Exception as exc:  # noqa: BLE001 - any failure means "start fresh"
        print(f"Note: no previous listings loaded from {previous} ({exc}).")
        return []


def deadline_sort_key(item: dict):
    """Dated deadlines first (soonest first), then rolling, then everything else."""
    order = {"due": 0, "estimated": 0, "through": 1, "anytime": 2, "none": 3}[item["deadline_kind"]]
    return (order, item.get("deadline") or "9999", item["title"].lower())


def run(out: Path, previous: Optional[str], today: dt.date, fetch_federal=grantsgov.fetch_federal,
        allow_errors: bool = False, now: Optional[dt.datetime] = None) -> dict:
    now = now or dt.datetime.combine(today, dt.time(12), tzinfo=dt.timezone.utc)
    site, federal_cfg = load_config("site.json"), load_config("federal.json")
    old = load_previous(previous)
    first_seen: Dict[str, str] = {i["id"]: i.get("first_seen", today.isoformat()) for i in old}
    status = []

    entries, problems = curated.load()
    if problems:
        raise SystemExit("Problems in opportunities/:\n  " + "\n  ".join(problems))
    items = [curated.to_record(slug, e, today) for slug, e in entries]
    status.append({"source": "Foundations, societies, and state programs", "ok": True, "count": len(items)})

    try:
        federal = fetch_federal(federal_cfg, today)
        status.append({"source": "Grants.gov", "ok": True, "count": len(federal)})
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: Grants.gov: {exc}")
        if not allow_errors:
            raise SystemExit("Grants.gov could not be reached; rerun with --allow-errors to publish anyway.")
        # Keep last run's federal listings whose deadlines have not passed.
        federal = [i for i in old if i.get("source") == "federal"
                   and not (i.get("deadline") and i["deadline"] < today.isoformat() and i["deadline_kind"] == "due")]
        status.append({"source": "Grants.gov", "ok": False, "error": str(exc)[:200], "count": len(federal)})
    items += federal

    for item in items:
        item["first_seen"] = first_seen.get(item["id"], today.isoformat())
    items.sort(key=deadline_sort_key)

    payload = {
        "generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "today": today.isoformat(),
        "site": site,
        "disciplines": list(DISCIPLINES),
        "kinds": list(classify.KIND_NAMES),
        "sponsor_types": SPONSOR_TYPES,
        "status_labels": STATUS_LABELS,
        "status": status,
        "review": [{"title": i["title"], "file": i["file"], "why": i["review"]} for i in items if i.get("review")],
        "items": items,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "opportunities.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
                                            encoding="utf-8")
    shutil.copyfile(ROOT / "site" / "index.html", out / "index.html")
    feeds.write_rss(out / "feeds" / "new.xml", items, site, now)
    feeds.write_ics(out / "feeds" / "deadlines.ics", items, site, now)
    print(f"Wrote {len(items)} opportunities ({len(federal)} federal); {len(payload['review'])} listing(s) to re-check.")
    return payload


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("output"))
    ap.add_argument("--previous", help="URL of the published site (or a local opportunities.json)")
    ap.add_argument("--allow-errors", action="store_true", help="publish even if Grants.gov cannot be reached")
    ap.add_argument("--validate", action="store_true", help="only check opportunities/*.yml")
    args = ap.parse_args(argv)
    if args.validate:
        entries, problems = curated.load()
        for p in problems:
            print(p)
        print(f"{len(entries)} valid file(s), {len(problems)} problem(s).")
        return 1 if problems else 0
    run(args.out, args.previous, dt.date.today(), allow_errors=args.allow_errors)
    return 0


if __name__ == "__main__":
    sys.exit(main())
