# -*- coding: utf-8 -*-
"""공개 데이터 → 10주제 × 5문항.

**모든 숫자는 raw/ 의 원본에서 계산합니다.** 지어낸 값이 하나도 없어야 합니다.
결과는 앱이 읽는 topics/*.json 과, 사람이 읽는 tools/정답지.md 로 나갑니다.

정답지와 이 스크립트는 .vercelignore 에 들어 있어 **배포되지 않습니다.**
공개 URL 에 정답지가 올라가면 게임이 성립하지 않습니다.

실행 (저장소 최상위에서):
    python tools/build_topics.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
import datetime as dt
from collections import Counter
from pathlib import Path
from statistics import mean

# 윈도우 콘솔(cp949)은 이모지 · 기호를 못 찍고 멈춘다. 출력만 UTF-8 로 맞춘다
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

HERE = Path(__file__).resolve().parent          # tools/
APP = HERE.parent                                # 저장소 최상위 = 배포되는 곳
RAW = APP / "data" / "raw"
OUT = APP / "topics"

TOPICS: list[dict] = []


def load_json(name):
    return json.load(io.open(RAW / name, encoding="utf-8"))


def load_csv(name):
    return list(csv.DictReader(io.open(RAW / name, encoding="utf-8")))


# World Bank·OWID 응답에는 '유럽연합' '고소득국' 같은 **집계치**가 섞여 있다.
# 그대로 순위를 매기면 나라와 대륙을 한 줄에 놓고 세는 셈이 된다.
REAL = {x["id"] for x in load_json("wb_countries.json")[1]
        if x["region"]["id"] != "NA"}


def wb_countries(rows, year):
    """그 해의 실제 국가 값만 남긴다 (집계치 제외)."""
    return {r["country"]["value"]: r["value"] for r in rows
            if int(r["date"]) == year and r["countryiso3code"] in REAL}


def owid_countries(rows, year, col):
    """OWID 도 마찬가지. code 가 비었거나 OWID_ 로 시작하면 집계치다."""
    return {r["entity"]: float(r[col]) for r in rows
            if int(r["year"]) == year and r["code"]
            and not r["code"].startswith("OWID")}


def topic(tid, emoji, title, blurb, source, source_url, questions, caveat=""):
    """caveat = 이 데이터를 믿을 때의 한계. 앱 화면에도 그대로 나간다.

    출처가 다르면 같은 '서울 기온'도 값이 다르다. 그 사실을 감추지 않는다.
    """
    TOPICS.append({"id": tid, "emoji": emoji, "title": title, "blurb": blurb,
                   "source": source, "source_url": source_url,
                   "caveat": caveat, "questions": questions})


def slider(qid, text, answer, unit, lo, hi, step, basis, why):
    return {"id": qid, "type": "slider", "text": text, "unit": unit,
            "min": lo, "max": hi, "step": step,
            "answer": round(float(answer), 1), "basis": basis, "why": why}


def choice(qid, text, options, answer, basis, why):
    assert answer in options, f"{qid}: 정답이 선택지에 없습니다"
    return {"id": qid, "type": "choice", "text": text, "options": options,
            "answer": answer, "basis": basis, "why": why}


# ════════════════════════════════════════════════════════════════
# 기상 공통
# ════════════════════════════════════════════════════════════════
w = load_json("seoul_weather.json")["daily"]
W = [{"d": dt.date.fromisoformat(t), "hi": hi, "lo": lo, "rain": r}
     for t, hi, lo, r in zip(w["time"], w["temperature_2m_max"],
                             w["temperature_2m_min"], w["precipitation_sum"])]
W24 = [x for x in W if x["d"].year == 2024]


def years(a, b):
    return [x for x in W if a <= x["d"].year <= b]


# ── 1. 서울 기온 ─────────────────────────────────────────────────
# ERA5 는 1950~70년대 구간의 품질이 낮고(초기 확장), 격자 평균이라 도심
# 관측값보다 낮게 나온다. 그래서 '역대 최고기온'이나 '폭염일 추세'처럼
# 그 구간에 기대는 문항은 쓰지 않는다. 열대야·연평균처럼 신호가 뚜렷한 것만 쓴다.
tropical_24 = sum(1 for x in W24 if x["lo"] >= 25)
trop_50s = sum(1 for x in years(1950, 1959) if x["lo"] >= 25) / 10
trop_10s = sum(1 for x in years(2015, 2024) if x["lo"] >= 25) / 10
t_ratio = trop_10s / trop_50s if trop_50s else 0
mean_50s = mean((x["hi"] + x["lo"]) / 2 for x in years(1950, 1959))
mean_10s = mean((x["hi"] + x["lo"]) / 2 for x in years(2015, 2024))
warming = mean_10s - mean_50s
below0_24 = sum(1 for x in W24 if x["lo"] < 0)
hot_days = Counter((x["d"].month, x["d"].day)
                   for x in years(1995, 2024) if x["hi"] >= 33)
peak_day = hot_days.most_common(1)[0]
# 한계 문장의 숫자도 손으로 적지 않는다 — 원본에서 가장 더웠던 날을 찾는다
hottest = max(W, key=lambda x: x["hi"])

topic(
    "seoul-heat", "🌡️", "서울은 얼마나 더워졌나",
    "1950년부터 2024년까지, 서울의 매일 기온",
    "Open-Meteo Archive (ERA5 재분석)", "https://open-meteo.com/",
    [
        slider("h1", "2024년 서울에서 열대야(밤 최저기온 25도 이상)는 며칠이었을까요?",
               tropical_24, "일", 0, 60, 1,
               f"2024년 일최저기온 25도 이상인 날 {tropical_24}일",
               "유난히 더웠던 밤 몇 번이 기억을 지배합니다. 실제 일수는 세어 봐야 "
               "압니다."),
        # 보기는 배수에 가장 가까운 것이 정답이 되게 경계를 둔다 (2.8배 → «약 3배»)
        choice("h2", "1950년대와 2015~2024년, 열대야는 몇 배 차이일까요?",
               ["거의 같다", "약 2배", "약 3배", "약 5배"],
               ["거의 같다", "약 2배", "약 3배", "약 5배"][
                   0 if t_ratio < 1.5 else 1 if t_ratio < 2.5
                   else 2 if t_ratio < 4 else 3],
               f"연평균 열대야 1950년대 {trop_50s:.1f}일 → 2015~2024년 "
               f"{trop_10s:.1f}일 ({t_ratio:.1f}배)",
               "'옛날에도 더웠다'는 느낌과 기록은 다릅니다. 기억은 유난히 더웠던 "
               "몇 밤으로 남지만, 기록은 해마다 빠짐없이 셉니다."),
        slider("h3", "1950년대와 비교해 서울의 연평균 기온은 몇 도 올랐을까요?",
               warming, "도", 0, 4, 0.1,
               f"1950년대 {mean_50s:.2f}도 → 2015~2024년 {mean_10s:.2f}도 "
               f"(+{warming:.2f}도)",
               "1~2도는 작아 보이지만, 그 변화가 열대야 일수를 몇 배로 바꿉니다. "
               "평균의 변화와 극단의 변화는 크기가 다릅니다."),
        choice("h4", "최근 30년간 33도 이상인 날이 가장 잦았던 날짜는?",
               ["7월 초", "7월 말", "8월 초", "8월 말"],
               "7월 말" if peak_day[0][0] == 7 and peak_day[0][1] >= 20
               else "8월 초" if peak_day[0][0] == 8 and peak_day[0][1] <= 10
               else "7월 초" if peak_day[0][0] == 7 else "8월 말",
               f"1995~2024년 중 가장 잦았던 날짜는 {peak_day[0][0]}월 "
               f"{peak_day[0][1]}일 ({peak_day[1]}회)",
               "장마가 끝나는 시점과 가장 더운 시점은 다릅니다."),
        slider("h5", "2024년 서울에서 밤 기온이 영하로 내려간 날은 며칠이었을까요?",
               below0_24, "일", 30, 150, 5,
               f"2024년 일최저기온 0도 미만인 날 {below0_24}일",
               "겨울이 짧아졌다고 느끼지만, 영하로 내려가는 날은 여전히 석 달 "
               "치가 넘습니다."),
    ],
    caveat="ERA5는 넓은 격자의 재분석 값이라 도심 관측소와 다르게 나옵니다. "
           f"예컨대 여기서는 역대 최고기온이 {hottest['hi']:.1f}도"
           f"({hottest['d']:%Y년})지만 기상청 서울 관측 기록은 2018년 39.6도입니다. "
           "같은 '서울 기온'도 출처에 따라 다릅니다.")

# ── 2. 비 ────────────────────────────────────────────────────────
rain_days = [sum(1 for x in W if x["d"].year == y and x["rain"] >= 1.0)
             for y in range(1995, 2025)]
rain_avg = mean(rain_days)
by_month = {m: mean([sum(x["rain"] for x in W
                         if x["d"].year == y and x["d"].month == m)
                     for y in range(1995, 2025)]) for m in range(1, 13)}
wettest_m = max(by_month, key=by_month.get)
max_day = max(W, key=lambda x: x["rain"])
ann = {y: sum(x["rain"] for x in W if x["d"].year == y) for y in range(1995, 2025)}
norm = mean(ann.values())
r2024 = ann[2024]


def days_to_half(y):
    v = sorted((x["rain"] for x in W if x["d"].year == y), reverse=True)
    half, s = sum(v) / 2, 0
    for i, r in enumerate(v, 1):
        s += r
        if s >= half:
            return i
    return len(v)


half_days = round(mean(days_to_half(y) for y in range(1995, 2025)))

topic(
    "seoul-rain", "☔", "비는 언제, 얼마나",
    "서울의 하루치 강수량 30년",
    "Open-Meteo Archive (ERA5 재분석)", "https://open-meteo.com/",
    [
        slider("r1", "서울에서 1년 중 비가 온 날(1mm 이상)은 며칠쯤일까요?",
               rain_avg, "일", 40, 160, 5,
               f"1995~2024년 평균 {rain_avg:.1f}일 "
               f"(최소 {min(rain_days)}일 · 최대 {max(rain_days)}일)",
               "비 오는 날은 기억에 오래 남아서 실제보다 많게 느껴집니다."),
        choice("r2", "1년 강수량이 가장 많은 달은?",
               ["6월", "7월", "8월", "9월"], f"{wettest_m}월",
               " · ".join(f"{m}월 {by_month[m]:.0f}mm" for m in (6, 7, 8, 9)),
               "장마가 낀 달과 비가 가장 많이 오는 달이 같지 않을 수 있습니다."),
        slider("r3", "하루에 내린 비의 최대 기록은?",
               max_day["rain"], "mm", 100, 500, 10,
               f"{max_day['d']:%Y년 %m월 %d일} {max_day['rain']:.1f}mm",
               f"가장 많이 온 날 하루에, 비가 가장 많은 {wettest_m}월 한 달 평균"
               f"({by_month[wettest_m]:.0f}mm)의 {max_day['rain'] / by_month[wettest_m] * 100:.0f}%가 "
               "쏟아졌습니다. 비는 고르게 오지 않습니다."),
        slider("r4", "1년 강수량의 절반은 '비 온 날' 며칠 만에 채워질까요?",
               half_days, "일", 3, 40, 1,
               f"많이 온 날부터 더해서 연 강수량의 절반에 도달하는 데 "
               f"평균 {half_days}일 (1995~2024년)",
               "비는 고르게 오지 않습니다. 열흘 남짓이 1년의 절반을 만듭니다."),
        slider("r5", "2024년 서울 강수량은 30년 평균의 몇 %였을까요?",
               r2024 / norm * 100, "%", 50, 180, 5,
               f"2024년 {r2024:.0f}mm · 1995~2024년 평균 {norm:.0f}mm",
               "'올해 비가 많았다'는 체감과 실제 총량은 자주 어긋납니다."),
    ],
    caveat="ERA5 재분석 값입니다. 기상청 관측 강수량과 조금씩 다릅니다.")

# ── 3. 미세먼지 ──────────────────────────────────────────────────
a = load_json("seoul_air.json")["hourly"]
A = [{"t": dt.datetime.fromisoformat(t), "pm25": p25, "pm10": p10}
     for t, p25, p10 in zip(a["time"], a["pm2_5"], a["pm10"])]
A24 = [x for x in A if x["t"].year == 2024]
pm_month = {m: mean([x["pm25"] for x in A if x["t"].month == m])
            for m in range(1, 13)}
worst_m = max(pm_month, key=pm_month.get)
pm_hour = {h: mean([x["pm25"] for x in A if x["t"].hour == h])
           for h in range(24)}
worst_h = max(pm_hour, key=pm_hour.get)
pm24_avg = mean(x["pm25"] for x in A24)


def daily_avg(year):
    d = {}
    for x in A:
        if x["t"].year == year:
            d.setdefault(x["t"].date(), []).append(x["pm25"])
    return {k: mean(v) for k, v in d.items()}


d24 = daily_avg(2024)
d23 = daily_avg(2023)
bad_ratio = sum(1 for v in d24.values() if v > 35) / len(d24) * 100
worse_year = "2023년" if mean(d23.values()) > mean(d24.values()) else "2024년"

topic(
    "seoul-air", "😷", "미세먼지, 언제 나쁜가",
    "서울의 시간별 초미세먼지 2년치",
    "Open-Meteo Air Quality (CAMS)", "https://open-meteo.com/",
    [
        choice("a1", "초미세먼지(PM2.5)가 가장 나쁜 달은?",
               ["1월", "3월", "5월", "11월"],
               f"{worst_m}월" if f"{worst_m}월" in ["1월", "3월", "5월", "11월"]
               else "3월",
               " · ".join(f"{m}월 {pm_month[m]:.1f}" for m in (1, 3, 5, 11))
               + f" (최악은 {worst_m}월 {pm_month[worst_m]:.1f})",
               "황사 뉴스가 많은 달과 실제 수치가 높은 달은 다를 수 있습니다."),
        slider("a2", "2024년 서울의 초미세먼지 연평균 농도는?",
               pm24_avg, "㎍/㎥", 5, 60, 1,
               f"2024년 시간값 {len(A24):,}개의 평균 {pm24_avg:.1f}㎍/㎥ "
               f"(WHO 권고 연평균 5, 국내 기준 15)",
               "'나쁨'인 날이 인상에 남아서 연평균을 높게 잡게 됩니다."),
        choice("a3", "하루 중 초미세먼지가 가장 높은 시간대는?",
               ["새벽 4시", "오전 10시", "오후 3시", "밤 9시"],
               {4: "새벽 4시", 10: "오전 10시", 15: "오후 3시",
                21: "밤 9시"}.get(worst_h, "오전 10시"),
               " · ".join(f"{h}시 {pm_hour[h]:.1f}" for h in (4, 10, 15, 21))
               + f" (최고는 {worst_h}시)",
               "출퇴근 시간이 가장 나쁠 것 같지만 대기가 정체되는 시간은 따로 "
               "있습니다."),
        slider("a4", "2024년 하루 평균이 '나쁨'(35㎍/㎥ 초과)이었던 날의 비율은?",
               bad_ratio, "%", 0, 60, 1,
               f"2024년 {len(d24)}일 중 "
               f"{sum(1 for v in d24.values() if v > 35)}일",
               "마스크를 챙긴 날은 강하게 기억되지만, 1년 전체로 보면 비율이 "
               "다릅니다."),
        choice("a5", "2023년과 2024년 중 초미세먼지가 더 나빴던 해는?",
               ["2023년", "2024년"], worse_year,
               f"연평균 2023년 {mean(d23.values()):.1f} · "
               f"2024년 {mean(d24.values()):.1f}㎍/㎥",
               "체감은 최근 쪽으로 쏠립니다. 두 해 차이는 생각보다 작습니다."),
    ],
    caveat="CAMS 대기질 모델의 추정값입니다. 에어코리아 측정소 실측값과 "
           "다를 수 있습니다.")

# ── 4. 노동시간 ──────────────────────────────────────────────────
wh = [r for r in load_csv("working_hours.csv") if r["working_hours_omm"]]
latest_year = max(int(r["year"]) for r in wh if r["code"] == "KOR")
cur = owid_countries(wh, latest_year, "working_hours_omm")
kor = cur["South Korea"]
rank = sorted(cur.items(), key=lambda kv: -kv[1])
kor_rank = [k for k, _ in rank].index("South Korea") + 1
longer = kor_rank - 1
past = {int(r["year"]): float(r["working_hours_omm"])
        for r in wh if r["code"] == "KOR"}
y30 = latest_year - 30
drop = past[y30] - kor
trio = {c: cur[c] for c in ("South Korea", "Japan", "Germany") if c in cur}
shortest = min(trio, key=trio.get)
name_ko = {"South Korea": "한국", "Japan": "일본", "Germany": "독일"}

topic(
    "working-hours", "⏰", "우리는 얼마나 일하나",
    "나라별 1인당 연간 노동시간",
    "Our World in Data", "https://ourworldindata.org/grapher/annual-working-hours-per-worker",
    [
        slider("w1", f"{latest_year}년 한국의 1인당 연간 노동시간은?",
               kor, "시간", 1200, 2600, 50,
               f"{latest_year}년 한국 {kor:,.0f}시간 "
               f"(주 5일 기준 하루 약 {kor / 250:.1f}시간)",
               "연 단위로 물으면 감이 잘 안 옵니다. 하루로 나눠 보면 체감과 "
               "맞는지 확인할 수 있습니다."),
        slider("w2", f"한국보다 더 오래 일하는 나라는 {len(cur)}개국 중 몇 개일까요?",
               longer, "개국", 0, 60, 1,
               f"{latest_year}년 기준 {len(cur)}개국 중 한국은 {kor_rank}위",
               "'한국이 제일 많이 일한다'는 인상이 강하지만, 비교 대상에 따라 "
               "순위가 달라집니다."),
        slider("w3", f"한국의 노동시간은 30년 전({y30}년)보다 몇 시간 줄었을까요?",
               drop, "시간", 0, 900, 50,
               f"{y30}년 {past[y30]:,.0f}시간 → {latest_year}년 {kor:,.0f}시간",
               "줄어든 폭은 대개 과소평가됩니다. 하루로 치면 크게 달라진 값입니다."),
        choice("w4", "한국·일본·독일 중 가장 적게 일하는 나라는?",
               ["한국", "일본", "독일"], name_ko[shortest],
               " · ".join(f"{name_ko[c]} {trio[c]:,.0f}시간" for c in trio),
               "나라마다 통계 기준이 다릅니다. 순위보다 격차의 크기를 봅니다."),
        slider("w5", "한국과 독일의 연간 노동시간 차이는?",
               abs(cur["South Korea"] - cur["Germany"]), "시간", 0, 900, 50,
               f"한국 {cur['South Korea']:,.0f} · 독일 "
               f"{cur['Germany']:,.0f}시간",
               "두 나라 차이를 주 단위로 나눠 보면 체감이 확 달라집니다."),
    ],
    caveat="이 자료에는 개발도상국이 많이 포함돼 있어, OECD 안에서의 순위와 "
           "전체 순위가 다릅니다. '어느 집단과 비교하느냐'가 순위를 만듭니다.")

# ── 5. 인구와 출산 ───────────────────────────────────────────────
fert = [r for r in load_json("wb_fertility.json")[1] if r["value"] is not None]
f_latest = max(int(r["date"]) for r in fert if r["countryiso3code"] == "KOR")
f_cur = wb_countries(fert, f_latest)
kor_f = f_cur["Korea, Rep."]
f_rank = sorted(f_cur.items(), key=lambda kv: kv[1])
kor_f_rank = [k for k, _ in f_rank].index("Korea, Rep.") + 1
kor_1970 = next(r["value"] for r in fert
                if r["countryiso3code"] == "KOR" and r["date"] == "1970")

pop = load_json("wb_pop_kor.json")[1]
tot = {int(r["date"]): r["value"] for r in pop
       if r["indicator"]["id"] == "SP.POP.TOTL" and r["value"]}
old = {int(r["date"]): r["value"] for r in pop
       if r["indicator"]["id"] == "SP.POP.65UP.TO.ZS" and r["value"]}
urb = {int(r["date"]): r["value"] for r in pop
       if r["indicator"]["id"] == "SP.URB.TOTL.IN.ZS" and r["value"]}
peak_year = max(tot, key=tot.get)
old_latest = max(old)
urb_latest = max(urb)

topic(
    "population", "👶", "인구와 출산",
    "전 세계 출산율과 한국의 인구 구조",
    "World Bank Open Data", "https://data.worldbank.org/",
    [
        slider("p1", f"{f_latest}년 한국의 합계출산율(여성 1명당 출생아 수)은?",
               kor_f, "명", 0.5, 3.0, 0.05,
               f"{f_latest}년 한국 {kor_f:.2f}명",
               "숫자는 자주 들었어도 '여성 1명당'이라는 단위는 잘 안 와닿습니다."),
        slider("p2", f"출산율이 낮은 순으로 세면 한국은 {len(f_cur)}개 나라·지역 중 몇 위일까요?",
               kor_f_rank, "위", 1, 30, 1,
               f"{f_latest}년 기준 {len(f_cur)}곳 중 {kor_f_rank}위 "
               f"(1위 {f_rank[0][0]} {f_rank[0][1]:.2f})",
               "'꼴찌'라고 알고 있지만, 비교 목록에 어떤 나라·지역이 들어가느냐에 "
               "따라 순위가 달라집니다."),
        slider("p3", "1970년 한국의 출산율은 몇 명이었을까요?",
               kor_1970, "명", 1.0, 7.0, 0.1,
               f"1970년 {kor_1970:.2f}명 → {f_latest}년 {kor_f:.2f}명",
               "한 세대 만에 일어난 변화의 크기는 대개 과소평가됩니다."),
        slider("p4", f"{old_latest}년 한국에서 65세 이상 인구의 비율은?",
               old[old_latest], "%", 5, 35, 1,
               f"{old_latest}년 {old[old_latest]:.1f}% "
               f"(World Bank 최신 공표치. 최근 연도는 추계값입니다)",
               "고령화는 '다가올 일'로 느껴지지만 이미 지나온 숫자입니다."),
        slider("p5", f"{urb_latest}년 한국에서 도시에 사는 사람의 비율은?",
               urb[urb_latest], "%", 50, 100, 1,
               f"{urb_latest}년 {urb[urb_latest]:.1f}% "
               f"(World Bank 최신 공표치. 최근 연도는 추계값입니다)",
               "'절반쯤'이라고 답하기 쉽지만 한국은 세계에서도 손꼽히는 도시 국가입니다."),
    ])

# ── 6. 인터넷 ────────────────────────────────────────────────────
net = [r for r in load_json("wb_internet.json")[1] if r["value"] is not None]
n_latest = max(int(r["date"]) for r in net if r["countryiso3code"] == "KOR")
n_cur = wb_countries(net, n_latest)
kor_n = n_cur["Korea, Rep."]
n_rank = sorted(n_cur.items(), key=lambda kv: -kv[1])
kor_n_rank = [k for k, _ in n_rank].index("Korea, Rep.") + 1
kor_2000 = next(r["value"] for r in net
                if r["countryiso3code"] == "KOR" and r["date"] == "2000")
world = next((r["value"] for r in net
              if r["countryiso3code"] == "WLD" and int(r["date"]) == n_latest), None)
if world is None:
    world = mean(n_cur.values())
offline = 100 - world

topic(
    "internet", "🌐", "인터넷과 연결",
    "나라별 인터넷 사용 인구 비율",
    "World Bank Open Data", "https://data.worldbank.org/",
    [
        slider("i1", f"{n_latest}년 한국에서 인터넷을 쓰는 사람의 비율은?",
               kor_n, "%", 60, 100, 1,
               f"{n_latest}년 한국 {kor_n:.1f}%",
               "'거의 다'라고 생각하지만 100%는 아닙니다. 남은 몇 %가 누구인지가 "
               "정책의 대상입니다."),
        slider("i2", f"한국보다 인터넷 사용률이 높은 나라는 {len(n_cur)}곳 중 몇 곳일까요?",
               kor_n_rank - 1, "곳", 0, 60, 1,
               f"{n_latest}년 {len(n_cur)}곳 중 한국 {kor_n_rank}위",
               "'IT 강국'이라는 말과 실제 보급률 순위는 다른 이야기입니다."),
        slider("i3", "2000년 한국의 인터넷 사용률은?",
               kor_2000, "%", 0, 100, 5,
               f"2000년 {kor_2000:.1f}% → {n_latest}년 {kor_n:.1f}%",
               "20여 년 전을 떠올릴 때는 지금의 기준으로 과대평가하기 쉽습니다."),
        slider("i4", f"{n_latest}년 전 세계 평균 인터넷 사용률은?",
               world, "%", 20, 100, 5,
               f"{n_latest}년 세계 {world:.1f}%",
               "내 주변이 전부 연결돼 있으면 세계도 그럴 거라고 생각하게 됩니다."),
        slider("i5", "전 세계에서 인터넷을 쓰지 않는 사람은 몇 %일까요?",
               offline, "%", 0, 70, 5,
               f"100 - {world:.1f} = {offline:.1f}%",
               "같은 사실을 뒤집어 물으면 전혀 다른 크기로 느껴집니다."),
    ])

# ── 7. 환율 ──────────────────────────────────────────────────────
fx = load_json("usdkrw.json")["rates"]
FX = sorted((d, v["KRW"]) for d, v in fx.items() if "KRW" in v)
hi_d, hi_v = max(FX, key=lambda x: x[1])
lo_d, lo_v = min(FX, key=lambda x: x[1])
avg_fx = mean(v for _, v in FX)
under1200 = sum(1 for _, v in FX if v < 1200) / len(FX) * 100
last_d, last_v = FX[-1]
era = ("1997~1999년 외환위기" if hi_d < "2005" else
       "2008~2009년 금융위기" if hi_d < "2012" else
       "2020년 코로나" if hi_d < "2022" else "2022년 이후")

topic(
    "usdkrw", "💵", "원달러 환율 26년",
    "1999년부터 오늘까지의 원달러 환율",
    "Frankfurter (유럽중앙은행 고시)", "https://frankfurter.dev/",
    [
        slider("x1", "1999년 이후 원달러 환율의 최고 기록은?",
               hi_v, "원", 1100, 1800, 25,
               f"{hi_d} {hi_v:,.2f}원",
               "최고치는 위기의 기억과 함께 남지만, 정확한 시점은 자주 헷갈립니다."),
        choice("x2", "그 최고치를 찍은 시기는?",
               ["1997~1999년 외환위기", "2008~2009년 금융위기",
                "2020년 코로나", "2022년 이후"], era,
               f"최고 {hi_v:,.2f}원 ({hi_d}). 이 데이터는 1999년부터라 "
               f"1997~98년 외환위기 구간은 포함되어 있지 않습니다",
               "데이터가 시작하는 시점을 확인하지 않으면 '역대 최고'를 잘못 "
               "말하게 됩니다."),
        slider("x3", "26년간의 평균 환율은?",
               avg_fx, "원", 900, 1500, 25,
               f"{FX[0][0]} ~ {FX[-1][0]} 거래일 {len(FX):,}일 평균 "
               f"{avg_fx:,.0f}원 (최저 {lo_v:,.0f}원 · {lo_d})",
               "최근 값이 기준점이 되어 과거 평균을 높게 잡게 됩니다."),
        slider("x4", "환율이 1,200원 아래였던 날은 전체의 몇 %일까요?",
               under1200, "%", 0, 100, 5,
               f"거래일 {len(FX):,}일 중 1,200원 미만은 "
               f"{sum(1 for _, v in FX if v < 1200):,}일",
               "'원래 1,100원대였는데'라는 감각이 맞는지 비율로 확인해 봅니다."),
        slider("x5", f"{last_d} 기준 환율은?",
               last_v, "원", 1100, 1800, 25,
               f"{last_d} {last_v:,.2f}원",
               "가장 최근 값조차 기억은 며칠 전 뉴스에 묶여 있습니다."),
    ])

# ── 8. 도시 비교 ─────────────────────────────────────────────────
CITY = {}
for cid in ("seoul", "tokyo", "london", "singapore"):
    _d = load_json(f"city_{cid}.json")["daily"]
    CITY[cid] = [{"d": dt.date.fromisoformat(t), "hi": a, "lo": b, "r": c}
                 for t, a, b, c in zip(_d["time"], _d["temperature_2m_max"],
                                       _d["temperature_2m_min"],
                                       _d["precipitation_sum"])]
CN = {"seoul": "서울", "tokyo": "도쿄", "london": "런던", "singapore": "싱가포르"}
YRS = 30
c_rain = {k: sum(x["r"] for x in v) / YRS for k, v in CITY.items()}
c_days = {k: sum(1 for x in v if x["r"] >= 1) / YRS for k, v in CITY.items()}
c_temp = {k: mean((x["hi"] + x["lo"]) / 2 for x in v) for k, v in CITY.items()}
c_hot = {k: max(x["hi"] for x in v) for k, v in CITY.items()}
c_jan = {k: mean(x["lo"] for x in v if x["d"].month == 1) for k, v in CITY.items()}
dry = min(c_rain, key=c_rain.get)
hottest = max(c_hot, key=c_hot.get)
colder = "서울" if c_jan["seoul"] < c_jan["tokyo"] else "도쿄"

topic(
    "cities", "🏙️", "서울·도쿄·런던·싱가포르",
    "네 도시의 30년 평년값 (1991~2020)",
    "Open-Meteo Archive (ERA5 재분석)", "https://open-meteo.com/",
    [
        choice("c1", "1년 강수량이 가장 적은 도시는?",
               ["서울", "도쿄", "런던", "싱가포르"], CN[dry],
               " · ".join(f"{CN[k]} {c_rain[k]:,.0f}mm" for k in CITY),
               "비가 자주 오는 것과 많이 오는 것은 다릅니다. 런던은 자주 오지만 "
               "적게 옵니다."),
        slider("c2", "런던에서 1년에 비가 오는 날(1mm 이상)은 며칠일까요?",
               c_days["london"], "일", 40, 220, 5,
               f"런던 {c_days['london']:.0f}일 · 서울 {c_days['seoul']:.0f}일 "
               f"(강수량은 런던 {c_rain['london']:,.0f}mm · "
               f"서울 {c_rain['seoul']:,.0f}mm)",
               "런던은 서울보다 비 오는 날이 많은데 총량은 절반입니다. "
               "'며칠 왔나'와 '얼마나 왔나'는 다른 질문입니다."),
        choice("c3", "30년간 가장 높은 기온을 기록한 도시는?",
               ["서울", "도쿄", "런던", "싱가포르"], CN[hottest],
               " · ".join(f"{CN[k]} {c_hot[k]:.1f}도" for k in CITY),
               "적도에 가까울수록 덥다고 생각하지만, 최고기온 기록은 중위도 "
               "도시에서 나옵니다."),
        slider("c4", "서울의 연평균 기온은?",
               c_temp["seoul"], "도", 5, 30, 0.5,
               " · ".join(f"{CN[k]} {c_temp[k]:.1f}도" for k in CITY),
               "여름과 겨울의 기억이 강해서 연평균은 감이 잘 안 옵니다."),
        choice("c5", "1월 밤이 더 추운 도시는?",
               ["서울", "도쿄"], colder,
               f"1월 평균 최저기온 서울 {c_jan['seoul']:.1f}도 · "
               f"도쿄 {c_jan['tokyo']:.1f}도",
               "위도가 비슷해도 대륙의 영향을 받는 도시가 훨씬 춥습니다."),
    ],
    caveat="ERA5 재분석 값이고, 도시별로 관측소 위치와 기준이 다릅니다.")

# ── 9. 지진 ──────────────────────────────────────────────────────
Q = [f["properties"] for f in load_json("quakes.geojson")["features"]]
QK = [f["properties"] for f in load_json("quakes_korea.geojson")["features"]]
n_years = 25
per_year = len(Q) / n_years
m7 = sum(1 for p in Q if p["mag"] >= 7.0) / n_years
biggest = max(Q, key=lambda p: p["mag"])


def region(place):
    return (place or "").split(",")[-1].strip()


top_region = Counter(region(p["place"]) for p in Q).most_common(1)[0]
region_ko = {"Japan": "일본", "Indonesia": "인도네시아", "Chile": "칠레",
             "Philippines": "필리핀"}
kr_band = ("50건 미만" if len(QK) < 50 else "50~150건" if len(QK) <= 150
           else "150~400건" if len(QK) <= 400 else "400건 이상")

topic(
    "quakes", "🌎", "지진은 얼마나 자주",
    "2000~2024년 전 세계 지진 기록",
    "USGS 지진 카탈로그", "https://earthquake.usgs.gov/",
    [
        slider("q1", "규모 5.5 이상 지진은 전 세계에서 1년에 몇 번쯤 일어날까요?",
               per_year, "회", 50, 1200, 50,
               f"2000~2024년 {len(Q):,}건 ÷ {n_years}년 = "
               f"연평균 {per_year:.0f}회",
               "뉴스에 나오는 지진만 세면 실제보다 훨씬 적게 잡게 됩니다."),
        slider("q2", "규모 7.0 이상은 1년에 몇 번쯤일까요?",
               m7, "회", 0, 40, 1,
               f"2000~2024년 규모 7.0 이상 "
               f"{sum(1 for p in Q if p['mag'] >= 7.0)}건, 연평균 {m7:.1f}회",
               "규모는 로그 척도입니다. 0.5만 올라가도 횟수가 크게 줄어듭니다."),
        choice("q3", "규모 5.5 이상 지진이 가장 자주 기록된 나라는?",
               ["일본", "인도네시아", "칠레", "필리핀"],
               region_ko.get(top_region[0], "인도네시아"),
               f"1위 {top_region[0]} {top_region[1]:,}건",
               "지진 하면 떠오르는 나라와 실제로 가장 많이 기록되는 곳은 "
               "다를 수 있습니다."),
        slider("q4", "2000년 이후 기록된 가장 큰 지진의 규모는?",
               biggest["mag"], "", 7.0, 9.9, 0.1,
               f"규모 {biggest['mag']} · "
               f"{dt.datetime.fromtimestamp(biggest['time'] / 1000, dt.UTC):%Y-%m-%d} "
               f"{biggest['place']}",
               "규모 9는 8보다 약 32배 큰 에너지입니다."),
        choice("q5", "한반도 주변(위도 33~39.5도)에서 25년간 기록된 규모 3.0 이상 지진은?",
               ["50건 미만", "50~150건", "150~400건", "400건 이상"], kr_band,
               f"USGS 기준 {len(QK)}건. 이 관측망은 작은 지진을 모두 잡지는 "
               f"못하므로 기상청 집계와 다릅니다",
               "'어느 기관이 센 숫자인가'를 확인하지 않으면 같은 현상도 다른 "
               "값이 됩니다."),
    ],
    caveat="USGS 카탈로그는 작은 지진을 모두 담지 못합니다. 한반도 지진은 "
           "기상청 집계가 더 많습니다.")

# ── 10. 수명 ─────────────────────────────────────────────────────
le = [r for r in load_csv("life_expectancy.csv") if r["life_expectancy_0"]]
l_latest = max(int(r["year"]) for r in le if r["code"] == "KOR")
l_cur = owid_countries(le, l_latest, "life_expectancy_0")
kor_l = l_cur["South Korea"]
l_rank = sorted(l_cur.items(), key=lambda kv: -kv[1])
kor_l_rank = [k for k, _ in l_rank].index("South Korea") + 1
_kle = {r["year"]: float(r["life_expectancy_0"]) for r in le if r["code"] == "KOR"}
kor_1950, kor_1953, kor_1955 = _kle["1950"], _kle["1953"], _kle["1955"]
wld = next(float(r["life_expectancy_0"]) for r in le
           if r["code"] == "OWID_WRL" and int(r["year"]) == l_latest)
trio_l = {c: l_cur[c] for c in ("South Korea", "Japan", "United States")
          if c in l_cur}
top_l = max(trio_l, key=trio_l.get)
name_l = {"South Korea": "한국", "Japan": "일본", "United States": "미국"}

topic(
    "life", "🩺", "얼마나 오래 사나",
    "나라별 기대수명 1950~현재",
    "Our World in Data", "https://ourworldindata.org/grapher/life-expectancy",
    [
        slider("l1", f"{l_latest}년 한국의 기대수명은?",
               kor_l, "세", 60, 95, 1,
               f"{l_latest}년 한국 {kor_l:.1f}세",
               "기대수명은 '지금 태어난 아이가 평균적으로 살 햇수'입니다. "
               "지금 살아 있는 사람의 예상 수명과는 다릅니다."),
        slider("l2", f"기대수명이 긴 순으로 세면 한국은 {len(l_cur)}곳 중 몇 위일까요?",
               kor_l_rank, "위", 1, 60, 1,
               f"{l_latest}년 {len(l_cur)}곳 중 {kor_l_rank}위 "
               f"(1위 {l_rank[0][0]} {l_rank[0][1]:.1f}세)",
               "상위권인 것은 맞지만 몇 위인지는 대개 크게 빗나갑니다."),
        slider("l3", "1950년 한국의 기대수명은?",
               kor_1950, "세", 20, 70, 1,
               f"1950년 {kor_1950:.1f}세. 한국전쟁 기간의 사망이 반영된 값이라 "
               f"1953년 {kor_1953:.1f}세, 1955년 {kor_1955:.1f}세로 빠르게 "
               f"회복합니다. {l_latest}년은 {kor_l:.1f}세",
               "숫자가 튀면 사건을 의심해야 합니다. 이 값은 오류가 아니라 "
               "전쟁의 기록입니다."),
        choice("l4", "한국·일본·미국 중 기대수명이 가장 긴 나라는?",
               ["한국", "일본", "미국"], name_l[top_l],
               " · ".join(f"{name_l[c]} {trio_l[c]:.1f}세" for c in trio_l),
               "가장 잘사는 나라가 가장 오래 사는 나라는 아닙니다."),
        slider("l5", f"{l_latest}년 세계 평균 기대수명은?",
               wld, "세", 50, 90, 1,
               f"{l_latest}년 세계 평균 {wld:.1f}세 · 한국 {kor_l:.1f}세",
               "내가 사는 곳의 수준을 세계 평균으로 착각하기 쉽습니다."),
    ])

# ── 11. 눈 ───────────────────────────────────────────────────────
# '눈 온 날' = 하루 강설량 1cm 이상. 모델이 흩뿌리듯 내놓는 0.1cm 안팎의 값은
# 실제로 눈이 왔다고 느끼기 어렵다. 첫눈은 달력 해로 세면 매년 1월이 되므로
# 7월 1일 ~ 이듬해 6월 30일을 한 겨울로 묶어 센다.
s_raw = load_json("seoul_snow.json")
s = s_raw["daily"]
S = [{"d": dt.date.fromisoformat(t), "snow": v}
     for t, v in zip(s["time"], s["snowfall_sum"])]
SNOW_CM = 1.0
snow_days = {y: sum(1 for x in S if x["d"].year == y and x["snow"] >= SNOW_CM)
             for y in range(1990, 2025)}
snow_avg = mean(snow_days.values())
snow_90s = mean(snow_days[y] for y in range(1990, 2000))
snow_10s = mean(snow_days[y] for y in range(2015, 2025))
s_ratio = snow_10s / snow_90s if snow_90s else 0
max_snow = max(S, key=lambda x: x["snow"])
first_snow = {}
for y in range(1990, 2024):
    c = [x["d"] for x in S if dt.date(y, 7, 1) <= x["d"] < dt.date(y + 1, 7, 1)
         and x["snow"] >= SNOW_CM]
    if c:
        first_snow[y] = min(c)
first_m = Counter(d.month for d in first_snow.values())
first_top = first_m.most_common(1)[0]
snow_month = {m: mean([sum(x["snow"] for x in S
                           if x["d"].year == y and x["d"].month == m)
                       for y in range(1990, 2025)]) for m in range(1, 13)}
snowiest_m = max(snow_month, key=snow_month.get)
# 한계 문장의 숫자도 원본에서 — 1cm 기준을 0.1cm 로 낮추면 몇 일이 되는지
trace_avg = mean(sum(1 for x in S if x["d"].year == y and x["snow"] >= 0.1)
                 for y in range(1990, 2025))

topic(
    "seoul-snow", "❄️", "서울엔 눈이 얼마나 오나",
    "1990년부터 2024년까지, 서울의 하루 강설량",
    "Open-Meteo Archive (ERA5 재분석)", "https://open-meteo.com/",
    [
        slider("s1", "1990~2024년, 서울에서 한 해에 눈이 온 날은 평균 며칠일까요?",
               snow_avg, "일", 0, 30, 1,
               f"1990~2024년 하루 강설량 {SNOW_CM:g}cm 이상인 날을 해마다 세어 "
               f"평균하면 {snow_avg:.1f}일 (최소 {min(snow_days.values())}일 · "
               f"최대 {max(snow_days.values())}일)",
               "함박눈이 온 며칠이 겨울 전체의 인상을 만듭니다. 쌓일 만큼 온 날은 "
               "세어 보면 많지 않습니다."),
        # 줄어든 쪽도 고를 수 있게 보기를 둔다. 경계는 이웃한 보기의 가운데
        choice("s2", "1990년대와 2015~2024년, 한 해 눈 온 날은 몇 배 차이일까요?",
               ["약 절반", "약 20% 줄었다", "거의 같다", "약 1.5배"],
               ["약 절반", "약 20% 줄었다", "거의 같다", "약 1.5배"][
                   0 if s_ratio < 0.65 else 1 if s_ratio < 0.9
                   else 2 if s_ratio < 1.25 else 3],
               f"하루 강설량 {SNOW_CM:g}cm 이상인 날의 연평균을 비교하면 "
               f"1990~1999년 {snow_90s:.1f}일 → 2015~2024년 {snow_10s:.1f}일 "
               f"({s_ratio:.2f}배)",
               "'요즘 눈이 안 온다'는 느낌은 맞는 방향이지만, 줄어든 폭은 "
               "느낌보다 작을 수 있습니다."),
        slider("s3", "1990~2024년, 서울에서 하루에 가장 많이 내린 눈은 몇 cm일까요?",
               max_snow["snow"], "cm", 0, 40, 1,
               f"1990~2024년 하루 강설량의 최댓값은 "
               f"{max_snow['d']:%Y년 %m월 %d일} {max_snow['snow']:.1f}cm",
               "폭설 뉴스의 숫자는 관측소 한 곳의 값입니다. 넓은 격자를 평균한 "
               "값은 그보다 낮게 나옵니다."),
        choice("s4", "1990~2024년, 서울의 첫눈은 보통 몇 월에 올까요?",
               ["10월", "11월", "12월", "1월"], f"{first_top[0]}월",
               f"7월~이듬해 6월을 한 겨울로 묶어 하루 강설량 {SNOW_CM:g}cm 이상인 "
               f"첫날의 달을 세면 {len(first_snow)}번의 겨울 중 "
               + " · ".join(f"{m}월 {n}번" for m, n in sorted(
                   first_m.items(), key=lambda kv: (kv[0] < 7, kv[0]))),
               "첫눈 소식은 흩날리기만 해도 나옵니다. 쌓일 만큼 오는 첫눈은 그보다 "
               "늦습니다."),
        choice("s5", "서울에서 눈이 가장 많이 내리는 달은 언제일까요?",
               ["12월", "1월", "2월", "3월"], f"{snowiest_m}월",
               "1990~2024년 달별 강설량 합계를 해마다 구해 평균하면 "
               + " · ".join(f"{m}월 {snow_month[m]:.1f}cm" for m in (12, 1, 2, 3)),
               "가장 추운 달과 눈이 가장 많이 오는 달이 같은지는 따로 확인해야 "
               "합니다."),
    ],
    caveat="이 숫자는 서울 관측소가 아니라 약 25km 격자 한 칸"
           f"(북위 {s_raw['latitude']}° · 동경 {s_raw['longitude']}°)을 모델로 "
           "추정한 값이고, 강설량은 쌓인 눈을 잰 깊이가 아니라 모델이 낸 물의 양을 "
           "고정 비율(물 10mm = 눈 7cm)로 바꾼 것이며, '눈 온 날'은 하루 "
           f"{SNOW_CM:g}cm 이상만 세어 0.1cm 이상까지 세면 한 해 {trace_avg:.1f}일로 "
           "늘어나므로, 관측소 기록이나 뉴스에서 본 숫자와 다를 수 있습니다.")

# ── 12. 제천의 겨울 ──────────────────────────────────────────────
# 영하 = 일최저기온 0도 미만, 눈 온 날 = 하루 강설량 1cm 이상 (서울 주제와 같은 기준).
# 11~2월은 해를 넘기므로 11월이 속한 해로 겨울을 묶는다 — 1980/81 ~ 2024/25 의 45번.
# 1월 최저기온은 30년 평년이 아니라 받은 기간 전체(1980~2025)의 평균이다.
j_raw = load_json("jecheon_winter.json")
j = j_raw["daily"]
J = [{"d": dt.date.fromisoformat(t), "lo": lo, "mean": m, "snow": s}
     for t, lo, m, s in zip(j["time"], j["temperature_2m_min"],
                            j["temperature_2m_mean"], j["snowfall_sum"])]
J_YEARS = range(1980, 2026)
j_below0 = {y: sum(1 for x in J if x["d"].year == y and x["lo"] < 0) for y in J_YEARS}
j_below0_avg = mean(j_below0.values())
j_snow = {y: sum(1 for x in J if x["d"].year == y and x["snow"] >= SNOW_CM)
          for y in J_YEARS}
j_snow_avg = mean(j_snow.values())
j_winter = [x["mean"] for x in J
            if (x["d"].month >= 11 and x["d"].year <= 2024)
            or (x["d"].month <= 2 and x["d"].year >= 1981)]
j_winter_avg = mean(j_winter)
j_jan_lo = mean(x["lo"] for x in J if x["d"].month == 1)
j_coldest = min(J, key=lambda x: x["lo"])

topic(
    "jecheon-winter", "⛄", "제천의 겨울 얼마나 추울까?",
    "1980년부터 2025년까지, 제천의 매일 기온과 눈",
    "Open-Meteo Archive (ERA5 재분석)", "https://open-meteo.com/",
    [
        slider("j1", "1980~2025년, 제천에서 기온이 영하로 내려간 날은 한 해 평균 며칠일까요?",
               j_below0_avg, "일", 20, 200, 5,
               f"1980~2025년 일최저기온 0도 미만인 날을 해마다 세어 평균하면 "
               f"{j_below0_avg:.1f}일 (최소 {min(j_below0.values())}일 · "
               f"최대 {max(j_below0.values())}일)",
               "한겨울 몇 주만 떠올리기 쉽지만, 늦가을과 이른 봄의 새벽도 "
               "영하로 내려갑니다."),
        slider("j2", "1980~2025년, 제천에서 한 해에 눈이 온 날은 평균 며칠일까요?",
               j_snow_avg, "일", 0, 40, 1,
               f"1980~2025년 하루 강설량 {SNOW_CM:g}cm 이상인 날을 해마다 세어 "
               f"평균하면 {j_snow_avg:.1f}일 (최소 {min(j_snow.values())}일 · "
               f"최대 {max(j_snow.values())}일)",
               "눈 덮인 풍경은 오래 남지만, 쌓일 만큼 온 날은 세어 보면 "
               "많지 않습니다."),
        slider("j3", "1980~2025년, 제천의 11월~2월 평균 기온은 몇 도일까요?",
               j_winter_avg, "도", -10, 10, 0.5,
               f"1980/81~2024/25년 겨울 45번의 11~2월 날짜 {len(j_winter):,}일의 "
               f"일평균기온을 평균하면 {j_winter_avg:.2f}도",
               "가장 추운 아침이 기억을 차지해서, 낮까지 합친 평균은 생각보다 "
               "덜 춥게 나옵니다."),
        slider("j4", "1980~2025년, 제천의 1월 일 최저기온은 평균 몇 도일까요?",
               j_jan_lo, "도", -20, 5, 0.5,
               f"1980~2025년 1월 {sum(1 for x in J if x['d'].month == 1):,}일의 "
               f"일최저기온을 평균하면 {j_jan_lo:.2f}도 (30년 평년이 아니라 "
               f"받은 기간 전체의 평균)",
               "1월 아침의 기온은 '영하 몇 도'로 기억되지만, 평균을 내 보면 "
               "숫자가 달라집니다."),
        slider("j5", "1980~2025년, 제천에서 가장 낮았던 기온은 몇 도일까요?",
               j_coldest["lo"], "도", -35, -5, 1,
               f"1980~2025년 일최저기온의 최솟값은 "
               f"{j_coldest['d']:%Y년 %m월 %d일} {j_coldest['lo']:.1f}도",
               "극값은 관측소 한 곳의 기록으로 기억되지만, 넓은 격자를 평균한 "
               "값은 그보다 덜 극단적으로 나옵니다."),
    ],
    caveat="이 숫자는 제천 관측소가 아니라 시내에서 떨어진 약 25km 격자 한 칸"
           f"(북위 {j_raw['latitude']}° · 동경 {j_raw['longitude']}° · "
           f"고도 {j_raw['elevation']:g}m)을 모델로 추정한 값이고, 일최저기온은 "
           "정시 24번 중 가장 낮은 값이라 그 사이에 더 내려간 추위가 빠지며, "
           "강설량은 쌓인 눈을 잰 깊이가 아니라 모델이 낸 물의 양을 눈으로 바꾼 "
           "것이고, 1월 최저기온은 30년 평년이 아니라 1980~2025년 전체의 평균이므로, "
           "기상청 관측 기록이나 뉴스에서 본 숫자와 다를 수 있습니다.")

# ── 13. 절도 ─────────────────────────────────────────────────────
# 원본은 CP949. 열은 시·군·구 229개 + '외국 ○○' 17개, 줄은 범죄 유형 38개(합계 줄 없음).
# 국내 = '외국'으로 시작하지 않는 열. 시·군·구는 원본 열 그대로 비교한다 —
# 특·광역시는 구 단위, 그 밖은 일반구를 합친 시 단위라 큰 시가 유리하다.
_c = list(csv.reader(io.StringIO((RAW / "crime_region_2025.csv").read_bytes()
                                 .decode("cp949"))))
C_HEAD, C_ROWS = _c[0], _c[1:]
C_DOM = [i for i in range(2, len(C_HEAD)) if not C_HEAD[i].startswith("외국")]
C_FRN = [i for i in range(2, len(C_HEAD)) if C_HEAD[i].startswith("외국")]


def num(x):
    return int(x.replace(",", "") or 0)


theft = next(r for r in C_ROWS if r[0] == "절도범죄")
theft_dom = sum(num(theft[i]) for i in C_DOM)
crime_dom = sum(num(r[i]) for r in C_ROWS for i in C_DOM)
theft_share = theft_dom / crime_dom * 100
# 한계 문장의 숫자도 원본에서 — 분모에서 교통범죄를 빼면 비율이 얼마가 되는지
traffic_dom = sum(num(r[i]) for r in C_ROWS if r[0] == "교통범죄" for i in C_DOM)
theft_share_nt = theft_dom / (crime_dom - traffic_dom) * 100
theft_sgg = sorted(((num(theft[i]), C_HEAD[i]) for i in C_DOM), reverse=True)
sgg_opts = sorted(name for _, name in theft_sgg[:4])     # 상위 4곳을 가나다순으로
SIDO_KO = {"서울": "서울", "경기도": "경기", "부산": "부산", "인천": "인천"}
theft_sido = Counter()
for i in C_DOM:
    theft_sido[C_HEAD[i].split(" ")[0]] += num(theft[i])
top_sido = theft_sido.most_common(1)[0]

topic(
    "theft-2025", "👜", "한국의 절도 범죄는 어디서 많이 일어날까?",
    "2025년, 전국 시·군·구별 절도 발생 건수",
    "경찰청 범죄 발생 지역별 통계 (공공데이터포털)",
    "https://www.data.go.kr/data/3074462/fileData.do",
    [
        slider("t1", "2025년 국내에서 발생한 절도는 몇 건일까요?",
               theft_dom, "건", 0, 400000, 10000,
               f"2025년 '절도범죄' 줄에서 국외 {len(C_FRN)}개 열을 빼고 시·군·구 {len(C_DOM)}곳을 "
               f"더하면 {theft_dom:,}건",
               "뉴스에 나오는 큰 절도 몇 건이 인상을 만듭니다. 하루로 나누면 "
               f"약 {theft_dom / 365:,.0f}건입니다."),
        choice("t2", "2025년 절도가 가장 많이 발생한 시·군·구는?",
               sgg_opts, theft_sgg[0][1],
               f"원본 시·군·구 열 {len(C_DOM)}곳을 그대로 비교하면 "
               + " · ".join(f"{n} {v:,}건" for v, n in theft_sgg[:4])
               + " (특·광역시는 구 단위, 그 밖은 시 단위)",
               "번화가가 있는 구를 떠올리기 쉽지만, 원본의 단위가 달라 "
               "구를 합친 큰 시가 위로 올라옵니다."),
        slider("t3", "2025년 국내 범죄 중 절도는 몇 %일까요?",
               theft_share, "%", 0, 50, 1,
               f"국내 절도 {theft_dom:,}건 ÷ 국내 범죄 {len(C_ROWS)}개 유형 합계 "
               f"{crime_dom:,}건 = {theft_share:.1f}%",
               "'범죄' 하면 도둑부터 떠올리지만, 절도가 전체에서 차지하는 몫은 "
               "생각과 다를 수 있습니다."),
        choice("t4", "2025년 절도가 가장 많이 발생한 시·도는?",
               ["서울", "경기", "부산", "인천"], SIDO_KO.get(top_sido[0], top_sido[0]),
               "시·군·구 열을 시·도별로 더하면 "
               + " · ".join(f"{s} {v:,}건" for s, v in theft_sido.most_common(4)),
               "서울이 가장 붐비는 곳이라는 인상이 강하지만, 사람 수가 더 많은 "
               "곳은 따로 있습니다."),
    ],
    caveat="이 숫자는 경찰에 접수된 사건만 사건 발생일이 아니라 통계원표 작성일 "
           "기준으로 센 것이라 연말 사건이 해를 넘나들 수 있고, 국외 "
           f"{len(C_FRN)}개 열은 빼고 셌으며, 시·군·구는 특·광역시는 구 단위인데 "
           f"수원·청주·창원처럼 일반구가 있는 시는 구를 합친 한 덩어리라 순위가 "
           f"그 단위에 따라 달라지고(1·2위 차이 {theft_sgg[0][0] - theft_sgg[1][0]}건), "
           f"절도 비율의 분모에는 교통범죄·기타범죄까지 {len(C_ROWS)}개 유형이 모두 "
           f"들어가 교통범죄만 빼도 {theft_share:.1f}%가 {theft_share_nt:.1f}%로 "
           "바뀌므로, 다른 통계나 뉴스에서 본 숫자와 다를 수 있습니다.")

# ── 14. 지하철 혼잡도 ────────────────────────────────────────────
# 원본은 UTF-8(BOM). 첫 줄 한글 열이름, 둘째 줄 영문 열이름. 시간대 열은 5:30~ ~ 24:30~ 39개,
# 마지막 열 '분기'는 2017~2023년 연 1회 자료면 '-'. 빈 칸은 빼고 평균한다.
# 기간 = 최근 8분기(2024년 2분기~2026년 1분기, 2026년 2분기는 아직 없음), 요일 = 평일만.
# 역 = 역 이름별 — 같은 이름의 호선·방향 줄을 모두 모아 평균한다.
# 5번(덜 붐비는 역)도 하루 전체가 아니라 2번에서 나온 가장 혼잡한 시간대 기준이다.
_m = list(csv.reader(io.open(RAW / "[서울교통공사] 지하철혼잡도 정보.csv",
                             encoding="utf-8-sig")))
M_SLOTS = _m[0][6:45]
M_FROM, M_TO = ("2024", "2"), ("2026", "1")
M = [r for r in _m[2:] if r[-1] != "-" and M_FROM <= (r[0], r[-1]) <= M_TO
     and r[1] == "평일"]
M_Q = sorted({(r[0], r[-1]) for r in M})
assert len(M_Q) == 8, f"지하철: 분기가 8개가 아닙니다 {M_Q}"
M_PERIOD = f"{M_FROM[0]}년 {M_FROM[1]}분기~{M_TO[0]}년 {M_TO[1]}분기 평일"


def slot_name(label):
    """'8:00~ (%)' → '8:00~8:30'. 24시 넘은 열은 0시로 바꿔 적는다 ('24:30~' → '0:30~1:00')."""
    h, m = map(int, label.split("~")[0].split(":"))
    a = h * 60 + m
    return "~".join(f"{t // 60 % 24}:{t % 60:02d}" for t in (a, a + 30))


m_cells = [float(v) for r in M for v in r[6:45] if v.strip()]
m_blank = sum(1 for r in M for v in r[6:45] if not v.strip())
# 한계 문장의 숫자도 원본에서 — 0 칸 수, 1호선 역 수
m_zero = sum(1 for v in m_cells if v == 0)
m_line1 = len({r[4] for r in M if r[2] == "1"})
m_avg = mean(m_cells)
m_slot = {slot_name(s): mean(float(r[6 + i]) for r in M if r[6 + i].strip())
          for i, s in enumerate(M_SLOTS)}
m_rank = sorted(m_slot, key=m_slot.get)
m_peak, m_2nd, m_low = m_rank[-1], m_rank[-2], m_rank[0]
_pi = [slot_name(s) for s in M_SLOTS].index(m_peak)
_st = {}
for r in M:
    if r[6 + _pi].strip():
        _st.setdefault(r[4], []).append(float(r[6 + _pi]))
m_station = sorted(((mean(v), k) for k, v in _st.items()), reverse=True)
top_opts = sorted(k for _, k in m_station[:4])           # 상위 4곳을 가나다순으로
low_opts = sorted(k for _, k in m_station[-4:])          # 하위 4곳을 가나다순으로

topic(
    "subway-crowd", "🚇", "지하철 혼잡이 가장 큰 시간과 역은?",
    f"{M_PERIOD}, 서울 지하철 1~8호선 30분 단위 혼잡도",
    "서울교통공사 지하철혼잡도 정보 (서울 데이터 허브)",
    "https://data.seoul.go.kr/bsp/wgs/dataView/data300View/645.do",
    [
        slider("m1", "최근 2년, 평일 서울 지하철의 평균 혼잡도는 몇 %일까요?",
               m_avg, "%", 0, 100, 1,
               f"{M_PERIOD} 역·방향·30분 시간대별 혼잡도 {len(m_cells):,}칸"
               f"(빈 칸 {m_blank:,}개 제외)을 모두 평균하면 {m_avg:.1f}%",
               "만원 열차의 기억이 평균을 끌어올립니다. 새벽·밤·한낮과 한산한 "
               "구간까지 합치면 좌석이 다 찬 정도(34%) 언저리입니다."),
        choice("m2", "평일 서울 지하철이 가장 혼잡한 30분은 언제일까요?",
               ["7:30~8:00", "8:00~8:30", "17:30~18:00", "18:00~18:30"], m_peak,
               f"{M_PERIOD} 시간대별로 모든 역·방향을 평균하면 1위 {m_peak} "
               f"{m_slot[m_peak]:.1f}% · 2위 {m_2nd} {m_slot[m_2nd]:.1f}%",
               "퇴근길이 더 지친다고 느끼지만, 출근길은 짧은 시간에 몰려서 "
               "30분 단위로는 두 시간대가 거의 같습니다."),
        choice("m3", f"평일 {m_peak}, 가장 혼잡한 역은 어디일까요?",
               top_opts, m_station[0][1],
               f"{M_PERIOD} {m_peak} 혼잡도를 역 이름별로 모든 호선·방향을 "
               f"평균하면 " + " · ".join(f"{k} {v:.1f}%" for v, k in m_station[:4]),
               "환승역이나 번화가가 먼저 떠오르지만, 열차가 이미 꽉 찬 채로 "
               "도심 쪽으로 들어가는 길목의 역이 위로 올라옵니다."),
        choice("m4", "평일 서울 지하철이 가장 한산한 30분은 언제일까요?",
               ["5:30~6:00", "11:30~12:00", "23:30~0:00", "0:30~1:00"], m_low,
               f"{M_PERIOD} 시간대별로 모든 역·방향을 평균하면 가장 낮은 "
               f"{m_low} {m_slot[m_low]:.1f}% · 첫차 무렵 5:30~6:00 "
               f"{m_slot['5:30~6:00']:.1f}% · 한낮 11:30~12:00 "
               f"{m_slot['11:30~12:00']:.1f}%",
               "첫차가 가장 비었을 것 같지만, 새벽 출근하는 사람이 생각보다 "
               "많습니다."),
        choice("m5", f"평일 {m_peak}에도 가장 한산한 역은 어디일까요?",
               low_opts, m_station[-1][1],
               f"{M_PERIOD} {m_peak} 혼잡도를 역 이름별로 모든 호선·방향을 "
               f"평균하면 낮은 순으로 "
               + " · ".join(f"{k} {v:.1f}%" for v, k in m_station[::-1][:4])
               + f" ({len(m_station)}개 역 중)",
               "가장 붐비는 시간에도 종점 근처는 열차가 비어서 출발합니다. "
               "혼잡은 노선의 어디에 있느냐가 만듭니다."),
    ],
    caveat="이 숫자는 열차 안 사람을 센 것이 아니라 교통카드 승하차 기록으로 탑승 인원을 "
           "추정해 정원 대비 비율(좌석이 다 차면 34%)로 바꾼 뒤 30분 동안 지난 열차를 "
           "평균한 값이고, 각 분기 전체가 아니라 날짜가 밝혀지지 않은 특정 기간만 "
           f"쓴 데다 {M_PERIOD}만 셌고(이 파일엔 2026년 2분기가 없지만 공공데이터포털엔 "
           "3분기 자료가 이미 있음), 같은 이름의 역은 호선·방향을 합쳐 평균했으며 "
           f"빈 칸 {m_blank:,}개는 빼고 종점에서 들어오는 방향처럼 0으로 적힌 칸 "
           f"{m_zero:,}개는 그대로 넣어 평균이 낮아지고, 1호선은 서울교통공사 구간인 "
           f"서울역~청량리 {m_line1}개 역뿐이므로, 한 열차가 가장 붐빈 순간의 수치나 "
           "서울교통공사 밖 구간까지 넣은 1호선 수치, 최신 분기 자료와 다를 수 있습니다.")


# ════════════════════════════════════════════════════════════════
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # 내 주제를 목록 맨 위에 띄운다 — 제천, 절도, 지하철 순 (나머지는 만든 순서 그대로)
    MINE = ["jecheon-winter", "theft-2025", "subway-crowd"]
    TOPICS.sort(key=lambda t: MINE.index(t["id"]) if t["id"] in MINE else len(MINE))
    index = []
    for t in TOPICS:
        # 절도 주제만 4문항 (국외 절도 문항을 뺐다). 나머지는 5문항 그대로 지킨다
        n_q = 4 if t["id"] == "theft-2025" else 5
        assert len(t["questions"]) == n_q, f"{t['id']}: 문항이 {n_q}개가 아닙니다"
        pack = {k: t[k] for k in ("id", "emoji", "title", "blurb",
                                  "source", "source_url", "caveat")}
        pack["questions"] = t["questions"]
        io.open(OUT / f"{t['id']}.json", "w", encoding="utf-8").write(
            json.dumps(pack, ensure_ascii=False, indent=2))
        index.append({k: t[k] for k in ("id", "emoji", "title", "blurb",
                                        "source")})

    # 제목·부제는 화면을 바꾸며 고친 값을 지킨다 (2장에서 내 제목으로 바꾼다).
    # 다시 계산해도 내 제목이 «감 테스트»로 돌아가지 않게, 있던 값을 읽어 쓴다
    old = {}
    if (APP / "topics.json").exists():
        try:
            old = json.load(io.open(APP / "topics.json", encoding="utf-8"))
        except ValueError:
            old = {}
    io.open(APP / "topics.json", "w", encoding="utf-8").write(json.dumps({
        "title": old.get("title", "감 테스트"),
        "subtitle": old.get("subtitle", "숫자에 대한 당신의 감은 몇 점입니까"),
        # 등급·문구는 여기서 고칩니다. 코드를 건드릴 일이 아닙니다
        "grades": [
            {"min": 90, "name": "촉이 데이터급", "emoji": "🎯"},
            {"min": 70, "name": "감이 좋은 편", "emoji": "📊"},
            {"min": 50, "name": "보통의 감각", "emoji": "🙂"},
            {"min": 30, "name": "느낌대로 삽니다", "emoji": "🎲"},
            {"min": 0, "name": "감은 접어두시죠", "emoji": "🙈"},
        ],
        "reactions_choice": {"hit": "맞히셨습니다", "miss": "다들 그렇게 찍습니다"},
        "reactions": [
            {"max": 5, "text": "촉이 좋으시네요"},
            {"max": 20, "text": "비슷하게 보셨습니다"},
            {"max": 60, "text": "음…"},
            {"max": 999, "text": "꽤 멀리 가셨습니다"},
        ],
        "topics": index,
    }, ensure_ascii=False, indent=2))

    # 사람이 읽는 정답지
    md = [f"# 문항 정답지 — {len(TOPICS)}주제 "
          f"{sum(len(t['questions']) for t in TOPICS)}문항", "",
          "> 모든 값은 `data/raw/` 의 원본에서 `tools/build_topics.py` 가 계산합니다.", ""]
    for t in TOPICS:
        md += [f"## {t['emoji']} {t['title']}", "",
               f"- 출처: {t['source']} · {t['source_url']}"]
        if t["caveat"]:
            md += [f"- **한계** {t['caveat']}"]
        md += [""]
        for q in t["questions"]:
            a = f"{q['answer']}{q.get('unit', '')}" if q["type"] == "slider" \
                else q["answer"]
            md += [f"**{q['text']}**", "",
                   f"- 정답 **{a}**", f"- 근거 {q['basis']}",
                   f"- 왜 틀리나 {q['why']}", ""]
    io.open(HERE / "정답지.md", "w", encoding="utf-8").write("\n".join(md))

    print(f"주제 {len(TOPICS)}개 · 문항 {sum(len(t['questions']) for t in TOPICS)}개")
    for t in TOPICS:
        print(f"\n{t['emoji']} {t['title']}  ({t['source']})")
        for q in t["questions"]:
            a = f"{q['answer']}{q.get('unit', '')}" if q["type"] == "slider" \
                else q["answer"]
            print(f"    [{q['type'][:6]:<6}] {q['text'][:44]:<44} → {a}")


if __name__ == "__main__":
    main()
