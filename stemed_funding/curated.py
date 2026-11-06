"""Programs that Grants.gov does not cover (foundations, societies, state and regional
programs), kept by hand as one YAML file each in opportunities/."""
import datetime as dt
import json
from pathlib import Path
from typing import List, Tuple

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "opportunities"
SCHEMA = json.loads((ROOT / "schema" / "opportunity.schema.json").read_text(encoding="utf-8"))
REVIEW_AFTER_DAYS = 180


def _plain(value):
    """YAML reads dates as date objects; the schema and the site want strings."""
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def load(folder: Path = FOLDER) -> Tuple[List[Tuple[str, dict]], List[str]]:
    """(slug, entry) for every valid file, and a list of problems."""
    validator = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
    entries, problems = [], []
    for path in sorted(folder.glob("*.yml")):
        try:
            data = _plain(yaml.safe_load(path.read_text(encoding="utf-8")))
        except yaml.YAMLError as exc:
            problems.append(f"{path.name}: not valid YAML ({exc})")
            continue
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        for e in errors:
            where = ".".join(str(p) for p in e.path) or "(file)"
            problems.append(f"{path.name}: {where}: {e.message}")
        if not errors:
            entries.append((path.stem, data))
    return entries, problems


def to_record(slug: str, e: dict, today: dt.date) -> dict:
    today_s = today.isoformat()
    status, deadline = e["status"], e.get("deadline", "")
    if deadline and deadline < today_s:
        status, deadline = "passed", ""
    if deadline:
        kind = "due"
    elif status == "rolling":
        kind = "anytime"
    else:
        kind = "none"
    checked = e["checked"]
    review = []
    if status == "passed":
        review.append("deadline passed")
    if e["status"] in ("open", "upcoming") and not e.get("deadline"):
        review.append("open or upcoming without a deadline")
    if checked < (today - dt.timedelta(days=REVIEW_AFTER_DAYS)).isoformat():
        review.append(f"last checked {checked}")
    return {
        "id": f"curated:{slug}",
        "source": "curated",
        "sponsor_type": e["sponsor_type"],
        "sponsor": e["sponsor"],
        "title": e["name"],
        "number": "",
        "url": e["url"],
        "announcement": "",
        "status": status,
        "opens": e.get("opens", ""),
        "deadline": deadline,
        "deadline_kind": kind,
        "deadline_note": e.get("deadline_note", ""),
        "posted": "",
        "amount": e.get("amount", ""),
        "eligibility": [e["eligibility"]] if e.get("eligibility") else [],
        "summary": e["summary"],
        "disciplines": e.get("disciplines", []),
        "all_fields": not e.get("disciplines"),
        "kinds": e.get("kinds", []),
        "states": e.get("states", []),
        "checked": checked,
        "review": review,
        "file": f"opportunities/{slug}.yml",
    }
