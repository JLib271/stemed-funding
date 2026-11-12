"""Tag opportunities with disciplines and with what they fund.

The discipline rules are the STEMEd+ Jobs categories (disciplines.py); the extra word
lists match those used by the STEMEd+ Digest for preprints, so all STEMEd+ sites agree.
"""
import html
import re
from typing import Iterable, List

from .disciplines import DISCIPLINES, matching_disciplines

NOT_STEM = re.compile(
    r"\b(?:prompt|context|social|human) engineer\w*|\bre-?engineer\w*"
    r"|\bscience of (?:learning|reading|teaching)\b"
    r"|\b(?:social|political|learning|cognitive|behaviou?ral|library|information|educational|education"
    r"|implementation|improvement) sciences?\b"
    r"|\b(?:school|classroom|campus|organi[sz]ational|institutional) climate\b",
    re.IGNORECASE,
)
WORD_DISCIPLINES = (
    ("Mathematics", re.compile(r"\bmaths?\b|\bmathematical\b|\bgeometr(?:y|ic|ical)\b|\balgebra\w*|\bcalculus\b"
                               r"|\bfractions?\b|\bnumeracy\b|\barithmetic\b|\bstatistical\b|\bdata science\b", re.IGNORECASE)),
    ("Engineering", re.compile(r"\bcomputer science\b|\bcomputing\b|\bcomputational thinking\b|\bprogramming\b"
                               r"|\bcoding\b|\brobotics\b|\bcyber\w*", re.IGNORECASE)),
    ("Health Education", re.compile(r"\bbiomedical\b|\bclinical\b|\bpatients?\b", re.IGNORECASE)),
)

# What an opportunity pays for. Matched in the title and the start of the description.
KINDS = (
    ("Research", re.compile(r"\bresearch\b(?! (?:experiences?|training|education|infrastructure))|\bstud(?:y|ies)\b"
                            r"|\bevaluation\b", re.IGNORECASE)),
    ("Teaching and curriculum", re.compile(r"\bcurricul\w*|\bcourses?\b|\binstruction\w*|\bteaching\b|\bpedagog\w*"
                                           r"|\bundergraduate (?:STEM )?education\b|\bclassroom", re.IGNORECASE)),
    ("Students and training", re.compile(r"\bstudents?\b|\bscholarships?\b|\bfellowships?\b|\btrainees?\b|\btraining\b"
                                         r"|\bresearch experiences?\b|\bREU\b|\bS-STEM\b|\binternships?\b"
                                         r"|\bpostbaccalaureate\b|\bundergraduate research\b|\bgraduate education\b",
                                         re.IGNORECASE)),
    ("Early career", re.compile(r"\bearly[- ]career\b|(?-i:\bCAREER\b)|\bnew faculty\b|\bjunior faculty\b",
                                re.IGNORECASE)),
    ("K-12 and teachers", re.compile(r"\bK-?12\b|\bPreK\b|\bteachers?\b|\bhigh school\b|\bmiddle school\b"
                                     r"|\belementary\b|\bschool districts?\b|\bNoyce\b", re.IGNORECASE)),
    ("Institutional capacity", re.compile(r"\binstitutional\b|\bcapacity\b|\binfrastructure\b|\btribal colleges?\b"
                                          r"|\bHBCU\b|\bminority[- ]serving\b|\bHispanic[- ]serving\b|\btwo-year\b"
                                          r"|\bdepartments?\b|\bconsorti\w*", re.IGNORECASE)),
    ("Broadening participation", re.compile(r"\bbroadening participation\b|\bunderrepresented\b|\bunder-represented\b"
                                            r"|\bequity\b|\binclusi\w*|\bdiversity\b|\btribal\b|\bHBCU\b"
                                            r"|\bminority\b|\bHispanic\b|\bwomen\b|\bgirls\b", re.IGNORECASE)),
    ("Outreach and informal learning", re.compile(r"\boutreach\b|\binformal\b|\bmuseums?\b|\bpublic engagement\b"
                                                  r"|\bcommunity\b|\bpartnership award\b", re.IGNORECASE)),
)
KIND_NAMES = tuple(name for name, _ in KINDS)
# Small grants and awards for teachers and instructors. Only curated listings carry these; the
# Grants.gov classifier never assigns them, because federal awards are not classroom mini-grants.
TEACHER_KINDS = ("Classroom grants", "Teaching awards", "Teaching travel and professional development")


def plain(text: str) -> str:
    """HTML from Grants.gov -> plain text."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


SPELLED_OUT_STEM = re.compile(r"\bscience,? technology,? engineering,? (?:and |& )?math(?:ematics)?\b", re.IGNORECASE)


def disciplines(text: str, extra: Iterable[str] = ()) -> List[str]:
    """Disciplines named in the text, plus any given (e.g. an agency's default)."""
    text = NOT_STEM.sub(" ", SPELLED_OUT_STEM.sub("STEM", text))
    found = {d for d in matching_disciplines(text) if d != "Learning Science"}
    found |= {d for d, pattern in WORD_DISCIPLINES if pattern.search(text)}
    found |= set(extra)
    return [d for d in DISCIPLINES if d in found]


def open_to_all(fields: List[str]) -> bool:
    """No specific field, or only general STEM education: open to every discipline."""
    return not fields or fields == ["Science Education"]


def kinds(text: str) -> List[str]:
    return [name for name, pattern in KINDS if pattern.search(text)]
