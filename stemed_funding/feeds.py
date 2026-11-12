"""RSS of newly listed opportunities, and a calendar (.ics) of every dated deadline."""
import datetime as dt
from email.utils import format_datetime
from pathlib import Path
from typing import List
from xml.etree import ElementTree as ET


def describe(item: dict) -> str:
    parts = [item["sponsor"]]
    if item.get("deadline") and item["deadline_kind"] in ("due", "estimated"):
        parts.append(("Estimated deadline " if item["deadline_kind"] == "estimated" else "Deadline ") + item["deadline"])
    elif item.get("deadline_note"):
        parts.append(item["deadline_note"])
    if item.get("amount"):
        parts.append(item["amount"])
    return ". ".join(p.rstrip(".") for p in parts if p) + "."


def write_rss(path: Path, items: List[dict], site: dict, now: dt.datetime, label: str = "newly listed") -> None:
    rss = ET.Element("rss", version="2.0")
    ch = ET.SubElement(rss, "channel")
    ET.SubElement(ch, "title").text = f"{site['title']}: {label}"
    ET.SubElement(ch, "link").text = site["site_url"]
    ET.SubElement(ch, "description").text = site["tagline"]
    ET.SubElement(ch, "lastBuildDate").text = format_datetime(now)
    newest = sorted(items, key=lambda i: (i["first_seen"], i["id"]), reverse=True)[: site.get("feed_size", 100)]
    for item in newest:
        e = ET.SubElement(ch, "item")
        ET.SubElement(e, "title").text = item["title"]
        ET.SubElement(e, "link").text = item["url"]
        ET.SubElement(e, "guid", isPermaLink="false").text = item["id"]
        ET.SubElement(e, "description").text = (item.get("summary", "") + " " + describe(item)).strip()
        day = dt.datetime.fromisoformat(item["first_seen"]).replace(tzinfo=dt.timezone.utc)
        ET.SubElement(e, "pubDate").text = format_datetime(day)
        for d in item["disciplines"]:
            ET.SubElement(e, "category").text = d
        ET.SubElement(e, "category").text = item["sponsor_type"]
    ET.indent(rss)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(rss, encoding="utf-8") + b"\n")


def _ics_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> List[str]:
    """iCalendar lines are at most 75 octets; longer ones continue with a leading space."""
    out, data = [], line.encode("utf-8")
    while len(data) > 75:
        cut = 75 if not out else 74
        while cut and (data[cut] & 0xC0) == 0x80:   # do not split a UTF-8 character
            cut -= 1
        out.append(data[:cut].decode("utf-8"))
        data = data[cut:]
    out.append(data.decode("utf-8"))
    return [out[0]] + [" " + s for s in out[1:]]


def ics_event(item: dict, stamp: str) -> List[str]:
    day = item["deadline"].replace("-", "")
    end = (dt.date.fromisoformat(item["deadline"]) + dt.timedelta(days=1)).strftime("%Y%m%d")
    prefix = "Estimated deadline" if item["deadline_kind"] == "estimated" else "Deadline"
    lines = [
        "BEGIN:VEVENT",
        f"UID:{item['id'].replace(':', '-')}@stemed-funding",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{day}",
        f"DTEND;VALUE=DATE:{end}",
        "SUMMARY:" + _ics_text(f"{prefix}: {item['title']} ({item['sponsor']})"),
        "DESCRIPTION:" + _ics_text(f"{describe(item)} Always confirm on the sponsor's page: {item['url']}"),
        "URL:" + item["url"],
        "END:VEVENT",
    ]
    return [part for line in lines for part in _fold(line)]


def write_ics(path: Path, items: List[dict], site: dict, now: dt.datetime) -> None:
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//STEMEd+//Funding//EN", "CALSCALE:GREGORIAN",
             "X-WR-CALNAME:" + _ics_text(f"{site['title']} deadlines"),
             "X-WR-CALDESC:" + _ics_text("Deadlines for STEM+ education funding. Always confirm on the sponsor's page.")]
    for item in items:
        if item.get("deadline") and item["deadline_kind"] in ("due", "estimated"):
            lines += ics_event(item, stamp)
    lines.append("END:VCALENDAR")
    lines = [part for line in lines for part in (_fold(line) if not line.startswith(" ") else [line])]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))
