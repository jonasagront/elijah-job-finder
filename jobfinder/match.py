"""Decide whether a posting is an entry-level software / AI / data job (or an
internship a recent grad can take), and how well it fits the resume.

Score out of 100:
  up to 40  how clearly it's software / AI / data work
  up to 35  how many of the resume's skills the posting asks for
  up to 25  eligibility (entry level, years of experience, student-only, degree level)
"""
from __future__ import annotations

import datetime as dt
import re

from .util import compile_terms, hits

INTERN_RX = re.compile(r"(?i)(?<![a-z])(intern|interns|internship|internships|co-?op|co op)(?![a-z])")

SEASON_WORDS = r"(summer|fall|autumn|spring|winter)"
SEASON_RX = re.compile(rf"(?i)(?<![a-z]){SEASON_WORDS}\s*(?:of\s*)?'?(20)?(2[5-9]|3[0-1])(?![0-9])"
                       rf"|(?<![0-9])(20)?(2[5-9]|3[0-1])\s*{SEASON_WORDS}")
SEASON_END_MONTH = {"spring": 5, "summer": 8, "fall": 12, "winter": 3}
GRAD_RX = re.compile(r"(?i)graduat\w*")
YEAR_RX = re.compile(r"(?<![0-9])(20[2-3]\d)(?![0-9])")
GPA_RX = re.compile(
    r"(?i)(?:gpa|grade point average)[^.\n]{0,40}?([2-4]\.\d{1,2})"
    r"|([2-4]\.\d{1,2})\s*(?:/\s*4\.0\s*)?(?:cumulative\s*|overall\s*|minimum\s*)?(?:gpa|grade point)")
CITIZEN_RX = re.compile(
    r"(?i)u\.?\s?s\.?\s+citizen|united states citizen|u\.?\s?s\.?\s+person|\bitar\b|"
    r"export[- ]control|lawful permanent resident|green card|citizenship is required")
CLEARANCE_RX = re.compile(
    r"(?i)security clearance|secret clearance|top secret|ts/sci|obtain (?:and maintain )?(?:a |an )?"
    r"(?:dod |government )?clearance|clearance (?:is )?required")
GRAD_DEGREE_ONLY_RX = re.compile(
    r"(?i)(pursuing|enrolled in) an? (master'?s|ph\.?d|doctoral|graduate) (degree|program)"
    r"(?! or)(?!.{0,30}bachelor)|graduate students only|ph\.?d\.? (candidate|student)s? only")
# Internships that want someone still in school
ENROLLED_RX = re.compile(
    r"(?i)currently enrolled|currently pursuing|actively pursuing|"
    r"must be (?:a |an )?(?:current(?:ly)? )?(?:enrolled )?student|returning to (?:school|your studies|their studies)|"
    r"enrolled (?:full[- ]time )?in an? (?:accredited )?(?:college|university|degree)|"
    r"pursuing an? (?:bachelor|undergraduate|b\.?s\.?|degree)|current (?:undergraduate|college|university) students?|"
    r"rising (?:junior|senior)s?|(?:junior|senior) standing|at least one (?:semester|quarter|term) remaining")
RECENT_GRAD_RX = re.compile(
    r"(?i)recent (?:college |university )?grad|new grad|new college grad|graduated (?:with)?in the (?:last|past)|"
    r"within the (?:last|past) (?:12|twelve|18|24) months|early[- ]career|entry[- ]level|"
    r"no (?:prior |previous )?(?:professional )?experience (?:is )?(?:required|necessary)")
STUDENT_RX = re.compile(r"(?i)\b(?:students?|undergrad\w*|sophomores?)\b")
# Internships that explicitly take people who already graduated (narrower: intern
# postings mention "early career" and "recent grads on our team" all the time)
INTERN_GRAD_OK_RX = re.compile(
    r"(?i)(?:or|and) (?:have )?recently graduated|(?:or|and) (?:are )?(?:a )?recent (?:college |university )?graduates?\b"
    r"|graduated (?:with)?in the (?:last|past) (?:\d+|six|twelve)|open to recent grad"
    r"|within (?:the )?(?:last |past )?(?:\d+|six|twelve) months (?:of|after) (?:graduat|complet)")
# "3+ years of experience", "2-4 years of professional experience", "Experience: 5+ years"
YEARS_RX = re.compile(
    r"(?i)(?:minimum of |at least )?(\d{1,2})\s*(?:\+|plus)?\s*(?:(?:-|–|to)\s*\d{1,2}\s*\+?\s*)?(?:years?|yrs?)\b"
    r"(?:\s+of)?[^.\n;]{0,60}?\bexperience"
    r"|experience\s*[:\-–]\s*(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b")
PREF_LINE_RX = re.compile(r"(?i)preferred|nice[- ]to[- ]have|a plus|bonus|ideally|desired")
PREF_HEAD_RX = re.compile(r"(?i)preferred|nice[- ]to[- ]have|bonus|desired|additional")
REQ_HEAD_RX = re.compile(r"(?i)required|minimum|basic|qualifications|requirements|what you|who you are|about you")
DEGREE_OR_RX = re.compile(r"(?i)degree[^.\n]{0,60}\bor\b[^.\n]{0,20}$")

# ---- where a job is: "us", "foreign", or "unknown" ("16 Locations", "")
US_STATES = ("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ "
             "NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC PR").split()
US_RX = re.compile(
    r"(?i)united states|\busa\b|\bu\.s\.|^us\b|\bus-|remote|"
    r"\b(alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|"
    r"illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|"
    r"mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|"
    r"north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|"
    r"south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming)\b|"
    r"\b(san francisco|sf|nyc|los angeles|pittsburgh|seattle|boston|denver|houston|austin|"
    r"chicago|san diego|phoenix|albuquerque|orlando|tampa|miami|fort lauderdale|boca raton|jacksonville|"
    r"west palm beach|plantation|sunrise|atlanta|dallas|fort worth|san antonio|salt lake|las vegas|"
    r"sacramento|san jose|palo alto|mountain view|sunnyvale|menlo park|redwood city|irvine|santa clara|"
    r"bellevue|kirkland|redmond|cambridge|detroit|cleveland|minneapolis|st\.? louis|mclean|arlington|"
    r"raleigh|durham|charlotte|columbus|nashville|portland|philadelphia|baltimore|reston|herndon|bay area)\b")
US_STATE_RX = re.compile(r"(?:,|\s-)\s*(" + "|".join(US_STATES) + r")\b")
FOREIGN_RX = re.compile(
    r"(?i)\b(canada|united kingdom|(?<!new )england|scotland|wales|germany|deutschland|france|poland|turkey|"
    r"t[uü]rkiye|india|singapore|japan|australia|new zealand|israel|netherlands|spain|italy|(?<!new )mexico|"
    r"brazil|ireland|"
    r"luxembourg|switzerland|sweden|norway|denmark|finland|belgium|austria|czech|hungary|romania|portugal|"
    r"greece|china|korea|taiwan|philippines|malaysia|indonesia|vietnam|thailand|uae|emirates|saudi|qatar|"
    r"south africa|argentina|chile|colombia|ukraine|estonia|lithuania|latvia|serbia|costa rica|"
    r"ontario|quebec|british columbia|alberta|nova scotia|manitoba|"
    r"toronto|montreal|vancouver|calgary|ottawa|markham|waterloo|bengaluru|bangalore|hyderabad|pune|chennai|"
    r"gurgaon|gurugram|noida|mumbai|tel aviv|tokyo|sydney|melbourne(?!,? fl)|auckland|warsaw|krakow|istanbul|"
    r"prague|bucharest|madrid|barcelona|milan|amsterdam|dublin|zurich|munich|m[uü]nchen|berlin|hamburg|"
    r"london|paris|stockholm|copenhagen|seoul|shanghai|beijing|shenzhen|hong kong|dubai|abu dhabi|lisbon|"
    r"manila|s[aã]o paulo|buenos aires|bogot[aá]|uk|nz)\b|^(gbr|deu|esp|fra|ita|pol|tur|ind|can|aus|nzl|jpn|"
    r"sgp|isr|nld|mex|bra|irl|che|swe|nor|dnk|bel|aut|cze|rou|prt|chn|kor|twn|phl|mys|are|sau)\s*-|"
    r",\s*(ON|BC|QC|AB|MB|NS|NB|SK|NL|PE)\b")


def where(location: str) -> str:
    """Is this location in the U.S.? A posting with any U.S. option counts as U.S."""
    parts = [p.strip() for p in re.split(r"[;|]| / ", location or "") if p.strip()]
    seen = set()
    for p in parts:
        if FOREIGN_RX.search(p) and not re.search(r"(?i)united states|\busa\b|^us-", p):
            seen.add("foreign")
        elif US_RX.search(p) or US_STATE_RX.search(p):
            seen.add("us")
    return "us" if "us" in seen else "foreign" if "foreign" in seen else "unknown"


def years_required(desc: str) -> int | None:
    """Smallest number of years a posting *requires* (preferred lines are skipped).
    With several requirements ("3+ years of software, 1+ year of AWS") the largest wins."""
    found = []
    preferred = False
    for line in desc.splitlines():
        s = line.strip()
        if not s:
            continue
        if len(s) <= 70 and not re.match(r"^\s*[-•*▪●◦]", line):  # a heading
            if PREF_HEAD_RX.search(s):
                preferred = True
            elif REQ_HEAD_RX.search(s):
                preferred = False
        if preferred or PREF_LINE_RX.search(s):
            continue
        for m in YEARS_RX.finditer(s):
            n = int(m.group(1) or m.group(2))
            if n > 15:
                continue  # "our 20 years of experience" is about the company
            if DEGREE_OR_RX.search(s[:m.start()]):
                continue  # "a degree or 4 years of equivalent experience"
            found.append(n)
    return max(found) if found else None


class Matcher:
    def __init__(self, profile: dict, sources_cfg: dict):
        self.p = profile
        st = profile["student"]
        se = profile["search"]
        self.grad_year = int(st["graduation_year"])
        self.gpa = float(st.get("gpa") or 0)
        self.max_years = int(se.get("max_years_experience", 4))
        self.include_interns = bool(se.get("include_internships", True))
        self.min_score = int(se.get("min_score", 40))
        self.max_age = int(se.get("max_age_days", 150))
        self.us_only = bool(se.get("us_only", False))

        rel = profile["relevance"]
        self.t_strong = compile_terms(rel["title_strong"])
        self.t_medium = compile_terms(rel["title_medium"])
        self.t_weak = compile_terms(rel["title_weak"])
        self.text_kw = compile_terms(rel["text_keywords"])
        self.majors = {k.lower(): v for k, v in rel.get("majors", {}).items()}
        self.entry = compile_terms(rel.get("entry", {}).get("title", []))
        self.exclude = compile_terms(rel.get("exclude", {}).get("title", []))
        self.exclude_always = compile_terms(rel.get("exclude", {}).get("title_always", []))

        loc = profile.get("location", {})
        self.home = compile_terms(loc.get("home", []))
        self.remote = compile_terms(loc.get("remote", []))

        self.skills = []
        for s in profile.get("skill", []):
            self.skills.append({
                "name": s["name"], "weight": int(s.get("weight", 1)),
                "aliases": compile_terms(s.get("aliases", [])),
                "related": compile_terms(s.get("related", [])),
            })
        self.gaps = [{"name": g["name"], "aliases": compile_terms(g.get("aliases", []))}
                     for g in profile.get("gap", [])]
        self.tech_companies = [re.compile(r"(?<![a-z0-9])" + re.escape(n.lower()) + r"(?![a-z0-9])")
                               for n in sources_cfg.get("tech_companies", {}).get("names", [])]
        self.qc = None  # set by run.py to a quals.QualChecker

    # ---------------------------------------------------------- quick filter

    def title_ok(self, title: str) -> tuple[bool, str]:
        """Cheap check before fetching anything else."""
        t = title.lower()
        if hits(self.exclude_always, t):
            return False, "too senior or grad-degree role"
        if INTERN_RX.search(t) and not self.include_interns:
            return False, "internship"
        if not (hits(self.t_strong, t) or hits(self.t_medium, t) or hits(self.t_weak, t)):
            return False, "not a tech role"
        if hits(self.exclude, t) and not hits(self.t_strong, t):
            return False, "not a tech role"
        return True, ""

    def wanted_title(self, title: str) -> bool:
        return self.title_ok(title)[0]

    def is_tech_company(self, company: str) -> bool:
        c = company.lower()
        return any(rx.search(c) for rx in self.tech_companies)

    def near_home(self, location: str) -> str:
        """"home" for Florida, "remote" for remote, "" otherwise."""
        loc = (location or "").lower()
        if hits(self.home, loc):
            return "home"
        if hits(self.remote, loc):
            return "remote"
        return ""

    # ---------------------------------------------------------- season

    @staticmethod
    def season_of(text: str) -> tuple[str, str]:
        """Returns (status, label). status: past | upcoming | none"""
        found = set()
        for m in SEASON_RX.finditer(text):
            s1, _c1, y1, _c2, y2, s2 = m.groups()
            season = (s1 or s2 or "").lower().replace("autumn", "fall")
            found.add((season, 2000 + int(y1 or y2)))
        if not found:
            return "none", ""
        today = dt.date.today()
        upcoming = [(s, y) for s, y in found if (y, SEASON_END_MONTH[s]) >= (today.year, today.month)]
        if not upcoming:
            s, y = max(found, key=lambda x: (x[1], SEASON_END_MONTH[x[0]]))
            return "past", f"{s.title()} {y}"
        s, y = min(upcoming, key=lambda x: (x[1], SEASON_END_MONTH[x[0]]))
        return "upcoming", f"{s.title()} {y}"

    # ---------------------------------------------------------- eligibility

    def grad_check(self, text: str) -> tuple[bool, str] | None:
        """Look for graduation-date windows like 'graduating between Dec 2025 and Aug 2026'."""
        problems, oks = [], []
        for m in GRAD_RX.finditer(text):
            window = text[max(0, m.start() - 30): m.end() + 110]
            years = sorted({int(y) for y in YEAR_RX.findall(window)})
            years = [y for y in years if 2022 <= y <= 2032]
            if not years:
                continue
            w = window.lower()
            lo, hi = min(years), max(years)
            if re.search(r"or later|or after|and later|and beyond|after", w) and len(years) == 1:
                ok = self.grad_year >= lo
            elif re.search(r"or (before|earlier|sooner)|no later than|prior to|by ", w) and len(years) == 1:
                ok = self.grad_year <= hi
            elif len(years) >= 2:
                ok = lo <= self.grad_year <= hi
            else:
                ok = self.grad_year == lo
            label = f"{lo}" if lo == hi else f"{lo}–{hi}"
            (oks if ok else problems).append(label)
        if problems:
            return False, problems[0]
        if oks:
            return True, oks[0]
        return None

    # ---------------------------------------------------------- main

    def analyze(self, job: dict) -> tuple[dict | None, str]:
        """Returns (analysis, drop_reason). analysis is None when the job is dropped."""
        title = job.get("title", "")
        desc = job.get("description") or ""
        t = title.lower()
        d = desc.lower()
        full = f"{t}\n{d}"

        ok, why = self.title_ok(title)
        if not ok:
            return None, why

        kind = "intern" if INTERN_RX.search(t) or job.get("kind_hint") == "intern" else "full-time"
        entry_title = bool(hits(self.entry, t))
        entry_source = job.get("kind_hint") == "entry"

        # Too old?
        if job.get("posted"):
            try:
                age = (dt.date.today() - dt.date.fromisoformat(job["posted"][:10])).days
                if age > self.max_age:
                    return None, "posting too old"
            except ValueError:
                pass

        # Outside the U.S.? (unknown locations like "16 Locations" are kept)
        if self.us_only and where(job.get("location", "")) == "foreign":
            return None, "outside the U.S."

        # Internship for a season that's already over? (titles and list tags only;
        # descriptions mention past seasons for all kinds of reasons)
        season_status, season_label = self.season_of(
            f"{job.get('season_hint', '')}\n{title}" + (f"\n{desc}" if kind == "intern" else ""))
        if season_status == "past":
            return None, "season already over"

        years = years_required(desc) if desc else None
        if years is not None and years > self.max_years:
            return None, "too much experience required"

        # ---- role fit (0-40)
        strong, medium, weak = hits(self.t_strong, t), hits(self.t_medium, t), hits(self.t_weak, t)
        best = 3 if strong else 2 if medium else 1 if weak else 0
        text_hits = hits(self.text_kw, d)
        major_pts = max([v for k, v in self.majors.items() if k in d] or [0])
        tech_co = self.is_tech_company(job.get("company", ""))

        if desc:
            if best <= 1 and len(text_hits) < 3 and major_pts < 6:
                return None, "not a tech role"
            if best == 2 and len(text_hits) < 2 and major_pts < 4 and not tech_co:
                return None, "not a tech role"
        else:
            if best == 1 and not (tech_co or entry_source):
                return None, "not a tech role"

        relevance = {3: 22, 2: 14, 1: 6, 0: 0}[best]
        relevance += 4 * min(2, max(0, len(strong) + len(medium) - 1))
        relevance += min(10, 2 * len(text_hits))
        relevance += major_pts
        relevance += 6 if tech_co else 0
        relevance = min(40, relevance)

        # ---- skills (0-35)
        matched, related, gaps = [], [], []
        related_terms = set()
        if desc:
            weight = 0.0
            for s in self.skills:
                found = hits(s["aliases"], full)
                if found:
                    matched.append(s["name"])
                    # A posting that mentions a skill several ways leans on it hard
                    weight += s["weight"] * (1 + 0.5 * min(2, len(found) - 1))
                else:
                    rel = hits(s["related"], full)
                    if rel:
                        tool = rel[0].rstrip("*")
                        tool = tool.upper() if len(tool) <= 4 else tool.title()
                        related.append(f"{tool} (close to {s['name']})")
                        related_terms.update(r.rstrip("*") for r in rel)
                        weight += s["weight"] / 2
            for g in self.gaps:
                g_hits = hits(g["aliases"], d)
                if g_hits and not (set(h.rstrip("*") for h in g_hits) <= related_terms):
                    gaps.append(g["name"])
            skills_pts = min(35, round(weight * 3))
        else:
            skills_pts = 12  # unknown: neutral

        # ---- eligibility (0-25)
        flags = []
        elig = 25
        cap = 100  # hard limits: a posting he likely can't get never ranks as a strong fit
        if kind == "intern":
            flags.append({"kind": "info", "label": "Internship" + (f" · {season_label}" if season_label else "")})
        elif entry_title or entry_source:
            flags.append({"kind": "good", "label": "Entry level"})

        if desc:
            recent_ok = bool(RECENT_GRAD_RX.search(desc))
            if years is not None:
                if years == 0:
                    flags.append({"kind": "good", "label": "No experience required"})
                elif years == 1:
                    flags.append({"kind": "info", "label": "Asks 1+ year experience"})
                    elig -= 4
                else:
                    flags.append({"kind": "warn", "label": f"Asks {years}+ years experience"})
                    elig -= 10 if years == 2 else 18
                    if years >= 3:
                        cap = min(cap, 55)
            elif kind != "intern" and not (entry_title or entry_source or recent_ok):
                flags.append({"kind": "info", "label": "Level not stated"})
                elig -= 6
            if kind == "intern":
                # Internships are for students unless they say graduates can apply
                if INTERN_GRAD_OK_RX.search(desc):
                    flags.append({"kind": "good", "label": "Open to recent grads"})
                elif ENROLLED_RX.search(desc) or STUDENT_RX.search(desc):
                    flags.append({"kind": "warn", "label": "Wants a current student"})
                    elig -= 14
                    cap = min(cap, 50)
                else:
                    flags.append({"kind": "info", "label": "Ask if grads can apply"})
                    elig -= 6
                    cap = min(cap, 60)
            elif recent_ok and not (entry_title or entry_source):
                flags.append({"kind": "good", "label": "Open to new grads"})
            g = self.grad_check(desc)
            if g:
                ok, label = g
                if ok:
                    flags.append({"kind": "good", "label": f"Grad window {label} fits"})
                else:
                    flags.append({"kind": "warn", "label": f"Grad window {label}"})
                    elig -= 12
            if GRAD_DEGREE_ONLY_RX.search(desc):
                flags.append({"kind": "warn", "label": "Grad students only?"})
                elig -= 18
                cap = min(cap, 50)
            gm = GPA_RX.search(desc)
            if gm:
                need = float(gm.group(1) or gm.group(2))
                if 2.0 <= need <= 4.0:
                    if self.gpa and self.gpa < need:
                        flags.append({"kind": "warn", "label": f"Min GPA {need:.1f}"})
                        elig -= 12
                    else:
                        flags.append({"kind": "info", "label": f"Min GPA {need:.1f}"})
            if CITIZEN_RX.search(desc) or job.get("source") == "USAJOBS":
                flags.append({"kind": "info", "label": "U.S. person / ITAR", "id": "citizen"})
            if CLEARANCE_RX.search(desc):
                flags.append({"kind": "info", "label": "Clearance", "id": "clearance"})
        else:
            if kind == "intern":
                elig -= 6  # most internships want a current student
                cap = min(cap, 58)
            flags.append({"kind": "info", "label": "Full description not loaded"})
        elig = max(0, elig)

        near = self.near_home(job.get("location", ""))
        if near == "home":
            flags.insert(0, {"kind": "good", "label": "Florida"})
        elif near == "remote":
            flags.insert(0, {"kind": "good", "label": "Remote"})

        # ---- qualification-by-qualification check (see quals.py)
        quals = self.qc.check(desc, kind) if (self.qc and desc) else None
        req_penalty = 0
        if quals:
            # Skip misses the eligibility points above already took off
            already = ("Grad date", "Asks for a grad", "Wants a current", "Experience:", "Needs GPA")
            hard = [r for r in quals.get("required", [])
                    if r["status"] == "missing" and not r["why"].startswith(already)]
            req_penalty = min(15, 5 * len(hard))

        raw = int(max(0, min(100, relevance + skills_pts + elig) - req_penalty))
        score = min(raw, cap)
        if score < self.min_score:
            return None, "low score"
        tier = "strong" if score >= 72 else "good" if score >= 56 else "look"

        return {
            "score": score,
            "tier": tier,
            "parts": {"role": relevance, "skills": skills_pts, "eligibility": elig,
                      "requirements": -req_penalty, "capped": cap if raw > cap else 0},
            "quals": quals,
            "matched": matched,
            "related": related,
            "gaps": gaps,
            "flags": flags,
            "kind": kind,
            "near": near,
            "years": years,
            "has_description": bool(desc),
        }, ""
