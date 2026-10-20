"""Check a posting's qualification bullets, one by one, against the resume.

Finds the "Qualifications / Requirements / Preferred" sections of a description,
then marks each bullet:
  met      clearly on the resume (a skill, the CS degree, a recent-grad rule...)
  partial  close but not exact (a related tool, "or related field")
  missing  clearly not (a skill not on the resume, years of experience, current students only...)
  check    needs a human to confirm (citizenship, coursework)
  soft     soft skills and logistics (not counted)
"""
from __future__ import annotations

import re

from .match import (CITIZEN_RX, CLEARANCE_RX, ENROLLED_RX, GPA_RX, GRAD_DEGREE_ONLY_RX,
                    RECENT_GRAD_RX, years_required)
from .util import hits

REQ_HEAD = re.compile(
    r"(?i)qualifications|requirements|^(basic|minimum|required|must[- ]have|essential|skills)|"
    r"you['’]ll (need|bring)|you will (need|bring)|what we['’]?re looking for|what we are looking for|"
    r"what you bring|^you have|who you are|about you|you should have|your experience|^experience")
PREF_HEAD = re.compile(r"(?i)(preferred|desired|nice[- ]to[- ]have|bonus|plus(es)?\b|additional (skills|qualifications))")
END_HEAD = re.compile(
    r"(?i)responsibilit|what you(['’]| wi)ll (do|work on)|duties|benefits|compensation|\bpay\b|salary|about|"
    r"who we are|the role|perks|schedule|why |equal opportunity|\beeo|additional information|"
    r"security clearance|physical|work environment|overview|summary|job description|the opportunity|"
    r"life at|culture|day to day|your impact|the team|location")
# Legal boilerplate headings ("Export Requirements", "E-Verify Statement") are never qualifications
SKIP_HEAD = re.compile(r"(?i)itar|export|e-verify|right to work|equal opportunity|\beeo|statement|notice|"
                       r"disclaimer|privacy|accommodation|read more")
COURSE_ONLY_RX = re.compile(r"(?i)course\s*work|\bcourses\b|\bclasses\b")
BULLET = re.compile(r"^\s*(?:[-•*▪●◦]|\d+[.)])\s*")
PLUS_RX = re.compile(r"(?i)\b(is a plus|a plus|nice to have|preferred|desired|bonus)\b")

MAJOR_RX = re.compile(r"(?i)computer science|\bcs\b|software engineering|\bstem\b|technical (field|discipline|degree)|"
                      r"quantitative field|computer engineering|information technology|any (field|major|discipline)")
RELATED_FIELD_RX = re.compile(r"(?i)related (technical |engineering |stem |science )?(field|discipline|degree|major)|equivalent")
OTHER_FIELD_RX = re.compile(r"(?i)electrical|mechanical|chemical|civil|industrial|aerospace|biomedical|physics|"
                            r"business|finance|accounting|economics|marketing|nursing|health|biology|chemistry")
GRAD_LEVEL_RX = re.compile(r"(?i)(?<!under)graduate (school|study|studies|coursework|level|research)|master['’]?s|ph\.?d|doctoral")
UNDERGRAD_RX = re.compile(r"(?i)undergrad|bachelor|b\.?s\.?\b|or equivalent")
FOREIGN_CLEARANCE_RX = re.compile(r"(?i)australian|british|\buk\b|canadian|nz government")
INTEREST_RX = re.compile(r"(?i)^(a |an )?(strong |genuine |deep )?(desire|interest|passion|enthusiasm|curiosity)\b")
DEGREE_RX = re.compile(r"(?i)\b(degree|pursuing|enrolled|major(ing)?|bachelor'?s?|undergraduate|studying|"
                       r"b\.?s\.?\b|student in)")
ACTIVE_CLEARANCE_RX = re.compile(r"(?i)(active|existing|current)\b[^\n]{0,60}?clearance|clearance required on day")
COURSEWORK_RX = re.compile(r"(?i)course\s*work|courses|classes in|knowledge of|understanding of|fundamentals|familiarity")
PROJECT_RX = re.compile(r"(?i)\b(personal projects?|side projects?|school projects?|academic projects?|team projects?|"
                        r"capstone|portfolio|github profile|open[- ]source|hackathons?)\b")
SOFT_RX = re.compile(r"(?i)communicat|teamwork|team player|collaborat|self[- ]starter|motivat|detail[- ]oriented|"
                     r"attention to detail|problem[- ]solv|enthusias|passion|independently|fast[- ]paced|eager|curious|"
                     r"initiative|ownership|organiz|prioritiz|first principles|mindset|work ethic|interpersonal|"
                     r"adaptab|willing(ness)? to learn|ability to learn|critical thinking|growth")
LOGISTICS_RX = re.compile(r"(?i)available|full[- ]time|\d+\s*hours|relocat|on[- ]?site|in[- ]person|hybrid|commut|"
                          r"\d+\s*weeks|lift \d+|travel|work authorization|sponsorship|drug|background check|"
                          r"located near|reliable transportation|start date")

MAX_ITEMS = {"required": 12, "preferred": 8}


def _is_heading(line: str) -> bool:
    s = line.strip()
    if not s or BULLET.match(line) or len(s) > 70 or s.endswith((".", ",", ";")):
        return False
    if s.endswith(":") or s.isupper():
        return True
    return len(s.split()) <= 6 and bool(REQ_HEAD.search(s) or PREF_HEAD.search(s) or END_HEAD.search(s)
                                        or SKIP_HEAD.search(s))


def extract(desc: str) -> dict[str, list[str]]:
    """Returns {"required": [...], "preferred": [...]} bullet texts."""
    out = {"required": [], "preferred": []}
    seen = set()
    section, had_bullets, lone_marker = None, False, False
    for raw in desc.splitlines():
        line = raw.strip()
        if not line:
            continue
        if BULLET.fullmatch(line):  # "-" alone on a line: its text is on the next line
            lone_marker = True
            continue
        is_bullet = bool(BULLET.match(raw)) or lone_marker
        lone_marker = False
        if not is_bullet and _is_heading(raw):
            head = line.rstrip(":").strip()
            if SKIP_HEAD.search(head):
                section = None
            elif PREF_HEAD.search(head) and len(head.split()) <= 8:
                section = "preferred"
            elif REQ_HEAD.search(head):
                section = "required"
            else:
                section = None  # Responsibilities, Benefits, Pay, About us...
            had_bullets = False
            continue
        if section is None:
            continue
        if not is_bullet and had_bullets:
            section = None  # plain paragraph after the list: the section is over
            continue
        if not is_bullet and not 4 < len(line.split()) <= 40:
            continue  # intro paragraph before the list, or a stray "Read more"
        had_bullets = had_bullets or is_bullet
        text = BULLET.sub("", line).strip()
        if len(text) < 3 or text.lower() in seen:
            continue
        seen.add(text.lower())
        sec = "preferred" if section == "required" and PLUS_RX.search(text) else section
        if len(out[sec]) < MAX_ITEMS[sec]:
            out[sec].append(text)
    return out


def _gpa(x: float) -> str:
    s = f"{x:.2f}"
    return s[:-1] if s.endswith("0") else s


class QualChecker:
    def __init__(self, matcher, profile: dict):
        self.m = matcher
        st = profile["student"]
        self.degree = st.get("degree") or st.get("major", "your degree")
        self.grad = f"{st.get('graduation_month', '')} {st['graduation_year']}".strip()
        self.gpa = float(st.get("gpa") or 0)
        self.citizen = st.get("us_citizen")  # True / False / missing = unknown
        self.project = st.get("project_blurb", "Your projects")
        self.gaps = [(g["name"], g["aliases"]) for g in matcher.gaps]

    def _one(self, b: str, coursework: bool, kind: str) -> tuple[str, str]:
        t = b.lower()
        # ---- eligibility
        if CLEARANCE_RX.search(b) or CITIZEN_RX.search(b):
            if FOREIGN_CLEARANCE_RX.search(b):
                return "missing", "Needs a foreign government clearance"
            if ACTIVE_CLEARANCE_RX.search(b):
                return "missing", "Needs a clearance you'd already have to hold"
            if self.citizen is True:
                return "met", "U.S. citizen"
            if self.citizen is False:
                return "missing", "Requires U.S. citizenship / U.S. person"
            return "check", "U.S. citizenship / U.S. person (set us_citizen in profile.toml)"
        gm = GPA_RX.search(b)
        if gm:
            need = float(gm.group(1) or gm.group(2))
            if self.gpa:
                return ("met", f"GPA {_gpa(self.gpa)} ≥ {_gpa(need)}") if self.gpa >= need else \
                       ("missing", f"Needs GPA {_gpa(need)}+")
            return "check", f"Needs GPA {_gpa(need)}+"
        yrs = years_required(b)
        if yrs is not None:
            if yrs == 0:
                return "met", "No experience required"
            if yrs == 1:
                return "partial", "Experience: asks for 1 year; project work may count"
            return "missing", f"Experience: asks for {yrs}+ years (new grad)"
        g = self.m.grad_check(b)
        if g:
            return ("met", f"Grad date rule ({g[1]}) fits {self.grad}") if g[0] else \
                   ("missing", f"Grad date rule ({g[1]}) doesn't fit {self.grad}")
        if RECENT_GRAD_RX.search(b):
            return "met", f"Recent grad ({self.grad})"
        if ENROLLED_RX.search(b):
            return "missing", f"Wants a current student (graduated {self.grad})"
        if DEGREE_RX.search(b) and not COURSE_ONLY_RX.search(b):
            if GRAD_DEGREE_ONLY_RX.search(b) or (GRAD_LEVEL_RX.search(b) and not UNDERGRAD_RX.search(b)):
                return "missing", "Asks for a graduate degree"
            if MAJOR_RX.search(b):
                return "met", f"Has a {self.degree}"
            if RELATED_FIELD_RX.search(b):
                return "partial", f"Other majors listed; {self.degree} may count as related"
            if OTHER_FIELD_RX.search(b):
                return "missing", "Wants a different major"
            return "met", f"Has a {self.degree}"
        if GRAD_LEVEL_RX.search(b) and not UNDERGRAD_RX.search(b):
            return "missing", "Asks for graduate-level experience"
        # ---- skills from the resume
        have = [s["name"] for s in self.m.skills if hits(s["aliases"], t)]
        if have:
            return "met", "Has: " + ", ".join(have[:3])
        close = [(hits(s["related"], t)[0].rstrip("*"), s["name"]) for s in self.m.skills if hits(s["related"], t)]
        if close:
            tool, base = close[0]
            return "partial", f"Close: {tool.upper() if len(tool) <= 4 else tool.title()} ≈ {base}"
        if PROJECT_RX.search(b):
            return "met", self.project
        if INTEREST_RX.search(b):
            return "soft", ""
        missing = [name for name, al in self.gaps if hits(al, t)]
        if missing:
            if coursework or COURSEWORK_RX.search(b):
                return "check", "Coursework: " + ", ".join(missing[:2]) + " (check his classes)"
            return "missing", "Not on the resume: " + ", ".join(missing[:3])
        if coursework or COURSEWORK_RX.search(b):
            return "check", "Coursework or background (check his classes)"
        if SOFT_RX.search(b) or LOGISTICS_RX.search(b):
            return "soft", ""
        return "check", ""

    def check(self, desc: str, kind: str = "full-time") -> dict | None:
        found = extract(desc)
        if not found["required"] and not found["preferred"]:
            return None
        result = {}
        for sec, items in found.items():
            rows, coursework = [], False
            for b in items:
                if b.endswith(":"):  # "Coursework in:" / "Experience with:" introduces sub-bullets
                    coursework = bool(COURSEWORK_RX.search(b))
                    continue
                status, why = self._one(b, coursework, kind)
                rows.append({"text": b[:160], "status": status, "why": why})
            result[sec] = rows
        req = [r for r in result.get("required", []) if r["status"] in ("met", "partial", "missing")]
        met = sum(1 for r in req if r["status"] == "met") + 0.5 * sum(1 for r in req if r["status"] == "partial")
        result["summary"] = {
            "required_checked": len(req),
            "required_met": met,
            "required_missing": sum(1 for r in req if r["status"] == "missing"),
            "to_check": sum(1 for sec in ("required", "preferred") for r in result.get(sec, [])
                            if r["status"] == "check" and r["why"]),
            "preferred_met": sum(1 for r in result.get("preferred", []) if r["status"] == "met"),
            "preferred_total": sum(1 for r in result.get("preferred", []) if r["status"] in ("met", "partial", "missing")),
        }
        return result
