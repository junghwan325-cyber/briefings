#!/usr/bin/env python3
"""
briefing_saver.py
OpenClaw 브리핑을 GitHub Pages에 저장하고 텔레그램으로 링크 발송

설치:
  pip3 install requests --break-system-packages

환경변수 설정 (~/.bashrc):
  export GITHUB_TOKEN="github_pat_xxxx..."
  export TELEGRAM_TOKEN="your_bot_token"
  export TELEGRAM_CHAT_ID="your_chat_id"

OpenClaw에서 호출:
  from briefing_saver import save_briefing
  save_briefing(category='semi', content=text, summary=summary)

CLI:
  python3 briefing_saver.py --category semi --content "내용" --summary "요약"
  echo "내용" | python3 briefing_saver.py --category ai
"""

import os, re, sys, json, base64, argparse, requests
from datetime import datetime

# ─── 설정 ────────────────────────────────────────────────────────────────────
GITHUB_TOKEN   = os.getenv("GITHUB_TOKEN", "")
GITHUB_USER    = "junghwan325-cyber"
GITHUB_REPO    = "briefings"
GITHUB_BRANCH  = "main"
BASE_URL       = f"https://{GITHUB_USER}.github.io/{GITHUB_REPO}"
GITHUB_API     = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents"
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

CATEGORIES = {
    "semi":  {"label": "반도체",     "class": "",      "emoji": "🔬", "color": "#c4410c"},
    "ai":    {"label": "AI / LLM",  "class": "ai",    "emoji": "🤖", "color": "#1a5c3a"},
    "stock": {"label": "주식 · 시장","class": "stock", "emoji": "📈", "color": "#1a3a5c"},
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
    print(f"[GH] {'✅' if ok else '❌'} {path} {'저장완료' if ok else res.text[:120]}")
    return ok

# ─── 콘텐츠 파싱 ─────────────────────────────────────────────────────────────
def convert_body(body):
    html, list_items = [], []

    def flush():
        if list_items:
            html.append('<div class="hl"><div class="hl-lbl">핵심 포인트</div>' + "".join(list_items) + "</div>")
            list_items.clear()

    for line in body.split("\n"):
        line = line.strip()
        if not line:
            flush(); continue
        if line.startswith(("- ", "• ")):
            text = line[2:].strip()
            cls = "up" if any(k in text for k in ["상승","↑","▲","강세"]) else \
                  "dn" if any(k in text for k in ["하락","↓","▼","약세"]) else ""
            list_items.append(f'<div class="hi"><span class="arr {cls}">→</span><span>{text}</span></div>')
        else:
            flush()
            line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            html.append(f"<p>{line}</p>")
    flush()
    return "\n".join(html)

def parse_sections(content):
    parts = re.split(r'\n## ', content.strip())
    out = []
    for i, part in enumerate(parts):
        if not part.strip(): continue
        lines = part.strip().split("\n")
        title = lines[0].replace("## ", "").strip()
        body  = "\n".join(lines[1:]).strip()
        out.append(f'<div class="sec"><div class="sh"><div class="sn">0{i+1}</div>'
                   f'<div class="st">{title}</div></div>'
                   f'<div class="sb">{convert_body(body)}</div></div>')
    if not out:
        out.append(f'<div class="sec"><div class="sh"><div class="sn">01</div>'
                   f'<div class="st">오늘의 브리핑</div></div>'
                   f'<div class="sb">{convert_body(content)}</div></div>')
    return "\n".join(out)

# ─── HTML 빌더 ────────────────────────────────────────────────────────────────
def build_page(title, date_label, time_str, category, summary, content, item_count):
    cat = CATEGORIES.get(category, CATEGORIES["semi"])
    c   = cat["color"]
    return f"""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Source+Sans+3:wght@300;400;500&family=Source+Code+Pro:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{{--bg:#f7f4ef;--paper:#fdfcfa;--ink:#1a1814;--ink2:#3d3a34;--mu:#8a8578;--ru:#ddd9d0;--ac:{c};}}
*{{margin:0;padding:0;box-sizing:border-box;}} body{{background:var(--bg);color:var(--ink);font-family:'Source Sans 3',sans-serif;font-weight:300;line-height:1.8;}}
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
.hi{{display:flex;gap:10px;padding:6px 0;border-bottom:1px solid var(--ru);font-size:14px;color:var(--ink2);}}
.hi:last-child{{border-bottom:none;}}
.arr{{color:{c};font-weight:500;flex-shrink:0;}} .arr.up{{color:#2e7d4f;}} .arr.dn{{color:#c4410c;}}
footer{{background:var(--ink);color:#6b6860;padding:18px 40px;font-family:'Source Code Pro',monospace;font-size:11px;letter-spacing:1px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;}}
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
  {parse_sections(content)}
</div>
<footer><span>BRONCS BRIEFING · {date_label}</span><a href="./index.html">← 목록으로</a></footer>
</body></html>"""

def build_index(meta_list):
    js = json.dumps(meta_list, ensure_ascii=False, indent=2)
    return f"""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>BRONCS BRIEFING</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Source+Sans+3:wght@300;400;500&family=Source+Code+Pro:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{{--bg:#f7f4ef;--paper:#fdfcfa;--ink:#1a1814;--ink2:#3d3a34;--mu:#8a8578;--ru:#ddd9d0;--ac:#c4410c;--a2:#1a5c3a;--a3:#1a3a5c;}}
*{{margin:0;padding:0;box-sizing:border-box;}} body{{background:var(--bg);color:var(--ink);font-family:'Source Sans 3',sans-serif;font-weight:300;min-height:100vh;}}
a{{color:inherit;text-decoration:none;}}
.tb{{background:var(--ink);padding:11px 40px;display:flex;justify-content:space-between;font-family:'Source Code Pro',monospace;font-size:11px;color:#6b6860;letter-spacing:2px;}}
.mh{{border-bottom:3px solid var(--ink);padding:44px 40px 28px;max-width:960px;margin:0 auto;}}
h1{{font-family:'Playfair Display',serif;font-size:clamp(52px,9vw,100px);font-weight:900;letter-spacing:-2px;line-height:.92;margin-bottom:18px;}}
h1 span{{color:var(--ac);}}
.ms{{display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:10px;}}
.md{{font-size:14px;color:var(--mu);line-height:1.7;}}
.td{{font-family:'Source Code Pro',monospace;font-size:12px;color:var(--mu);letter-spacing:2px;text-align:right;}}
.stats{{max-width:960px;margin:0 auto;padding:16px 40px;display:flex;gap:28px;border-bottom:1px solid var(--ru);flex-wrap:wrap;}}
.stat{{display:flex;flex-direction:column;gap:2px;}}
.sv{{font-family:'Playfair Display',serif;font-size:24px;font-weight:700;}}
.sk{{font-family:'Source Code Pro',monospace;font-size:10px;letter-spacing:2px;color:var(--mu);}}
.flt{{max-width:960px;margin:0 auto;padding:14px 40px;display:flex;gap:6px;border-bottom:1px solid var(--ru);flex-wrap:wrap;}}
.fb{{font-family:'Source Code Pro',monospace;font-size:11px;letter-spacing:2px;text-transform:uppercase;padding:7px 14px;border:1px solid var(--ru);background:var(--paper);color:var(--mu);cursor:pointer;border-radius:2px;transition:all .15s;}}
.fb:hover,.fb.active{{background:var(--ink);color:var(--bg);border-color:var(--ink);}}
.fb.semi.active{{background:var(--ac);border-color:var(--ac);}}
.fb.ai.active{{background:var(--a2);border-color:var(--a2);}}
.fb.stock.active{{background:var(--a3);border-color:var(--a3);}}
.main{{max-width:960px;margin:0 auto;padding:26px 40px 80px;}}
.dg{{margin-bottom:40px;}}
.dh{{display:flex;align-items:center;gap:14px;margin-bottom:16px;}}
.dht{{font-family:'Playfair Display',serif;font-size:19px;font-weight:600;}}
.dhl{{flex:1;height:1px;background:var(--ru);}}
.dhc{{font-family:'Source Code Pro',monospace;font-size:11px;color:var(--mu);}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:14px;}}
.card{{background:var(--paper);border:1px solid var(--ru);border-radius:2px;padding:20px;display:flex;flex-direction:column;gap:9px;transition:all .15s;position:relative;overflow:hidden;}}
.card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--ac);transform:scaleX(0);transform-origin:left;transition:transform .2s;}}
.card.ai::before{{background:var(--a2);}} .card.stock::before{{background:var(--a3);}}
.card:hover{{box-shadow:0 4px 20px rgba(0,0,0,.08);transform:translateY(-2px);}}
.card:hover::before{{transform:scaleX(1);}}
.cc{{display:flex;align-items:center;gap:7px;font-family:'Source Code Pro',monospace;font-size:10px;letter-spacing:3px;text-transform:uppercase;color:var(--mu);}}
.cd{{width:6px;height:6px;border-radius:50%;background:var(--ac);}}
.cd.ai{{background:var(--a2);}} .cd.stock{{background:var(--a3);}}
.ct{{font-family:'Playfair Display',serif;font-size:16px;font-weight:600;line-height:1.4;color:var(--ink);}}
.cs{{font-size:13px;color:var(--mu);line-height:1.6;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;}}
.cf{{display:flex;justify-content:space-between;align-items:center;margin-top:auto;padding-top:9px;border-top:1px solid var(--ru);font-family:'Source Code Pro',monospace;font-size:11px;color:var(--mu);}}
.ca{{color:var(--ac);font-size:14px;}} .card.ai .ca{{color:var(--a2);}} .card.stock .ca{{color:var(--a3);}}
.empty{{text-align:center;padding:80px 20px;color:var(--mu);}}
footer{{background:var(--ink);color:#6b6860;padding:18px 40px;font-family:'Source Code Pro',monospace;font-size:11px;letter-spacing:1px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;}}
@media(max-width:600px){{.mh,.main,.flt,.stats{{padding-left:18px;padding-right:18px;}}.tb{{padding:10px 18px;}}h1{{letter-spacing:-1px;}}footer{{padding:14px 18px;}}}}
</style></head><body>
<div class="tb"><span>BRONCS BRIEFING SYSTEM</span><span id="ct">--:--:--</span></div>
<div class="mh">
  <h1>DAILY<br>BRIEF<span>.</span></h1>
  <div class="ms"><div class="md">반도체 · AI/LLM · 한국/미국 주식<br>매일 7AM 자동 수집 브리핑</div><div class="td" id="td">--</div></div>
</div>
<div class="stats">
  <div class="stat"><div class="sv" id="tc">0</div><div class="sk">총 브리핑</div></div>
  <div class="stat"><div class="sv" id="sc" style="color:var(--ac)">0</div><div class="sk" style="color:var(--ac)">반도체</div></div>
  <div class="stat"><div class="sv" id="ac2" style="color:var(--a2)">0</div><div class="sk" style="color:var(--a2)">AI/LLM</div></div>
  <div class="stat"><div class="sv" id="stc" style="color:var(--a3)">0</div><div class="sk" style="color:var(--a3)">주식</div></div>
</div>
<div class="flt">
  <button class="fb active" onclick="flt('all',this)">ALL</button>
  <button class="fb semi" onclick="flt('semi',this)">반도체</button>
  <button class="fb ai" onclick="flt('ai',this)">AI / LLM</button>
  <button class="fb stock" onclick="flt('stock',this)">주식</button>
</div>
<div class="main" id="main"></div>
<footer><span>BRONCS BRIEFING · AUTO-GENERATED</span><span>OpenClaw + GitHub Pages</span></footer>
<script>
const DATA={js};
const CAT={{semi:'반도체',ai:'AI / LLM',stock:'주식·시장'}};
function tick(){{
  const n=new Date();
  document.getElementById('ct').textContent=n.toLocaleTimeString('ko-KR',{{hour12:false}});
  document.getElementById('td').textContent=n.toLocaleDateString('ko-KR',{{year:'numeric',month:'long',day:'numeric',weekday:'long'}});
}}
tick();setInterval(tick,1000);
function stats(){{
  document.getElementById('tc').textContent=DATA.length;
  document.getElementById('sc').textContent=DATA.filter(b=>b.category==='semi').length;
  document.getElementById('ac2').textContent=DATA.filter(b=>b.category==='ai').length;
  document.getElementById('stc').textContent=DATA.filter(b=>b.category==='stock').length;
}}
function render(data){{
  const m=document.getElementById('main');
  if(!data.length){{m.innerHTML='<div class="empty"><p>브리핑이 없습니다.</p></div>';return;}}
  const g={{}};data.forEach(b=>{{if(!g[b.date])g[b.date]=[];g[b.date].push(b);}});
  m.innerHTML=Object.keys(g).sort().reverse().map(date=>{{
    const items=g[date];
    const dl=new Date(date+'T00:00:00').toLocaleDateString('ko-KR',{{year:'numeric',month:'long',day:'numeric',weekday:'long'}});
    return `<div class="dg"><div class="dh"><div class="dht">${{dl}}</div><div class="dhl"></div><div class="dhc">${{items.length}}건</div></div>
    <div class="cards">${{items.map(b=>`<a class="card ${{b.category}}" href="${{b.file}}">
      <div class="cc"><div class="cd ${{b.category}}"></div>${{CAT[b.category]||b.category}}</div>
      <div class="ct">${{b.title}}</div><div class="cs">${{b.summary}}</div>
      <div class="cf"><span>⏰ ${{b.time}}</span><span class="ca">→</span></div>
    </a>`).join('')}}</div></div>`;
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
    gh_put("briefings_meta.json", json.dumps(meta_list, ensure_ascii=False, indent=2),
           "chore: update meta", sha)

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
    print(f"[TG] {'✅ 발송' if res.ok else '❌ ' + res.text[:80]}")

# ─── 메인 ────────────────────────────────────────────────────────────────────
def save_briefing(category: str, content: str, summary: str = "", title_override: str = "") -> str:
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN 환경변수가 없습니다.")

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

    # 중복 파일명 처리
    filename = f"{date_str}_{category}.html"
    existing, _ = gh_get(filename)
    if existing:
        filename = f"{date_str}_{category}_{now.strftime('%H%M')}.html"

    # 브리핑 페이지 업로드
    html = build_page(title, date_label, time_str, category, summary, content, item_count)
    gh_put(filename, html, f"briefing: {title}")

    # 메타 업데이트
    meta = load_meta()
    meta = [m for m in meta if m.get("file") != f"./{filename}"]
    meta.append({"id": filename.replace(".html",""), "date": date_str, "time": time_str,
                 "category": category, "title": title, "summary": summary, "file": f"./{filename}"})
    meta.sort(key=lambda x: (x["date"], x["time"]), reverse=True)
    save_meta(meta)

    # 인덱스 재생성
    _, idx_sha = gh_get("index.html")
    gh_put("index.html", build_index(meta), "chore: rebuild index", idx_sha)

    url = f"{BASE_URL}/{filename}"
    send_tg(category, title, summary, url)
    print(f"[DONE] {url}")
    return url

# ─── CLI ─────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--category", choices=["semi","ai","stock"], required=True)
    p.add_argument("--content", type=str)
    p.add_argument("--content-file", type=str)
    p.add_argument("--summary", type=str, default="")
    p.add_argument("--title", type=str, default="")
    args = p.parse_args()

    if args.content_file:   content = open(args.content_file, encoding="utf-8").read()
    elif args.content:      content = args.content
    else:                   content = sys.stdin.read()

    save_briefing(category=args.category, content=content,
                  summary=args.summary, title_override=args.title)

if __name__ == "__main__":
    main()
