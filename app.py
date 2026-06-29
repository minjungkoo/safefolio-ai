import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.graph_objects as go

st.set_page_config(
    page_title="SafeFolio AI", page_icon="🛡️",
    layout="wide", initial_sidebar_state="collapsed"
)

# ──────────────────────────────────────────────
# 상수 및 헬퍼
# ──────────────────────────────────────────────
DIVIDEND_TAX          = 0.154
CAPITAL_GAIN_TAX_NORM = 0.22
CAPITAL_GAIN_TAX_ISA  = 0.099
ISA_ANNUAL_LIMIT      = 20_000_000

def fmt(n):
    return f"₩{int(n):,}"

def donut_chart(labels, values, title="", colors=None, center_text=""):
    total  = sum(values)
    custom = [f"{fmt(v)}<br>{v/total*100:.1f}%" if total > 0 else fmt(v) for v in values]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.6,
        customdata=custom,
        hovertemplate="%{label}<br>%{customdata}<extra></extra>",
        textinfo="label+percent", textposition="outside",
        marker_colors=colors,
    ))
    fig.add_annotation(text=center_text, x=0.5, y=0.5,
                       font_size=13, showarrow=False, font_color="#555")
    fig.update_layout(
        title=dict(text=title, x=0.5, font_size=14),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.35),
        margin=dict(t=40, b=70, l=10, r=10), height=340,
    )
    return fig


def grouped_bar_line_chart(months, income, expense, savings, rates):
    fig = go.Figure()
    fig.add_trace(go.Bar(name="수입", x=months, y=income,
                         marker_color="#4C9BE8", yaxis="y"))
    fig.add_trace(go.Bar(name="지출", x=months, y=expense,
                         marker_color="#E87B4C", yaxis="y"))
    fig.add_trace(go.Bar(name="저축", x=months, y=savings,
                         marker_color="#4CE87B", yaxis="y"))
    fig.add_trace(go.Scatter(
        name="저축률(%)", x=months, y=rates,
        mode="lines+markers+text",
        text=[f"{r:.0f}%" for r in rates], textposition="top center",
        line=dict(color="#F0C040", width=2), marker=dict(size=6),
        yaxis="y2"
    ))
    fig.update_layout(
        barmode="group",
        yaxis=dict(title="금액 (원)", tickformat=","),
        yaxis2=dict(title="저축률 (%)", overlaying="y", side="right",
                    range=[0, 120], showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=-0.3),
        margin=dict(t=20, b=80, l=20, r=20), height=380,
    )
    return fig

# ──────────────────────────────────────────────
# AI 에이전트 도구 (Tools - Function Calling용)
# ──────────────────────────────────────────────
def get_macro_indicators() -> dict:
    """
    미국 10년물 국채 금리(US10Y)와 VIX 공포지수의 실시간 데이터를 조회합니다.
    시장의 위험 회피 심리와 인플레이션 압력을 분석할 때 반드시 사용하세요.
    """
    try:
        import yfinance as yf
        us10y = yf.Ticker("^TNX").history(period="1d")["Close"].iloc[-1]
        vix = yf.Ticker("^VIX").history(period="1d")["Close"].iloc[-1]
        return {"US10Y": round(us10y, 2), "VIX": round(vix, 2), "status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def search_fed_policy() -> str:
    """
    최근 연방준비제도(Fed)의 통화정책 기조와 주요 거시 경제 일정을 반환합니다.
    금리 이슈나 거시 경제 리스크를 질문받았을 때 호출하세요.
    """
    return (
        "2026년 5월 연방준비제도 의장의 임기 만료를 앞두고 통화정책의 불확실성이 "
        "단기적으로 확대될 가능성이 있습니다. 시장 변동성이 커지는 국면이므로, "
        "미국배당다우존스와 같은 하방 방어력이 강한 자산의 비중 유지가 권장됩니다."
    )

# ──────────────────────────────────────────────
# 청년 정책 데이터 및 포트폴리오
# ──────────────────────────────────────────────
POLICIES = [
    {
        "id": "youth_savings", "name": "청년미래적금",
        "conditions": {
            "age_min": 19, "age_max": 34,
            "income_max_general": 60_000_000,
            "job_types": ["정규직", "계약직", "프리랜서"],
        },
        "benefit": "월 최대 ₩500,000 납입, 만기 3년, 정부 기여금 6~12%, 비과세",
        "monthly_amount": 500_000,
        "action": "📌 매월 ₩500,000을 청년미래적금에 자동이체 설정하세요.",
        "conflicts": ["youth_isa"], "note": None,
    },
    {
        "id": "isa_general", "name": "중개형 ISA",
        "conditions": {
            "age_min": 19, "age_max": 99,
            "income_max_general": None,
            "job_types": ["정규직", "계약직", "프리랜서", "무직"],
        },
        "benefit": "연 ₩2,000만원 납입, 비과세 ₩200만원(서민형 ₩400만원), 초과분 9.9% 분리과세",
        "monthly_amount": None,
        "action": "📌 투자용 ETF는 ISA 계좌에 담아 배당세 15.4%를 아끼세요.",
        "conflicts": [], "note": None,
    },
    {
        "id": "youth_isa", "name": "청년형 ISA",
        "conditions": {
            "age_min": 19, "age_max": 34,
            "income_max_general": 75_000_000,
            "job_types": ["정규직", "계약직"],
        },
        "benefit": "비과세 한도 ₩400만원 (일반형 2배), 납입금 소득공제 혜택",
        "monthly_amount": None,
        "action": "📌 중개형 ISA 대신 청년형 ISA를 개설하세요. 비과세 한도가 2배예요.",
        "conflicts": ["youth_savings"],
        "note": "⚠️ 2026년 7월 세제개편안 확정 전, 세부 수치 변동 가능",
    },
    {
        "id": "youth_jeonse", "name": "청년버팀목 전세대출",
        "conditions": {
            "age_min": 19, "age_max": 34,
            "income_max_general": 50_000_000,
            "asset_max": 337_000_000,
            "housing": "무주택",
        },
        "benefit": "최대 ₩1억5천만원, 금리 연 1.3~4.3%, 전세보증금 ₩3억 이하 85㎡ 이하",
        "monthly_amount": None,
        "action": "📌 전세 계약 전 주택도시기금 앱에서 한도 조회 후 신청하세요.",
        "conflicts": [],
        "note": "병역 이행 시 최대 만 39세까지 가능",
    },
]

PORTFOLIO_ISA_MAP = {
    "A": [
        {"name": "TIGER 미국S&P500",            "account": "ISA ★1순위", "reason": "배당세+양도세 모두 절세"},
        {"name": "KODEX 단기채권 / 비상금 통장", "account": "일반 계좌",  "reason": "유동성 필요, 세금 적음"},
    ],
    "B": [
        {"name": "ACE 미국30년국채액티브", "account": "ISA ★1순위", "reason": "이자소득세 15.4% 절세"},
        {"name": "TIGER 미국S&P500",       "account": "ISA ★2순위", "reason": "배당세+양도세 절세"},
        {"name": "TIGER 미국채10년선물",    "account": "ISA ★3순위", "reason": "이자소득세 절세"},
        {"name": "ACE KRX금현물",           "account": "일반 계좌",  "reason": "금 현물 매매차익 비과세"},
        {"name": "KODEX 미국S&P원자재",     "account": "일반 계좌",  "reason": "변동성 커서 ISA 비추"},
    ],
    "C": [
        {"name": "TIGER 미국S&P500",    "account": "ISA ★1순위", "reason": "배당세+양도세 모두 절세"},
        {"name": "ACE 미국배당다우존스", "account": "ISA ★2순위", "reason": "배당세 15.4% 매년 절세"},
        {"name": "KODEX 단기채권",       "account": "일반 계좌",  "reason": "유동성 필요, 세금 적음"},
    ],
}

PORTFOLIOS = {
    "A": {
        "name": "버핏식 단순 인덱스", "type": "공격형", "emoji": "🚀",
        "basis": "워런 버핏 — S&P500 90% + 단기채 10%",
        "expected_return": 0.09, "expected_risk": 0.15,
        "colors": ["#E74C3C", "#F39C12"],
        "assets": [
            {"name": "TIGER 미국S&P500", "ratio": 90},
            {"name": "KODEX 단기채권",    "ratio": 10},
        ],
    },
    "B": {
        "name": "올웨더 포트폴리오", "type": "안정형", "emoji": "🌤️",
        "basis": "레이 달리오 — 주식 30% + 채권 55% + 실물자산 15%",
        "expected_return": 0.055, "expected_risk": 0.07,
        "colors": ["#2ECC71","#27AE60","#1ABC9C","#F1C40F","#E67E22"],
        "assets": [
            {"name": "TIGER 미국S&P500",      "ratio": 30},
            {"name": "ACE 미국30년국채액티브", "ratio": 40},
            {"name": "TIGER 미국채10년선물",   "ratio": 15},
            {"name": "ACE KRX금현물",          "ratio":  8},
            {"name": "KODEX 미국S&P원자재",    "ratio":  7},
        ],
    },
    "C": {
        "name": "코어-위성 전략", "type": "균형형", "emoji": "⚖️",
        "basis": "핵심-위성 전략 — S&P500 50% + 고배당 30% + 단기채 20%",
        "expected_return": 0.075, "expected_risk": 0.11,
        "colors": ["#3498DB","#9B59B6","#1ABC9C"],
        "assets": [
            {"name": "TIGER 미국S&P500",    "ratio": 50},
            {"name": "ACE 미국배당다우존스", "ratio": 30},
            {"name": "KODEX 단기채권",       "ratio": 20},
        ],
    },
}

ETF_TICKERS = {
    "TIGER 미국S&P500":       "379800.KS",
    "ACE 미국배당다우존스":    "402970.KS",
    "ACE 미국30년국채액티브":  "476760.KS",
    "TIGER 미국채10년선물":    "305080.KS",
    "ACE KRX금현물":           "411060.KS",
    "KODEX 단기채권":          "153130.KS",
    "KODEX 미국S&P원자재":     "453870.KS",
}

@st.cache_data(ttl=3600)
def fetch_etf_data(portfolio_key: str) -> dict:
    try:
        import yfinance as yf
        port   = PORTFOLIOS[portfolio_key]
        assets = port["assets"]
        results = []
        weighted_return = 0.0
        weighted_div    = 0.0
        fetch_time = None

        for asset in assets:
            name   = asset["name"]
            ratio  = asset["ratio"] / 100
            ticker = ETF_TICKERS.get(name)
            if not ticker:
                results.append({
                    "name": name, "ratio": asset["ratio"],
                    "price": None, "return_1y": None, "div_yield": None,
                    "status": "티커 없음"
                })
                continue
            try:
                t    = yf.Ticker(ticker)
                hist = t.history(period="1y")
                info = t.info
                if hist.empty or len(hist) < 5:
                    results.append({
                        "name": name, "ratio": asset["ratio"],
                        "price": None, "return_1y": None, "div_yield": None,
                        "status": "데이터 없음"
                    })
                    continue

                price    = round(hist["Close"].iloc[-1])
                ret_1y   = round((hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100, 2)
                div_raw  = info.get("dividendYield") or 0
                div_yield= round(div_raw * 100, 2)
                fetch_time = str(hist.index[-1].date())

                weighted_return += ret_1y * ratio
                weighted_div    += div_yield * ratio

                results.append({
                    "name": name, "ratio": asset["ratio"],
                    "price": price, "return_1y": ret_1y,
                    "div_yield": div_yield, "status": "✅"
                })
            except Exception as e:
                results.append({
                    "name": name, "ratio": asset["ratio"],
                    "price": None, "return_1y": None, "div_yield": None,
                    "status": f"오류: {str(e)[:30]}"
                })

        return {
            "success": True,
            "assets": results,
            "weighted_return": round(weighted_return, 2),
            "weighted_div":    round(weighted_div, 2),
            "fetch_time":      fetch_time,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# ──────────────────────────────────────────────
# 핵심 알고리즘
# ──────────────────────────────────────────────
def match_policies(profile):
    age    = profile.get("age", 30)
    income = profile.get("annual_income", 0)
    job    = profile.get("job_type", "정규직")
    housing= profile.get("housing", "월세")
    assets = profile.get("total_assets", 0)
    matched = []
    for p in POLICIES:
        c, ok = p["conditions"], True
        if age < c.get("age_min",0) or age > c.get("age_max",99): ok = False
        if c.get("income_max_general") and income > c["income_max_general"]: ok = False
        if "job_types" in c and job not in c["job_types"]: ok = False
        if c.get("housing") and housing != "무주택": ok = False
        if c.get("asset_max") and assets > c["asset_max"]: ok = False
        matched.append({"policy": p, "eligible": ok, "conflict": False})
    youth_ok = any(m["eligible"] and m["policy"]["id"]=="youth_savings" for m in matched)
    if youth_ok:
        for m in matched:
            if m["policy"]["id"] == "youth_isa":
                m["conflict"] = True
    return matched

def calc_risk_profile(profile):
    score = 0
    age = profile.get("age", 30)
    if age <= 30:         score += 2
    elif age <= 35:       score += 1
    dr = profile.get("debt_rate", 0)
    if dr < 5:            score += 2
    elif dr < 8:          score += 1
    if profile.get("emergency_ok"): score += 2
    yrs = profile.get("invest_years", 5)
    if yrs >= 7:          score += 2
    elif yrs >= 4:        score += 1
    if score >= 7: return "A"
    elif score >= 4: return "C"
    else: return "B"

def calc_account_split(profile, matched_policies):
    monthly      = profile.get("monthly_income", 0)
    fixed        = profile.get("fixed_expense", 0)
    variable     = profile.get("variable_expense", 0)
    total_expense= fixed + variable
    emg_cur      = profile.get("emergency_current", 0)
    debt_rate    = profile.get("debt_rate", 0)
    debt_tot     = profile.get("debt_total", 0)
    isa_current  = profile.get("isa_current_year", 0)

    emg_target = total_expense * 6
    emg_gap    = max(0, emg_target - emg_cur)
    emg_ok     = emg_gap == 0
    monthly_interest = round(debt_tot * debt_rate / 100 / 12) if debt_tot > 0 else 0
    debt_prio = debt_rate >= 5.0
    youth_ok = any(m["eligible"] and not m["conflict"] and m["policy"]["id"] == "youth_savings" for m in matched_policies)
    isa_remaining = max(0, ISA_ANNUAL_LIMIT - isa_current)
    isa_monthly_max = round(isa_remaining / 12)

    surplus = monthly - total_expense
    remaining = surplus
    alloc = {}

    if surplus <= 0:
        return {
            "surplus_warning": True, "monthly_income": monthly, "fixed_expense": fixed,
            "variable_expense": variable, "total_expense": total_expense,
            "emergency_target": emg_target, "emergency_gap": emg_gap,
            "emergency_ok": emg_ok, "monthly_interest": monthly_interest,
            "debt_priority": debt_prio, "isa_remaining": isa_remaining,
            "allocations": {}, "surplus": surplus,
        }

    if not emg_ok:
        a = min(remaining * 0.20, emg_gap / 12)
        alloc["비상금 통장"] = round(a); remaining -= a
    else:
        a = remaining * 0.03
        alloc["비상금 통장"] = round(a); remaining -= a

    if monthly_interest > 0:
        alloc["대출 이자"] = monthly_interest; remaining -= monthly_interest

    if debt_prio and debt_tot > 0:
        a = remaining * 0.25
        alloc["부채 원금 상환"] = round(a); remaining -= a

    if youth_ok and remaining >= 500_000:
        alloc["청년미래적금"] = 500_000; remaining -= 500_000

    invest_want = remaining * 0.65
    invest_actual = min(invest_want, isa_monthly_max) if isa_monthly_max > 0 else invest_want
    alloc["ISA / 투자"] = round(invest_actual); remaining -= invest_actual
    alloc["자유 지출"] = max(0, round(remaining))

    return {
        "surplus_warning": False, "monthly_income": monthly, "fixed_expense": fixed,
        "variable_expense": variable, "total_expense": total_expense, "surplus": surplus,
        "fixed_ratio": total_expense / monthly if monthly else 0,
        "fixed_warning": total_expense / monthly > 0.6 if monthly else False,
        "emergency_target": emg_target, "emergency_gap": emg_gap,
        "emergency_ok": emg_ok, "monthly_interest": monthly_interest,
        "debt_priority": debt_prio, "isa_remaining": isa_remaining,
        "allocations": alloc,
    }

def calc_goal_simulation(profile, split_result):
    alloc       = split_result.get("allocations", {})
    monthly_inv = alloc.get("ISA / 투자", 0) + alloc.get("청년미래적금", 0)
    current_assets = profile.get("total_assets", 0)
    goal_3y        = profile.get("goal_3y", 0)

    risk_key = st.session_state.get("risk_profile", "C")
    r_annual = PORTFOLIOS[risk_key]["expected_return"]
    r_monthly = (1 + r_annual) ** (1/12) - 1

    results = []
    capital = current_assets
    for month in range(1, 37):
        capital = capital * (1 + r_monthly) + monthly_inv
        if month % 12 == 0:
            results.append({"연도": f"{month//12}년 후", "예상 자산": round(capital)})

    final = results[-1]["예상 자산"] if results else current_assets
    achievable = final >= goal_3y
    return {
        "yearly": results, "final_3y": final, "goal_3y": goal_3y,
        "achievable": achievable, "monthly_inv": monthly_inv, "shortfall": max(0, goal_3y - final),
    }

def calc_debt_vs_invest(profile):
    debt_rate = profile.get("debt_rate", 0)
    debt_tot  = profile.get("debt_total", 0)
    if debt_tot == 0: return None
    risk_key = st.session_state.get("risk_profile", "C")
    exp_return = PORTFOLIOS[risk_key]["expected_return"] * 100
    after_tax_return = exp_return * (1 - DIVIDEND_TAX)

    amount, years = 1_000_000, 5
    repay_gain  = amount * debt_rate / 100 * years
    invest_gain = amount * ((1 + after_tax_return/100)**years - 1)

    return {
        "debt_rate": debt_rate, "exp_return": exp_return, "after_tax_return": after_tax_return,
        "repay_gain": repay_gain, "invest_gain": invest_gain,
        "prefer_repay": debt_rate >= after_tax_return, "diff": abs(repay_gain - invest_gain),
    }

def get_gemini_portfolio_explanation(profile, portfolio_key):
    try:
        import google.generativeai as genai
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-2.5-flash")

        p = PORTFOLIOS[portfolio_key]
        assets_str = ", ".join([f"{a['name']} {a['ratio']}%" for a in p["assets"]])
        diff_points = {
            "A": "단순함·저비용·최대 성장 추구. S&P500 장기 연평균 10%. 단점: 하락장 변동성 크고 방어 자산 없음.",
            "B": "전천후 방어. 2008년 금융위기에 -3.9% (S&P500은 -37%). 단점: 채권 55% 비중으로 강세장 수익 낮음.",
            "C": "성장+배당 균형. ISA 절세 구조에 최적화. 단점: 3개 상품 관리 필요, 리밸런싱 주기 설정해야 함.",
        }

        prompt = f"""당신은 한국 사회초년생 자산관리 전문가입니다.
아래 포트폴리오의 장단점을 이 특정 사용자에게 맞게 설명하세요.
사용자: {profile.get('age')}세 {profile.get('job_type')}, 월수입 {fmt(profile.get('monthly_income',0))}
포트폴리오: [{portfolio_key}] {p['name']} ({p['type']})

반드시 아래 JSON만. 마크다운 없이.
{{
  "fit_reason": "{p['name']}이 이 사용자에게 맞는 구체적 이유 1문장",
  "pros": ["{p['name']}만의 장점 1", "{p['name']}만의 장점 2"],
  "cons": ["{p['name']}의 단점 1", "{p['name']}의 단점 2"]
}}"""
        resp = model.generate_content(prompt)
        text = resp.text.strip().replace("```json","").replace("```","").strip()
        return json.loads(text)
    except Exception:
        fallbacks = {
            "A": {"fit_reason": "장기 성장에 집중하고 싶은 분께 맞아요.", "pros": ["S&P500 장기 수익률", "관리 부담 적음"], "cons": ["하락장 변동성 큼", "방어 자산 없음"]},
            "B": {"fit_reason": "안정적으로 가고 싶은 분께 맞아요.", "pros": ["위기 방어력 우수", "4계절 분산"], "cons": ["강세장 수익률 낮음", "리밸런싱 번거로움"]},
            "C": {"fit_reason": "성장과 배당을 함께 잡고 싶은 분께 맞아요.", "pros": ["ISA 절세 최적화", "현금흐름 확보"], "cons": ["고배당 Tax Drag 주의", "리밸런싱 필요"]},
        }
        return fallbacks[portfolio_key]

# ──────────────────────────────────────────────
# 에이전트형 챗봇 엔진 (Function Calling 활성화)
# ──────────────────────────────────────────────
def get_gemini_chat_response(messages, profile, split_result, selected_portfolio):
    try:
        import google.generativeai as genai
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

        # 도구(Tools)를 쥐여주어 에이전트로 동작하게 만듦
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            tools=[get_macro_indicators, search_fed_policy]
        )

        alloc     = split_result.get("allocations", {})
        alloc_str = "\n".join([f"  - {k}: {fmt(v)}" for k, v in alloc.items()])
        port      = PORTFOLIOS.get(selected_portfolio, {})

        system = f"""당신은 한국 사회초년생의 자산을 방어하는 거시경제 특화 AI 에이전트 'SafeFolio AI'입니다.
단순히 질문에 답하는 것을 넘어, 필요하다면 제공된 도구(get_macro_indicators, search_fed_policy)를 적극적으로 호출하여 실시간 데이터를 기반으로 답변하세요.

[사용자 프로필 및 현황]
나이: {profile.get('age')}세 / 직업: {profile.get('job_type')}
월 여윳돈: {fmt(split_result.get('surplus',0))}
비상금 상태: {'충족' if split_result.get('emergency_ok') else '미충족'}
현재 포트폴리오: {port.get('name','미선택')} ({port.get('type','')})

[행동 지침]
1. 사용자가 금리, 경제 상황, 시장 변동성, 포트폴리오 방어력을 물어보면 반드시 함수를 호출하여 현재 VIX, 국채금리, 연준 이슈를 파악한 뒤 객관적으로 답변하세요.
2. 하방 경직성을 중시하는 방어적 투자 관점(인덱스 및 고배당 ETF의 역할)을 강조하세요.
3. 2026년 세법 기준을 따르며, 구체적인 수치를 들어 간결하게 설명하세요.
"""
        history = []
        for m in messages[1:-1]:
            role = "user" if m["role"] == "user" else "model"
            history.append({"role": role, "parts": [m["content"]]})

        # 자동 함수 호출(Function Calling) 활성화
        chat = model.start_chat(
            history=history,
            enable_automatic_function_calling=True
        )

        user_msg = messages[-1]["content"]
        full_msg = f"{system}\n\n사용자 질문: {user_msg}" if not history else user_msg

        return chat.send_message(full_msg).text
    except Exception as e:
        return f"⚠️ API 오류: {str(e)}"

# ──────────────────────────────────────────────
# session_state 초기화
# ──────────────────────────────────────────────
def init_state():
    defaults = {
        "page": "onboarding", "profile": {}, "assets": {},
        "monthly_income_list": [0]*12, "monthly_expense_list": [0]*12,
        "matched_policies": [], "split_result": {},
        "selected_portfolio": None, "portfolio_explanations": {},
        "analysis_done": False, "risk_profile": "C", "chat_messages": [],
        "realtime_A": None, "realtime_B": None, "realtime_C": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

def nav():
    pages = {"onboarding":"1️⃣ 내 재무 진단","dashboard":"2️⃣ 자산 현황",
             "recommend":"3️⃣ 맞춤 추천","chatbot":"4️⃣ AI 상담"}
    cols = st.columns(len(pages))
    for col, (key, label) in zip(cols, pages.items()):
        active = st.session_state.page == key
        if col.button(label, use_container_width=True,
                      type="primary" if active else "secondary"):
            st.session_state.page = key; st.rerun()
    st.divider()

# ──────────────────────────────────────────────
# 페이지1 — 온보딩
# ──────────────────────────────────────────────
def page_onboarding():
    st.title("🛡️ SafeFolio AI")
    st.subheader("내 재무 상태를 알려주세요")
    
    with st.form("onboarding_form"):
        st.markdown("**기본 정보**")
        c1, c2, c3 = st.columns(3)
        age      = c1.number_input("나이", 19, 65, 27, step=1)
        gender   = c2.selectbox("성별", ["남성","여성","선택 안 함"])
        job_type = c3.selectbox("직업 형태", ["정규직","계약직","프리랜서","무직"])

        st.markdown("**소득 정보**")
        c1, c2 = st.columns(2)
        monthly_income = c1.number_input("월 세후 수입 (원)", min_value=0, value=3_000_000, step=100_000, format="%d")
        bonus_yn  = c2.selectbox("성과급/상여금 여부", ["없음","분기","반기","연간"])
        bonus_amt = st.number_input("예상 성과급 1회 금액 (원)", min_value=0, value=3_000_000, step=500_000, format="%d") if bonus_yn != "없음" else 0

        st.markdown("**지출 정보**")
        c1, c2, c3 = st.columns(3)
        fixed_expense    = c1.number_input("월 고정지출 (원)", min_value=0, value=900_000, step=50_000, format="%d")
        variable_expense = c2.number_input("월 변동지출 (원)", min_value=0, value=600_000, step=50_000, format="%d")
        housing = c3.selectbox("주거 형태", ["월세","전세","자가","부모님 거주","무주택"])

        st.markdown("**부채 정보**")
        debt_yn = st.selectbox("부채 여부", ["없음","있음"])
        debt_total, debt_rate = 0, 0.0
        if debt_yn == "있음":
            c1, c2 = st.columns(2)
            debt_total = c1.number_input("총 부채 금액 (원)", min_value=0, value=10_000_000, step=1_000_000, format="%d")
            debt_rate  = c2.number_input("연이자율 (%)", 0.0, 30.0, 4.5, step=0.1)

        st.markdown("**비상금 및 목표**")
        c1, c2, c3, c4 = st.columns(4)
        emergency_current = c1.number_input("현재 비상금 잔액 (원)", min_value=0, value=500_000, step=100_000, format="%d")
        isa_current_year  = c2.number_input("올해 ISA 납입액 (원)", min_value=0, value=0, step=100_000, format="%d")
        invest_years = c3.slider("투자 기간 (년)", 1, 30, 5)
        goal_3y      = c4.number_input("3년 목표 저축액 (원)", min_value=0, value=30_000_000, step=1_000_000, format="%d")

        if st.form_submit_button("✅ 진단 시작", use_container_width=True, type="primary"):
            multiplier = {"없음":0,"분기":4,"반기":2,"연간":1}[bonus_yn]
            annual     = monthly_income * 12 + bonus_amt * multiplier
            total_exp  = fixed_expense + variable_expense
            emg_ok     = emergency_current >= total_exp * 6

            st.session_state.profile = {
                "age": age, "gender": gender, "job_type": job_type,
                "monthly_income": monthly_income, "annual_income": annual,
                "bonus_yn": bonus_yn, "bonus_amt": bonus_amt,
                "fixed_expense": fixed_expense, "variable_expense": variable_expense,
                "housing": housing, "debt_total": debt_total, "debt_rate": debt_rate,
                "emergency_current": emergency_current, "emergency_ok": emg_ok,
                "isa_current_year": isa_current_year,
                "invest_years": invest_years, "goal_3y": goal_3y,
            }
            st.session_state.analysis_done      = False
            st.session_state.selected_portfolio  = None
            st.session_state.chat_messages       = []
            st.success("✅ 입력 완료! '2️⃣ 자산 현황' 탭으로 이동해주세요.")
            st.balloons()

# ──────────────────────────────────────────────
# 페이지2 — 대시보드
# ──────────────────────────────────────────────
def page_dashboard():
    st.subheader("📊 자산 현황 대시보드")
    if not st.session_state.profile:
        st.warning("먼저 '1️⃣ 내 재무 진단' 탭에서 정보를 입력해주세요.")
        return

    p = st.session_state.profile
    months = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"]
    left, right = st.columns([1, 1.4], gap="large")

    with left:
        st.markdown("**💰 자산 입력**")
        with st.form("asset_form"):
            c1, c2 = st.columns(2)
            isa_etf     = c1.number_input("ISA — ETF/주식", min_value=0, value=0, step=100_000, format="%d")
            isa_deposit = c2.number_input("ISA — 예적금/채권", min_value=0, value=0, step=100_000, format="%d")
            youth_sav   = st.number_input("청년미래적금", min_value=0, value=0, step=100_000, format="%d")

            c1, c2 = st.columns(2)
            stock_gen   = c1.number_input("일반계좌 — 주식/ETF", min_value=0, value=0, step=100_000, format="%d")
            savings_gen = c2.number_input("일반계좌 — 예적금", min_value=0, value=0, step=100_000, format="%d")
            emergency   = st.number_input("비상금 통장", min_value=0, value=int(p.get("emergency_current",0)), step=100_000, format="%d")

            st.markdown("**부채 정보**")
            debt_yn2 = st.selectbox("부채 여부", ["없음","있음"], index=1 if p.get("debt_total",0) > 0 else 0)
            debt_total2 = p.get("debt_total", 0)
            debt_rate2  = p.get("debt_rate", 0.0)
            if debt_yn2 == "있음":
                c1, c2 = st.columns(2)
                debt_total2 = c1.number_input("총 부채 금액", min_value=0, value=int(p.get("debt_total",10_000_000)), step=1_000_000, format="%d")
                debt_rate2 = c2.number_input("연이자율 (%)", 0.0, 30.0, float(p.get("debt_rate",4.5)), step=0.1)

            st.markdown("**📅 월별 예상 수입 (12개월)**")
            income_list = []
            inc_cols = st.columns(4)
            for i, m in enumerate(months):
                default = p.get("monthly_income", 0)
                if p.get("bonus_yn") == "분기" and i % 3 == 2: default += p.get("bonus_amt", 0)
                elif p.get("bonus_yn") == "반기" and i in [5,11]: default += p.get("bonus_amt", 0)
                elif p.get("bonus_yn") == "연간" and i == 11: default += p.get("bonus_amt", 0)
                v = inc_cols[i%4].number_input(m, min_value=0, value=int(default), step=100_000, format="%d", key=f"inc_{i}")
                income_list.append(v)

            st.markdown("**📅 월별 예상 지출 (12개월)**")
            expense_list = []
            exp_cols = st.columns(4)
            total_exp_default = int(p.get("fixed_expense",0) + p.get("variable_expense",0))
            for i, m in enumerate(months):
                v = exp_cols[i%4].number_input(m, min_value=0, value=total_exp_default, step=100_000, format="%d", key=f"exp_{i}")
                expense_list.append(v)

            if st.form_submit_button("📊 대시보드 업데이트", use_container_width=True, type="primary"):
                st.session_state.assets = {
                    "ISA-ETF/주식": isa_etf, "ISA-예적금/채권": isa_deposit, "청년미래적금": youth_sav,
                    "일반계좌-주식/ETF": stock_gen, "일반계좌-예적금": savings_gen, "비상금 통장": emergency,
                }
                st.session_state.monthly_income_list  = income_list
                st.session_state.monthly_expense_list = expense_list
                st.session_state.profile.update({
                    "emergency_current": emergency,
                    "emergency_ok": emergency >= (p.get("fixed_expense",0) + p.get("variable_expense",0)) * 6,
                    "debt_total": debt_total2, "debt_rate": debt_rate2,
                    "total_assets": sum([isa_etf, isa_deposit, youth_sav, stock_gen, savings_gen, emergency])
                })
                st.rerun()

    with right:
        assets = st.session_state.assets
        if not assets:
            st.info("좌측에서 자산 정보를 입력하고 '대시보드 업데이트'를 눌러주세요.")
            return

        total_assets = sum(assets.values())
        debt_tot     = st.session_state.profile.get("debt_total", 0)
        net_worth    = total_assets - debt_tot
        goal         = p.get("goal_3y", 0)

        m1, m2, m3 = st.columns(3)
        m1.metric("총 자산",  fmt(total_assets))
        m2.metric("순 자산", fmt(net_worth))
        m3.metric("3년 목표 달성률", f"{min(net_worth/goal*100,999):.0f}%" if goal else "—")

        # 🚨 AI 에이전트 마켓 시그널 UI 추가
        st.divider()
        st.markdown("#### 🚨 실시간 마켓 리스크 시그널")
        with st.expander("AI 에이전트가 분석한 현재 시장 온도입니다.", expanded=True):
            if st.button("🔄 실시간 매크로 지표 분석"):
                with st.spinner("VIX 및 국채 금리 수집 중..."):
                    macro_data = get_macro_indicators()
                    if macro_data.get("status") == "success":
                        vix = macro_data["VIX"]
                        us10y = macro_data["US10Y"]
                        
                        c1, c2 = st.columns(2)
                        c1.metric("VIX (공포 지수)", f"{vix}", 
                                  delta="🔴 위험(20 이상)" if vix > 20 else "🟢 안정", 
                                  delta_color="inverse" if vix > 20 else "normal")
                        c2.metric("미국 10년물 국채 금리", f"{us10y}%", 
                                  delta="국채 수익률 매력도 상승" if us10y > 4.2 else "주식 프리미엄 확대")
                        
                        if vix > 20:
                            st.warning("⚠️ 시장 변동성이 커지고 있습니다. 포트폴리오의 하방을 지키는 단기채와 고배당 ETF의 역할이 중요한 시점입니다.")
                        else:
                            st.success("✅ 시장 심리가 안정적입니다. 설정하신 인덱스 적립식 투자를 그대로 유지하세요.")
                    else:
                        st.error("지표를 불러올 수 없습니다.")

        nonzero = {k:v for k,v in assets.items() if v > 0}
        if nonzero:
            fig = donut_chart(list(nonzero.keys()), list(nonzero.values()), title="자산 분포", center_text=fmt(total_assets))
            st.plotly_chart(fig, use_container_width=True)

        if debt_tot > 0:
            fig2 = donut_chart(["순자산","부채"], [max(net_worth,0), debt_tot], title="자본 vs 부채", colors=["#2ECC71","#E74C3C"])
            st.plotly_chart(fig2, use_container_width=True)

        inc_list, exp_list = st.session_state.monthly_income_list, st.session_state.monthly_expense_list
        if any(v > 0 for v in inc_list):
            sav_list  = [max(i-e,0) for i,e in zip(inc_list, exp_list)]
            rate_list = [s/i*100 if i>0 else 0 for s,i in zip(sav_list, inc_list)]
            fig3 = grouped_bar_line_chart(months, inc_list, exp_list, sav_list, rate_list)
            st.plotly_chart(fig3, use_container_width=True)

# ──────────────────────────────────────────────
# 페이지3 — 추천 엔진
# ──────────────────────────────────────────────
def page_recommend():
    st.subheader("🎯 맞춤형 추천 엔진")
    if not st.session_state.profile:
        st.warning("먼저 '1️⃣ 내 재무 진단' 탭에서 정보를 입력해주세요.")
        return

    if st.button("🚀 분석 시작", type="primary", use_container_width=True):
        with st.spinner("분석 중..."):
            p       = st.session_state.profile
            matched = match_policies(p)
            split   = calc_account_split(p, matched)
            st.session_state.matched_policies = matched
            st.session_state.split_result     = split
            st.session_state.risk_profile     = calc_risk_profile({**p, "emergency_ok": split["emergency_ok"]})
            st.session_state.analysis_done    = True
            st.session_state.portfolio_explanations = {}
        st.rerun()

    if not st.session_state.analysis_done: return

    tab1, tab2, tab3 = st.tabs(["① 청년 정책 매칭","② 통장 쪼개기","③ 포트폴리오 추천"])

    with tab1:
        for m in st.session_state.matched_policies:
            pol, eligible, conflict = m["policy"], m["eligible"], m.get("conflict",False)
            if eligible and not conflict: badge, color, border = "✅ 가입 가능", "#d4edda", "#28a745"
            elif conflict: badge, color, border = "⚠️ 중복 불가", "#fff3cd", "#ffc107"
            else: badge, color, border = "❌ 해당 없음", "#f8d7da", "#dc3545"
            action_html = f"<br/><span style='font-size:0.85em;color:#1a5276'>{pol.get('action','')}</span>" if eligible and not conflict and pol.get("action") else ""
            st.markdown(f"<div style='background:{color};border-left:4px solid {border};padding:12px 16px;border-radius:6px;margin-bottom:10px;'><b>{pol['name']}</b> &nbsp; <span style='font-size:0.85em'>{badge}</span><br/><span style='font-size:0.9em'>{pol['benefit']}</span>{action_html}</div>", unsafe_allow_html=True)

    with tab2:
        split, p = st.session_state.split_result, st.session_state.profile
        if split.get("surplus_warning"):
            st.error("🚨 월 수입이 총 지출보다 적어요.")
            return

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("월 수입", fmt(split["monthly_income"]))
        c2.metric("월 총 지출", fmt(split["total_expense"]))
        c3.metric("월 여윳돈", fmt(split["surplus"]))
        c4.metric("월 이자 비용", fmt(split.get("monthly_interest",0)) if split.get("monthly_interest",0) > 0 else "없음")

        alloc = split.get("allocations", {})
        nz = [(l,v) for l,v in zip(list(alloc.keys()) + ["고정지출","변동지출"], list(alloc.values()) + [split.get("fixed_expense",0), split.get("variable_expense",0)]) if v > 0]
        if nz:
            lbs, vls = zip(*nz)
            fig = donut_chart(list(lbs), list(vls), title="월급 쪼개기", center_text=fmt(split["monthly_income"]))
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        risk = st.session_state.get("risk_profile","C")
        orders = {"A":{"A":0,"C":1,"B":2},"B":{"B":0,"C":1,"A":2},"C":{"C":0,"A":1,"B":2}}
        
        for key in sorted(PORTFOLIOS.keys(), key=lambda k: orders[risk][k]):
            port, is_rec = PORTFOLIOS[key], key == risk
            with st.expander(f"{port['emoji']} **{port['name']}** ({port['type']})" + (" ⭐ 추천" if is_rec else ""), expanded=is_rec):
                labels, ratios = [a["name"] for a in port["assets"]], [a["ratio"] for a in port["assets"]]
                fig = go.Figure(go.Pie(labels=labels, values=ratios, hole=0.6, marker_colors=port["colors"]))
                st.plotly_chart(fig, use_container_width=True)
                
                realtime_key = f"realtime_{key}"
                if st.button("🔴 실시간 ETF 데이터 불러오기", key=f"fetch_{key}"):
                    with st.spinner("실시간 데이터 수집 중..."):
                        st.session_state[realtime_key] = fetch_etf_data(key)

                rd = st.session_state.get(realtime_key)
                if rd and rd.get("success"):
                    st.dataframe(pd.DataFrame(rd["assets"]), use_container_width=True, hide_index=True)

                if key not in st.session_state.portfolio_explanations:
                    with st.spinner(f"{port['name']} AI 분석 중..."):
                        st.session_state.portfolio_explanations[key] = get_gemini_portfolio_explanation(st.session_state.profile, key)

                exp = st.session_state.portfolio_explanations.get(key, {})
                st.success(f"✅ {exp.get('fit_reason','')}")

                if st.button("이 포트폴리오 선택하기", key=f"sel_{key}", type="primary"):
                    st.session_state.selected_portfolio = key
                    st.rerun()

# ──────────────────────────────────────────────
# 페이지4 — 챗봇 (AI 에이전트 도입)
# ──────────────────────────────────────────────
def page_chatbot():
    st.subheader("💬 AI 재무 비서 상담")
    if not st.session_state.profile:
        st.warning("먼저 '1️⃣ 내 재무 진단' 탭에서 정보를 입력해주세요.")
        return

    # 🤖 챗봇 진입 시 선제적 에이전트 브리핑
    if not st.session_state.chat_messages:
        p       = st.session_state.profile
        split   = st.session_state.split_result
        surplus = split.get("surplus", 0)
        
        intro = (
            f"안녕하세요! 당신의 포트폴리오 하방을 지키는 **SafeFolio AI 에이전트** 입니다. 🛡️\n\n"
            f"월 여윳돈 **{fmt(surplus)}** 기준으로 자산을 모니터링하고 있습니다. "
            f"방금 최신 시장 데이터를 스캔해 보니, **2026년 5월 연준 의장 임기 만료**와 관련된 "
            f"통화 정책 불확실성 시그널이 감지되었습니다.\n\n"
            f"현재 투자 중이신 배당 및 인덱스 포트폴리오에 미칠 영향이나, "
            f"추가적인 거시 지표(VIX 등)가 궁금하시다면 언제든 질문해 주세요!"
        )
        st.session_state.chat_messages = [{"role":"assistant","content":intro}]

    chat_box = st.container(height=450)
    with chat_box:
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if prompt := st.chat_input("질문을 입력하세요 (예: 최근 연준 이슈 때문에 주식 비중을 줄여야 할까?)"):
        st.session_state.chat_messages.append({"role":"user","content":prompt})
        with st.spinner("AI 에이전트가 시장 데이터를 분석하며 답변 생성 중..."):
            reply = get_gemini_chat_response(
                st.session_state.chat_messages, st.session_state.profile,
                st.session_state.split_result, st.session_state.selected_portfolio or "")
        st.session_state.chat_messages.append({"role":"assistant","content":reply})
        st.rerun()


# ──────────────────────────────────────────────
# 메인 라우터
# ──────────────────────────────────────────────
nav()
{"onboarding":page_onboarding,"dashboard":page_dashboard,
 "recommend":page_recommend,"chatbot":page_chatbot}[st.session_state.page]()

st.divider()
st.caption("⚠️ 본 서비스는 교육 목적이며 투자 권유가 아닙니다. 실제 투자 결정 전 전문가와 상담하세요.")
