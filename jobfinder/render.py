"""Build docs/index.html (the job page) and the table at the top of README.md."""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Entry-level tech jobs</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>💻</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#F6F4EF; --panel:#FFFFFF; --ink:#1B1A2E; --muted:#5D5B70; --line:#DDD9CF;
  --strong:#0F7B6C; --good:#4B47B8; --look:#A8610B; --warn:#B23A48;
  --chip:#F0EEE8; --focus:#4B47B8; --accent:#4B47B8;
  --head:"Space Grotesk","Segoe UI",Arial,sans-serif;
  --body:"IBM Plex Sans","Segoe UI",Roboto,Arial,sans-serif;
  --mono:"IBM Plex Mono",Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#121220; --panel:#1C1B2E; --ink:#ECEAF6; --muted:#A3A1B8; --line:#2F2D45;
  --strong:#3CC3AE; --good:#9C98FF; --look:#E8A94A; --warn:#F07A88; --chip:#26253B; --focus:#9C98FF; --accent:#9C98FF;
}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 var(--body)}
a{color:inherit}
:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
.wrap{max-width:1040px;margin:0 auto;padding:32px 16px 64px}
header .eyebrow{font:600 13px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin:0 0 10px}
header h1{font:700 clamp(28px,5vw,44px)/1.05 var(--head);letter-spacing:-.02em;margin:0 0 8px}
header p{margin:0;color:var(--muted)}
.counts{display:flex;flex-wrap:wrap;gap:6px 20px;margin-top:16px;font:500 15px/1.3 var(--body);color:var(--muted)}
.counts b{font:600 22px/1 var(--mono);color:var(--ink);margin-right:6px}
.controls{position:sticky;top:0;z-index:5;background:var(--bg);padding:14px 0 12px;margin-top:18px;border-bottom:1px solid var(--line);display:grid;gap:10px}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
input[type=search]{flex:1 1 240px;min-width:0;font:inherit;padding:9px 12px;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--ink)}
select{font:inherit;padding:8px 10px;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--ink)}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:var(--panel)}
.seg button{font:600 14px/1 var(--head);padding:9px 12px;border:0;background:transparent;color:var(--muted);cursor:pointer}
.seg button[aria-pressed=true]{background:var(--accent);color:var(--bg)}
label.tog{display:inline-flex;gap:6px;align-items:center;font-size:14px;color:var(--muted);cursor:pointer}
.gapbox{margin:20px 0 6px;background:var(--panel);border:1px solid var(--line);border-radius:12px}
.gapbox summary{cursor:pointer;padding:12px 16px;font:600 17px/1.3 var(--head)}
.gapbox .inner{padding:0 16px 16px;display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}
.gapbox h3{font:600 14px/1.3 var(--body);margin:0 0 8px;color:var(--muted)}
.bar{display:grid;grid-template-columns:170px 1fr 40px;gap:8px;align-items:center;font-size:14px;margin:4px 0}
.bar i{display:block;height:8px;border-radius:4px;background:var(--chip)}
.bar i span{display:block;height:100%;border-radius:4px}
.bar em{font:500 13px/1 var(--mono);font-style:normal;color:var(--muted);text-align:right}
#list{display:grid;gap:12px;margin-top:16px}
.strip{display:grid;grid-template-columns:84px 1fr auto;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.strip.done{opacity:.55}
.score{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:10px 4px;border-right:1px solid var(--line)}
.score b{font:600 30px/1 var(--mono)}
.score small{font:600 11px/1.2 var(--body);margin-top:4px;text-align:center;text-transform:uppercase;letter-spacing:.04em}
.t-strong .score{color:var(--strong)} .t-good .score{color:var(--good)} .t-look .score{color:var(--look)}
.t-strong{border-left:4px solid var(--strong)} .t-good{border-left:4px solid var(--good)} .t-look{border-left:4px solid var(--look)}
.main{padding:12px 16px;min-width:0}
.co{font:600 14px/1.3 var(--body);color:var(--muted)}
.title{font:600 20px/1.25 var(--head);margin:2px 0 4px}
.meta{font-size:14px;color:var(--muted);display:flex;flex-wrap:wrap;gap:2px 14px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.chip{font-size:13px;padding:2px 9px;border-radius:999px;background:var(--chip);border:1px solid transparent}
.chip.good{border-color:var(--strong);color:var(--strong)}
.chip.warn{border-color:var(--warn);color:var(--warn)}
.chip.new{background:var(--accent);color:var(--bg);font-weight:600}
details.why{margin-top:8px}
details.why summary{cursor:pointer;font-size:14px;font-weight:600;color:var(--accent)}
.why dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 12px;margin:8px 0 0;font-size:14px}
.why dt{color:var(--muted)} .why dd{margin:0}
.ai{margin-top:8px;padding:8px 10px;border-left:3px solid var(--accent);background:var(--chip);border-radius:0 8px 8px 0;font-size:14px}
.acts{display:flex;flex-direction:column;gap:8px;padding:12px 14px 12px 0;justify-content:center}
.btn{font:600 15px/1 var(--head);text-decoration:none;text-align:center;padding:10px 16px;border-radius:10px;border:1px solid var(--accent);background:var(--accent);color:var(--bg);white-space:nowrap;cursor:pointer}
.btn.ghost{background:transparent;color:var(--ink);border-color:var(--line);font-weight:500}
.qh{font:600 13px/1.3 var(--mono);margin:10px 0 0;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.ql{list-style:none;margin:4px 0 0;padding:0;display:grid;gap:5px;font-size:14px}
.ql li{display:grid;grid-template-columns:18px 1fr;gap:6px}
.ql b{text-align:center} .ql small{display:block;color:var(--muted)}
.q-met b{color:var(--strong)} .q-partial b{color:var(--look)} .q-missing b{color:var(--warn)} .q-check b,.q-soft b{color:var(--muted)}
.shown{margin:12px 0 0;font:500 14px/1.3 var(--mono);color:var(--muted)}
.empty{padding:40px 20px;text-align:center;background:var(--panel);border:1px dashed var(--line);border-radius:12px;color:var(--muted)}
footer{margin-top:36px;font-size:14px;color:var(--muted)}
footer details summary{cursor:pointer;font-weight:600}
footer table{border-collapse:collapse;margin-top:8px;width:100%;font-size:13px}
footer td,footer th{text-align:left;padding:4px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.tbl{overflow-x:auto}
@media (max-width:640px){
  .strip{grid-template-columns:64px 1fr}
  .score b{font-size:24px}
  .acts{grid-column:1/-1;flex-direction:row;padding:0 12px 12px}
  .acts .btn{flex:1}
  .bar{grid-template-columns:130px 1fr 36px}
}
@media (prefers-reduced-motion:no-preference){.strip{transition:opacity .2s}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <p class="eyebrow" id="eyebrow">Job finder</p>
  <h1>Entry-level tech jobs &amp; internships</h1>
  <p id="sub"></p>
  <div class="counts" id="counts"></div>
</header>

<details class="gapbox" id="gapbox">
  <summary>What these postings ask for</summary>
  <div class="inner">
    <div><h3>Resume skills that come up most</h3><div id="have"></div></div>
    <div><h3>Skills to learn next (not on the resume yet)</h3><div id="need"></div></div>
  </div>
</details>

<div class="controls">
  <div class="row">
    <input type="search" id="q" placeholder="Search company, title, location, skill" aria-label="Search">
    <select id="sort" aria-label="Sort">
      <option value="score">Best fit first</option>
      <option value="reqs">Most qualifications met</option>
      <option value="new">Newest first</option>
      <option value="company">Company A to Z</option>
    </select>
  </div>
  <div class="row">
    <div class="seg" role="group" aria-label="Fit" id="tierSeg">
      <button data-v="all" aria-pressed="true">All</button>
      <button data-v="strong" aria-pressed="false">Strong fit</button>
      <button data-v="good" aria-pressed="false">Good fit</button>
      <button data-v="look" aria-pressed="false">Worth a look</button>
    </div>
    <div class="seg" role="group" aria-label="Job type" id="kindSeg">
      <button data-v="all" aria-pressed="true">All roles</button>
      <button data-v="full-time" aria-pressed="false">Full-time</button>
      <button data-v="intern" aria-pressed="false">Internships</button>
    </div>
  </div>
  <div class="row">
    <label class="tog"><input type="checkbox" id="onlyNear"> Florida or remote</label>
    <label class="tog"><input type="checkbox" id="onlyNew"> Posted this week</label>
    <label class="tog"><input type="checkbox" id="hideDone" checked> Hide applied and dismissed</label>
  </div>
</div>

<p class="shown" id="shown" aria-live="polite"></p>
<div id="list"></div>

<footer>
  <p id="foot"></p>
  <details>
    <summary>Sources checked on this run</summary>
    <div class="tbl"><table id="src"></table></div>
  </details>
</footer>
</div>

<script id="data" type="application/json">__DATA__</script>
<script>
(function(){
const D = JSON.parse(document.getElementById('data').textContent);
const store = {
  get(){ try { return JSON.parse(localStorage.getItem('ejf-status') || '{}'); } catch(e){ return {}; } },
  set(v){ try { localStorage.setItem('ejf-status', JSON.stringify(v)); } catch(e){} }
};
let status = store.get();
let tier = 'all', kind = 'all';
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = iso => { if(!iso) return ''; const d = new Date(iso + 'T12:00:00'); return d.toLocaleDateString(undefined,{month:'short',day:'numeric'}); };
const TIER = {strong:'Strong fit', good:'Good fit', look:'Worth a look'};
const weekAgo = new Date(Date.parse(D.today + 'T12:00:00') - 7*864e5).toISOString().slice(0,10);
const ageDays = iso => iso ? Math.round((Date.parse(D.today + 'T12:00:00') - Date.parse(iso + 'T12:00:00')) / 864e5) : null;
// "This week" goes by the posting date; first_seen only when a source gives no date
const postedThisWeek = j => (j.posted || j.first_seen) >= weekAgo;

$('eyebrow').textContent = `${D.name}'s job finder`;
$('sub').textContent = D.sources.length ? `Scored against ${D.name}'s resume (${D.degree}). Updated ${D.updated_label}.` : 'Waiting for the first scan.';
const c = D.counts;
$('counts').innerHTML = `<span><b>${c.total}</b>matches</span><span><b>${c.strong}</b>strong fits</span><span><b>${c.fulltime}</b>full-time</span><span><b>${c.near}</b>Florida or remote</span><span><b>${c.new_today}</b>new today</span>`;

function bars(list, color){
  if(!list.length) return '<p style="color:var(--muted);font-size:14px;margin:0">Not enough descriptions yet.</p>';
  return list.map(g => `<div class="bar"><span>${esc(g.name)}</span><i><span style="width:${g.pct}%;background:${color}"></span></i><em>${g.pct}%</em></div>`).join('');
}
$('have').innerHTML = bars(D.have, 'var(--strong)');
$('need').innerHTML = bars(D.need, 'var(--warn)');

$('src').innerHTML = '<tr><th>Source</th><th>Type</th><th>Result</th></tr>' + D.sources.map(s =>
  `<tr><td>${esc(s.name)}</td><td>${esc(s.kind)}</td><td>${s.ok ? s.count + ' postings read' : 'Failed: ' + esc(s.error)}</td></tr>`).join('');
const bad = D.sources.filter(s => !s.ok && !String(s.error).startsWith('skipped')).length;
$('foot').textContent = `${D.sources.length} sources checked` + (bad ? `, ${bad} failed (see below; fix or remove them in sources.toml).` : '.') + ' Scores are keyword-based estimates. Always read the posting before applying.';

const QI = {met:'✓', partial:'~', missing:'✗', check:'?', soft:'·'};
const num = x => Number.isInteger(x) ? x : x.toFixed(1);
const reqPct = j => { const s = j.quals && j.quals.summary; return s && s.required_checked ? s.required_met / s.required_checked : -1; };
function qualChip(q){
  const s = q && q.summary;
  if(!s || !s.required_checked) return '';
  const cls = s.required_missing ? 'warn' : s.required_met === s.required_checked ? 'good' : '';
  return `<span class="chip ${cls}">Meets ${num(s.required_met)} of ${s.required_checked} required</span>`;
}
function qualList(q){
  if(!q) return '';
  const sec = (name, rows) => rows && rows.length ? `<div class="qh">${name}</div><ul class="ql">` + rows.map(r =>
    `<li class="q-${r.status}"><b>${QI[r.status]}</b><span>${esc(r.text)}${r.why ? `<small>${esc(r.why)}</small>` : (r.status === 'check' ? '<small>Couldn\'t check this one automatically</small>' : '')}</span></li>`).join('') + '</ul>' : '';
  const s = q.summary;
  const head = s.required_checked ? `Meets ${num(s.required_met)} of ${s.required_checked} required qualifications that could be checked` +
    (s.preferred_total ? `, and ${s.preferred_met} of ${s.preferred_total} preferred` : '') + (s.to_check ? `. ${s.to_check} to confirm.` : '.') : 'Qualifications found, but none could be checked automatically.';
  return `<details class="why"><summary>Qualifications vs the resume</summary><p style="margin:8px 0 0;font-size:14px">${head}</p>${sec('Required', q.required)}${sec('Preferred', q.preferred)}</details>`;
}

function card(j){
  const st = status[j.key];
  const chips = [];
  if(j.first_seen >= D.today) chips.push('<span class="chip new">New</span>');
  const qc = qualChip(j.quals); if(qc) chips.push(qc);
  for(const f of j.flags) chips.push(`<span class="chip ${f.kind === 'info' ? '' : f.kind}">${esc(f.label)}</span>`);
  const rows = [];
  if(j.matched.length) rows.push(`<dt>Resume skills it asks for</dt><dd>${esc(j.matched.join(', '))}</dd>`);
  if(j.related.length) rows.push(`<dt>Transferable</dt><dd>${esc(j.related.join(', '))}</dd>`);
  if(j.gaps.length) rows.push(`<dt>Not on the resume</dt><dd>${esc(j.gaps.join(', '))}</dd>`);
  rows.push(`<dt>Score breakdown</dt><dd>Role fit ${j.parts.role}/40, skills ${j.parts.skills}/35, eligibility ${j.parts.eligibility}/25` +
    (j.parts.requirements ? `, ${j.parts.requirements} for missing required qualifications` : '') +
    (j.parts.capped ? `. Capped at ${j.parts.capped} (wants a current student, a grad degree, or 3+ years, or it's an internship whose rules couldn't be read)` : '') + `</dd>`);
  rows.push(`<dt>Found via</dt><dd>${esc(j.source)}</dd>`);
  const ai = j.ai ? `<div class="ai"><b>Claude's take (${esc(j.ai.fit)}):</b> ${esc(j.ai.summary)}${j.ai.talking_point ? '<br><b>Lead with:</b> ' + esc(j.ai.talking_point) : ''}</div>` : '';
  const meta = [j.location && `<span>${esc(j.location)}</span>`, j.posted && `<span>Posted ${fmt(j.posted)} (${ageDays(j.posted) === 0 ? 'today' : ageDays(j.posted) + 'd ago'})</span>`, `<span>Found ${fmt(j.first_seen)}</span>`].filter(Boolean).join('');
  return `<article class="strip t-${j.tier} ${st ? 'done' : ''}" data-key="${esc(j.key)}">
    <div class="score" title="Fit score out of 100"><b>${j.score}</b><small>${TIER[j.tier]}</small></div>
    <div class="main">
      <div class="co">${esc(j.company)}</div>
      <h2 class="title">${esc(j.title)}</h2>
      <div class="meta">${meta}</div>
      <div class="chips">${chips.join('')}</div>
      ${ai}
      ${qualList(j.quals)}
      <details class="why"><summary>Why this score</summary><dl>${rows.join('')}</dl></details>
    </div>
    <div class="acts">
      <a class="btn" href="${esc(j.url)}" target="_blank" rel="noopener">Apply</a>
      <button class="btn ghost" data-act="applied">${st === 'applied' ? 'Applied ✓' : 'Mark applied'}</button>
      <button class="btn ghost" data-act="dismissed">${st === 'dismissed' ? 'Dismissed' : 'Dismiss'}</button>
    </div>
  </article>`;
}

function render(){
  const q = $('q').value.trim().toLowerCase();
  const hide = $('hideDone').checked, onlyNew = $('onlyNew').checked, onlyNear = $('onlyNear').checked;
  let jobs = D.jobs.filter(j => {
    if(tier !== 'all' && j.tier !== tier) return false;
    if(kind !== 'all' && j.kind !== kind) return false;
    if(hide && status[j.key]) return false;
    if(onlyNew && !postedThisWeek(j)) return false;
    if(onlyNear && !j.near) return false;
    if(q){
      const hay = [j.company, j.title, j.location, j.matched.join(' '), j.gaps.join(' ')].join(' ').toLowerCase();
      if(!q.split(/\s+/).every(w => hay.includes(w))) return false;
    }
    return true;
  });
  const s = $('sort').value;
  jobs.sort(s === 'new' ? (a,b) => (b.first_seen + (b.posted||'')).localeCompare(a.first_seen + (a.posted||'')) || b.score - a.score
         : s === 'company' ? (a,b) => a.company.localeCompare(b.company) || b.score - a.score
         : s === 'reqs' ? (a,b) => reqPct(b) - reqPct(a) || b.score - a.score
         : (a,b) => b.score - a.score);
  if(!D.jobs.length){
    $('list').innerHTML = `<div class="empty"><p><b>No scan results yet.</b></p><p>In the GitHub repo, open the Actions tab, choose “Daily job scan”, and click “Run workflow”. This page fills in about five minutes later.</p></div>`;
    return;
  }
  $('shown').textContent = `Showing ${jobs.length} of ${D.jobs.length} postings`;
  $('list').innerHTML = jobs.length ? jobs.map(card).join('') :
    '<div class="empty">No postings match these filters. Clear the search or choose “All”.</div>';
}

function seg(id, set){
  document.querySelectorAll(`#${id} button`).forEach(b => b.addEventListener('click', () => {
    set(b.dataset.v);
    document.querySelectorAll(`#${id} button`).forEach(x => x.setAttribute('aria-pressed', x === b));
    render();
  }));
}
seg('tierSeg', v => tier = v);
seg('kindSeg', v => kind = v);
['q','sort','onlyNew','onlyNear','hideDone'].forEach(id => $(id).addEventListener(id === 'q' ? 'input' : 'change', render));
$('list').addEventListener('click', e => {
  const btn = e.target.closest('button[data-act]');
  if(!btn) return;
  const key = btn.closest('.strip').dataset.key;
  status[key] = status[key] === btn.dataset.act ? undefined : btn.dataset.act;
  if(!status[key]) delete status[key];
  store.set(status);
  render();
});
render();
})();
</script>
</body>
</html>
"""


def _pct_list(counter: dict, total: int, top: int = 8) -> list[dict]:
    if not total:
        return []
    items = sorted(counter.items(), key=lambda kv: -kv[1])[:top]
    return [{"name": k, "count": v, "pct": round(100 * v / total)} for k, v in items if v]


def build_page(jobs: list[dict], sources: list[dict], profile: dict, now: dt.datetime) -> str:
    with_desc = [j for j in jobs if j.get("has_description")]
    have, need = {}, {}
    for j in with_desc:
        for s in j["matched"]:
            have[s] = have.get(s, 0) + 1
        for g in j["gaps"]:
            need[g] = need.get(g, 0) + 1
    today = now.date().isoformat()
    page_jobs = [{k: j.get(k) for k in (
        "key", "company", "title", "location", "url", "source", "posted", "first_seen",
        "score", "tier", "parts", "matched", "related", "gaps", "flags", "kind", "near", "ai", "quals")}
        for j in jobs]
    try:
        from zoneinfo import ZoneInfo
        eastern = now.astimezone(ZoneInfo("America/New_York"))
    except Exception:  # noqa: BLE001 - label only
        eastern = now - dt.timedelta(hours=4)
    st = profile["student"]
    data = {
        "name": st.get("name", "you"),
        "degree": st.get("degree") or st.get("major", ""),
        # %-d / %-I are Linux-only, so build the unpadded parts by hand
        "updated_label": (f"{eastern:%b} {eastern.day}, {eastern.year} at "
                          f"{eastern.hour % 12 or 12}:{eastern:%M %p} ET") if jobs or sources else "never",
        "today": today,
        "jobs": page_jobs,
        "have": _pct_list(have, len(with_desc)),
        "need": _pct_list(need, len(with_desc)),
        "sources": sources,
        "counts": {
            "total": len(jobs),
            "strong": sum(1 for j in jobs if j["tier"] == "strong"),
            "fulltime": sum(1 for j in jobs if j.get("kind") == "full-time"),
            "near": sum(1 for j in jobs if j.get("near")),
            "new_today": sum(1 for j in jobs if j.get("first_seen") == today),
        },
    }
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.replace("__DATA__", blob)


def update_readme(path: Path, jobs: list[dict], page_url: str, now: dt.datetime, top: int = 25) -> None:
    start, end = "<!-- JOBS:START -->", "<!-- JOBS:END -->"
    text = path.read_text(encoding="utf-8")
    if start not in text or end not in text:
        return
    today = now.date().isoformat()
    lines = [
        f"**{len(jobs)} matches** as of {now:%b} {now.day}, {now.year}. "
        f"Full list with filters: **[open the job page]({page_url})**",
        "",
        "| Fit | Company | Role | Type | Required quals met | Location | Posted | Apply |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for j in sorted(jobs, key=lambda j: -j["score"])[:top]:
        new = " 🆕" if j.get("first_seen") == today else ""
        loc = re.sub(r"\s+", " ", (j.get("location") or ""))[:40]
        title = (j["title"] or "").replace("|", "/")
        s = (j.get("quals") or {}).get("summary") or {}
        reqs = f"{s['required_met']:g} of {s['required_checked']}" if s.get("required_checked") else "–"
        kind = "Internship" if j.get("kind") == "intern" else "Full-time"
        lines.append(f"| {j['score']} | {j['company'].replace('|', '/')} | {title}{new} | {kind} | {reqs} | {loc} "
                     f"| {j.get('posted') or '?'} | [Apply]({j['url']}) |")
    if not jobs:
        lines.append("| | No matches yet | Run the workflow from the Actions tab | | | | | |")
    block = start + "\n" + "\n".join(lines) + "\n" + end
    text = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: block, text, flags=re.S)
    path.write_text(text, encoding="utf-8")
