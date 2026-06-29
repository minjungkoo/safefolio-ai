import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="SafeFolio AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ──────────────────────────────────────────────
# 전역 상수
# ──────────────────────────────────────────────
DIVIDEND_TAX = 0.154
CAPITAL_GAIN_TAX_NORMAL = 0.22
CAPITAL_GAIN_TAX_ISA = 0.099
ISA_EXEMPTION_GENERAL = 2_000_000
ISA_EXEMPTION_YOUTH = 4_000_000

def fmt(n):
    """원화 3자리 쉼표 포맷"""
    return f"₩{int(n):,}"

# ──────────────────────────────────────────────
# 청년 정책 하드코딩 데이터
# ──────────────────────────────────────────────
POLICIES = [
    {
        "id": "youth_savings",
        "name": "청년미래적금",
        "conditions": {
            "age_min": 19, "age_max": 34,
            "income_max_general": 60_000_000,
            "income_max_priority": 36_000_000,
            "job_types": ["정규직", "계약직", "프리랜서"],
        },
        "benefit": "월 최대 ₩500,000 납입, 만기 3년, 정부 기여금 6~12%, 비과세",
        "monthly_amount": 500_000,
        "conflicts": ["youth_isa"],
        "note": None,
    },
    {
        "id": "isa_general",
        "name": "중개형 ISA",
        "conditions": {
            "age_min": 19, "age_max": 99,
            "income_max_general": None,
            "job_types": ["정규직", "계약직", "프리랜서", "무직"],
        },
        "benefit": "연 ₩2,000만원 납입, 비과세 ₩200만원(서민형 ₩400만원), 초과분 9.9% 분리과세",
        "monthly_amount": None,
        "conflicts": [],
        "note": None,
    },
    {
        "id": "youth_isa",
        "name": "청년형 ISA",
        "conditions": {
            "age_min": 19, "age_max": 34,
            "income_max_general": 75_000_000,
            "job_types": ["정규직", "계약직"],
        },
        "benefit": "비과세 한도 ₩400만원, 납입금 소득공제 혜택",
        "monthly_amount": None,
        "conflicts": ["youth_savings"],
        "note": "⚠️ 2026년 7월 세제개편안 확정 전, 세부 수치 변동 가능",
    },
    {
        "id": "youth_jeonse",
        "name": "청년버팀목 전세대출",
        "conditions": {
            "age_min": 19, "age_max": 34,
            "income_max_general": 50_000_000,
            "asset_max": 337_000_000,
            "housing": "무주택",
        },
        "benefit": "최대 ₩1억5천만원, 금리 연 1.3~4.3%, 전세보증금 ₩3억 이하 85㎡ 이하",
        "monthly_amount": None,
        "conflicts": [],
        "note": "병역 이행 시 최대 만 39세까지 가능",
    },
]

ISA_PRIORITY = [
    {"asset": "해외주식형 ETF (S&P500 등)", "rank": 1, "account": "ISA 우선", "reason": "배당세 15.4% + 양도세 22% 동시 절세 효과 최대"},
    {"asset": "고배당 ETF", "rank": 2, "account": "ISA 우선", "reason": "배당세 15.4% Tax Drag 매년 제거, 복리 효과 극대화"},
    {"asset": "채권형 ETF", "rank": 3, "account": "ISA 권장", "reason": "이자소득세 15.4% 절세"},
    {"asset": "단기채 / 예적금", "rank": 4, "account": "일반 계좌 가능", "reason": "세금 부담 적고 유동성 필요 자산"},
    {"asset": "원자재 ETF", "rank": 5, "account": "일반 계좌 권장", "reason": "변동성 높아 ISA 비과세 한도 낭비 우려"},
]

PORTFOLIO_ISA_MAP = {
    "A": [
        {"name": "TIGER 미국S&P500", "account": "ISA ★1순위", "reason": "배당세+양도세 모두 절세"},
        {"name": "KODEX 단기채권 / 비상금 통장", "account": "일반 계좌", "reason": "유동성 필요, 세금 적음"},
    ],
    "B": [
        {"name": "ACE 미국30년국채액티브", "account": "ISA ★1순위", "reason": "이자소득세 15.4% 절세"},
        {"name": "TIGER 미국S&P500",       "account": "ISA ★2순위", "reason": "배당세+양도세 절세"},
        {"name": "TIGER 미국채10년선물",    "account": "ISA ★3순위", "reason": "이자소득세 절세"},
        {"name": "ACE KRX금현물",           "account": "일반 계좌", "reason": "매매차익 비과세(금 현물)"},
        {"name": "KODEX 미국S&P원자재",     "account": "일반 계좌", "reason": "변동성 커서 ISA 비추"},
    ],
    "C": [
        {"name": "TIGER 미국S&P500",       "account": "ISA ★1순위", "reason": "배당세+양도세 모두 절세"},
        {"name": "ACE 미국배당다우존스",     "account": "ISA ★2순위", "reason": "배당세 15.4% 매년 절세"},
        {"name": "KODEX 단기채권",          "account": "일반 계좌", "reason": "유동성 필요, 세금 적음"},
    ],
}

PORTFOLIOS = {
    "A": {
        "name": "버핏식 단순 인덱스", "type": "공격형", "color": "#E74C3C", "emoji": "🚀",
        "basis": "워런 버핏 — S&P500 90% + 단기채 10%",
        "assets": [
            {"name": "TIGER 미국S&P500", "ratio": 90, "category": "해외주식형 ETF"},
            {"name": "KODEX 단기채권",    "ratio": 10, "category": "단기채"},
        ],
    },
    "B": {
        "name": "올웨더 포트폴리오", "type": "안정형", "color": "#2ECC71", "emoji": "🌤️",
        "basis": "레이 달리오 — 주식 30% + 채권 55% + 실물자산 15%",
        "assets": [
            {"name": "TIGER 미국S&P500",       "ratio": 30, "category": "해외주식형 ETF"},
            {"name": "ACE 미국30년국채액티브",   "ratio": 40, "category": "채권형 ETF"},
            {"name": "TIGER 미국채10년선물",     "ratio": 15, "category": "채권형 ETF"},
            {"name": "ACE KRX금현물",           "ratio":  8, "category": "원자재 ETF"},
            {"name": "KODEX 미국S&P원자재",      "ratio":  7, "category": "원자재 ETF"},
        ],
    },
    "C": {
        "name": "코어-위성 전략", "type": "균형형", "color": "#3498DB", "emoji": "⚖️",
        "basis": "핵심-위성 전략 — S&P500 50% + 고배당 30% + 단기채 20%",
        "assets": [
            {"name": "TIGER 미국S&P500",    "ratio": 50, "category": "해외주식형 ETF"},
            {"name": "ACE 미국배당다우존스", "ratio": 30, "category": "고배당 ETF"},
            {"name": "KODEX 단기채권",       "ratio": 20, "category": "단기채"},
        ],
    },
}

# ──────────────────────────────────────────────
# 핵심 알고리즘
# ──────────────────────────────────────────────
def match_policies(profile: dict) -> list:
    age = profile.get("age", 30)
    income = profile.get("annual_income", 0)
    job = profile.get("job_type", "정규직")
    housing = profile.get("housing", "월세")
    assets = profile.get("total_assets", 0)
    matched = []

    for p in POLICIES:
        c = p["conditions"]
        ok = True
        if age < c.get("age_min", 0) or age > c.get("age_max", 99): ok = False
        if c.get("income_max_general") and income > c["income_max_general"]: ok = False
        if "job_types" in c and job not in c["job_types"]: ok = False
        if c.get("housing") and housing != "무주택": ok = False
        if c.get("asset_max") and assets > c["asset_max"]: ok = False
        matched.append({"policy": p, "eligible": ok})

    youth_savings_ok = any(m["eligible"] and m["policy"]["id"] == "youth_savings" for m in matched)
    for m in matched:
        if youth_savings_ok and m["policy"]["id"] == "youth_isa":
            m["conflict"] = True
        else:
            m["conflict"] = False

    return matched

def calc_risk_profile(profile: dict) -> str:
    age, debt_rate, emergency_ok, invest_years = profile.get("age", 30), profile.get("debt_rate", 0), profile.get("emergency_ok", False), profile.get("invest_years", 5)
    score = 0
    if age <= 30: score += 2
    elif age <= 35: score += 1
    if debt_rate < 5: score += 2
    elif debt_rate < 8: score += 1
    if emergency_ok: score += 2
    if invest_years >= 7: score += 2
    elif invest_years >= 4: score += 1

    if score >= 7: return "A"
    elif score >= 4: return "C"
    else: return "B"

def calc_account_split(profile: dict, matched_policies: list) -> dict:
    monthly_income = profile.get("monthly_income", 0)
    fixed_expense = profile.get("fixed_expense", 0)
    emergency_current = profile.get("emergency_current", 0)
    debt_rate = profile.get("debt_rate", 0)
    debt_total = profile.get("debt_total", 0)

    result = {}
    result["fixed_ratio"] = fixed_expense / monthly_income if monthly_income > 0 else 0
    result["fixed_warning"] = result["fixed_ratio"] > 0.5
    
    emergency_target = fixed_expense * 6
    emergency_gap = max(0, emergency_target - emergency_current)
    emergency_ok = emergency_gap == 0
    result["emergency_target"] = emergency_target
    result["emergency_gap"] = emergency_gap
    result["emergency_ok"] = emergency_ok
    
    debt_priority = debt_rate >= 5.0
    result["debt_priority"] = debt_priority

    youth_savings_ok = any(m["eligible"] and not m.get("conflict") and m["policy"]["id"] == "youth_savings" for m in matched_policies)
    youth_savings_amount = 500_000 if youth_savings_ok else 0

    remaining = monthly_income - fixed_expense
    allocations = {}

    if not emergency_ok:
        emg_alloc = min(remaining * 0.20, emergency_gap / 12)
        allocations["비상금 통장"] = round(emg_alloc)
        remaining -= emg_alloc
    else:
        allocations["비상금 통장"] = round(monthly_income * 0.05)
        remaining -= allocations["비상금 통장"]

    if debt_priority and debt_total > 0:
        debt_alloc = remaining * 0.30
        allocations["부채 상환"] = round(debt_alloc)
        remaining -= debt_alloc

    if youth_savings_ok and remaining >= youth_savings_amount:
        allocations["청년미래적금"] = youth_savings_amount
        remaining -= youth_savings_amount

    invest_alloc = remaining * 0.60
    allocations["ISA / 투자"] = round(invest_alloc)
    remaining -= invest_alloc
    allocations["자유 지출"] = max(0, round(remaining))

    result["allocations"] = allocations
    result["monthly_income"] = monthly_income
    result["fixed_expense"] = fixed_expense
    return result

def get_gemini_portfolio_explanation(profile: dict, portfolio_key: str) -> dict:
    try:
        import google.generativeai as genai
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-1.5-flash-latest")

        p = PORTFOLIOS[portfolio_key]
        assets_str = ", ".join([f"{a['name']} {a['ratio']}%" for a in p["assets"]])

        prompt = f"""
다음 JSON 형식으로만 답해줘. 마크다운 코드블록 없이 순수 JSON만.

사용자 프로필:
- 나이: {profile.get('age')}세
- 월 수입: {fmt(profile.get('monthly_income', 0))}
- 부채 여부: {'있음 (금리 ' + str(profile.get('debt_rate', 0)) + '%)' if profile.get('debt_total', 0) > 0 else '없음'}
- 비상금 충족: {'예' if profile.get('emergency_ok') else '아니오'}
- 투자 기간: {profile.get('invest_years', 5)}년

추천 포트폴리오: {p['name']} ({p['type']})
자산 구성: {assets_str}
근거: {p['basis']}

[중요 지시사항]
각 포트폴리오(공격형, 안정형, 균형형)의 철학과 구성이 뚜렷하게 다르므로, 위 포트폴리오만의 '가장 차별화된 고유의 장단점'을 반드시 강조해주세요. 평범한 분산투자 장점은 지양하세요.

{{
  "fit_reason": "이런 분께 맞아요 — 위 사용자 프로필을 반영한 1문장 (50자 이내)",
  "pros": ["이 포트폴리오만의 고유한 장점 1 (30자 이내)", "이 포트폴리오만의 고유한 장점 2 (30자 이내)"],
  "cons": ["이 포트폴리오만의 치명적 단점/주의사항 1 (30자 이내)", "이 포트폴리오만의 단점/주의사항 2 (30자 이내)"]
}}
"""
        response = model.generate_content(prompt)
        text = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        return {
            "fit_reason": f"{PORTFOLIOS[portfolio_key]['type']} 투자자에게 적합한 포트폴리오예요.",
            "pros": ["장기 분산 투자 효과", "검증된 거장의 전략 기반"],
            "cons": ["시장 상황에 따라 수익률 변동 가능", "정기 리밸런싱 필요"],
        }

def get_gemini_chat_response(messages: list, profile: dict, split_result: dict, selected_portfolio: str) -> str:
    try:
        import google.generativeai as genai
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-1.5-flash-latest")

        alloc = split_result.get("allocations", {})
        alloc_str = "\n".join([f"  - {k}: {fmt(v)}" for k, v in alloc.items()])
        port = PORTFOLIOS.get(selected_portfolio, {})
        port_name = port.get("name", "미선택")

        system = f"""당신은 한국 사회초년생을 위한 자산 관리 AI 비서 'SafeFolio AI'입니다.
아래는 현재 사용자의 재무 현황과 분석 결과입니다. 이를 바탕으로 질문에 답해주세요.

[사용자 프로필]
- 나이: {profile.get('age')}세 / 직업: {profile.get('job_type')}
- 월 수입: {fmt(profile.get('monthly_income', 0))} / 월 고정지출: {fmt(profile.get('fixed_expense', 0))}
- 부채: {'있음 (' + fmt(profile.get('debt_total', 0)) + ', 금리 ' + str(profile.get('debt_rate', 0)) + '%)' if profile.get('debt_total', 0) > 0 else '없음'}
- 현재 비상금: {fmt(profile.get('emergency_current', 0))} / 목표: {fmt(split_result.get('emergency_target', 0))}

[통장 쪼개기 결과]
{alloc_str}

[선택한 포트폴리오]
{port_name} ({port.get('type', '')})

[답변 원칙]
1. 2026년 한국 세법 기준으로 정확하게 답변하세요.
2. 위 수치를 적극 활용해 구체적으로 설명하세요.
3. 사회초년생 눈높이로 쉽게 설명하세요.
4. 투자 권유가 아닌 교육·정보 제공임을 명심하세요.
5. 간결하게 핵심만 답변하세요.
"""
        gemini_history = []
        for m in messages[1:-1]:
            role = "user" if m["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [m["content"]]})

        chat = model.start_chat(history=gemini_history)
        user_msg = messages[-1]["content"]
        full_msg = f"{system}\n\n사용자 질문: {user_msg}" if not gemini_history else user_msg
        return chat.send_message(full_msg).text
    except Exception as e:
        return f"⚠️ API 오류: {str(e)}"

# ──────────────────────────────────────────────
# session_state 초기화
# ──────────────────────────────────────────────
def init_state():
    defaults = {
        "page": "onboarding", "profile": {}, "assets": {},
        "monthly_income_list": [0] * 12, "monthly_expense_list": [0] * 12,
        "matched_policies": [], "split_result": {}, "selected_portfolio": None,
        "portfolio_explanations": {}, "analysis_done": False, "chat_messages": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
init_state()

# ──────────────────────────────────────────────
# 네비게이션
# ──────────────────────────────────────────────
def nav():
    pages = {"onboarding": "1️⃣ 내 재무 진단", "dashboard": "2️⃣ 자산 현황", "recommend": "3️⃣ 맞춤 추천", "chatbot": "4️⃣ AI 상담"}
    cols = st.columns(len(pages))
    for col, (key, label) in zip(cols, pages.items()):
        if col.button(label, use_container_width=True, type="primary" if st.session_state.page == key else "secondary"):
            st.session_state.page = key
            st.rerun()
    st.divider()

# ──────────────────────────────────────────────
# 페이지 1, 3, 4, 2 라우팅
# ──────────────────────────────────────────────
def page_onboarding():
    st.title("🛡️ SafeFolio AI")
    st.subheader("내 재무 상태를 알려주세요")
    
    with st.form("onboarding_form"):
        st.markdown("**기본 정보**")
        c1, c2, c3 = st.columns(3)
        age = c1.number_input("나이", 19, 65, 27, step=1)
        gender = c2.selectbox("성별", ["남성", "여성", "선택 안 함"])
        job_type = c3.selectbox("직업 형태", ["정규직", "계약직", "프리랜서", "무직"])

        st.markdown("**소득 정보**")
        c1, c2 = st.columns(2)
        monthly_income = c1.number_input("월 세후 수입 (원)", 0, 20_000_000, 3_000_000, step=100_000, format="%d")
        bonus_yn = c2.selectbox("성과급/상여금 여부", ["없음", "분기", "반기", "연간"])
        bonus_amt = st.number_input("예상 성과급 (1회 금액, 원)", 0, 50_000_000, 3_000_000, step=500_000, format="%d") if bonus_yn != "없음" else 0

        st.markdown("**지출 및 주거**")
        c1, c2 = st.columns(2)
        fixed_expense = c1.number_input("월 고정지출 합산 (원)", 0, 10_000_000, 1_200_000, step=100_000, format="%d")
        housing = c2.selectbox("주거 형태", ["월세", "전세", "자가", "부모님 거주", "무주택"])

        st.markdown("**부채 정보**")
        debt_yn = st.selectbox("부채 여부", ["없음", "있음"])
        debt_total, debt_rate = 0, 0.0
        if debt_yn == "있음":
            c1, c2 = st.columns(2)
            debt_total = c1.number_input("총 부채 금액 (원)", 0, 500_000_000, 10_000_000, step=1_000_000, format="%d")
            debt_rate = c2.number_input("대출 금리 (%)", 0.0, 30.0, 4.5, step=0.1)

        st.markdown("**현재 비상금 및 목표**")
        c1, c2, c3 = st.columns(3)
        emergency_current = c1.number_input("현재 비상금 잔액 (원)", 0, 100_000_000, 500_000, step=100_000, format="%d")
        invest_years = c2.slider("투자 기간 (년)", 1, 30, 5)
        goal_3y = c3.number_input("3년 목표 저축액 (원)", 0, 200_000_000, 30_000_000, step=1_000_000, format="%d")

        if st.form_submit_button("✅ 진단 시작", use_container_width=True, type="primary"):
            annual_income = monthly_income * 12 + (bonus_amt * {"없음": 0, "분기": 4, "반기": 2, "연간": 1}[bonus_yn])
            st.session_state.profile = {
                "age": age, "gender": gender, "job_type": job_type,
                "monthly_income": monthly_income, "annual_income": annual_income,
                "bonus_yn": bonus_yn, "bonus_amt": bonus_amt,
                "fixed_expense": fixed_expense, "housing": housing,
                "debt_total": debt_total, "debt_rate": debt_rate,
                "emergency_current": emergency_current, "emergency_ok": emergency_current >= fixed_expense * 6,
                "invest_years": invest_years, "goal_3y": goal_3y,
            }
            st.session_state.analysis_done = False
            st.session_state.selected_portfolio = None
            st.success("✅ 입력 완료! '2️⃣ 자산 현황' 탭으로 이동해주세요.")
            st.balloons()

def page_dashboard():
    st.subheader("📊 자산 현황 대시보드")
    if not st.session_state.profile:
        st.warning("먼저 '1️⃣ 내 재무 진단' 탭에서 정보를 입력해주세요.")
        return

    p = st.session_state.profile
    left, right = st.columns([1, 1.4], gap="large")

    with left:
        with st.form("asset_form"):
            st.markdown("**💰 자산 입력 (계좌별)**")
            isa_account = st.number_input("ISA 계좌 (원)", 0, None, 0, step=100_000, format="%d")
            general_stock = st.number_input("일반 주식/ETF (원)", 0, None, 0, step=100_000, format="%d")
            savings_acc = st.number_input("예적금/청년적금 등 (원)", 0, None, 0, step=100_000, format="%d")
            emergency_acc = st.number_input("비상금 통장 (원)", 0, None, int(p.get("emergency_current", 0)), step=100_000, format="%d")
            
            st.markdown("**💸 부채 입력**")
            c1, c2 = st.columns(2)
            dash_debt_total = c1.number_input("총 부채 금액 (원)", 0, None, int(p.get("debt_total", 0)), step=1_000_000, format="%d")
            dash_debt_rate = c2.number_input("대출 금리 (%)", 0.0, 100.0, float(p.get("debt_rate", 0.0)), step=0.1)

            st.markdown("**📅 월별 예상 수입·지출 (12개월)**")
            months = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"]
            inc_cols = st.columns(4)
            exp_cols = st.columns(4)
            income_list, expense_list = [], []
            for i, m in enumerate(months):
                default_inc = p.get("monthly_income", 0)
                if p.get("bonus_yn") == "분기" and i % 3 == 2: default_inc += p.get("bonus_amt", 0)
                elif p.get("bonus_yn") == "반기" and i in [5, 11]: default_inc += p.get("bonus_amt", 0)
                elif p.get("bonus_yn") == "연간" and i == 11: default_inc += p.get("bonus_amt", 0)
                
                v_inc = inc_cols[i % 4].number_input(f"{m} 수입", 0, None, int(default_inc), step=100_000, format="%d", key=f"inc_{i}")
                v_exp = exp_cols[i % 4].number_input(f"{m} 지출", 0, None, int(p.get("fixed_expense", 0)), step=100_000, format="%d", key=f"exp_{i}")
                income_list.append(v_inc)
                expense_list.append(v_exp)

            if st.form_submit_button("📊 대시보드 업데이트", use_container_width=True, type="primary"):
                st.session_state.assets = {
                    "ISA 계좌": isa_account, "일반 주식/ETF": general_stock,
                    "예적금": savings_acc, "비상금": emergency_acc
                }
                st.session_state.monthly_income_list = income_list
                st.session_state.monthly_expense_list = expense_list
                st.session_state.profile.update({
                    "emergency_current": emergency_acc,
                    "emergency_ok": emergency_acc >= p.get("fixed_expense", 0) * 6,
                    "debt_total": dash_debt_total,
                    "debt_rate": dash_debt_rate
                })
                st.rerun()

    with right:
        assets = st.session_state.assets
        if not assets:
            st.info("좌측에서 자산 정보를 입력하고 '대시보드 업데이트'를 눌러주세요.")
            return

        total_assets = sum(assets.values())
        total_debt = p.get("debt_total", 0)
        net_worth = total_assets - total_debt

        m1, m2, m3 = st.columns(3)
        m1.metric("총 자산", fmt(total_assets))
        m2.metric("순 자산", fmt(net_worth), delta=fmt(-total_debt) if total_debt > 0 else None)
        m3.metric("3년 목표 달성률", f"{min(net_worth / p['goal_3y'] * 100, 999):.0f}%" if p.get("goal_3y") else "—")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**🍩 자산 분포**")
            asset_df = pd.DataFrame([{"자산": k, "금액": v} for k, v in assets.items() if v > 0])
            if not asset_df.empty:
                fig_asset = px.pie(asset_df, names="자산", values="금액", hole=0.4)
                fig_asset.update_traces(textinfo='percent+value')
                fig_asset.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_asset, use_container_width=True)

        with c2:
            if total_debt > 0 or net_worth > 0:
                st.markdown("**⚖️ 자본 vs 부채**")
                ratio_df = pd.DataFrame({"구분": ["순자산", "부채"], "금액": [max(net_worth, 0), total_debt]})
                fig_debt = px.pie(ratio_df, names="구분", values="금액", hole=0.4, color="구분",
                                  color_discrete_map={"순자산": "#2ECC71", "부채": "#E74C3C"})
                fig_debt.update_traces(textinfo='percent+value')
                fig_debt.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_debt, use_container_width=True)

        inc_list = st.session_state.monthly_income_list
        exp_list = st.session_state.monthly_expense_list
        if any(v > 0 for v in inc_list):
            st.markdown("**📈 월별 예상 수입·지출·저축률**")
            sav_list = [max(i - e, 0) for i, e in zip(inc_list, exp_list)]
            rate_list = [s / i * 100 if i > 0 else 0 for s, i in zip(sav_list, inc_list)]
            
            fig_monthly = go.Figure()
            fig_monthly.add_trace(go.Bar(x=months, y=inc_list, name="수입", marker_color="#3498DB"))
            fig_monthly.add_trace(go.Bar(x=months, y=exp_list, name="지출", marker_color="#E74C3C"))
            fig_monthly.add_trace(go.Bar(x=months, y=sav_list, name="저축", marker_color="#2ECC71"))
            fig_monthly.add_trace(go.Scatter(x=months, y=rate_list, name="저축률(%)", yaxis="y2", mode="lines+markers", line=dict(color="#F1C40F", width=3)))

            fig_monthly.update_layout(
                barmode="group",
                yaxis=dict(title="금액 (원)"),
                yaxis2=dict(title="저축률 (%)", overlaying="y", side="right", range=[0, max(rate_list + [100])]),
                legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
                margin=dict(t=40, b=0, l=0, r=0)
            )
            st.plotly_chart(fig_monthly, use_container_width=True)

def page_recommend():
    st.subheader("🎯 맞춤형 추천 엔진")
    if not st.session_state.profile:
        st.warning("먼저 '1️⃣ 내 재무 진단' 탭에서 정보를 입력해주세요.")
        return

    if st.button("🚀 분석 시작", type="primary", use_container_width=True):
        with st.spinner("분석 중..."):
            p = st.session_state.profile
            matched = match_policies(p)
            split = calc_account_split(p, matched)
            risk = calc_risk_profile({**p, "emergency_ok": split["emergency_ok"]})
            st.session_state.matched_policies = matched
            st.session_state.split_result = split
            st.session_state.risk_profile = risk
            st.session_state.analysis_done = True
            st.session_state.portfolio_explanations = {}
        st.rerun()

    if not st.session_state.analysis_done: return
    tab1, tab2, tab3 = st.tabs(["① 청년 정책 매칭", "② 통장 쪼개기", "③ 포트폴리오 추천"])

    with tab1:
        st.markdown("### 🏛️ 내가 받을 수 있는 청년 정책")
        for m in st.session_state.matched_policies:
            p = m["policy"]
            if m["eligible"] and not m.get("conflict"): badge, color, border = "✅ 가입 가능", "#d4edda", "#28a745"
            elif m.get("conflict"): badge, color, border = "⚠️ 중복 불가", "#fff3cd", "#ffc107"
            else: badge, color, border = "❌ 해당 없음", "#f8d7da", "#dc3545"
            st.markdown(f"<div style='background:{color}; border-left:4px solid {border}; padding:12px 16px; border-radius:6px; margin-bottom:10px;'><b>{p['name']}</b> &nbsp; <span style='font-size:0.85em'>{badge}</span><br/><span style='font-size:0.9em'>{p['benefit']}</span></div>", unsafe_allow_html=True)

    with tab2:
        st.markdown("### 💳 내 월급 쪼개기 플랜")
        split = st.session_state.split_result
        if split.get("fixed_warning"): st.error(f"⚠️ 고정지출 비율이 {split['fixed_ratio']*100:.0f}%로 높아요.")
        
        c1, c2 = st.columns([1, 1])
        with c1:
            labels = list(split["allocations"].keys()) + ["고정지출"]
            values = list(split["allocations"].values()) + [split.get("fixed_expense", 0)]
            fig_split = px.pie(names=labels, values=values, hole=0.4)
            fig_split.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_split, use_container_width=True)
        with c2:
            st.markdown("**배분 상세**")
            rows = [{"항목": k, "금액": fmt(v)} for k, v in split["allocations"].items()]
            rows.append({"항목": "고정지출", "금액": fmt(split.get("fixed_expense", 0))})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab3:
        st.markdown("### 📈 나에게 맞는 포트폴리오 후보")
        risk = st.session_state.get("risk_profile", "C")
        order = {"A": 0, "B": 1, "C": 2} if risk == "A" else {"B": 0, "C": 1, "A": 2} if risk == "B" else {"C": 0, "A": 1, "B": 2}
        
        for key in sorted(PORTFOLIOS.keys(), key=lambda k: order[k]):
            port = PORTFOLIOS[key]
            is_rec = key == risk
            with st.expander(f"{port['emoji']} **{port['name']}** ({port['type']})" + (" ⭐ 추천" if is_rec else ""), expanded=is_rec):
                c1, c2 = st.columns([1, 2])
                with c1:
                    fig_port = px.pie(pd.DataFrame(port["assets"]), names="name", values="ratio", hole=0.4)
                    fig_port.update_traces(textinfo='percent+label')
                    fig_port.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                    st.plotly_chart(fig_port, use_container_width=True)
                with c2:
                    if key not in st.session_state.portfolio_explanations:
                        with st.spinner("AI 분석 중..."):
                            st.session_state.portfolio_explanations[key] = get_gemini_portfolio_explanation(st.session_state.profile, key)
                    exp = st.session_state.portfolio_explanations.get(key, {})
                    st.success(f"✅ {exp.get('fit_reason', '')}")
                    st.markdown("**👍 장점**\n" + "\n".join([f"• {p}" for p in exp.get("pros", [])]))
                    st.markdown("**⚠️ 주의사항**\n" + "\n".join([f"• {c}" for c in exp.get("cons", [])]))

                if st.button(f"이 포트폴리오 선택하기", key=f"sel_{key}", type="primary"):
                    st.session_state.selected_portfolio = key
                    st.rerun()

        if st.session_state.selected_portfolio:
            sel = st.session_state.selected_portfolio
            st.divider()
            st.markdown(f"### 📋 {PORTFOLIOS[sel]['name']} 계좌 배치 가이드")
            isa_df = pd.DataFrame(PORTFOLIO_ISA_MAP.get(sel, []))[["name", "account", "reason"]]
            isa_df.columns = ["자산", "담을 계좌", "이유"]
            st.dataframe(isa_df, use_container_width=True, hide_index=True)

def page_chatbot():
    st.subheader("💬 AI 재무 비서 상담")
    if not st.session_state.profile:
        st.warning("먼저 '1️⃣ 내 재무 진단' 탭에서 정보를 입력해주세요.")
        return

    chat_box = st.container(height=450)
    with chat_box:
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])

    if prompt := st.chat_input("질문을 입력하세요"):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.spinner("답변 생성 중..."):
            reply = get_gemini_chat_response(st.session_state.chat_messages, st.session_state.profile, st.session_state.split_result, st.session_state.selected_portfolio or "")
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()

nav()
page_map = {"onboarding": page_onboarding, "dashboard": page_dashboard, "recommend": page_recommend, "chatbot": page_chatbot}
page_map[st.session_state.page]()