import streamlit as st
import pandas as pd
import numpy as np
import json
import time
import datetime
import plotly.graph_objects as go

st.set_page_config(
    page_title="SafeFolio AI", page_icon="🛡️",
    layout="wide", initial_sidebar_state="collapsed"
)

# ══════════════════════════════════════════════════════════════
#  AGENT STYLE INJECTION
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── 신호등 배지 ── */
.signal-green  { background:#16a34a; color:#fff; border-radius:50%; width:18px; height:18px;
                 display:inline-block; text-align:center; line-height:18px; font-size:10px; }
.signal-yellow { background:#d97706; color:#fff; border-radius:50%; width:18px; height:18px;
                 display:inline-block; text-align:center; line-height:18px; font-size:10px; }
.signal-red    { background:#dc2626; color:#fff; border-radius:50%; width:18px; height:18px;
                 display:inline-block; text-align:center; line-height:18px; font-size:10px; }

/* ── 에이전트 사고 흐름 카드 ── */
.agent-step {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border-left: 3px solid #3b82f6;
    border-radius: 8px;
    padding: 10px 14px;
    margin: 6px 0;
    color: #e2e8f0;
    font-size: 0.85rem;
}
.agent-step .step-label {
    font-size: 0.7rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 2px;
}

/* ── 마켓 신호등 바 ── */
.macro-banner {
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 12px;
}
.macro-banner.green  { background: linear-gradient(90deg,#052e16,#14532d); border:1px solid #16a34a; }
.macro-banner.yellow { background: linear-gradient(90deg,#1c1400,#451a03); border:1px solid #d97706; }
.macro-banner.red    { background: linear-gradient(90deg,#1c0a0a,#450a0a); border:1px solid #dc2626; }
.macro-banner .signal { font-size:2rem; }
.macro-banner .desc  { color:#e2e8f0; }
.macro-banner .desc strong { font-size:1.05rem; }

/* ── 에이전트 브리핑 버블 ── */
.agent-brief {
    background: linear-gradient(135deg,#1e3a5f,#0f2744);
    border: 1px solid #2563eb;
    border-radius: 12px;
    padding: 14px 18px;
    color: #bfdbfe;
    font-size:0.9rem;
    margin-bottom: 12px;
}

/* ── 인디케이터 카드 ── */
.indicator-card {
    background:#1e293b;
    border-radius:10px;
    padding:12px;
    text-align:center;
    border: 1px solid #334155;
}
.indicator-card .ic-label { font-size:0.72rem; color:#94a3b8; margin-bottom:4px; }
.indicator-card .ic-value { font-size:1.4rem; font-weight:700; color:#f1f5f9; }
.indicator-card .ic-delta { font-size:0.75rem; margin-top:2px; }
.ic-up   { color:#f87171; }
.ic-down { color:#4ade80; }
.ic-neu  { color:#94a3b8; }

/* ── 사고 흐름 타임라인 ── */
.workflow-bar {
    display:flex; gap:0; margin:8px 0 14px;
}
.wf-step {
    flex:1; text-align:center; padding:7px 4px;
    font-size:0.7rem; font-weight:600;
    border-top: 3px solid #334155;
    color:#64748b;
    transition: all .3s;
}
.wf-step.active {
    border-top-color: #3b82f6;
    color:#93c5fd;
}
.wf-step.done {
    border-top-color: #16a34a;
    color:#4ade80;
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  상수 & 헬퍼
# ══════════════════════════════════════════════════════════════
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
    fig.add_trace(go.Bar(name="수입", x=months, y=income, marker_color="#4C9BE8", yaxis="y"))
    fig.add_trace(go.Bar(name="지출", x=months, y=expense, marker_color="#E87B4C", yaxis="y"))
    fig.add_trace(go.Bar(name="저축", x=months, y=savings, marker_color="#4CE87B", yaxis="y"))
    fig.add_trace(go.Scatter(
        name="저축률(%)", x=months, y=rates,
        mode="lines+markers+text",
        text=[f"{r:.0f}%" for r in rates], textposition="top center",
        line=dict(color="#F0C040", width=2), marker=dict(size=6), yaxis="y2"
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


# ══════════════════════════════════════════════════════════════
#  청년 정책 데이터
# ══════════════════════════════════════════════════════════════
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


# ══════════════════════════════════════════════════════════════
#  ███████╗  AGENT TOOLS  (Function Calling Layer)
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=1800)   # 30분 캐시
def get_macro_indicators() -> dict:
    """
    Tool 1 — 거시 지표 수집
    VIX, 10년물 국채, S&P500, 고배당 ETF 실시간 데이터 수집
    yfinance 사용. 네트워크 차단 환경 대비 fallback 내장.
    """
    try:
        import yfinance as yf
        tickers = {
            "^VIX":   "VIX 공포지수",
            "^TNX":   "미국 10년물 국채금리",
            "^GSPC":  "S&P 500",
            "DVY":    "고배당 ETF (iShares DVY)",
            "GLD":    "금 ETF (SPDR GLD)",
        }
        results = {}
        for sym, label in tickers.items():
            try:
                t    = yf.Ticker(sym)
                hist = t.history(period="5d")
                if hist.empty:
                    continue
                cur  = round(hist["Close"].iloc[-1], 2)
                prev = round(hist["Close"].iloc[-2], 2) if len(hist) >= 2 else cur
                chg  = round(cur - prev, 2)
                pct  = round((chg / prev) * 100, 2) if prev else 0
                results[sym] = {
                    "label": label, "current": cur,
                    "prev": prev, "change": chg, "pct_change": pct,
                }
            except Exception:
                pass

        # CPI — 최근 발표치 내장값 사용 (실시간 API 별도 키 필요)
        results["CPI_LAST"] = {
            "label": "미국 CPI (최근 발표, 전년비)",
            "current": 3.4, "prev": 3.5,
            "change": -0.1, "pct_change": -0.1,
            "note": "2024년 4월 BLS 발표 기준 내장값"
        }
        results["FED_RATE"] = {
            "label": "미국 기준금리",
            "current": 5.5, "prev": 5.5,
            "change": 0.0, "pct_change": 0.0,
            "note": "2024년 FOMC 동결 기준 내장값"
        }
        # 위험 수준 계산 (0=안전/1=주의/2=위험)
        vix = results.get("^VIX", {}).get("current", 15)
        tnx = results.get("^TNX", {}).get("current", 4.2)
        cpi = results.get("CPI_LAST", {}).get("current", 3.0)

        risk_score = 0
        if vix > 30:   risk_score += 2
        elif vix > 20: risk_score += 1
        if tnx > 5.0:  risk_score += 2
        elif tnx > 4.5:risk_score += 1
        if cpi > 4.0:  risk_score += 2
        elif cpi > 3.0:risk_score += 1

        if risk_score >= 4:   risk_level = "red"
        elif risk_score >= 2: risk_level = "yellow"
        else:                 risk_level = "green"

        return {
            "success": True,
            "indicators": results,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "fetch_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        # Fallback: 내장 더미 데이터
        return {
            "success": False,
            "error": str(e),
            "indicators": {
                "^VIX":     {"label":"VIX 공포지수",       "current":16.8, "prev":15.9, "change":0.9,  "pct_change":5.66},
                "^TNX":     {"label":"미국 10년물 국채금리","current":4.31, "prev":4.28, "change":0.03, "pct_change":0.70},
                "^GSPC":    {"label":"S&P 500",             "current":5277, "prev":5254, "change":23,   "pct_change":0.44},
                "CPI_LAST": {"label":"미국 CPI (전년비)",   "current":3.4,  "prev":3.5,  "change":-0.1, "pct_change":-0.1,"note":"BLS 내장값"},
                "FED_RATE": {"label":"미국 기준금리",       "current":5.5,  "prev":5.5,  "change":0.0,  "pct_change":0.0, "note":"FOMC 내장값"},
            },
            "risk_level": "yellow",
            "risk_score": 2,
            "fetch_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + " (내장 데이터)",
        }


def search_fed_policy(query: str = "") -> dict:
    """
    Tool 2 — 연준 정책 뉴스 검색 (Gemini web_search 활용)
    API 호출로 최신 FOMC/금리/인사 관련 뉴스 수집.
    """
    try:
        import google.generativeai as genai
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

        tools = [{"google_search": {}}]
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            tools=tools,
        )
        search_q = query if query else (
            "2026 Federal Reserve FOMC rate decision Jerome Powell leadership "
            "inflation CPI outlook market impact"
        )
        resp = model.generate_content(search_q)
        text = resp.text if hasattr(resp, "text") else str(resp)

        return {
            "success": True,
            "query": search_q,
            "summary": text[:1200],
            "fetch_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        # Fallback 내장 시나리오
        fallback_news = [
            {
                "headline": "Fed 2026: 연준 의장 리더십 교체 시나리오 분석",
                "summary": (
                    "2026년 5월 파월 의장 임기 종료 가능성이 시장의 주목을 받고 있습니다. "
                    "후임 의장 성향에 따라 금리 경로가 변할 수 있으며, "
                    "불확실성이 높아지는 구간에서 VIX 상승 가능성이 존재합니다."
                ),
                "impact": "yellow",
                "source": "내장 시나리오 (API 연결 전)",
            },
            {
                "headline": "FOMC 2026: 금리 동결 vs 인하 논쟁 지속",
                "summary": (
                    "2026년 상반기 FOMC는 CPI 3%대 진입 여부를 핵심 기준으로 "
                    "금리 인하 시점을 저울질 중입니다. "
                    "인플레이션 재가속 시나리오 대비가 필요합니다."
                ),
                "impact": "yellow",
                "source": "내장 시나리오",
            },
            {
                "headline": "배당 ETF 방어력: 금리 5% 구간 과거 성과 분석",
                "summary": (
                    "2022~2023년 금리 급등기에 ACE 미국배당다우존스는 "
                    "S&P500 대비 낙폭이 약 8%p 낮았습니다. "
                    "고배당 종목의 안정적 현금흐름이 방어막 역할을 했습니다."
                ),
                "impact": "green",
                "source": "내장 시나리오",
            },
        ]
        return {
            "success": False,
            "error": str(e),
            "news_items": fallback_news,
            "fetch_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + " (내장 데이터)",
        }


@st.cache_data(ttl=3600)
def analyze_defensive_impact(macro_data: str = "") -> dict:
    """
    Tool 3 — 방어력 분석
    VIX/금리 구간별 포트폴리오 하방 방어력을 yfinance 과거 데이터로 매핑.
    """
    try:
        import yfinance as yf

        # 금리 급등기 (2022-01 ~ 2022-12) 방어력 비교
        period_start = "2022-01-01"
        period_end   = "2022-12-31"
        defense_tickers = {
            "^GSPC":   "S&P 500",
            "DVY":     "고배당 ETF (DVY)",
            "TLT":     "미국 20년 국채 ETF (TLT)",
            "GLD":     "금 ETF (GLD)",
            "^VIX":    "VIX",
        }
        results = {}
        for sym, label in defense_tickers.items():
            try:
                t = yf.Ticker(sym)
                h = t.history(start=period_start, end=period_end)
                if h.empty:
                    continue
                ret = (h["Close"].iloc[-1] / h["Close"].iloc[0] - 1) * 100
                results[sym] = {"label": label, "return_pct": round(ret, 1)}
            except Exception:
                pass

        if not results:
            raise ValueError("yfinance 데이터 없음")

        return {
            "success": True,
            "period": f"{period_start} ~ {period_end} (금리 급등기)",
            "scenario": "2022년 연준 급격한 금리 인상 (0.25%→4.25%) 시나리오",
            "data": results,
        }

    except Exception:
        return {
            "success": False,
            "period": "2022-01 ~ 2022-12 (내장 데이터)",
            "scenario": "2022년 연준 급격한 금리 인상 시나리오",
            "data": {
                "^GSPC": {"label": "S&P 500",             "return_pct": -19.4},
                "DVY":   {"label": "고배당 ETF (DVY)",     "return_pct":  -4.3},
                "TLT":   {"label": "미국 20년 국채 (TLT)", "return_pct": -31.2},
                "GLD":   {"label": "금 ETF (GLD)",         "return_pct":  -0.3},
            },
        }


# ══════════════════════════════════════════════════════════════
#  ███████╗  AGENT ORCHESTRATOR  (자율 사고 흐름)
# ══════════════════════════════════════════════════════════════

def agent_perceive_intent(user_message: str) -> dict:
    """
    Step 1 — Perception: 사용자 메시지 의도 분류
    Returns: intent_type, tools_needed, confidence
    """
    msg = user_message.lower()

    # 키워드 기반 의도 분류
    macro_keywords = ["vix","금리","인플레","cpi","연준","fomc","fed","금리인상","경기침체",
                      "하락","폭락","위기","공포","매파","비둘기","파월","기준금리","채권","국채"]
    defensive_keywords = ["방어","하방","보호","걱정","불안","무서","위험","리스크","헷지",
                          "안전","떨어지면","급락","손실","멘탈","겁","무섭","떨려"]
    fed_keywords = ["연준","fomc","파월","powell","금리결정","통화정책","의장","임기","교체"]

    intent_scores = {
        "macro_analysis":   sum(1 for k in macro_keywords   if k in msg),
        "defensive_shield": sum(1 for k in defensive_keywords if k in msg),
        "fed_policy":       sum(1 for k in fed_keywords      if k in msg),
        "general_finance":  1,  # 기본값
    }
    top_intent = max(intent_scores, key=lambda k: intent_scores[k])

    # 도구 선택 로직
    tools_needed = []
    if intent_scores["macro_analysis"] > 0 or intent_scores["defensive_shield"] > 0:
        tools_needed.append("get_macro_indicators")
    if intent_scores["fed_policy"] > 0 or intent_scores["macro_analysis"] > 1:
        tools_needed.append("search_fed_policy")
    if intent_scores["defensive_shield"] > 1:
        tools_needed.append("analyze_defensive_impact")
    if not tools_needed:
        tools_needed = ["get_macro_indicators"]  # 기본 컨텍스트

    return {
        "intent_type": top_intent,
        "tools_needed": tools_needed,
        "is_anxiety": intent_scores["defensive_shield"] > 0,
        "needs_macro": intent_scores["macro_analysis"] > 0 or intent_scores["fed_policy"] > 0,
    }


def agent_run(user_message: str, profile: dict, split_result: dict,
              selected_portfolio: str, workflow_placeholder=None) -> str:
    """
    에이전트 메인 실행 루프
    Perception → Action (Tool Calls) → Analysis → Output
    """

    def _update_workflow(step_idx: int, steps: list, placeholder):
        if placeholder is None:
            return
        html = '<div class="workflow-bar">'
        for i, s in enumerate(steps):
            cls = "done" if i < step_idx else ("active" if i == step_idx else "wf-step")
            if i < step_idx:
                css = "wf-step done"
            elif i == step_idx:
                css = "wf-step active"
            else:
                css = "wf-step"
            html += f'<div class="{css}">{s}</div>'
        html += '</div>'
        placeholder.markdown(html, unsafe_allow_html=True)

    steps = ["🔍 의도 파악", "⚙️ 도구 실행", "🧹 데이터 정제", "📋 인사이트 출력"]

    # ── STEP 1: Perception ──
    _update_workflow(0, steps, workflow_placeholder)
    intent = agent_perceive_intent(user_message)
    time.sleep(0.2)

    # ── STEP 2: Action (Tool Calls) ──
    _update_workflow(1, steps, workflow_placeholder)
    tool_results = {}

    if "get_macro_indicators" in intent["tools_needed"]:
        tool_results["macro"] = get_macro_indicators()
        time.sleep(0.1)

    if "search_fed_policy" in intent["tools_needed"]:
        tool_results["fed"] = search_fed_policy(user_message)
        time.sleep(0.1)

    if "analyze_defensive_impact" in intent["tools_needed"]:
        tool_results["defense"] = analyze_defensive_impact()
        time.sleep(0.1)

    # ── STEP 3: Analysis (Gemini에 컨텍스트 주입) ──
    _update_workflow(2, steps, workflow_placeholder)

    macro_ctx  = _format_macro_context(tool_results)
    fed_ctx    = _format_fed_context(tool_results)
    defense_ctx= _format_defense_context(tool_results)

    # ── STEP 4: Output (Gemini 최종 답변) ──
    _update_workflow(3, steps, workflow_placeholder)

    reply = _call_gemini_agent(
        user_message=user_message,
        profile=profile,
        split_result=split_result,
        selected_portfolio=selected_portfolio,
        macro_ctx=macro_ctx,
        fed_ctx=fed_ctx,
        defense_ctx=defense_ctx,
        intent=intent,
    )
    return reply


def _format_macro_context(tool_results: dict) -> str:
    macro = tool_results.get("macro", {})
    if not macro:
        return "거시 지표 데이터 없음"
    inds = macro.get("indicators", {})
    lines = [f"[거시 지표 — {macro.get('fetch_time','')}]"]
    for sym, d in inds.items():
        chg_str = f"{d['change']:+.2f} ({d['pct_change']:+.1f}%)"
        lines.append(f"• {d['label']}: {d['current']} {chg_str}")
    lines.append(f"→ 종합 리스크 레벨: {macro.get('risk_level','unknown').upper()} (점수: {macro.get('risk_score',0)}/6)")
    return "\n".join(lines)


def _format_fed_context(tool_results: dict) -> str:
    fed = tool_results.get("fed", {})
    if not fed:
        return "연준 정책 데이터 없음"
    if fed.get("success"):
        return f"[연준 정책 뉴스 요약]\n{fed.get('summary','')[:600]}"
    else:
        items = fed.get("news_items", [])
        lines = ["[연준 정책 뉴스 — 내장 시나리오]"]
        for item in items:
            lines.append(f"• {item['headline']}: {item['summary'][:120]}")
        return "\n".join(lines)


def _format_defense_context(tool_results: dict) -> str:
    defense = tool_results.get("defense", {})
    if not defense:
        return ""
    lines = [f"[방어력 분석 — {defense.get('scenario','')}]"]
    for sym, d in defense.get("data", {}).items():
        arrow = "▲" if d["return_pct"] > 0 else "▼"
        lines.append(f"• {d['label']}: {arrow} {d['return_pct']:+.1f}%")
    return "\n".join(lines)


def _call_gemini_agent(user_message, profile, split_result,
                       selected_portfolio, macro_ctx, fed_ctx, defense_ctx, intent):
    try:
        import google.generativeai as genai
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-2.5-flash")

        alloc     = split_result.get("allocations", {})
        alloc_str = "\n".join([f"  - {k}: {fmt(v)}" for k, v in alloc.items()])
        port      = PORTFOLIOS.get(selected_portfolio, {})
        dvi       = calc_debt_vs_invest(profile)

        tone_guide = (
            "사용자가 시장 하락에 대한 불안감을 표현하고 있습니다. "
            "데이터 기반으로 안심을 주되, 근거 없는 낙관은 피하세요. "
            "포트폴리오의 방어력을 수치로 설명하세요.\n"
            if intent.get("is_anxiety") else ""
        )

        system = f"""당신은 한국 사회초년생 전문 재무 AI 'SafeFolio AI'의 매크로 방어 분석가입니다.
아래 실시간 수집한 거시 데이터와 연준 정책 뉴스를 활용해 답변하세요.

{tone_guide}

━━━ 실시간 수집 데이터 (에이전트가 자동 수집) ━━━
{macro_ctx}

{fed_ctx}

{defense_ctx}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[사용자 프로필]
나이: {profile.get('age')}세 / 직업: {profile.get('job_type')} / 월수입: {fmt(profile.get('monthly_income',0))}
부채: {'있음 (금리 '+str(profile.get('debt_rate',0))+'%)' if profile.get('debt_total',0)>0 else '없음'}
비상금: {'충족' if split_result.get('emergency_ok') else '미충족'}

[통장 쪼개기]
{alloc_str}

[선택 포트폴리오]
{port.get('name','')} ({port.get('type','')}) — 기대수익률 {port.get('expected_return',0)*100:.1f}%

[부채 vs 투자]
{f"대출금리 {dvi['debt_rate']}% vs 세후 기대수익률 {dvi['after_tax_return']:.1f}% → {'상환 우선 권장' if dvi['prefer_repay'] else '투자 병행 가능'}" if dvi else "부채 없음"}

[답변 원칙]
1. 반드시 위 실시간 데이터의 수치를 직접 인용하여 근거를 제시하세요.
2. VIX, 금리, CPI 등 지표를 포트폴리오 방어력과 연결지어 설명하세요.
3. "현재 VIX XX — {port.get('name','')}의 과거 방어율" 형태로 구체적으로.
4. 사회초년생 눈높이로, 쉽고 간결하게. 이모지 적극 활용.
5. 마지막에 한 줄 요약 인사이트를 **굵게** 제시하세요.
6. 투자 권유 아닌 교육·정보 제공임을 명심하세요.
"""
        history = []
        for m in st.session_state.chat_messages[1:-1]:
            history.append({
                "role": "user" if m["role"] == "user" else "model",
                "parts": [m["content"]]
            })
        chat     = model.start_chat(history=history)
        full_msg = f"{system}\n\n사용자 질문: {user_message}" if not history else user_message
        return chat.send_message(full_msg).text

    except Exception as e:
        return f"⚠️ 에이전트 오류: {str(e)}\n\n일반 답변으로 대체합니다: {user_message}에 대한 분석을 위해 거시 지표를 확인하세요."


# ══════════════════════════════════════════════════════════════
#  PROACTIVE BRIEFING (선제적 브리핑 생성)
# ══════════════════════════════════════════════════════════════

def generate_proactive_briefing(macro_data: dict) -> dict:
    """
    챗봇 진입 시 선제적 브리핑 생성.
    거시 데이터를 분석해 오늘의 핵심 이슈를 1~2줄로 제시.
    """
    try:
        import google.generativeai as genai
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-2.5-flash")

        inds      = macro_data.get("indicators", {})
        risk_lv   = macro_data.get("risk_level", "green")
        vix_val   = inds.get("^VIX",   {}).get("current", 15)
        tnx_val   = inds.get("^TNX",   {}).get("current", 4.3)
        cpi_val   = inds.get("CPI_LAST",{}).get("current", 3.4)
        spx_pct   = inds.get("^GSPC",  {}).get("pct_change", 0)

        prompt = f"""아래 거시 지표 기준으로 오늘 시장의 핵심 이슈 한 문장과
투자자에게 능동적으로 던질 질문 한 문장을 만들어주세요.

VIX: {vix_val}, 10년금리: {tnx_val}%, CPI: {cpi_val}%, S&P500 전일비: {spx_pct:+.2f}%
리스크레벨: {risk_lv.upper()}

형식 (JSON만, 마크다운 없이):
{{"issue": "오늘 시장 핵심 이슈 1문장 (VIX/금리 수치 포함)",
 "question": "투자자에게 던지는 능동적 질문 1문장"}}"""

        resp = model.generate_content(prompt)
        text = resp.text.strip().replace("```json","").replace("```","").strip()
        return json.loads(text)
    except Exception:
        risk_map = {
            "red":    {"issue": f"VIX {inds.get('^VIX',{}).get('current','—')} 급등 — 시장 공포 심리가 고조되고 있습니다.",
                       "question": "포트폴리오 방어력 점검을 지금 바로 해볼까요?"},
            "yellow": {"issue": f"10년물 국채금리 {inds.get('^TNX',{}).get('current','—')}% — 연준 동향을 주시해야 합니다.",
                       "question": "오늘 연준 관련 뉴스가 감지됐어요. 포트폴리오 영향 분석을 들어보시겠어요?"},
            "green":  {"issue": f"VIX {inds.get('^VIX',{}).get('current','—')} — 시장이 비교적 안정적입니다.",
                       "question": "현재 거시 환경에서 배당 전략의 기회를 점검해볼까요?"},
        }
        inds = macro_data.get("indicators", {})
        return risk_map.get(macro_data.get("risk_level","green"),
                            risk_map["green"])


# ══════════════════════════════════════════════════════════════
#  기존 Gemini 함수들 (유지)
# ══════════════════════════════════════════════════════════════

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
                results.append({"name":name,"ratio":asset["ratio"],"price":None,
                                 "return_1y":None,"div_yield":None,"status":"티커 없음"})
                continue
            try:
                t    = yf.Ticker(ticker)
                hist = t.history(period="1y")
                info = t.info
                if hist.empty or len(hist) < 5:
                    results.append({"name":name,"ratio":asset["ratio"],"price":None,
                                     "return_1y":None,"div_yield":None,"status":"데이터 없음"})
                    continue
                price     = round(hist["Close"].iloc[-1])
                ret_1y    = round((hist["Close"].iloc[-1]/hist["Close"].iloc[0]-1)*100, 2)
                div_raw   = info.get("dividendYield") or 0
                div_yield = round(div_raw*100, 2)
                fetch_time= str(hist.index[-1].date())
                weighted_return += ret_1y * ratio
                weighted_div    += div_yield * ratio
                results.append({"name":name,"ratio":asset["ratio"],"price":price,
                                 "return_1y":ret_1y,"div_yield":div_yield,"status":"✅"})
            except Exception as e:
                results.append({"name":name,"ratio":asset["ratio"],"price":None,
                                 "return_1y":None,"div_yield":None,"status":f"오류:{str(e)[:30]}"})

        return {"success":True,"assets":results,
                "weighted_return":round(weighted_return,2),
                "weighted_div":round(weighted_div,2),"fetch_time":fetch_time}
    except Exception as e:
        return {"success":False,"error":str(e)}


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
        matched.append({"policy":p,"eligible":ok,"conflict":False})
    youth_ok = any(m["eligible"] and m["policy"]["id"]=="youth_savings" for m in matched)
    if youth_ok:
        for m in matched:
            if m["policy"]["id"] == "youth_isa":
                m["conflict"] = True
    return matched


def calc_risk_profile(profile):
    score = 0
    age = profile.get("age", 30)
    if age <= 30:   score += 2
    elif age <= 35: score += 1
    dr = profile.get("debt_rate", 0)
    if dr < 5:      score += 2
    elif dr < 8:    score += 1
    if profile.get("emergency_ok"): score += 2
    yrs = profile.get("invest_years", 5)
    if yrs >= 7:    score += 2
    elif yrs >= 4:  score += 1
    if score >= 7: return "A"
    elif score >= 4: return "C"
    else: return "B"


def calc_account_split(profile, matched_policies):
    monthly       = profile.get("monthly_income", 0)
    fixed         = profile.get("fixed_expense", 0)
    variable      = profile.get("variable_expense", 0)
    total_expense = fixed + variable
    emg_cur       = profile.get("emergency_current", 0)
    debt_rate     = profile.get("debt_rate", 0)
    debt_tot      = profile.get("debt_total", 0)
    isa_current   = profile.get("isa_current_year", 0)

    emg_target = total_expense * 6
    emg_gap    = max(0, emg_target - emg_cur)
    emg_ok     = emg_gap == 0
    monthly_interest = round(debt_tot * debt_rate / 100 / 12) if debt_tot > 0 else 0
    debt_prio  = debt_rate >= 5.0
    youth_ok   = any(
        m["eligible"] and not m["conflict"] and m["policy"]["id"]=="youth_savings"
        for m in matched_policies
    )
    isa_remaining  = max(0, ISA_ANNUAL_LIMIT - isa_current)
    isa_monthly_max= round(isa_remaining / 12)
    surplus        = monthly - total_expense
    remaining      = surplus
    alloc          = {}

    if surplus <= 0:
        return {
            "surplus_warning": True,
            "monthly_income": monthly, "fixed_expense": fixed,
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

    invest_want   = remaining * 0.65
    invest_actual = min(invest_want, isa_monthly_max) if isa_monthly_max > 0 else invest_want
    alloc["ISA / 투자"] = round(invest_actual); remaining -= invest_actual
    alloc["자유 지출"]  = max(0, round(remaining))

    return {
        "surplus_warning": False,
        "monthly_income": monthly, "fixed_expense": fixed,
        "variable_expense": variable, "total_expense": total_expense,
        "surplus": surplus,
        "fixed_ratio": total_expense/monthly if monthly else 0,
        "fixed_warning": total_expense/monthly > 0.6 if monthly else False,
        "emergency_target": emg_target, "emergency_gap": emg_gap,
        "emergency_ok": emg_ok, "monthly_interest": monthly_interest,
        "debt_priority": debt_prio, "isa_remaining": isa_remaining,
        "allocations": alloc,
    }


def calc_goal_simulation(profile, split_result):
    alloc          = split_result.get("allocations", {})
    monthly_inv    = alloc.get("ISA / 투자", 0) + alloc.get("청년미래적금", 0)
    current_assets = profile.get("total_assets", 0)
    goal_3y        = profile.get("goal_3y", 0)
    risk_key       = st.session_state.get("risk_profile", "C")
    r_annual       = PORTFOLIOS[risk_key]["expected_return"]
    r_monthly      = (1 + r_annual) ** (1/12) - 1
    results = []
    capital = current_assets
    for month in range(1, 37):
        capital = capital * (1 + r_monthly) + monthly_inv
        if month % 12 == 0:
            results.append({"연도": f"{month//12}년 후", "예상 자산": round(capital)})
    final     = results[-1]["예상 자산"] if results else current_assets
    achievable= final >= goal_3y
    return {
        "yearly": results, "final_3y": final, "goal_3y": goal_3y,
        "achievable": achievable, "monthly_inv": monthly_inv,
        "shortfall": max(0, goal_3y - final),
    }


def calc_debt_vs_invest(profile):
    debt_rate = profile.get("debt_rate", 0)
    debt_tot  = profile.get("debt_total", 0)
    if debt_tot == 0:
        return None
    risk_key        = st.session_state.get("risk_profile", "C")
    exp_return      = PORTFOLIOS[risk_key]["expected_return"] * 100
    after_tax_return= exp_return * (1 - DIVIDEND_TAX)
    amount          = 1_000_000
    years           = 5
    repay_gain      = amount * debt_rate / 100 * years
    invest_gain     = amount * ((1 + after_tax_return/100)**years - 1)
    return {
        "debt_rate": debt_rate, "exp_return": exp_return,
        "after_tax_return": after_tax_return,
        "repay_gain": repay_gain, "invest_gain": invest_gain,
        "prefer_repay": debt_rate >= after_tax_return,
        "diff": abs(repay_gain - invest_gain),
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

사용자: {profile.get('age')}세 {profile.get('job_type')}, 월수입 {fmt(profile.get('monthly_income',0))},
투자기간 {profile.get('invest_years')}년, 부채 {'있음(금리'+str(profile.get('debt_rate'))+'%)' if profile.get('debt_total',0)>0 else '없음'},
비상금 {'충족' if profile.get('emergency_ok') else '미충족'}

포트폴리오: [{portfolio_key}] {p['name']} ({p['type']})
구성: {assets_str}
특성: {diff_points[portfolio_key]}
기대수익률: 연 {p['expected_return']*100:.1f}% / 예상변동성: {p['expected_risk']*100:.0f}%

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
            "A": {"fit_reason": "단순하고 비용 낮은 전략으로 장기 성장에 집중하고 싶은 분께 맞아요.",
                  "pros": ["S&P500 연평균 10% 장기 수익률 검증됨","운용 수수료 최저, 관리 부담 거의 없음"],
                  "cons": ["주식 90%로 하락장 낙폭 클 수 있음","채권·금 등 방어 자산 전혀 없음"]},
            "B": {"fit_reason": "어떤 국면에도 크게 잃지 않고 안정적으로 가고 싶은 분께 맞아요.",
                  "pros": ["2008년 금융위기 -3.9% 방어 (S&P500 -37%)","주식·채권·금·원자재 4계절 분산"],
                  "cons": ["채권 55% 비중으로 강세장 수익률 낮음","5개 ETF 관리·리밸런싱 번거로울 수 있음"]},
            "C": {"fit_reason": "성장과 배당 현금흐름 두 마리 토끼를 잡고 싶은 사회초년생께 맞아요.",
                  "pros": ["ISA 절세 구조에 최적화된 자산 배치","배당 현금흐름으로 심리적 안정감 확보"],
                  "cons": ["고배당 ETF 비중으로 Tax Drag 주의 필요","연 1회 리밸런싱 직접 챙겨야 함"]},
        }
        return fallbacks[portfolio_key]


# ══════════════════════════════════════════════════════════════
#  SESSION STATE 초기화
# ══════════════════════════════════════════════════════════════
def init_state():
    defaults = {
        "page": "onboarding", "profile": {}, "assets": {},
        "monthly_income_list": [0]*12, "monthly_expense_list": [0]*12,
        "matched_policies": [], "split_result": {},
        "selected_portfolio": None, "portfolio_explanations": {},
        "analysis_done": False, "risk_profile": "C", "chat_messages": [],
        "realtime_A": None, "realtime_B": None, "realtime_C": None,
        # ── 에이전트 신규 상태 ──
        "macro_cache":     None,   # 거시 지표 캐시
        "macro_cache_ts":  None,   # 캐시 타임스탬프
        "agent_briefing":  None,   # 선제적 브리핑
        "briefing_done":   False,  # 브리핑 최초 생성 여부
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ══════════════════════════════════════════════════════════════
#  MACRO SIGNAL BANNER  (대시보드 상단 신호등)
# ══════════════════════════════════════════════════════════════
def render_macro_signal_banner():
    """대시보드/챗봇 상단에 거시 리스크 신호등 렌더링"""
    macro = get_macro_indicators()
    st.session_state.macro_cache = macro

    risk_lv = macro.get("risk_level", "green")
    inds    = macro.get("indicators", {})
    vix     = inds.get("^VIX", {}).get("current", "—")
    tnx     = inds.get("^TNX", {}).get("current", "—")
    cpi     = inds.get("CPI_LAST", {}).get("current", "—")

    signal_map = {
        "green":  ("🟢", "안전", "시장 변동성 낮음 — 투자 심리 안정적"),
        "yellow": ("🟡", "주의", "매크로 리스크 상승 — 방어 자산 비중 점검 권장"),
        "red":    ("🔴", "경고", "고위험 구간 — 포트폴리오 하방 방어력 즉시 점검"),
    }
    icon, label, desc = signal_map[risk_lv]

    st.markdown(f"""
<div class="macro-banner {risk_lv}">
  <span class="signal">{icon}</span>
  <div class="desc">
    <strong>매크로 리스크 {label}</strong> &nbsp;
    <span style="font-size:0.78rem;color:#94a3b8">({macro.get('fetch_time','')})</span><br/>
    {desc} &nbsp;|&nbsp; VIX <b>{vix}</b> &nbsp;·&nbsp; 10년금리 <b>{tnx}%</b> &nbsp;·&nbsp; CPI <b>{cpi}%</b>
  </div>
</div>
""", unsafe_allow_html=True)

    return macro


# ══════════════════════════════════════════════════════════════
#  NAVIGATION
# ══════════════════════════════════════════════════════════════
def nav():
    pages = {"onboarding":"1️⃣ 내 재무 진단","dashboard":"2️⃣ 자산 현황",
             "recommend":"3️⃣ 맞춤 추천","chatbot":"4️⃣ AI 매크로 상담"}
    cols = st.columns(len(pages))
    for col, (key, label) in zip(cols, pages.items()):
        active = st.session_state.page == key
        if col.button(label, use_container_width=True,
                      type="primary" if active else "secondary"):
            if key == "chatbot":
                # 챗봇 진입 시 브리핑 초기화 → 재생성
                st.session_state.briefing_done  = False
                st.session_state.chat_messages  = []
                st.session_state.agent_briefing = None
            st.session_state.page = key
            st.rerun()
    st.divider()


# ══════════════════════════════════════════════════════════════
#  PAGE 1 — 온보딩 (기존 유지)
# ══════════════════════════════════════════════════════════════
def page_onboarding():
    st.title("🛡️ SafeFolio AI")
    st.subheader("내 재무 상태를 알려주세요")
    st.caption("입력하신 정보는 분석에만 사용되며 저장되지 않아요.")

    with st.form("onboarding_form"):
        st.markdown("**기본 정보**")
        c1, c2, c3 = st.columns(3)
        age      = c1.number_input("나이", 19, 65, 27, step=1)
        gender   = c2.selectbox("성별", ["남성","여성","선택 안 함"])
        job_type = c3.selectbox("직업 형태", ["정규직","계약직","프리랜서","무직"])

        st.markdown("**소득 정보**")
        c1, c2 = st.columns(2)
        monthly_income = c1.number_input("월 세후 수입 (원)",
            min_value=0, value=3_000_000, step=100_000, format="%d")
        bonus_yn  = c2.selectbox("성과급/상여금 여부", ["없음","분기","반기","연간"])
        bonus_amt = 0
        if bonus_yn != "없음":
            bonus_amt = st.number_input("예상 성과급 1회 금액 (원)",
                min_value=0, value=3_000_000, step=500_000, format="%d")

        st.markdown("**지출 정보**")
        st.caption("고정지출: 주거비·통신비·보험료 등 / 변동지출: 식비·교통비·여가 등")
        c1, c2, c3 = st.columns(3)
        fixed_expense    = c1.number_input("월 고정지출 (원)",
            min_value=0, value=900_000, step=50_000, format="%d")
        variable_expense = c2.number_input("월 변동지출 (원)",
            min_value=0, value=600_000, step=50_000, format="%d")
        housing = c3.selectbox("주거 형태", ["월세","전세","자가","부모님 거주","무주택"])

        st.markdown("**부채 정보**")
        debt_yn = st.selectbox("부채 여부", ["없음","있음"])
        debt_total, debt_rate = 0, 0.0
        if debt_yn == "있음":
            c1, c2 = st.columns(2)
            debt_total = c1.number_input("총 부채 금액 (원)",
                min_value=0, value=10_000_000, step=1_000_000, format="%d")
            debt_rate  = c2.number_input("연이자율 (%)", 0.0, 30.0, 4.5, step=0.1)

        st.markdown("**비상금 및 목표**")
        c1, c2, c3, c4 = st.columns(4)
        emergency_current = c1.number_input("현재 비상금 잔액 (원)",
            min_value=0, value=500_000, step=100_000, format="%d")
        isa_current_year  = c2.number_input("올해 ISA 납입액 (원)",
            min_value=0, value=0, step=100_000, format="%d")
        invest_years = c3.slider("투자 기간 (년)", 1, 30, 5)
        goal_3y      = c4.number_input("3년 목표 저축액 (원)",
            min_value=0, value=30_000_000, step=1_000_000, format="%d")

        submitted = st.form_submit_button("✅ 진단 시작",
            use_container_width=True, type="primary")

    if submitted:
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
        st.session_state.analysis_done     = False
        st.session_state.selected_portfolio= None
        st.session_state.chat_messages     = []
        st.session_state.briefing_done     = False

        total_exp_display  = fixed_expense + variable_expense
        emg_target_display = total_exp_display * 6
        if not emg_ok:
            st.warning(
                f"📌 비상금 목표: **{fmt(emg_target_display)}** "
                f"(월 생활비 {fmt(total_exp_display)} × 6개월)\n\n"
                f"현재 {fmt(emergency_current)} 보유 — 부족분 {fmt(emg_target_display - emergency_current)}"
            )
        st.success("✅ 입력 완료! '2️⃣ 자산 현황' 탭으로 이동해주세요.")
        st.balloons()


# ══════════════════════════════════════════════════════════════
#  PAGE 2 — 대시보드 (신호등 배너 추가)
# ══════════════════════════════════════════════════════════════
def page_dashboard():
    st.subheader("📊 자산 현황 대시보드")
    if not st.session_state.profile:
        st.warning("먼저 '1️⃣ 내 재무 진단' 탭에서 정보를 입력해주세요.")
        return

    # ── [신규] 매크로 신호등 배너 ──
    with st.spinner("거시 지표 수집 중..."):
        render_macro_signal_banner()

    p = st.session_state.profile
    months = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"]
    left, right = st.columns([1, 1.4], gap="large")

    with left:
        st.markdown("**💰 자산 입력**")
        st.caption("ISA 계좌 안에 담긴 ETF는 'ISA-ETF/주식'에 입력하세요.")
        with st.form("asset_form"):
            st.markdown("*절세 계좌*")
            c1, c2 = st.columns(2)
            isa_etf     = c1.number_input("ISA — ETF/주식 (원)", min_value=0, value=0, step=100_000, format="%d")
            isa_deposit = c2.number_input("ISA — 예적금/채권 (원)", min_value=0, value=0, step=100_000, format="%d")
            youth_sav   = st.number_input("청년미래적금 (원)", min_value=0, value=0, step=100_000, format="%d")

            st.markdown("*일반 계좌*")
            c1, c2 = st.columns(2)
            stock_gen   = c1.number_input("일반계좌 — 주식/ETF (원)", min_value=0, value=0, step=100_000, format="%d")
            savings_gen = c2.number_input("일반계좌 — 예적금 (원)", min_value=0, value=0, step=100_000, format="%d")
            emergency   = st.number_input("비상금 통장 (원)", min_value=0,
                value=int(p.get("emergency_current",0)), step=100_000, format="%d")

            st.markdown("**부채 정보**")
            debt_yn2    = st.selectbox("부채 여부", ["없음","있음"],
                index=1 if p.get("debt_total",0)>0 else 0, key="debt_yn2")
            debt_total2 = p.get("debt_total", 0)
            debt_rate2  = p.get("debt_rate", 0.0)
            if debt_yn2 == "있음":
                c1, c2 = st.columns(2)
                debt_total2 = c1.number_input("총 부채 금액 (원)", min_value=0,
                    value=int(p.get("debt_total",10_000_000)), step=1_000_000, format="%d", key="dt2")
                debt_rate2  = c2.number_input("연이자율 (%)", 0.0, 30.0,
                    float(p.get("debt_rate",4.5)), step=0.1, key="dr2")

            st.markdown("**📅 월별 예상 수입 (12개월)**")
            st.caption("성과급 달은 높게 입력하세요")
            income_list = []
            inc_cols = st.columns(4)
            for i, m in enumerate(months):
                default = p.get("monthly_income", 0)
                if p.get("bonus_yn") == "분기" and i % 3 == 2:
                    default += p.get("bonus_amt", 0)
                elif p.get("bonus_yn") == "반기" and i in [5,11]:
                    default += p.get("bonus_amt", 0)
                elif p.get("bonus_yn") == "연간" and i == 11:
                    default += p.get("bonus_amt", 0)
                v = inc_cols[i%4].number_input(m, min_value=0, value=int(default),
                    step=100_000, format="%d", key=f"inc_{i}")
                income_list.append(v)

            st.markdown("**📅 월별 예상 지출 (12개월)**")
            expense_list = []
            exp_cols = st.columns(4)
            total_exp_default = p.get("fixed_expense",0) + p.get("variable_expense",0)
            for i, m in enumerate(months):
                v = exp_cols[i%4].number_input(m, min_value=0,
                    value=int(total_exp_default), step=50_000, format="%d", key=f"exp_{i}")
                expense_list.append(v)

            submitted2 = st.form_submit_button("💾 저장 및 차트 업데이트", use_container_width=True)

        if submitted2:
            assets = {
                "ISA — ETF/주식": isa_etf, "ISA — 예적금/채권": isa_deposit,
                "청년미래적금": youth_sav, "일반 주식/ETF": stock_gen,
                "일반 예적금": savings_gen, "비상금 통장": emergency,
            }
            st.session_state.assets               = assets
            st.session_state.monthly_income_list  = income_list
            st.session_state.monthly_expense_list = expense_list
            p["debt_total"] = debt_total2
            p["debt_rate"]  = debt_rate2
            st.rerun()

    with right:
        assets     = st.session_state.assets
        debt_tot   = p.get("debt_total", 0)
        debt_rate2 = p.get("debt_rate", 0.0)
        total_assets = sum(assets.values()) if assets else 0
        net_worth    = total_assets - debt_tot

        if total_assets > 0:
            labels = [k for k,v in assets.items() if v>0]
            values = [v for v in assets.values() if v>0]
            colors = ["#3498DB","#2ECC71","#F1C40F","#E74C3C","#9B59B6","#1ABC9C"]
            fig = donut_chart(labels, values, title="자산 구성",
                colors=colors[:len(labels)], center_text=fmt(total_assets))
            st.plotly_chart(fig, use_container_width=True)

        if debt_tot > 0:
            fig2 = donut_chart(
                ["순자산","부채"], [max(net_worth,0), debt_tot],
                title="자본 vs 부채",
                colors=["#2ECC71","#E74C3C"],
                center_text=f"부채비율\n{debt_tot/total_assets*100:.0f}%" if total_assets else ""
            )
            st.plotly_chart(fig2, use_container_width=True)
            monthly_int = round(debt_tot * debt_rate2 / 100 / 12) if debt_tot > 0 else 0
            if monthly_int > 0:
                st.info(f"💸 월 이자 비용: **{fmt(monthly_int)}** (연 {debt_rate2}% / 연간 {fmt(monthly_int*12)})")

        inc_list = st.session_state.monthly_income_list
        exp_list = st.session_state.monthly_expense_list
        if any(v>0 for v in inc_list):
            sav_list  = [max(i-e,0) for i,e in zip(inc_list,exp_list)]
            rate_list = [s/i*100 if i>0 else 0 for s,i in zip(sav_list,inc_list)]
            fig3 = grouped_bar_line_chart(months, inc_list, exp_list, sav_list, rate_list)
            st.plotly_chart(fig3, use_container_width=True)
            avg_rate       = sum(rate_list)/len(rate_list)
            annual_savings = sum(sav_list)
            c1, c2 = st.columns(2)
            c1.metric("평균 저축률", f"{avg_rate:.1f}%")
            c2.metric("연간 예상 저축액", fmt(annual_savings))

        total_exp   = p.get("fixed_expense",0) + p.get("variable_expense",0)
        emg_target  = total_exp * 6
        emg_current = assets.get("비상금 통장", 0)
        emg_pct     = min(emg_current/emg_target*100, 100) if emg_target else 0
        st.markdown("**비상금 현황** (목표 = 월 총 생활비 × 6개월)")
        st.progress(int(emg_pct),
            text=f"목표 {fmt(emg_target)} 중 {fmt(emg_current)} 달성 ({emg_pct:.0f}%)")


# ══════════════════════════════════════════════════════════════
#  PAGE 3 — 추천 엔진 (기존 + 매크로 배너)
# ══════════════════════════════════════════════════════════════
def page_recommend():
    st.subheader("🎯 맞춤형 추천 엔진")
    if not st.session_state.profile:
        st.warning("먼저 '1️⃣ 내 재무 진단' 탭에서 정보를 입력해주세요.")
        return

    # ── [신규] 매크로 신호등 배너 ──
    with st.spinner("거시 지표 수집 중..."):
        render_macro_signal_banner()

    if st.button("🚀 분석 시작", type="primary", use_container_width=True):
        with st.spinner("분석 중..."):
            p       = st.session_state.profile
            matched = match_policies(p)
            split   = calc_account_split(p, matched)
            risk    = calc_risk_profile({**p, "emergency_ok": split["emergency_ok"]})
            st.session_state.matched_policies       = matched
            st.session_state.split_result           = split
            st.session_state.risk_profile           = risk
            st.session_state.analysis_done          = True
            st.session_state.portfolio_explanations = {}
        st.rerun()

    if not st.session_state.analysis_done:
        st.info("'분석 시작' 버튼을 눌러주세요.")
        return

    tab1, tab2, tab3 = st.tabs(["① 청년 정책 매칭","② 통장 쪼개기","③ 포트폴리오 추천"])

    with tab1:
        st.markdown("### 🏛️ 내가 받을 수 있는 청년 정책")
        eligible_count = 0
        for m in st.session_state.matched_policies:
            pol, eligible, conflict = m["policy"], m["eligible"], m.get("conflict",False)
            if eligible and not conflict:
                badge, color, border = "✅ 가입 가능","#d4edda","#28a745"
                eligible_count += 1
            elif conflict:
                badge, color, border = "⚠️ 중복 불가","#fff3cd","#ffc107"
            else:
                badge, color, border = "❌ 해당 없음","#f8d7da","#dc3545"

            conflict_note = "<br/><span style='font-size:0.8em;color:#856404'>⚠️ 청년미래적금 가입 시 중복 불가</span>" if conflict else ""
            policy_note   = f"<br/><span style='font-size:0.8em;color:#6c757d'>{pol['note']}</span>" if pol.get("note") else ""
            action_html   = f"<br/><span style='font-size:0.85em;color:#1a5276'>{pol.get('action','')}</span>" if eligible and not conflict and pol.get("action") else ""
            st.markdown(f"""
<div style='background:{color};border-left:4px solid {border};
     padding:12px 16px;border-radius:6px;margin-bottom:10px;'>
  <b>{pol['name']}</b> &nbsp; <span style='font-size:0.85em'>{badge}</span><br/>
  <span style='font-size:0.9em'>{pol['benefit']}</span>
  {conflict_note}{policy_note}{action_html}
</div>""", unsafe_allow_html=True)

        if eligible_count > 0:
            st.success(f"🎉 총 **{eligible_count}개** 정책에 가입 가능해요!")

    with tab2:
        st.markdown("### 💳 내 월급 쪼개기 플랜")
        split = st.session_state.split_result
        p     = st.session_state.profile

        if split.get("surplus_warning"):
            st.error(f"🚨 월 수입 {fmt(split['monthly_income'])}이 총 지출 {fmt(split['total_expense'])}보다 적어요.")
            return

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("월 수입",    fmt(split["monthly_income"]))
        c2.metric("월 총 지출", fmt(split["total_expense"]),
                  delta=f"고정 {fmt(split['fixed_expense'])} + 변동 {fmt(split['variable_expense'])}")
        c3.metric("월 여윳돈",  fmt(split["surplus"]))
        c4.metric("월 이자 비용", fmt(split.get("monthly_interest",0)) if split.get("monthly_interest",0)>0 else "없음")

        if split.get("fixed_warning"):
            st.warning(f"⚠️ 총 지출 비율 {split['fixed_ratio']*100:.0f}% — 60% 초과")
        if not split.get("emergency_ok"):
            st.warning(f"📌 비상금 목표 {fmt(split['emergency_target'])} 중 {fmt(p.get('emergency_current',0))} 보유. 부족분 {fmt(split['emergency_gap'])}")

        isa_rem = split.get("isa_remaining", ISA_ANNUAL_LIMIT)
        if isa_rem < ISA_ANNUAL_LIMIT:
            st.info(f"📋 ISA 올해 잔여 납입 한도: **{fmt(isa_rem)}**")

        alloc   = split.get("allocations", {})
        monthly = split.get("monthly_income", 1)
        all_labels = list(alloc.keys()) + ["고정지출","변동지출"]
        all_values = list(alloc.values()) + [split.get("fixed_expense",0), split.get("variable_expense",0)]
        nz = [(l,v) for l,v in zip(all_labels,all_values) if v>0]
        if nz:
            lbs, vls = zip(*nz)
            fig = donut_chart(list(lbs), list(vls), title="월급 쪼개기",
                colors=["#4C9BE8","#E74C3C","#F1C40F","#2ECC71","#9B59B6","#E67E22","#BDC3C7","#95A5A6"],
                center_text=fmt(monthly))
            st.plotly_chart(fig, use_container_width=True)

        rows = [{"항목":k,"금액":fmt(v),"비율":f"{v/monthly*100:.1f}%"} for k,v in alloc.items()]
        rows += [
            {"항목":"고정지출","금액":fmt(split.get("fixed_expense",0)),"비율":f"{split.get('fixed_expense',0)/monthly*100:.1f}%"},
            {"항목":"변동지출","금액":fmt(split.get("variable_expense",0)),"비율":f"{split.get('variable_expense',0)/monthly*100:.1f}%"},
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        dvi = calc_debt_vs_invest(p)
        if dvi:
            st.divider()
            st.markdown("#### ⚖️ 부채 상환 vs 투자, 뭐가 더 유리할까?")
            st.caption("₩100만원을 5년간 운용했을 때 비교")
            c1, c2 = st.columns(2)
            c1.metric("💰 부채 상환 시 이자 절감 (확정)", fmt(dvi["repay_gain"]),
                      delta=f"금리 {dvi['debt_rate']}% 확정 수익")
            c2.metric("📈 투자 시 기대 수익 (변동)", fmt(dvi["invest_gain"]),
                      delta=f"세후 기대수익률 {dvi['after_tax_return']:.1f}%")
            if dvi["prefer_repay"]:
                st.error(f"🏦 **상환 우선 권장** — 대출금리({dvi['debt_rate']}%)가 세후 투자 기대수익률({dvi['after_tax_return']:.1f}%)보다 높아요.")
            else:
                st.success(f"📊 **투자 병행 가능** — 세후 투자 기대수익률({dvi['after_tax_return']:.1f}%)이 대출금리({dvi['debt_rate']}%)보다 높아요.")

        if st.session_state.get("risk_profile"):
            goal_sim = calc_goal_simulation(p, split)
            st.divider()
            st.markdown("#### 🎯 3년 목표 달성 시뮬레이션")
            st.caption(f"월 투자액 {fmt(goal_sim['monthly_inv'])} 기준 복리 계산")
            for yr in goal_sim["yearly"]:
                st.write(f"**{yr['연도']}**: {fmt(yr['예상 자산'])}")
            if goal_sim["achievable"]:
                st.success(f"✅ 3년 후 예상 자산 {fmt(goal_sim['final_3y'])} — 목표 {fmt(goal_sim['goal_3y'])} 달성 가능!")
            else:
                st.warning(f"⚠️ 3년 후 예상 자산 {fmt(goal_sim['final_3y'])} — 목표까지 {fmt(goal_sim['shortfall'])} 부족.")

        if p.get("bonus_amt",0) > 0:
            emg_ok = split.get("emergency_ok")
            st.info(f"💡 **성과급 {fmt(p['bonus_amt'])} 처리 방법**\n\n"
                + ("➡️ 비상금 부족 → **전액 비상금 통장** 입금"
                   if not emg_ok
                   else f"➡️ 비상금 충족! **{fmt(int(p['bonus_amt']*0.7))} 투자** + **{fmt(int(p['bonus_amt']*0.3))} 자유**"))

    with tab3:
        st.markdown("### 📈 나에게 맞는 포트폴리오 후보")
        risk   = st.session_state.get("risk_profile","C")
        orders = {"A":{"A":0,"C":1,"B":2},"B":{"B":0,"C":1,"A":2},"C":{"C":0,"A":1,"B":2}}
        sorted_keys = sorted(PORTFOLIOS.keys(), key=lambda k: orders[risk][k])

        for key in sorted_keys:
            port   = PORTFOLIOS[key]
            is_rec = key == risk
            with st.expander(
                f"{port['emoji']} **{port['name']}** ({port['type']})"
                + (" ⭐ 추천" if is_rec else ""), expanded=is_rec
            ):
                c1, c2 = st.columns(2)
                c1.metric("연 기대수익률 E(R)", f"{port['expected_return']*100:.1f}%")
                c2.metric("예상 변동성 σ", f"±{port['expected_risk']*100:.0f}%")

                labels = [a["name"] for a in port["assets"]]
                ratios = [a["ratio"] for a in port["assets"]]
                fig = go.Figure(go.Pie(
                    labels=labels, values=ratios, hole=0.6,
                    textinfo="label+percent", textposition="outside",
                    marker_colors=port["colors"],
                ))
                fig.update_layout(showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=-0.35),
                    margin=dict(t=10, b=70, l=10, r=10), height=300)
                st.plotly_chart(fig, use_container_width=True)
                st.caption(f"📚 근거: {port['basis']}")

                realtime_key = f"realtime_{key}"
                if realtime_key not in st.session_state:
                    st.session_state[realtime_key] = None

                if st.button("🔴 실시간 ETF 데이터 불러오기", key=f"fetch_{key}"):
                    with st.spinner("실시간 데이터 수집 중..."):
                        st.session_state[realtime_key] = fetch_etf_data(key)

                rd = st.session_state.get(realtime_key)
                if rd:
                    if rd.get("success"):
                        st.markdown("**📡 실시간 ETF 데이터**")
                        st.caption(f"기준일: {rd.get('fetch_time','—')} | 출처: Yahoo Finance")
                        rows = []
                        for a in rd["assets"]:
                            rows.append({
                                "ETF": a["name"], "비중": f"{a['ratio']}%",
                                "현재가": f"₩{a['price']:,}" if a["price"] else "—",
                                "1년 수익률": f"{a['return_1y']:+.1f}%" if a["return_1y"] is not None else "—",
                                "배당 수익률": f"{a['div_yield']:.1f}%" if a["div_yield"] is not None else "—",
                                "상태": a["status"],
                            })
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                        w_ret = rd["weighted_return"]
                        w_div = rd["weighted_div"]
                        rc1, rc2, rc3 = st.columns(3)
                        rc1.metric("포트폴리오 가중 평균 1년 수익률", f"{w_ret:+.1f}%",
                                   delta=f"기존 추정 {port['expected_return']*100:.1f}% 대비 {w_ret - port['expected_return']*100:+.1f}%p")
                        rc2.metric("가중 평균 배당 수익률", f"{w_div:.1f}%")
                        rc3.metric("데이터 기반 위험 조정 후",
                                   "실제 데이터 반영됨" if w_ret != 0 else "데이터 부족")
                        if w_ret > 0:
                            st.success(f"📊 실제 1년 수익률 기준 가중 평균 수익률은 **{w_ret:+.1f}%** 예요.")
                        elif w_ret < -5:
                            st.warning(f"⚠️ 최근 1년 수익률이 **{w_ret:.1f}%** 로 부진해요.")
                    else:
                        st.error(f"데이터 수집 실패: {rd.get('error','알 수 없는 오류')}")

                if key not in st.session_state.portfolio_explanations:
                    with st.spinner(f"{port['name']} AI 분석 중..."):
                        exp = get_gemini_portfolio_explanation(st.session_state.profile, key)
                        st.session_state.portfolio_explanations[key] = exp

                exp = st.session_state.portfolio_explanations.get(key, {})
                st.success(f"✅ {exp.get('fit_reason','')}")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**👍 장점**")
                    for pro in exp.get("pros",[]): st.markdown(f"• {pro}")
                with c2:
                    st.markdown("**⚠️ 주의사항**")
                    for con in exp.get("cons",[]): st.markdown(f"• {con}")

                if st.button("이 포트폴리오 선택하기", key=f"sel_{key}", type="primary"):
                    st.session_state.selected_portfolio = key
                    st.rerun()

        if st.session_state.selected_portfolio:
            sel  = st.session_state.selected_portfolio
            port = PORTFOLIOS[sel]
            st.divider()
            st.markdown("### 📋 내 포트폴리오 계좌 배치 가이드")
            st.caption(f"선택: {port['emoji']} {port['name']}")
            df = pd.DataFrame(PORTFOLIO_ISA_MAP[sel])[["name","account","reason"]]
            df.columns = ["자산","담을 계좌","이유"]
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.info("💡 ISA 연간 납입 한도 ₩20,000,000 초과분은 일반 계좌를 활용하세요.")


# ══════════════════════════════════════════════════════════════
#  PAGE 4 — AI 매크로 상담 챗봇  ★ 핵심 업그레이드 ★
# ══════════════════════════════════════════════════════════════
def page_chatbot():
    st.subheader("💬 AI 매크로 방어 분석가")
    if not st.session_state.profile:
        st.warning("먼저 '1️⃣ 내 재무 진단' 탭에서 정보를 입력해주세요.")
        return

    port_name = PORTFOLIOS[st.session_state.selected_portfolio]["name"] \
                if st.session_state.selected_portfolio else "미선택"
    st.caption(f"분석 기준: 월수입 {fmt(st.session_state.profile.get('monthly_income',0))} | 포트폴리오: {port_name}")

    # ── [신규] 매크로 신호등 배너 ──
    macro_data = st.session_state.get("macro_cache")
    if not macro_data:
        with st.spinner("거시 지표 수집 중..."):
            macro_data = render_macro_signal_banner()
    else:
        render_macro_signal_banner()

    # ── [신규] 선제적 브리핑 ──
    if not st.session_state.briefing_done and not st.session_state.chat_messages:
        with st.spinner("에이전트 브리핑 생성 중..."):
            briefing = generate_proactive_briefing(macro_data or {})
            st.session_state.agent_briefing = briefing

        p       = st.session_state.profile
        split   = st.session_state.split_result
        emg_ok  = split.get("emergency_ok", p.get("emergency_ok", False))
        surplus = split.get("surplus", 0)

        # 에이전트 첫 메시지 = 선제적 브리핑 + 기존 인트로
        intro_parts = [
            "안녕하세요! **SafeFolio AI 매크로 방어 분석가**입니다. 🛡️",
            "",
        ]
        if briefing:
            intro_parts += [
                "---",
                f"📡 **오늘의 매크로 브리핑**",
                f"{briefing.get('issue','')}",
                "",
                f"💬 {briefing.get('question','')}",
                "---",
                "",
            ]
        intro_parts += [
            f"월 수입 **{fmt(p.get('monthly_income',0))}** 기준으로 분석했어요.",
            f"- 월 여윳돈: **{fmt(surplus)}**",
            f"- 비상금: {'✅ 목표 달성' if emg_ok else ('⚠️ ' + fmt(split.get('emergency_gap',0)) + ' 부족')}",
            "",
            "📌 물가·금리·연준 동향부터 포트폴리오 방어력까지 — 거시 데이터 기반으로 분석해드립니다.",
            "궁금한 점을 질문해보세요!",
        ]
        st.session_state.chat_messages = [{"role":"assistant","content":"\n".join(intro_parts)}]
        st.session_state.briefing_done = True

    # ── 인디케이터 미니 대시보드 ──
    inds = (macro_data or {}).get("indicators", {})
    if inds:
        st.markdown("**📊 실시간 거시 지표 (에이전트 자동 수집)**")
        ind_items = [
            ("^VIX",    "🌡️ VIX",   ""),
            ("^TNX",    "📈 10년금리","%" ),
            ("^GSPC",   "🏛️ S&P500", ""),
            ("CPI_LAST","🛒 CPI",    "%"),
            ("FED_RATE","🏦 기준금리","%"),
        ]
        cols = st.columns(len(ind_items))
        for col, (sym, label, suffix) in zip(cols, ind_items):
            d = inds.get(sym, {})
            if d:
                val = d.get("current","—")
                pct = d.get("pct_change", 0)
                delta_cls = "ic-up" if pct > 0 else ("ic-down" if pct < 0 else "ic-neu")
                arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "—")
                col.markdown(f"""
<div class="indicator-card">
  <div class="ic-label">{label}</div>
  <div class="ic-value">{val}{suffix}</div>
  <div class="ic-delta {delta_cls}">{arrow} {abs(pct):.1f}%</div>
</div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── [신규] 방어력 분석 패널 ──
    with st.expander("🛡️ 금리 급등기 방어력 분석 (클릭하여 펼치기)", expanded=False):
        if st.button("⚡ 방어력 데이터 불러오기", key="defense_btn"):
            with st.spinner("과거 방어력 데이터 수집 중..."):
                defense = analyze_defensive_impact()
                st.session_state["defense_data"] = defense

        defense = st.session_state.get("defense_data")
        if defense:
            st.caption(f"분석 구간: {defense.get('period','')}")
            st.caption(f"시나리오: {defense.get('scenario','')}")

            d_data = defense.get("data", {})
            if d_data:
                names  = [v["label"]       for v in d_data.values()]
                rets   = [v["return_pct"]   for v in d_data.values() if "return_pct" in v]
                colors = ["#4ade80" if r > -5 else ("#fbbf24" if r > -15 else "#f87171") for r in rets]

                fig_d = go.Figure(go.Bar(
                    x=names, y=rets, marker_color=colors,
                    text=[f"{r:+.1f}%" for r in rets],
                    textposition="outside",
                ))
                fig_d.update_layout(
                    title="자산별 방어력 비교 (금리 급등기)",
                    yaxis_title="수익률 (%)",
                    height=320,
                    margin=dict(t=40,b=40,l=20,r=20),
                    showlegend=False,
                )
                st.plotly_chart(fig_d, use_container_width=True)

                best = min(d_data.values(), key=lambda x: abs(x.get("return_pct",0)))
                st.success(f"✅ **가장 방어적이었던 자산**: {best['label']} ({best.get('return_pct',0):+.1f}%)")
        else:
            st.info("위 버튼을 눌러 금리 급등기 방어력 데이터를 불러오세요.")

    st.markdown("---")

    # ── 채팅 UI ──
    chat_box = st.container(height=420)
    with chat_box:
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # ── 빠른 질문 버튼 (선제적 UX) ──
    st.markdown("**⚡ 빠른 질문**")
    quick_cols = st.columns(4)
    quick_questions = [
        "현재 VIX 수준이 내 포트폴리오에 미치는 영향은?",
        "연준 금리 동결이 배당 ETF에 좋은가요?",
        "인플레이션이 재가속되면 어떻게 해야 하나요?",
        "지금 시장에서 하방 방어가 되는 자산은?",
    ]
    for col, q in zip(quick_cols, quick_questions):
        if col.button(q, key=f"quick_{q[:10]}", use_container_width=True):
            st.session_state._quick_question = q
            st.rerun()

    # 빠른 질문 처리
    if hasattr(st.session_state, "_quick_question") and st.session_state._quick_question:
        prompt = st.session_state._quick_question
        st.session_state._quick_question = None
        st.session_state.chat_messages.append({"role":"user","content":prompt})
        wf_ph = st.empty()
        with st.spinner("에이전트 분석 중..."):
            reply = agent_run(
                user_message=prompt,
                profile=st.session_state.profile,
                split_result=st.session_state.split_result,
                selected_portfolio=st.session_state.selected_portfolio or "C",
                workflow_placeholder=wf_ph,
            )
        st.session_state.chat_messages.append({"role":"assistant","content":reply})
        st.rerun()

    # ── 일반 질문 입력 ──
    if prompt := st.chat_input("거시 경제·포트폴리오 방어 전략을 질문해보세요 (예: VIX가 30 넘으면 어떻게 해야 해요?)"):
        st.session_state.chat_messages.append({"role":"user","content":prompt})
        wf_ph = st.empty()
        with st.spinner("에이전트 분석 중..."):
            reply = agent_run(
                user_message=prompt,
                profile=st.session_state.profile,
                split_result=st.session_state.split_result,
                selected_portfolio=st.session_state.selected_portfolio or "C",
                workflow_placeholder=wf_ph,
            )
        st.session_state.chat_messages.append({"role":"assistant","content":reply})
        st.rerun()


# ══════════════════════════════════════════════════════════════
#  메인 라우터
# ══════════════════════════════════════════════════════════════
nav()
{
    "onboarding": page_onboarding,
    "dashboard":  page_dashboard,
    "recommend":  page_recommend,
    "chatbot":    page_chatbot,
}[st.session_state.page]()

st.divider()
st.caption("⚠️ 본 서비스는 교육 목적이며 투자 권유가 아닙니다. 실제 투자 결정 전 전문가와 상담하세요.")
