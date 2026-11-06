"""Federal funding calls from the Grants.gov API (https://www.grants.gov/api).

Grants.gov is where NSF, NIH, USDA, NOAA, NASA, the Department of Education, and most other
agencies post their calls. Each run searches posted and forecasted calls for a set of
keywords, keeps the STEM+ education ones by title (rules in config/federal.json), and then
fetches each kept call's details for its deadline, award size, eligibility, and links.
"""
import datetime as dt
import re
import time
from typing import Dict, Iterable, List, Optional

from . import classify
from .http import post_json, stamp

SUMMARY_LENGTH = 300


class Rules:
    """The patterns in config/federal.json, compiled."""

    def __init__(self, config: dict):
        self.config = config
        flags = re.IGNORECASE
        self.education = re.compile(config["education"], flags)
        self.stem = re.compile(config["stem"], flags)
        self.always = re.compile(config["always"], flags)
        self.drop = re.compile(config["drop"], flags)

    def keep(self, title: str, agency_code: str) -> bool:
        title = classify.plain(title)
        if self.always.search(title):
            return True
        if agency_code.startswith(tuple(self.config["drop_agencies"])) or self.drop.search(title):
            return False
        if not self.education.search(title):
            return False
        return bool(self.stem.search(title)) or agency_code.startswith(tuple(self.config["stem_agencies"]))

    def agency(self, code: str, fallback: str) -> str:
        prefixes = sorted(self.config["agencies"], key=len, reverse=True)
        for p in prefixes:
            if code == p or code.startswith(p + "-") or code.startswith(p):
                return self.config["agencies"][p]
        return fallback or code

    def agency_disciplines(self, code: str) -> List[str]:
        found: List[str] = []
        for prefix, ds in self.config["agency_disciplines"].items():
            if code.startswith(prefix):
                found += ds
        return found


def search(config: dict, rows: int = 1000, max_pages: int = 10) -> List[dict]:
    """Every posted or forecasted call matching any keyword, without duplicates."""
    hits: Dict[str, dict] = {}
    for keyword in config["keywords"]:
        start = 0
        for _ in range(max_pages):
            data = post_json(f"{config['api']}/search2", {
                "keyword": keyword, "oppStatuses": "forecasted|posted", "rows": rows, "startRecord": start,
            })["data"]
            page = data.get("oppHits") or []
            for h in page:
                hits.setdefault(str(h["id"]), h)
            start += len(page)
            if not page or start >= data.get("hitCount", 0):
                break
    return list(hits.values())


def fetch_detail(config: dict, opp_id: str) -> dict:
    return post_json(f"{config['api']}/fetchOpportunity", {"opportunityId": int(opp_id)})["data"]


def _money(value) -> Optional[int]:
    try:
        n = int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None
    return n if 1 < n < 100_000_000 else None   # 0/1 are placeholders; >$100M is a program total


def _amount(info: dict) -> str:
    floor, ceiling = _money(info.get("awardFloor")), _money(info.get("awardCeiling"))
    total = _money(info.get("estimatedFunding"))
    if floor and ceiling and floor < ceiling:
        text = f"${floor:,} to ${ceiling:,} per award"
    elif ceiling:
        text = f"Up to ${ceiling:,} per award"
    else:
        text = ""
    if total and total != ceiling:
        text += ("; " if text else "") + f"${total:,} in total"
    return text


def _eligibility(info: dict) -> List[str]:
    out = []
    for t in info.get("applicantTypes") or []:
        desc = classify.plain(t.get("description", ""))
        if desc.startswith("Unrestricted"):
            desc = "Unrestricted"
        elif desc.startswith("Others"):
            desc = "Others (see the announcement)"
        if desc and desc not in out:
            out.append(desc)
    return out


def _summary(text: str) -> str:
    text = re.sub(r"^(?:Synopsis of Program|Program Description|Purpose|Overview)\s*:\s*", "", text, flags=re.I)
    if len(text) <= SUMMARY_LENGTH:
        return text
    cut = text[:SUMMARY_LENGTH]
    end = max(cut.rfind(". "), cut.rfind("? "))
    return cut[:end + 1] if end > SUMMARY_LENGTH // 2 else cut.rsplit(" ", 1)[0] + "…"


def parse(detail: dict, rules: Rules, today: dt.date) -> Optional[dict]:
    """One Grants.gov call -> a listing, or None when it should not be listed (expired,
    a stale forecast, or a request for information)."""
    syn, fc = detail.get("synopsis"), detail.get("forecast")
    info = syn or fc
    if not info:
        return None
    if classify.plain(info.get("fundingActivityCategoryDesc", "")) in rules.config["skip_activity"]:
        return None
    code = detail.get("owningAgencyCode") or info.get("agencyCode") or ""
    top = (detail.get("topAgencyDetails") or {}).get("agencyName", "")
    title = classify.plain(detail.get("opportunityTitle"))
    description = classify.plain(info.get("synopsisDesc") or info.get("forecastDesc") or "")
    today_s = today.isoformat()

    if syn:
        status = "open"
        deadline = stamp(syn.get("responseDateStr"))
        note = classify.plain(syn.get("responseDateDesc"))
        if deadline and deadline < today_s:
            return None
        if not deadline:
            kind = "none"
        elif deadline[:4] >= str(today.year + 10):          # NSF uses 2076 for "accepted anytime"
            kind, deadline = "anytime", ""
        elif deadline > (today + dt.timedelta(days=400)).isoformat():
            kind = "through"                                 # e.g. NIH parent announcements
        else:
            kind = "due"
    else:
        status = "forecast"
        deadline = stamp(fc.get("estApplicationResponseDateStr"))
        note = ""
        updated = stamp(fc.get("lastUpdatedDateStr") or fc.get("createTimeStampStr")) or stamp(fc.get("postingDateStr"))
        if deadline and deadline < today_s:
            return None
        if not deadline and updated and updated < (today - dt.timedelta(days=730)).isoformat():
            return None
        kind = "estimated" if deadline else "none"

    opp_id = str(detail["id"])
    # Disciplines come from the title (and the agency): descriptions mention fields in
    # passing, while a call that names none in its title is open to all of them.
    fields = classify.disciplines(title, rules.agency_disciplines(code))
    return {
        "id": f"grantsgov:{opp_id}",
        "source": "federal",
        "sponsor_type": "Federal",
        "sponsor": rules.agency(code, top),
        "title": title,
        "number": detail.get("opportunityNumber", ""),
        "url": rules.config["listing_url"].format(id=opp_id),
        "announcement": (syn or {}).get("fundingDescLinkUrl") or "",
        "status": status,
        "deadline": deadline,
        "deadline_kind": kind,
        "deadline_note": note[:240],
        "posted": stamp(info.get("postingDateStr")),
        "amount": _amount(info),
        "eligibility": _eligibility(info),
        "summary": _summary(description),
        "disciplines": fields,
        "all_fields": classify.open_to_all(fields),
        "kinds": classify.kinds(f"{title}. {description[:600]}"),
        "states": [],
    }


def fetch_federal(config: dict, today: dt.date, pause: float = 0.2) -> List[dict]:
    rules = Rules(config)
    kept = [h for h in search(config) if rules.keep(h.get("title", ""), h.get("agencyCode", ""))]
    out = []
    for h in kept:
        time.sleep(pause)
        item = parse(fetch_detail(config, str(h["id"])), rules, today)
        if item:
            out.append(item)
    return out


def from_details(details: Iterable[dict], config: dict, today: dt.date) -> List[dict]:
    """Parse already-fetched details (used by the tests)."""
    rules = Rules(config)
    out = []
    for d in details:
        if rules.keep(d.get("opportunityTitle", ""), d.get("owningAgencyCode", "")):
            item = parse(d, rules, today)
            if item:
                out.append(item)
    return out
