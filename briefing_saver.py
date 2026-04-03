#!/usr/bin/env python3
"""
briefing_saver.py v2
OpenClaw 브리핑을 GitHub Pages에 저장하고 텔레그램으로 링크 발송
카테고리: semi / ai / stock / weather / schedule / tasks

설치:
  pip3 install requests --break-system-packages

환경변수 (~/.bashrc):
  export GITHUB_TOKEN="github_pat_..."
  export TELEGRAM_TOKEN="..."
  export TELEGRAM_CHAT_ID="..."
  export OWM_API_KEY="..."        # OpenWeatherMap API 키

OpenClaw에서 호출:
  from briefing_saver import save_briefing, save_weather, save_schedule, save_tasks
  save_briefing(category='semi', content=text, summary=summary)
  save_weather()          # 날씨 자동 수집
  save_schedule(events)   # Google Calendar 이벤트 리스트
  save_tasks(tasks)       # Google Tasks 리스트
"""

import os, re, sys, json, base64, argparse, requests
from datetime import datetime

# ─── 설정 ────────────────────────────────────────────────────────────────────
GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN", "")
GITHUB_USER      = "junghwan325-cyber"
GITHUB_REPO      = "briefings"
GITHUB_BRANCH    = "main"
BASE_URL         = f"https://{GITHUB_USER}.github.io/{GITHUB_REPO}"
GITHUB_API       = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents"
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
OWM_API_KEY      = os.getenv("OWM_API_KEY", "")
DONGTAN_LAT      = "37.2098"
DONGTAN_LON      = "126.9817"

CATEGORIES = {
    "semi":     {"label": "반도체",      "emoji": "🔬", "color": "#c4410c"},
    "ai":       {"label": "AI / LLM",   "emoji": "🤖", "color": "#1a5c3a"},
    "stock":    {"label": "주식 · 시장", "emoji": "📈", "color": "#1a3a5c"},
    "weather":  {"label": "날씨",        "emoji": "🌤", "color": "#0077b6"},
    "schedule": {"label": "일정",        "emoji": "📅", "color": "#6a0572"},
    "tasks":    {"label": "할일",        "emoji": "✅", "color": "#2d6a4f"},
}

# ─── GitHub API ───────────────────────────────────────────────────────────────
def gh_headers():
    return {"Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}

def gh_get(path):
    res = requests.get(f"{GITHUB_API}/{path}", headers=gh_headers())
    if res.status_code == 200:
        d = res.json()
        return base64.b64decode(d["content"]).decode("utf-8"), d["sha"]
    return None, None

def gh_put(path, content_str, message, sha=None):
    payload = {"message": message, "branch": GITHUB_BRANCH,
               "content": base64.b64encode(content_str.encode()).decode()}
    if sha:
        payload["sha"] = sha
    res = requests.put(f"{GITHUB_API}/{path}", headers=gh_headers(), json=payload)
    ok = res.status_code in (200, 201)
    print(f"[GH] {'OK' if ok else 'FAIL'} {path} {'' if ok else res.text[:100]}")
    return ok

# ─── 콘텐츠 파싱 ─────────────────────────────────────────────────────────────
def convert_body(body, color):
    """본문 텍스트 → HTML. URL 자동 링크 + 불릿 처리"""
    html, list_items = [], []

    def flush():
        if list_items:
            html.append('<div class="hl"><div class="hl-lbl">핵심 포인트</div>' + "".join(list_items) + "</div>")
            list_items.clear()

    # URL 자동 링크 변환
    def linkify(text):
        return re.sub(
            r'(https?://[^\s\)\]]+)',
            r'<a href="\1" target="_blank" class="src-link">🔗 기사 보기</a>',
            text
        )

    for line in body.split("\n"):
        line = line.strip()
        if not line:
            flush(); continue

        # URL만 있는 줄 → 링크 버튼으로
        if re.match(r'^https?://\S+$', line):
            flush()
            html.append(f'<div class="link-row"><a href="{line}" target="_blank" class="src-link">🔗 기사 보기</a></div>')
            continue

        # 불릿 처리
        if line.startswith(("- ", "• ")):
            text = line[2:].strip()
            cls = "up" if any(k in text for k in ["상승","↑","▲","강세"]) else \
                  "dn" if any(k in text for k in ["하락","↓","▼","약세"]) else ""
            text = linkify(text)
            list_items.append(f'<div class="hi"><span class="arr {cls}" style="color:{color}">→</span><span>{text}</span></div>')
        else:
            flush()
            line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            line = linkify(line)
            html.append(f"<p>{line}</p>")

    flush()
    return "\n".join(html)

def parse_sections(content, color):
    parts = re.split(r'\n## ', content.strip())
    out = []
    for i, part in enumerate(parts):
        if not part.strip(): continue
        lines = part.strip().split("\n")
        title = lines[0].replace("## ", "").strip()
        body  = "\n".join(lines[1:]).strip()
        out.append(
            f'<div class="sec">'
            f'<div class="sh"><div class="sn">0{i+1}</div><div class="st">{title}</div></div>'
            f'<div class="sb">{convert_body(body, color)}</div>'
            f'</div>'
        )
    if not out:
        out.append(
            f'<div class="sec">'
            f'<div class="sh"><div class="sn">01</div><div class="st">오늘의 브리핑</div></div>'
            f'<div class="sb">{convert_body(content, color)}</div>'
            f'</div>'
        )
    return "\n".join(out)

# ─── HTML 페이지 빌더 ─────────────────────────────────────────────────────────
def build_page(title, date_label, time_str, category, summary, content, item_count):
    cat = CATEGORIES.get(category, CATEGORIES["semi"])
    c   = cat["color"]
    secs = parse_sections(content, c)
    return f"""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Source+Sans+3:wght@300;400;500&family=Source+Code+Pro:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{{--bg:#f7f4ef;--paper:#fdfcfa;--ink:#1a1814;--ink2:#3d3a34;--mu:#8a8578;--ru:#ddd9d0;--ac:{c};}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:var(--bg);color:var(--ink);font-family:'Source Sans 3',sans-serif;font-weight:300;line-height:1.8;}}
a{{color:inherit;text-decoration:none;}}
.mh{{background:var(--ink);padding:40px;}}.mh-in{{max-width:860px;margin:0 auto;}}
.bk{{font-family:'Source Code Pro',monospace;font-size:11px;color:#6b6860;letter-spacing:1px;display:inline-block;margin-bottom:20px;}}
.bk:hover{{color:#f7f4ef;}}
.badge{{font-family:'Source Code Pro',monospace;font-size:11px;letter-spacing:3px;color:#6b6860;display:flex;align-items:center;gap:8px;margin-bottom:14px;}}
.dot{{width:6px;height:6px;border-radius:50%;background:{c};}}
h1{{font-family:'Playfair Display',serif;font-size:clamp(24px,4vw,44px);font-weight:700;color:#fdfcfa;line-height:1.15;margin-bottom:16px;}}
.meta{{font-family:'Source Code Pro',monospace;font-size:12px;color:#6b6860;display:flex;gap:18px;flex-wrap:wrap;}}
.main{{max-width:860px;margin:0 auto;padding:40px 40px 80px;}}
.sumbox{{background:var(--paper);border:1px solid var(--ru);border-left:3px solid {c};padding:20px 24px;margin-bottom:32px;border-radius:0 4px 4px 0;}}
.slbl{{font-family:'Source Code Pro',monospace;font-size:10px;letter-spacing:3px;color:var(--mu);margin-bottom:8px;}}
.stxt{{font-family:'Playfair Display',serif;font-size:17px;line-height:1.6;color:var(--ink2);font-style:italic;}}
.sec{{margin-bottom:32px;padding-bottom:32px;border-bottom:1px solid var(--ru);}}
.sec:last-child{{border-bottom:none;margin-bottom:0;padding-bottom:0;}}
.sh{{display:flex;align-items:baseline;gap:12px;margin-bottom:14px;}}
.sn{{font-family:'Playfair Display',serif;font-size:44px;font-weight:700;color:var(--ru);line-height:1;flex-shrink:0;}}
.st{{font-family:'Playfair Display',serif;font-size:20px;font-weight:600;color:var(--ink);}}
.sb{{font-size:15px;color:var(--ink2);line-height:1.9;}} .sb p{{margin-bottom:12px;}}
.hl{{background:var(--paper);border:1px solid var(--ru);border-radius:4px;padding:16px 20px;margin:14px 0;}}
.hl-lbl{{font-family:'Source Code Pro',monospace;font-size:10px;letter-spacing:3px;color:var(--mu);margin-bottom:8px;}}
.hi{{display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--ru);font-size:14px;color:var(--ink2);align-items:flex-start;}}
.hi:last-child{{border-bottom:none;}}
.arr{{font-weight:500;flex-shrink:0;margin-top:2px;}}
.arr.up{{color:#2e7d4f!important;}} .arr.dn{{color:#c4410c!important;}}
.src-link{{display:inline-flex;align-items:center;gap:4px;background:{c}18;color:{c};border:1px solid {c}44;padding:3px 10px;border-radius:20px;font-size:12px;font-family:'Source Code Pro',monospace;margin:4px 0;transition:all .15s;}}
.src-link:hover{{background:{c};color:#fff;}}
.link-row{{margin:8px 0;}}
footer{{background:var(--ink);color:#6b6860;padding:18px 40px;font-family:'Source Code Pro',monospace;font-size:11px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;}}
@media(max-width:600px){{.mh,.main{{padding:22px 18px;}}footer{{padding:14px 18px;}}}}
</style></head><body>
<div class="mh"><div class="mh-in">
<a href="./index.html" class="bk">← 전체 목록</a>
<div class="badge"><div class="dot"></div>{cat['label']}</div>
<h1>{title}</h1>
<div class="meta"><span>📅 {date_label}</span><span>⏰ {time_str}</span><span>📊 {item_count}개 항목</span></div>
</div></div>
<div class="main">
<div class="sumbox"><div class="slbl">오늘의 요약</div><div class="stxt">{summary}</div></div>
{secs}
</div>
<footer><span>BRONCS BRIEFING · {date_label}</span><a href="./index.html">← 목록으로</a></footer>
</body></html>"""

def build_index(meta_list):
    js = json.dumps(meta_list, ensure_ascii=False, indent=2)
    cat_colors = {
        "semi": "#c4410c", "ai": "#1a5c3a", "stock": "#1a3a5c",
        "weather": "#0077b6", "schedule": "#6a0572", "tasks": "#2d6a4f"
    }
    return f"""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>BRONCS BRIEFING</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Source+Sans+3:wght@300;400;500&family=Source+Code+Pro:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{{--bg:#f7f4ef;--paper:#fdfcfa;--ink:#1a1814;--mu:#8a8578;--ru:#ddd9d0;
  --semi:#c4410c;--ai:#1a5c3a;--stock:#1a3a5c;--weather:#0077b6;--schedule:#6a0572;--tasks:#2d6a4f;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:var(--bg);color:var(--ink);font-family:'Source Sans 3',sans-serif;font-weight:300;min-height:100vh;}}
a{{color:inherit;text-decoration:none;}}
.tb{{background:var(--ink);padding:11px 40px;display:flex;justify-content:space-between;font-family:'Source Code Pro',monospace;font-size:11px;color:#6b6860;letter-spacing:2px;}}
.mh{{border-bottom:3px solid var(--ink);padding:44px 40px 28px;max-width:960px;margin:0 auto;}}
h1{{font-family:'Playfair Display',serif;font-size:clamp(52px,9vw,100px);font-weight:900;letter-spacing:-2px;line-height:.92;margin-bottom:18px;}}
h1 span{{color:var(--semi);}}
.ms{{display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:10px;}}
.md{{font-size:14px;color:var(--mu);line-height:1.7;}}
.stats{{max-width:960px;margin:0 auto;padding:16px 40px;display:flex;gap:24px;border-bottom:1px solid var(--ru);flex-wrap:wrap;}}
.stat{{display:flex;flex-direction:column;gap:2px;}}
.sv{{font-family:'Playfair Display',serif;font-size:22px;font-weight:700;}}
.sk{{font-family:'Source Code Pro',monospace;font-size:10px;letter-spacing:2px;color:var(--mu);}}
.flt{{max-width:960px;margin:0 auto;padding:14px 40px;display:flex;gap:6px;border-bottom:1px solid var(--ru);flex-wrap:wrap;}}
.fb{{font-family:'Source Code Pro',monospace;font-size:11px;letter-spacing:2px;text-transform:uppercase;padding:6px 12px;border:1px solid var(--ru);background:var(--paper);color:var(--mu);cursor:pointer;border-radius:2px;transition:all .15s;}}
.fb:hover{{opacity:.8;}}
.fb.active{{color:#fff;border-color:transparent;}}
.fb.all.active{{background:var(--ink);}}
.fb.semi.active{{background:var(--semi);}}
.fb.ai.active{{background:var(--ai);}}
.fb.stock.active{{background:var(--stock);}}
.fb.weather.active{{background:var(--weather);}}
.fb.schedule.active{{background:var(--schedule);}}
.fb.tasks.active{{background:var(--tasks);}}
.main{{max-width:960px;margin:0 auto;padding:26px 40px 80px;}}
.dg{{margin-bottom:40px;}}
.dh{{display:flex;align-items:center;gap:14px;margin-bottom:16px;}}
.dht{{font-family:'Playfair Display',serif;font-size:19px;font-weight:600;}}
.dhl{{flex:1;height:1px;background:var(--ru);}}
.dhc{{font-family:'Source Code Pro',monospace;font-size:11px;color:var(--mu);}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px;}}
.card{{background:var(--paper);border:1px solid var(--ru);border-radius:2px;padding:20px;display:flex;flex-direction:column;gap:9px;transition:all .15s;position:relative;overflow:hidden;}}
.card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;transform:scaleX(0);transform-origin:left;transition:transform .2s;}}
.card.semi::before{{background:var(--semi);}}
.card.ai::before{{background:var(--ai);}}
.card.stock::before{{background:var(--stock);}}
.card.weather::before{{background:var(--weather);}}
.card.schedule::before{{background:var(--schedule);}}
.card.tasks::before{{background:var(--tasks);}}
.card:hover{{box-shadow:0 4px 20px rgba(0,0,0,.08);transform:translateY(-2px);}}
.card:hover::before{{transform:scaleX(1);}}
.cc{{display:flex;align-items:center;gap:7px;font-family:'Source Code Pro',monospace;font-size:10px;letter-spacing:3px;text-transform:uppercase;color:var(--mu);}}
.cd{{width:6px;height:6px;border-radius:50%;}}
.cd.semi{{background:var(--semi);}} .cd.ai{{background:var(--ai);}} .cd.stock{{background:var(--stock);}}
.cd.weather{{background:var(--weather);}} .cd.schedule{{background:var(--schedule);}} .cd.tasks{{background:var(--tasks);}}
.ct{{font-family:'Playfair Display',serif;font-size:16px;font-weight:600;line-height:1.4;color:var(--ink);}}
.cs{{font-size:13px;color:var(--mu);line-height:1.6;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;}}
.cf{{display:flex;justify-content:space-between;align-items:center;margin-top:auto;padding-top:9px;border-top:1px solid var(--ru);font-family:'Source Code Pro',monospace;font-size:11px;color:var(--mu);}}
.ca{{font-size:14px;}}
.card.semi .ca{{color:var(--semi);}} .card.ai .ca{{color:var(--ai);}} .card.stock .ca{{color:var(--stock);}}
.card.weather .ca{{color:var(--weather);}} .card.schedule .ca{{color:var(--schedule);}} .card.tasks .ca{{color:var(--tasks);}}
footer{{background:var(--ink);color:#6b6860;padding:18px 40px;font-family:'Source Code Pro',monospace;font-size:11px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;}}
@media(max-width:600px){{.mh,.main,.flt,.stats{{padding-left:18px;padding-right:18px;}}.tb{{padding:10px 18px;}}h1{{letter-spacing:-1px;}}footer{{padding:14px 18px;}}}}
</style></head><body>
<div class="tb"><span>BRONCS BRIEFING SYSTEM</span><span id="ct">--:--:--</span></div>
<div class="mh">
<h1>DAILY<br>BRIEF<span>.</span></h1>
<div class="ms"><div class="md">반도체 · AI/LLM · 주식 · 날씨 · 일정 · 할일<br>매일 7AM 자동 수집 브리핑</div></div>
</div>
<div class="stats">
<div class="stat"><div class="sv" id="tc">0</div><div class="sk">전체</div></div>
<div class="stat"><div class="sv" id="sc" style="color:var(--semi)">0</div><div class="sk">반도체</div></div>
<div class="stat"><div class="sv" id="ac" style="color:var(--ai)">0</div><div class="sk">AI/LLM</div></div>
<div class="stat"><div class="sv" id="stc" style="color:var(--stock)">0</div><div class="sk">주식</div></div>
<div class="stat"><div class="sv" id="wc" style="color:var(--weather)">0</div><div class="sk">날씨</div></div>
<div class="stat"><div class="sv" id="schc" style="color:var(--schedule)">0</div><div class="sk">일정</div></div>
<div class="stat"><div class="sv" id="taskc" style="color:var(--tasks)">0</div><div class="sk">할일</div></div>
</div>
<div class="flt">
<button class="fb all active" onclick="flt('all',this)">ALL</button>
<button class="fb semi" onclick="flt('semi',this)">반도체</button>
<button class="fb ai" onclick="flt('ai',this)">AI / LLM</button>
<button class="fb stock" onclick="flt('stock',this)">주식</button>
<button class="fb weather" onclick="flt('weather',this)">날씨</button>
<button class="fb schedule" onclick="flt('schedule',this)">일정</button>
<button class="fb tasks" onclick="flt('tasks',this)">할일</button>
</div>
<div class="main" id="main"></div>
<footer><span>BRONCS BRIEFING · AUTO-GENERATED</span><span>OpenClaw + GitHub Pages</span></footer>
<script>
const DATA={js};
const CAT={{semi:'반도체',ai:'AI / LLM',stock:'주식·시장',weather:'날씨',schedule:'일정',tasks:'할일'}};
function tick(){{const n=new Date();document.getElementById('ct').textContent=n.toLocaleTimeString('ko-KR',{{hour12:false}});}}
tick();setInterval(tick,1000);
function stats(){{
  document.getElementById('tc').textContent=DATA.length;
  ['semi','ai','stock','weather','schedule','tasks'].forEach(c=>{{
    const id={{semi:'sc',ai:'ac',stock:'stc',weather:'wc',schedule:'schc',tasks:'taskc'}}[c];
    document.getElementById(id).textContent=DATA.filter(b=>b.category===c).length;
  }});
}}
function render(data){{
  const m=document.getElementById('main');
  if(!data.length){{m.innerHTML='<div style="text-align:center;padding:80px;color:#8a8578">브리핑이 없습니다.</div>';return;}}
  const g={{}};data.forEach(b=>{{if(!g[b.date])g[b.date]=[];g[b.date].push(b);}});
  m.innerHTML=Object.keys(g).sort().reverse().map(date=>{{
    const items=g[date];
    const dl=new Date(date+'T00:00:00').toLocaleDateString('ko-KR',{{year:'numeric',month:'long',day:'numeric',weekday:'long'}});
    return '<div class="dg"><div class="dh"><div class="dht">'+dl+'</div><div class="dhl"></div><div class="dhc">'+items.length+'건</div></div><div class="cards">'+
    items.map(b=>'<a class="card '+b.category+'" href="'+b.file+'"><div class="cc"><div class="cd '+b.category+'"></div>'+(CAT[b.category]||b.category)+'</div><div class="ct">'+b.title+'</div><div class="cs">'+b.summary+'</div><div class="cf"><span>⏰ '+b.time+'</span><span class="ca">→</span></div></a>').join('')+
    '</div></div>';
  }}).join('');
}}
function flt(cat,btn){{
  document.querySelectorAll('.fb').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  render(cat==='all'?DATA:DATA.filter(b=>b.category===cat));
}}
stats();render(DATA);
</script></body></html>"""

# ─── 메타데이터 ───────────────────────────────────────────────────────────────
def load_meta():
    content, _ = gh_get("briefings_meta.json")
    if content:
        try: return json.loads(content)
        except: return []
    return []

def save_meta(meta_list):
    _, sha = gh_get("briefings_meta.json")
    gh_put("briefings_meta.json",
           json.dumps(meta_list, ensure_ascii=False, indent=2),
           "chore: update meta", sha)

def rebuild_index(meta):
    _, sha = gh_get("index.html")
    gh_put("index.html", build_index(meta), "chore: rebuild index", sha)

# ─── 텔레그램 ─────────────────────────────────────────────────────────────────
def send_tg(category, title, summary, url):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[TG] 토큰 없음, 스킵"); return
    cat = CATEGORIES.get(category, CATEGORIES["semi"])
    msg = (f"{cat['emoji']} *{cat['label']} 브리핑*\n\n"
           f"*{title}*\n_{summary}_\n\n"
           f"[📖 전체 보기]({url})\n[📋 전체 목록]({BASE_URL}/index.html)")
    res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    print(f"[TG] {'OK' if res.ok else 'FAIL: ' + res.text[:80]}")

# ─── 공통 저장 로직 ───────────────────────────────────────────────────────────
def _save(category, content, summary, title_override):
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN 없음")
    now        = datetime.now()
    date_str   = now.strftime("%Y-%m-%d")
    date_label = now.strftime("%Y년 %m월 %d일")
    time_str   = now.strftime("%H:%M")
    cat_info   = CATEGORIES.get(category, CATEGORIES["semi"])
    title = title_override or f"{cat_info['label']} 브리핑 — {date_label}"
    if not summary:
        first = content.split("\n")[0].strip()
        summary = first[:120] + ("..." if len(first) > 120 else "")
    item_count = content.count("\n## ") + 1
    filename = f"{date_str}_{category}.html"
    existing, _ = gh_get(filename)
    if existing:
        filename = f"{date_str}_{category}_{now.strftime('%H%M')}.html"
    html = build_page(title, date_label, time_str, category, summary, content, item_count)
    gh_put(filename, html, f"briefing: {title}")
    meta = load_meta()
    meta = [m for m in meta if m.get("file") != f"./{filename}"]
    meta.append({"id": filename.replace(".html",""), "date": date_str, "time": time_str,
                 "category": category, "title": title, "summary": summary, "file": f"./{filename}"})
    meta.sort(key=lambda x: (x["date"], x["time"]), reverse=True)
    save_meta(meta)
    rebuild_index(meta)
    url = f"{BASE_URL}/{filename}"
    send_tg(category, title, summary, url)
    print(f"[DONE] {url}")
    return url

# ─── 공개 API ─────────────────────────────────────────────────────────────────
def save_briefing(category: str, content: str, summary: str = "", title_override: str = "") -> str:
    """뉴스 브리핑 저장 (semi / ai / stock)"""
    return _save(category, content, summary, title_override)

def save_weather() -> str:
    """동탄 날씨 자동 수집 후 저장"""
    if not OWM_API_KEY:
        raise ValueError("OWM_API_KEY 없음")
    res = requests.get(
        "https://api.openweathermap.org/data/2.5/forecast",
        params={"lat": DONGTAN_LAT, "lon": DONGTAN_LON, "appid": OWM_API_KEY,
                "units": "metric", "lang": "kr", "cnt": 8}
    )
    data = res.json()
    now_res = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={"lat": DONGTAN_LAT, "lon": DONGTAN_LON, "appid": OWM_API_KEY,
                "units": "metric", "lang": "kr"}
    )
    now_data = now_res.json()
    temp     = now_data["main"]["temp"]
    feels    = now_data["main"]["feels_like"]
    humidity = now_data["main"]["humidity"]
    desc     = now_data["weather"][0]["description"]
    wind     = now_data["wind"]["speed"]

    content = f"""## 현재 날씨 — 동탄
기온 {temp:.1f}°C (체감 {feels:.1f}°C), {desc}
- 습도: {humidity}%
- 풍속: {wind}m/s

## 오늘 예보
"""
    forecasts = data.get("list", [])
    for f in forecasts[:4]:
        t = datetime.fromtimestamp(f["dt"]).strftime("%H:%M")
        tmp = f["main"]["temp"]
        dsc = f["weather"][0]["description"]
        content += f"- {t} · {tmp:.1f}°C · {dsc}\n"

    summary = f"현재 {temp:.1f}°C, {desc} · 습도 {humidity}%"
    return _save("weather", content, summary, "")

def save_schedule(events: list) -> str:
    """
    Google Calendar 이벤트 저장
    events: [{"title": str, "time": str, "location": str, "desc": str}, ...]
    """
    if not events:
        content = "## 오늘 일정\n오늘 등록된 일정이 없습니다."
        summary = "오늘 일정 없음"
    else:
        content = "## 오늘 일정\n"
        for e in events:
            content += f"- {e.get('time','')} **{e.get('title','')}**"
            if e.get('location'):
                content += f" · 📍{e['location']}"
            content += "\n"
            if e.get('desc'):
                content += f"  {e['desc']}\n"
        summary = f"오늘 일정 {len(events)}건"
    return _save("schedule", content, summary, "")

def save_tasks(tasks: list) -> str:
    """
    Google Tasks 저장
    tasks: [{"title": str, "due": str, "notes": str, "status": str}, ...]
    """
    pending = [t for t in tasks if t.get("status") != "completed"]
    done    = [t for t in tasks if t.get("status") == "completed"]

    content = f"## 미완료 할일 ({len(pending)}건)\n"
    for t in pending:
        due = f" · 마감 {t['due']}" if t.get('due') else ""
        content += f"- **{t['title']}**{due}\n"
        if t.get('notes'):
            content += f"  {t['notes']}\n"

    if done:
        content += f"\n## 완료된 할일 ({len(done)}건)\n"
        for t in done:
            content += f"- ~~{t['title']}~~\n"

    summary = f"미완료 {len(pending)}건 · 완료 {len(done)}건"
    return _save("tasks", content, summary, "")

# ─── CLI ─────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--category", choices=list(CATEGORIES.keys()), required=True)
    p.add_argument("--content", type=str)
    p.add_argument("--content-file", type=str)
    p.add_argument("--summary", type=str, default="")
    p.add_argument("--title", type=str, default="")
    p.add_argument("--weather", action="store_true", help="날씨 자동 수집")
    args = p.parse_args()

    if args.weather or args.category == "weather":
        save_weather(); return

    if args.content_file: content = open(args.content_file, encoding="utf-8").read()
    elif args.content:    content = args.content
    else:                 content = sys.stdin.read()

    save_briefing(category=args.category, content=content,
                  summary=args.summary, title_override=args.title)

if __name__ == "__main__":
    main()
