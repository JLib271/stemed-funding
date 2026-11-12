import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree as ET

from stemed_funding import build, classify, curated, feeds, grantsgov

FIX = Path(__file__).parent / "fixtures"
DETAILS = json.loads((FIX / "grantsgov_details.json").read_text(encoding="utf-8"))
SEARCH = json.loads((FIX / "grantsgov_search.json").read_text(encoding="utf-8"))
CONFIG = build.load_config("federal.json")
TODAY = dt.date(2026, 11, 6)


def by_title(items, start):
    return next(i for i in items if i["title"].startswith(start))


class FederalTests(unittest.TestCase):
    def setUp(self):
        self.items = grantsgov.from_details(DETAILS, CONFIG, TODAY)

    def test_title_rules(self):
        rules = grantsgov.Rules(CONFIG)
        self.assertTrue(rules.keep("Improving Undergraduate STEM Education: Directorate for STEM Education", "NSF"))
        self.assertTrue(rules.keep("Faculty Early Career Development Program (CAREER)", "NSF"))
        self.assertTrue(rules.keep("Robert Noyce Teacher Scholarship Program", "NSF"))           # always kept
        self.assertFalse(rules.keep("Plasma Physics", "NSF"))                                     # no education term
        self.assertFalse(rules.keep("Ruth L. Kirschstein NRSA Individual Postdoctoral Fellowship", "HHS-NIH11"))
        self.assertFalse(rules.keep("Culture of Research and University Exchanges in Agricultural STEM", "DOS-ZWE"))
        self.assertFalse(rules.keep("Integrating Machine Learning with Fluid Dynamics Models", "HHS-FDA"))
        # History & philosophy of science and science & health communication are kept as fields.
        self.assertTrue(rules.keep("Science and Technology Studies (STS)", "NSF"))
        self.assertTrue(rules.keep("NLM Grants for Scholarly Works in Biomedicine and Health (G13)", "HHS-NIH11"))
        self.assertTrue(rules.keep("Health Communication Research to Reduce Disparities", "HHS-NIH11"))
        self.assertFalse(rules.keep("Public Humanities Projects", "NEH"))
        self.assertTrue(rules.keep("Dynamics of Integrated Socio-Environmental Systems (DISES)", "NSF"))
        self.assertTrue(rules.keep("Human Dimensions of Wildlife Management Research", "DOI-FWS"))

    def test_search_combines_keywords_and_filters(self):
        calls = []

        def fake_post(url, body, **_):
            calls.append(body["keyword"])
            return SEARCH
        with mock.patch.object(grantsgov, "post_json", side_effect=fake_post):
            hits = grantsgov.search(CONFIG)
        self.assertEqual(calls, CONFIG["keywords"])
        self.assertEqual(len(hits), len(SEARCH["data"]["oppHits"]))                 # duplicates merged
        rules = grantsgov.Rules(CONFIG)
        kept = [h for h in hits if rules.keep(h["title"], h["agencyCode"])]
        self.assertFalse(any(h["title"].startswith(("Plasma", "Ruth", "Culture")) for h in kept))

    def test_parses_a_posted_call(self):
        iuse = by_title(self.items, "Improving Undergraduate STEM Education")
        self.assertEqual(iuse["id"], "grantsgov:344124")
        self.assertEqual(iuse["sponsor"], "National Science Foundation (NSF)")
        self.assertEqual(iuse["status"], "open")
        self.assertEqual((iuse["deadline"], iuse["deadline_kind"]), ("2027-01-20", "due"))
        self.assertEqual(iuse["url"], "https://www.grants.gov/search-results-detail/344124")
        self.assertIn("nsf23510", iuse["announcement"])
        self.assertEqual(iuse["amount"], "$200,000 to $2,000,000 per award; $61,000,000 in total")
        self.assertEqual(iuse["eligibility"], ["Unrestricted"])
        self.assertTrue(iuse["all_fields"])
        self.assertLessEqual(len(iuse["summary"]), grantsgov.SUMMARY_LENGTH + 1)

    def test_deadline_kinds(self):
        self.assertEqual(by_title(self.items, "NSF STEM K-12")["deadline_kind"], "anytime")      # NSF's 2076
        sepa = by_title(self.items, "NIH Science Education Partnership Award")
        self.assertEqual(sepa["deadline_kind"], "through")                                     # parent R25
        self.assertEqual(sepa["disciplines"][0], "Health Education")                           # NIH default
        self.assertEqual(by_title(self.items, "EONS 2018")["deadline_kind"], "none")

    def test_skips_requests_for_information_and_dropped_agencies(self):
        titles = [i["title"] for i in self.items]
        self.assertFalse(any("National Defense Education Program (NDEP) Science" in t for t in titles))  # RFI
        self.assertFalse(any("skin lightening" in t for t in titles))                              # FDA

    def test_skips_expired_calls_and_stale_forecasts(self):
        later = grantsgov.from_details(DETAILS, CONFIG, dt.date(2027, 2, 1))
        titles = [i["title"] for i in later]
        self.assertFalse(any(t.startswith("Improving Undergraduate STEM") for t in titles))      # closed Jan 20
        self.assertTrue(any(t.startswith("NSF STEM K-12") for t in titles))

    def test_disciplines_from_title(self):
        self.assertEqual(by_title(self.items, "Research Experiences for Teachers")["disciplines"], ["Engineering"])
        self.assertTrue(by_title(self.items, "NSF Scholarships in Science")["all_fields"])     # spelled-out STEM
        self.assertEqual(by_title(self.items, "Hispanic-Serving Institutions")["disciplines"], ["Agriculture"])


class ClassifyTests(unittest.TestCase):
    def test_disciplines_and_kinds(self):
        self.assertEqual(classify.disciplines("Undergraduate chemistry laboratory curriculum"), ["Chemistry"])
        self.assertEqual(classify.disciplines("Prompt engineering for teachers"), [])
        self.assertEqual(classify.disciplines("Science and Technology Studies (STS)"), ["History & Philosophy of Science"])
        self.assertEqual(classify.disciplines("Dynamics of Integrated Socio-Environmental Systems"), ["Human Dimensions"])
        self.assertEqual(classify.disciplines("Specialty Crop Research Initiative: entomology and horticulture"), ["Agriculture", "Bioscience"])
        self.assertEqual(classify.disciplines("Risk communication in public health emergencies"),
                         ["Health Education", "Science & Health Communication"])
        self.assertTrue(classify.open_to_all(classify.disciplines("Improving STEM education")))
        self.assertIn("K-12 and teachers", classify.kinds("Research Experiences for Teachers"))
        self.assertIn("Early career", classify.kinds("Faculty Early Career Development Program (CAREER)"))
        self.assertEqual(classify.plain("<p>A &amp; B</p>"), "A & B")


class CuratedTests(unittest.TestCase):
    def test_every_file_is_valid(self):
        entries, problems = curated.load()
        self.assertEqual(problems, [])
        self.assertGreaterEqual(len(entries), 20)
        for slug, e in entries:
            self.assertTrue(e["url"].startswith("https://"), slug)

    def test_invalid_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "bad.yml").write_text('name: "X"\nsponsor_type: "Company"\n', encoding="utf-8")
            entries, problems = curated.load(Path(tmp))
        self.assertEqual(entries, [])
        self.assertTrue(any("sponsor_type" in p for p in problems))
        self.assertTrue(any("required" in p for p in problems))

    def test_status_follows_the_calendar(self):
        entry = {"name": "Grant", "sponsor": "S", "sponsor_type": "Foundation", "url": "https://x.org", "status": "open",
                 "deadline": "2026-11-15", "summary": "Twenty characters or more.", "checked": "2026-11-06"}
        now = curated.to_record("g", entry, TODAY)
        self.assertEqual((now["status"], now["deadline_kind"], now["review"]), ("open", "due", []))
        later = curated.to_record("g", entry, dt.date(2026, 11, 20))
        self.assertEqual((later["status"], later["deadline"]), ("passed", ""))
        self.assertIn("deadline passed", later["review"])
        stale = curated.to_record("g", entry, dt.date(2027, 6, 1))
        self.assertTrue(any(r.startswith("last checked") for r in stale["review"]))
        self.assertTrue(now["all_fields"])


class BuildTests(unittest.TestCase):
    def run_build(self, out, previous=None, today=TODAY, fetch=None):
        fetch = fetch or (lambda cfg, day: grantsgov.from_details(DETAILS, cfg, day))
        return build.run(out, previous, today, fetch_federal=fetch)

    def test_full_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            payload = self.run_build(out)
            for name in ("index.html", "opportunities.json", "feeds/new.xml", "feeds/deadlines.ics"):
                self.assertTrue((out / name).exists(), name)
            items = payload["items"]
            self.assertTrue(any(i["source"] == "federal" for i in items))
            self.assertTrue(any(i["source"] == "curated" for i in items))
            dated = [i["deadline"] for i in items if i["deadline_kind"] in ("due", "estimated")]
            self.assertEqual(dated, sorted(dated))                       # soonest deadlines first
            self.assertEqual(items[0]["title"], "SIGCSE Special Project Grants")
            ics = (out / "feeds" / "deadlines.ics").read_bytes().decode("utf-8")
            self.assertTrue(ics.startswith("BEGIN:VCALENDAR\r\n"))
            self.assertEqual(ics.count("BEGIN:VEVENT"), len(dated))
            self.assertTrue(all(len(line.encode("utf-8")) <= 75 for line in ics.split("\r\n")))
            self.assertIn("DTSTART;VALUE=DATE:20261115", ics)
            rss = ET.parse(out / "feeds" / "new.xml").getroot()
            self.assertEqual(len(rss.findall("./channel/item")), len(items))

    def test_first_seen_carries_over(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = self.run_build(Path(tmp) / "a")
            prev = Path(tmp) / "prev.json"
            data = first
            data["items"][0]["first_seen"] = "2026-10-01"
            prev.write_text(json.dumps(data), encoding="utf-8")
            second = self.run_build(Path(tmp) / "b", str(prev), today=dt.date(2026, 11, 7))
        seen = {i["id"]: i["first_seen"] for i in second["items"]}
        self.assertEqual(seen[first["items"][0]["id"]], "2026-10-01")
        self.assertTrue(all(v in ("2026-10-01", "2026-11-06") for v in seen.values()))

    def test_grants_gov_outage_keeps_previous_federal_listings(self):
        def broken(cfg, day):
            raise RuntimeError("Grants.gov is down")
        with tempfile.TemporaryDirectory() as tmp:
            first = self.run_build(Path(tmp) / "a")
            prev = Path(tmp) / "prev.json"
            prev.write_text(json.dumps(first), encoding="utf-8")
            with self.assertRaises(SystemExit):
                self.run_build(Path(tmp) / "b", str(prev), fetch=broken)
            payload = build.run(Path(tmp) / "c", str(prev), TODAY, fetch_federal=broken, allow_errors=True)
        self.assertFalse(next(s for s in payload["status"] if s["source"] == "Grants.gov")["ok"])
        self.assertEqual(sum(i["source"] == "federal" for i in payload["items"]),
                         sum(i["source"] == "federal" for i in first["items"]))

    def test_ics_folding_keeps_characters_whole(self):
        long = "SUMMARY:" + "é" * 80
        parts = feeds._fold(long)
        self.assertTrue(all(len(p.encode("utf-8")) <= 75 for p in parts))
        self.assertEqual("".join(p[1:] if i else p for i, p in enumerate(parts)), long)


if __name__ == "__main__":
    unittest.main()


class TeacherKindTests(unittest.TestCase):
    def test_teacher_kinds_are_never_auto_assigned(self):
        from stemed_funding import classify
        text = "Classroom grants and teaching awards for teachers to travel to professional development workshops"
        self.assertFalse(set(classify.kinds(text)) & set(classify.TEACHER_KINDS))

    def test_curated_teacher_listings_validate(self):
        from stemed_funding import classify, curated
        entries, problems = curated.load()
        self.assertEqual(problems, [])
        tagged = {k for _, e in entries for k in e.get("kinds", []) if k in classify.TEACHER_KINDS}
        self.assertEqual(tagged, set(classify.TEACHER_KINDS))
