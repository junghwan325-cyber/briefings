#!/usr/bin/env python3
"""
daily_briefing.py
매일 7AM 실행되는 OpenClaw 브리핑 스크립트

카테고리: 날씨 / 반도체 / AI / 주식 / 국제정세 / 일정 / 할일

실행:
  python3 /home/broncs/daily_briefing.py

크론 등록:
  0 7 * * * /usr/bin/python3 /home/broncs/daily_briefing.py >> /home/broncs/logs/briefing.log 2>&1
"""

import os
import sys
import subprocess
import requests
from datetime import datetime, timedelta

# ── 설정 ─────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
OWM_API_KEY      = os.getenv("OWM_API_KEY", "")
DONGTAN_LAT      = "37.2098"
DONGTAN_LON      = "126.9817"
OPENCLAW_BIN     = "/root/.openclaw/bin/openclaw"  # openclaw 실행파일
BRIEFING_SAVER   = "/home/broncs/briefing_saver.py"
LOG_DIR          = "/home/broncs/logs"

os.makedirs(LOG_DIR, exist_ok=True)

def log(msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}", flush=True)

# ── 텔레그램 ──────────────────────────────────────────────────────────────────
def send_tg(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
        timeout=10
    )

# ── OpenClaw 호출 ─────────────────────────────────────────────────────────────
def ask_openclaw(prompt: str, model: str = "github-copilot/gpt-4o") -> str:
    """
    OpenClaw CLI를 통해 LLM에 질문하고 응답 반환
    """
    try:
        result = subprocess.run(
            [OPENCLAW_BIN, "run", "--model", model, "--no-stream", prompt],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            log(f"[OpenClaw 오류] {result.stderr[:200]}")
            return ""
    except subprocess.TimeoutExpired:
        log("[OpenClaw] 타임아웃")
        return ""
    except FileNotFoundError:
        log(f"[OpenClaw] 실행파일 없음: {OPENCLAW_BIN}")
        return ""

# ── briefing_saver 호출 ───────────────────────────────────────────────────────
def save_to_github(category: str, content: str, summary: str = ""):
    """briefing_saver.py를 subprocess로 호출해 GitHub Pages에 저장"""
    try:
        cmd = [
            sys.executable, BRIEFING_SAVER,
            "--category", category,
            "--content", content,
        ]
        if summary:
            cmd += ["--summary", summary]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                                env={**os.environ})
        log(f"[SAVE:{category}] {result.stdout.strip()}")
        if result.returncode != 0:
            log(f"[SAVE:{category}] STDERR: {result.stderr[:200]}")
    except Exception as e:
        log(f"[SAVE:{category}] 실패: {e}")

# ── 1. 날씨 브리핑 ────────────────────────────────────────────────────────────
def briefing_weather():
    log("=== 날씨 브리핑 시작 ===")
    try:
        # 현재 날씨
        now_res = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": DONGTAN_LAT, "lon": DONGTAN_LON,
                    "appid": OWM_API_KEY, "units": "metric", "lang": "kr"},
            timeout=10
        ).json()

        # 5일 예보
        fore_res = requests.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={"lat": DONGTAN_LAT, "lon": DONGTAN_LON,
                    "appid": OWM_API_KEY, "units": "metric", "lang": "kr", "cnt": 24},
            timeout=10
        ).json()

        temp     = now_res["main"]["temp"]
        feels    = now_res["main"]["feels_like"]
        humidity = now_res["main"]["humidity"]
        desc     = now_res["weather"][0]["description"]
        wind     = now_res["wind"]["speed"]
        sunrise  = datetime.fromtimestamp(now_res["sys"]["sunrise"]).strftime("%H:%M")
        sunset   = datetime.fromtimestamp(now_res["sys"]["sunset"]).strftime("%H:%M")

        # 날짜별 예보 정리
        daily = {}
        for f in fore_res.get("list", []):
            d = datetime.fromtimestamp(f["dt"]).strftime("%Y-%m-%d")
            if d not in daily:
                daily[d] = {"temps": [], "descs": [], "rain": 0}
            daily[d]["temps"].append(f["main"]["temp"])
            daily[d]["descs"].append(f["weather"][0]["description"])
            daily[d]["rain"] = max(daily[d]["rain"], f.get("pop", 0) * 100)

        today     = datetime.now().strftime("%Y-%m-%d")
        tomorrow  = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")

        def day_summary(d):
            if d not in daily:
                return "데이터 없음"
            t = daily[d]["temps"]
            desc_d = daily[d]["descs"][len(daily[d]["descs"])//2]
            return f"{desc_d} · 최저 {min(t):.0f}°C / 최고 {max(t):.0f}°C · 강수확률 {daily[d]['rain']:.0f}%"

        content = f"""## 현재 날씨 — 동탄
기온 {temp:.1f}°C (체감 {feels:.1f}°C), {desc}
- 습도: {humidity}%
- 풍속: {wind}m/s
- 일출: {sunrise} / 일몰: {sunset}

## 오늘 ({today})
{day_summary(today)}

## 내일 ({tomorrow})
{day_summary(tomorrow)}

## 모레 ({day_after})
{day_summary(day_after)}"""

        summary = f"현재 {temp:.1f}°C {desc} · 내일 {day_summary(tomorrow).split('·')[0].strip()}"

        # LLM으로 날씨 코멘트 생성
        comment = ask_openclaw(
            f"동탄 현재 날씨: {temp:.1f}°C, {desc}, 습도 {humidity}%, 풍속 {wind}m/s. "
            f"내일은 {day_summary(tomorrow)}. "
            f"오늘 외출이나 생활에 도움이 되는 날씨 코멘트를 2~3문장으로 짧게 한국어로 알려줘. "
            f"친근하고 실용적으로."
        )
        if comment:
            content += f"\n\n## 날씨 코멘트\n{comment}"

        save_to_github("weather", content, summary)
        log("=== 날씨 브리핑 완료 ===")
    except Exception as e:
        log(f"[날씨] 오류: {e}")

# ── 2. 반도체 브리핑 ──────────────────────────────────────────────────────────
def briefing_semi():
    log("=== 반도체 브리핑 시작 ===")
    prompt = """오늘 반도체 업계 최신 뉴스를 브리핑해줘. 아래 형식을 정확히 따라줘:

## [뉴스 제목]
[3~5줄 상세 설명. 배경, 의미, 영향까지 포함]
https://[실제 기사 URL 또는 관련 URL]
- [핵심 포인트 1]
- [핵심 포인트 2]
- [핵심 포인트 3]

다룰 주제: SK하이닉스, 삼성전자, TSMC, 엔비디아, HBM, AI 메모리, 반도체 수출, 공급망
최소 3개 이상의 뉴스 항목을 포함해줘. 한국어로."""

    content = ask_openclaw(prompt)
    if not content:
        content = "## 반도체 브리핑\n오늘 브리핑 데이터를 가져오지 못했습니다."

    summary = content.split("\n")[0].replace("## ", "")[:100]
    save_to_github("semi", content, summary)
    log("=== 반도체 브리핑 완료 ===")

# ── 3. AI/LLM 브리핑 ──────────────────────────────────────────────────────────
def briefing_ai():
    log("=== AI 브리핑 시작 ===")
    prompt = """오늘 AI/LLM 업계 최신 뉴스를 브리핑해줘. 아래 형식을 정확히 따라줘:

## [뉴스 제목]
[3~5줄 상세 설명. 기술적 의미, 산업 영향, 경쟁 구도까지 포함]
https://[실제 기사 URL 또는 관련 URL]
- [핵심 포인트 1]
- [핵심 포인트 2]
- [핵심 포인트 3]

다룰 주제: OpenAI, Anthropic, Google Gemini, Meta AI, 오픈소스 LLM, AI 규제, AI 투자, 한국 AI 정책
최소 3개 이상의 뉴스 항목을 포함해줘. 한국어로."""

    content = ask_openclaw(prompt)
    if not content:
        content = "## AI 브리핑\n오늘 브리핑 데이터를 가져오지 못했습니다."

    summary = content.split("\n")[0].replace("## ", "")[:100]
    save_to_github("ai", content, summary)
    log("=== AI 브리핑 완료 ===")

# ── 4. 주식 브리핑 ────────────────────────────────────────────────────────────
def briefing_stock():
    log("=== 주식 브리핑 시작 ===")
    prompt = """오늘 한국/미국 주식시장 브리핑을 해줘. 아래 형식을 정확히 따라줘:

## 한국 증시
[코스피/코스닥 동향, 주요 섹터, 특징주 3~5줄 상세 설명]
https://[관련 URL]
- [핵심 포인트 1]
- [핵심 포인트 2]

## 미국 증시
[나스닥/S&P500/다우 동향, 빅테크 동향 3~5줄 상세 설명]
https://[관련 URL]
- [핵심 포인트 1]
- [핵심 포인트 2]

## 주목할 종목
[SK하이닉스, 삼성전자, 엔비디아 등 반도체/AI 관련 종목 동향]
- [종목명]: [동향 및 이유]

## 환율/원자재
[원달러 환율, 유가, 금 시세]
- 원/달러: [시세]
- 유가(WTI): [시세]

한국어로."""

    content = ask_openclaw(prompt)
    if not content:
        content = "## 주식 브리핑\n오늘 브리핑 데이터를 가져오지 못했습니다."

    summary = content.split("\n")[0].replace("## ", "")[:100]
    save_to_github("stock", content, summary)
    log("=== 주식 브리핑 완료 ===")

# ── 5. 국제정세 브리핑 ────────────────────────────────────────────────────────
def briefing_world():
    log("=== 국제정세 브리핑 시작 ===")
    prompt = """오늘 주요 국제정세 뉴스를 브리핑해줘. 아래 형식을 정확히 따라줘:

## [뉴스 제목]
[3~5줄 상세 설명. 배경, 각국 입장, 한국에 미치는 영향까지 포함]
https://[실제 기사 URL 또는 관련 URL]
- [핵심 포인트 1]
- [핵심 포인트 2]
- [핵심 포인트 3]

다룰 주제: 미중 관계, 중동 정세, 러우 전쟁, 북한, 한미일 외교, 무역/관세, 글로벌 경제
최소 3개 이상의 뉴스 항목을 포함해줘. 한국어로."""

    content = ask_openclaw(prompt)
    if not content:
        content = "## 국제정세 브리핑\n오늘 브리핑 데이터를 가져오지 못했습니다."

    summary = content.split("\n")[0].replace("## ", "")[:100]
    save_to_github("world", content, summary)
    log("=== 국제정세 브리핑 완료 ===")

# ── 6. 일정 브리핑 (Google Calendar MCP) ─────────────────────────────────────
def briefing_schedule():
    log("=== 일정 브리핑 시작 ===")
    prompt = """Google Calendar MCP를 사용해서 오늘, 내일, 모레 3일치 일정을 가져와서 아래 형식으로 정리해줘:

## 오늘 일정
- [시간] **[제목]** · 📍[장소]
  [메모/설명]

## 내일 일정  
- [시간] **[제목]** · 📍[장소]

## 모레 일정
- [시간] **[제목]** · 📍[장소]

일정이 없으면 '일정 없음'으로 표시. 한국어로."""

    content = ask_openclaw(prompt)
    if not content:
        content = "## 일정 브리핑\n일정 데이터를 가져오지 못했습니다."

    summary = "3일치 일정 브리핑"
    save_to_github("schedule", content, summary)
    log("=== 일정 브리핑 완료 ===")

# ── 7. 할일 브리핑 (Google Tasks MCP) ────────────────────────────────────────
def briefing_tasks():
    log("=== 할일 브리핑 시작 ===")
    prompt = """Google Tasks MCP를 사용해서 미완료 할일 목록을 가져와서 아래 형식으로 정리해줘:

## 오늘 해야 할 일
- **[할일 제목]** · 마감: [날짜]
  [메모]

## 예정된 할일
- **[할일 제목]** · 마감: [날짜]

## 완료된 할일
- ~~[할일 제목]~~

우선순위 높은 것부터 정렬. 한국어로."""

    content = ask_openclaw(prompt)
    if not content:
        content = "## 할일 브리핑\n할일 데이터를 가져오지 못했습니다."

    summary = "오늘의 할일 브리핑"
    save_to_github("tasks", content, summary)
    log("=== 할일 브리핑 완료 ===")

# ── 메인 ─────────────────────────────────────────────────────────────────────
def main():
    now = datetime.now()
    log(f"{'='*50}")
    log(f"데일리 브리핑 시작 — {now.strftime('%Y년 %m월 %d일 %H:%M')}")
    log(f"{'='*50}")

    # 시작 알림
    send_tg(f"🌅 *데일리 브리핑 시작*\n{now.strftime('%Y년 %m월 %d일 %H:%M')}\n\n잠시 후 각 브리핑 링크를 보내드립니다.")

    # 순서대로 실행
    briefing_weather()
    briefing_schedule()
    briefing_tasks()
    briefing_semi()
    briefing_ai()
    briefing_stock()
    briefing_world()

    log(f"{'='*50}")
    log("데일리 브리핑 완료")
    log(f"{'='*50}")

    # 완료 알림
    from briefing_saver import BASE_URL
    send_tg(f"✅ *브리핑 완료*\n\n[📋 전체 목록 보기]({BASE_URL}/index.html)")

if __name__ == "__main__":
    main()
