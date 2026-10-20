"""Fetch job postings from every source listed in sources.toml.

Each fetcher returns a list of job dicts with these keys:
  company, title, location, url, source, posted (YYYY-MM-DD or ""),
  description (plain text, may be ""), season_hint (str, may be ""),
  kind_hint ("entry", "intern", or "", optional)
"""
from __future__ import annotations

import datetime as dt
import os
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from .util import FetchError, get_json, html_to_text, parse_ats_url, post_json, strip_tracking


def _date_from_iso(s) -> str:
    if not s:
        return ""
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return str(s)[:10]


def _date_from_epoch(n, ms=False) -> str:
    try:
        n = float(n) / (1000 if ms else 1)
        return dt.datetime.fromtimestamp(n, dt.timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return ""


# ------------------------------------------------------------ GitHub lists

def fetch_simplify_list(src: dict) -> list[dict]:
    data, err = None, None
    for url in src["urls"]:
        try:
            data = get_json(url, timeout=60)
            break
        except (FetchError, ValueError) as e:
            err = e
    if data is None:
        raise FetchError(f"list not reachable ({err})")
    cats = set(src.get("categories") or [])
    jobs = []
    for item in data:
        if not item.get("active", True) or not item.get("is_visible", True):
            continue
        if cats and item.get("category") and item["category"] not in cats:
            continue
        degrees = item.get("degrees") or []
        if degrees and "Bachelor's" not in degrees:
            continue  # Master's / PhD only
        terms = [t for t in (item.get("terms") or []) if t and t != "N/A"]
        locs = item.get("locations") or []
        jobs.append({
            "company": item.get("company_name", "").strip(),
            "title": item.get("title", "").strip(),
            "location": "; ".join(locs) if isinstance(locs, list) else str(locs),
            "url": strip_tracking(item.get("url", "")),
            "source": src["name"],
            "posted": _date_from_epoch(item.get("date_posted")),
            "description": "",
            "season_hint": ", ".join(terms),
            "kind_hint": src.get("kind", ""),
        })
    return jobs


# ------------------------------------------------------------ company boards

def fetch_greenhouse(board: str, company: str) -> list[dict]:
    data = get_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true", timeout=60)
    out = []
    for j in data.get("jobs", []):
        out.append({
            "company": company,
            "title": (j.get("title") or "").strip(),
            "location": (j.get("location") or {}).get("name", ""),
            "url": j.get("absolute_url", ""),
            "source": f"{company} careers",
            "posted": _date_from_iso(j.get("first_published") or j.get("updated_at")),
            "description": html_to_text(j.get("content")),
            "season_hint": "",
        })
    return out


def _lever_text(j: dict) -> str:
    parts = [j.get("descriptionPlain") or html_to_text(j.get("description"))]
    for lst in j.get("lists") or []:
        parts.append(lst.get("text", ""))
        parts.append(html_to_text(lst.get("content")))
    parts.append(j.get("additionalPlain") or "")
    return "\n".join(p for p in parts if p)


def fetch_lever(board: str, company: str) -> list[dict]:
    data = get_json(f"https://api.lever.co/v0/postings/{board}?mode=json", timeout=60)
    out = []
    for j in data:
        cats = j.get("categories") or {}
        out.append({
            "company": company,
            "title": (j.get("text") or "").strip(),
            "location": cats.get("location") or ", ".join(cats.get("allLocations") or []),
            "url": j.get("hostedUrl") or j.get("applyUrl", ""),
            "source": f"{company} careers",
            "posted": _date_from_epoch(j.get("createdAt"), ms=True),
            "description": _lever_text(j),
            "season_hint": "",
        })
    return out


_ashby_cache: dict[str, list] = {}


def _ashby_board(board: str) -> list:
    if board not in _ashby_cache:
        data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{board}", timeout=60)
        _ashby_cache[board] = data.get("jobs", [])
    return _ashby_cache[board]


def fetch_ashby(board: str, company: str) -> list[dict]:
    out = []
    for j in _ashby_board(board):
        if j.get("isListed") is False:
            continue
        out.append({
            "company": company,
            "title": (j.get("title") or "").strip(),
            "location": j.get("location", ""),
            "url": j.get("jobUrl") or j.get("applyUrl", ""),
            "source": f"{company} careers",
            "posted": _date_from_iso(j.get("publishedAt")),
            "description": j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml")),
            "season_hint": "",
        })
    return out


def _workday_detail(host: str, tenant: str, site: str, path: str) -> dict:
    data = get_json(f"https://{host}/wday/cxs/{tenant}/{site}{path}", timeout=30)
    return data.get("jobPostingInfo") or {}


def fetch_workday(host: str, site: str, company: str, terms: list[str], wanted_title,
                  max_pages: int = 10) -> list[dict]:
    tenant = host.split(".")[0]
    api = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    postings, seen_paths = [], set()
    for term in terms:
        offset = 0
        for _ in range(max_pages):
            page = post_json(api, {"appliedFacets": {}, "limit": 20, "offset": offset,
                                   "searchText": term}, timeout=40)
            batch = page.get("jobPostings") or []
            for p in batch:
                if p.get("externalPath") not in seen_paths:
                    seen_paths.add(p.get("externalPath"))
                    postings.append(p)
            offset += len(batch)
            if not batch or offset >= int(page.get("total") or 0):
                break
    # Workday's list has no descriptions, so only open the ones worth scoring.
    wanted = [p for p in postings if wanted_title(p.get("title", ""))]

    def detail(p):
        path = p.get("externalPath", "")
        try:
            info = _workday_detail(host, tenant, site, path)
        except FetchError:
            info = {}
        loc = p.get("locationsText") or info.get("location", "")
        if re.fullmatch(r"\d+ Locations", loc.strip()):  # the list only gives a count
            loc = "; ".join(filter(None, [info.get("location")] + (info.get("additionalLocations") or []))) or loc
        return {
            "company": company,
            "title": (p.get("title") or "").strip(),
            "location": loc,
            "url": info.get("externalUrl") or f"https://{host}/{site}{path}",
            "source": f"{company} careers",
            "posted": _date_from_iso(info.get("startDate")),
            "description": html_to_text(info.get("jobDescription")),
            "season_hint": "",
        }

    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(detail, wanted))


def fetch_eightfold(host: str, domain: str, company: str, terms: list[str], wanted_title,
                    max_pages: int = 15) -> list[dict]:
    """Eightfold career sites (e.g. Microsoft). Search pages hold 10 postings
    and no description, so each wanted posting is opened for its text."""
    api = f"https://{host}/api/pcsx"
    postings, seen = [], set()
    for term in terms:
        start = 0
        for _ in range(max_pages):
            page = get_json(f"{api}/search?domain={domain}&query={urllib.parse.quote(term)}&start={start}",
                            timeout=40)
            page = page.get("data", page)
            batch = page.get("positions") or []
            for p in batch:
                if p.get("id") not in seen:
                    seen.add(p.get("id"))
                    postings.append(p)
            start += len(batch)
            if not batch or start >= int(page.get("count") or 0):
                break
    wanted = [p for p in postings if wanted_title(p.get("name", ""))]

    def detail(p):
        try:
            info = get_json(f"{api}/position_details?position_id={p['id']}&domain={domain}&hl=en", timeout=30)
            info = info.get("data", info)
        except FetchError:
            info = {}
        return {
            "company": company,
            "title": (p.get("name") or "").strip(),
            "location": "; ".join(p.get("locations") or []),
            "url": info.get("publicUrl") or f"https://{host}{p.get('positionUrl', '')}",
            "source": f"{company} careers",
            "posted": _date_from_epoch(p.get("postedTs")),
            "description": html_to_text(info.get("jobDescription")),
            "season_hint": "",
        }

    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(detail, wanted))


# ------------------------------------------------------------ USAJOBS

def fetch_usajobs(cfg: dict) -> list[dict]:
    key, email = os.environ.get("USAJOBS_API_KEY"), os.environ.get("USAJOBS_EMAIL")
    if not key or not email:
        raise FetchError("skipped: add USAJOBS_API_KEY and USAJOBS_EMAIL secrets to enable")
    headers = {"Host": "data.usajobs.gov", "User-Agent": email, "Authorization-Key": key}
    path = cfg.get("hiring_path", "graduates")
    seen, out = set(), []
    for kw in cfg.get("keywords", []):
        url = (f"https://data.usajobs.gov/api/search?ResultsPerPage=250&HiringPath={path}&Keyword="
               + urllib.parse.quote(kw))
        data = get_json(url, headers=headers, timeout=60)
        for item in (data.get("SearchResult") or {}).get("SearchResultItems", []):
            d = item.get("MatchedObjectDescriptor") or {}
            pid = d.get("PositionID") or d.get("PositionURI")
            if pid in seen:
                continue
            seen.add(pid)
            details = (d.get("UserArea") or {}).get("Details") or {}
            desc = "\n".join(filter(None, [
                details.get("JobSummary", ""), d.get("QualificationSummary", ""),
                "\n".join(details.get("MajorDuties") or []),
                "U.S. citizenship is required for federal positions.",
            ]))
            apply = (d.get("ApplyURI") or [d.get("PositionURI", "")])[0]
            out.append({
                "company": " / ".join(filter(None, [d.get("OrganizationName"), d.get("DepartmentName")])),
                "title": d.get("PositionTitle", ""),
                "location": d.get("PositionLocationDisplay", ""),
                "url": apply,
                "source": "USAJOBS",
                "posted": _date_from_iso(d.get("PublicationStartDate")),
                "description": desc,
                "season_hint": "",
                "kind_hint": "entry" if path == "graduates" else "",
            })
    return out


# ------------------------------------------------------------ run them all

def fetch_all(cfg: dict, wanted_title) -> tuple[list[dict], list[dict]]:
    """Returns (jobs, source_status). One broken source never stops the rest.
    wanted_title(title) -> bool decides which search results are worth opening."""
    wd_terms = cfg.get("workday_search") or ["new grad", "entry level", "intern"]
    ef_terms = cfg.get("eightfold_search") or ["new grad", "entry level", "intern"]
    tasks = []  # (label, kind, callable)
    for src in cfg.get("list", []):
        tasks.append((src["name"], "Job list", lambda s=src: fetch_simplify_list(s)))
    for c in cfg.get("greenhouse", []):
        tasks.append((c["name"], "Greenhouse", lambda c=c: fetch_greenhouse(c["board"], c["name"])))
    for c in cfg.get("lever", []):
        tasks.append((c["name"], "Lever", lambda c=c: fetch_lever(c["board"], c["name"])))
    for c in cfg.get("ashby", []):
        tasks.append((c["name"], "Ashby", lambda c=c: fetch_ashby(c["board"], c["name"])))
    for c in cfg.get("workday", []):
        tasks.append((c["name"], "Workday",
                      lambda c=c: fetch_workday(c["host"], c["site"], c["name"], wd_terms, wanted_title)))
    for c in cfg.get("eightfold", []):
        tasks.append((c["name"], "Eightfold",
                      lambda c=c: fetch_eightfold(c["host"], c["domain"], c["name"], ef_terms, wanted_title)))
    if "usajobs" in cfg:
        tasks.append(("USAJOBS", "Federal", lambda: fetch_usajobs(cfg["usajobs"])))

    def run(task):
        label, kind, fn = task
        try:
            jobs = fn()
            for j in jobs:
                j["source_id"] = label
            return jobs, {"name": label, "kind": kind, "ok": True, "count": len(jobs), "error": ""}
        except Exception as e:  # noqa: BLE001 - report anything, keep going
            return [], {"name": label, "kind": kind, "ok": False, "count": 0, "error": str(e)[:160]}

    jobs, status = [], []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for got, st in pool.map(run, tasks):
            jobs.extend(got)
            status.append(st)
            mark = "ok " if st["ok"] else "ERR"
            print(f"  [{mark}] {st['name']:<45} {st['count']:>5} jobs  {st['error']}")
    return jobs, status


# ------------------------------------------------------------ fill in descriptions

def _smartrecruiters_text(j: dict) -> str:
    sections = (j.get("jobAd") or {}).get("sections") or {}
    parts = []
    for key in ("jobDescription", "qualifications", "additionalInformation"):
        sec = sections.get(key) or {}
        if sec.get("text"):
            parts.append(sec.get("title") or "")
            parts.append(html_to_text(sec["text"]))
    return "\n".join(p for p in parts if p)


def fetch_description(url: str) -> str:
    """Get the full posting text for a link from a list (lists only give titles)."""
    info = parse_ats_url(url)
    if not info:
        return ""
    if info["ats"] == "greenhouse":
        j = get_json(f"https://boards-api.greenhouse.io/v1/boards/{info['board']}/jobs/{info['id']}", timeout=30)
        return html_to_text(j.get("content"))
    if info["ats"] == "lever":
        j = get_json(f"https://api.lever.co/v0/postings/{info['board']}/{info['id']}?mode=json", timeout=30)
        return _lever_text(j)
    if info["ats"] == "ashby":
        for j in _ashby_board(info["board"]):
            if j.get("id") == info["id"]:
                return j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml"))
        return ""
    if info["ats"] == "workday":
        d = _workday_detail(info["host"], info["tenant"], info["site"], info["path"])
        return html_to_text(d.get("jobDescription"))
    if info["ats"] == "smartrecruiters":
        j = get_json(f"https://api.smartrecruiters.com/v1/companies/{info['board']}/postings/{info['id']}",
                     timeout=30)
        return _smartrecruiters_text(j)
    return ""
