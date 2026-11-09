# STEMEd+ Funding

Open calls and deadlines for STEM+ education research and practice, in one place:

* **Federal calls** from [Grants.gov](https://www.grants.gov/), where NSF (IUSE, S-STEM, ATE,
  CAREER, STEM K-12, and more), NIH (research education R25 and SEPA), USDA NIFA, NOAA, NASA,
  the Department of Education (IES), and other agencies post their funding calls. Collected
  automatically every day.
* **Foundations, professional societies, and state programs** that Grants.gov does not cover,
  such as the Spencer Foundation, the Sloan Foundation, HHMI, the Gates Foundation, the Research
  Corporation (Cottrell Scholars), the Dreyfus Foundation, the Macy Foundation, NCTM, AAPT, ACS,
  SIGCSE, MAA, NAGT, NASA Space Grant consortia, and state STEM programs. Kept by hand, one file
  per program in [`opportunities/`](opportunities/), each checked against the funder's own page.

The focus is the United States. Disciplines use the same categories as
[STEMEd+ Jobs](https://github.com/JLib271/stemed-jobs), the
[STEMEd+ Digest](https://github.com/JLib271/STEMEd-Digest), and the
[STEM+ Education Research Graduate Programs](https://github.com/JLib271/stem-ed-research-programs) list.

🔎 **Website:** https://jlib271.github.io/stemed-funding/ (once GitHub Pages is turned on)

## What you get

| | |
|---|---|
| **Website** | Search and filter by funder type, funder, discipline, what it funds (research, teaching and curriculum, students and training, early career, K-12 and teachers, institutional capacity, broadening participation, outreach), status, and how soon the deadline is. Deadlines are color-coded by how close they are, and "Closing in the next 30 days" is at the top. "Copy link to this view" shares any filtered view. |
| **Deadline calendar** | [`feeds/deadlines.ics`](https://jlib271.github.io/stemed-funding/feeds/deadlines.ics) has every dated deadline. Subscribe in Google Calendar, Outlook, or Apple Calendar ("add calendar from URL") and new deadlines appear on their own. Each listing also has an "Add to calendar" link for just that deadline. |
| **RSS** | [`feeds/new.xml`](https://jlib271.github.io/stemed-funding/feeds/new.xml) lists newly added opportunities. |

The site updates itself every day. Deadlines and rules change, so always confirm on the funder's
page before applying; every listing links there.

## How federal calls are chosen

Each day the site searches Grants.gov for posted and forecasted calls matching education
keywords ("education", "STEM", "teacher", "undergraduate", "curriculum", "Faculty Early Career", and
others), which returns about 1,250 calls. It keeps a call when its title has an education term
**and** either a STEM+ term or the call comes from a STEM agency (NSF, NIH, NASA, NOAA, USDA NIFA,
DOE, HRSA, CDC, NIST, EPA, USGS, or the Department of Education). It leaves out research-training
awards that are not about education (NIH K awards, NRSA fellowships, postdoctoral fellowships),
small-business programs, international exchanges, and requests for information. A short list of
programs is always kept when posted, such as Noyce, LSAMP, the Graduate Research Fellowship, and
DRK-12. In November 2026 this kept about 60 calls. All of these rules are in
[`config/federal.json`](config/federal.json) and can be adjusted.

Deadlines are shown the way agencies post them:

* **Due** or **expected around** a date: a deadline, or a forecast's estimated date.
* **Accepts applications through** a date: for long-running announcements, such as NIH parent
  R25 announcements that use standard due dates until they expire. Check the announcement for
  the dates in between.
* **Accepted anytime or on recurring dates**: NSF programs with no single deadline.

Expired calls and forecasts whose estimated date has passed are left out. Disciplines for federal
calls come from the title (NIH, HRSA, and CDC calls are Health Education; NIFA calls are
Agriculture). Calls in the history and philosophy of science (including science and technology
studies and the history of medicine) and in science and health communication are kept even when
their titles do not mention education. Calls that name no particular field are marked "All STEM+ fields" and appear under
every discipline. "What it funds" is matched automatically from the title and description, so
treat it as a guide.

## Foundations, societies, and state programs

These change too often and in too many places to collect automatically, so each one is a short
file in [`opportunities/`](opportunities/), checked against the funder's page. Programs between
cycles stay listed, with how the cycle usually runs ("Annual. The 2026 deadline was July 1."), so
the list shows what is coming as well as what is open. When a listed deadline passes, the
listing switches to "Deadline passed" by itself, and the site's footer lists it for a maintainer
to check, along with any listing not checked in 180 days.

A listing looks like this:

```yaml
name: "SIGCSE Special Project Grants"
sponsor: "ACM SIGCSE"
sponsor_type: "Society or association"   # Foundation, Society or association, State or regional, Federal
url: "https://sigcse.org/programs/special/"
status: "open"          # open, upcoming, rolling, between-cycles, paused, invitation, no-open-call
deadline: 2026-11-15    # the next deadline, if announced
deadline_note: "Twice a year: May 15 and November 15."
amount: "Up to $5,000"
eligibility: "SIGCSE members."
summary: "Small projects that bring new knowledge, shared resources, or good practice to computing education."
kinds: ["Teaching and curriculum", "Research"]
disciplines: ["Engineering"]   # leave empty for programs open to all STEM+ fields
states: ["MI"]                 # only for state or regional programs
checked: 2026-11-06            # when someone last checked the funder's page
```

The full rules are in [`schema/opportunity.schema.json`](schema/opportunity.schema.json), and every
file is checked automatically. Summaries are written in our own words rather than copied.

## Add or correct a listing

* **Suggest an opportunity:** use the [Suggest an opportunity](../../issues/new?template=suggest_opportunity.yml) form.
* **Report a correction:** use the [Correct a listing](../../issues/new?template=update_opportunity.yml) form,
  or the "Report a correction" link on any listing.
* **No GitHub account?** Email the maintainer at libarkin@msu.edu.
* **Edit directly:** add or change a file in [`opportunities/`](opportunities/) and open a pull request.
  The checks run on every pull request.

Suggestions arrive as issues labeled `add opportunity` or `update opportunity`.

## Running it

Python 3.10+ with PyYAML and jsonschema (`pip install -r requirements.txt`).

```bash
python -m unittest discover -s tests -t .   # tests (no network)
python -m stemed_funding --validate         # check the files in opportunities/
python -m stemed_funding --out output       # collect everything and build the site in output/
```

`.github/workflows/update.yml` runs this every day and publishes to GitHub Pages. It carries over
when each listing was first seen from the published site's `opportunities.json`, so the
repository never needs data commits. Turn it on once in **Settings → Pages → Source: GitHub Actions**.

## Settings

| File | What it controls |
|---|---|
| `config/federal.json` | Grants.gov search keywords, the title rules for keeping a call, STEM agencies, dropped agencies, programs always kept, agency display names, and agency default disciplines. |
| `config/site.json` | Title, tagline, links to the other STEMEd+ sites, and the size of the RSS feed. |
| `opportunities/*.yml` | The hand-kept listings. |

## License

Code: MIT. Listings in `opportunities/`: [CC BY 4.0](opportunities/LICENSE.md). The disciplines
(labels, definitions, and matching words) come from the STEMEd+ discipline list shared across
STEMEd+ Commons, kept in [HuMeta](https://github.com/JLib271/HuMeta)
(`standard/humeta/stemedplus_disciplines.json`) and stored here as
`stemed_funding/stemedplus_disciplines.json`; each build refreshes the stored copy.
