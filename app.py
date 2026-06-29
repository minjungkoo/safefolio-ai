import streamlit as st
import pandas as pd
import numpy as np
import json

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
ISA_EXEMPTION_YOUTH = 4_000_000  # 청년형 (미확정, 예상치)

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

# ──────────────────────────────────────────────
# ISA 우선 담기 원칙 (하드코딩)
# ──────────────────────────────────────────────
ISA_PRIORITY = [
    {"asset": "해외주식형 ETF (S&P500 등)", "rank": 1,
     "account": "ISA 우선",
     "reason": "배당세 15.4% + 양도세 22% 동시 절세 효과 최대"},
    {"asset": "고배당 ETF",                 "rank": 2,
     "account": "ISA 우선",
     "reason": "배당세 15.4% Tax Drag 매년 제거, 복리 효과 극대화"},
    {"asset": "채권형 ETF",                 "rank": 3,
     "account": "ISA 권장",
     "reason": "이자소득세 15.4% 절세"},
    {"asset": "단기채 / 예적금",             "rank": 4,
     "account": "일반 계좌 가능",
     "reason": "세금 부담 적고 유동성 필요 자산"},
    {"asset": "원자재 ETF",                 "rank": 5,
     "account": "일반 계좌 권장",
     "reason": "변동성 높아 ISA 비과세 한도 낭비 우려"},
]

# 포트폴리오별 ISA 배치 매핑
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

# 포트폴리오 정의
PORTFOLIOS = {
    "A": {
        "name": "버핏식 단순 인덱스",
        "type": "공격형",
        "color": "#E74C3C",
        "emoji": "🚀",
        "basis": "워런 버핏 — S&P500 90% + 단기채 10%",
        "assets": [
            {"name": "TIGER 미국S&P500", "ratio": 90, "category": "해외주식형 ETF"},
            {"name": "KODEX 단기채권",    "ratio": 10, "category": "단기채"},
        ],
    },
    "B": {
        "name": "올웨더 포트폴리오",
        "type": "안정형",
        "color": "#2ECC71",
        "emoji": "🌤️",
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
        "name": "코어-위성 전략",
        "type": "균형형",
        "color": "#3498DB",
        "emoji": "⚖️",
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
    """청년 정책 매칭 (코드 기반)"""
    age = profile.get("age", 30)
    income = profile.get("annual_income", 0)
    job = profile.get("job_type", "정규직")
    housing = profile.get("housing", "월세")
    assets = profile.get("total_assets", 0)
    matched = []

    for p in POLICIES:
        c = p["conditions"]
        ok = True
        if age < c.get("age_min", 0) or age > c.get("age_max", 99):
            ok = False
        if c.get("income_max_general") and income > c["income_max_general"]:
            ok = False
        if "job_types" in c and job not in c["job_types"]:
            ok = False
        if c.get("housing") and housing != "무주택":
            ok = False
        if c.get("asset_max") and assets > c["asset_max"]:
            ok = False
        matched.append({"policy": p, "eligible": ok})

    # 충돌 처리: youth_savings 가능 → youth_isa 비추천 (중복 불가)
    youth_savings_ok = any(
        m["eligible"] and m["policy"]["id"] == "youth_savings" for m in matched
    )
    if youth_savings_ok:
        for m in matched:
            if m["policy"]["id"] == "youth_isa":
                m["conflict"] = True
            else:
                m["conflict"] = False
    else:
        for m in matched:
            m["conflict"] = False

    return matched


def calc_risk_profile(profile: dict) -> str:
    """위험 성향 자동 판단"""
    age = profile.get("age", 30)
    debt_rate = profile.get("debt_rate", 0)
    emergency_ok = profile.get("emergency_ok", False)
    invest_years = profile.get("invest_years", 5)

    score = 0
    if age <= 30:         score += 2
    elif age <= 35:       score += 1
    if debt_rate < 5:     score += 2
    elif debt_rate < 8:   score += 1
    if emergency_ok:      score += 2
    if invest_years >= 7: score += 2
    elif invest_years >= 4: score += 1

    if score >= 7:   return "A"  # 공격형
    elif score >= 4: return "C"  # 균형형
    else:            return "B"  # 안정형


def calc_account_split(profile: dict, matched_policies: list) -> dict:
    """통장 쪼개기 비율 계산 (코드 기반)"""
    monthly_income = profile.get("monthly_income", 0)
    fixed_expense = profile.get("fixed_expense", 0)
    emergency_current = profile.get("emergency_current", 0)
    debt_rate = profile.get("debt_rate", 0)
    debt_total = profile.get("debt_total", 0)

    result = {}

    # Step1: 고정지출 비율 검증
    fixed_ratio = fixed_expense / monthly_income if monthly_income > 0 else 0
    result["fixed_ratio"] = fixed_ratio
    result["fixed_warning"] = fixed_ratio > 0.5

    # Step2: 비상금 부족분
    emergency_target = fixed_expense * 6
    emergency_gap = max(0, emergency_target - emergency_current)
    emergency_ok = emergency_gap == 0
    result["emergency_target"] = emergency_target
    result["emergency_gap"] = emergency_gap
    result["emergency_ok"] = emergency_ok

    # Step3: 부채 상환 우선순위
    debt_priority = debt_rate >= 5.0
    result["debt_priority"] = debt_priority

    # Step4: 정책 매칭 결과 반영
    youth_savings_ok = any(
        m["eligible"] and not m.get("conflict") and m["policy"]["id"] == "youth_savings"
        for m in matched_policies
    )
    youth_savings_amount = 500_000 if youth_savings_ok else 0

    # Step5: 배분 계산
    remaining = monthly_income - fixed_expense
    allocations = {}

    # 비상금
    if not emergency_ok:
        emg_alloc = min(remaining * 0.20, emergency_gap / 12)
        allocations["비상금 통장"] = round(emg_alloc)
        remaining -= emg_alloc
    else:
        allocations["비상금 통장"] = round(monthly_income * 0.05)
        remaining -= allocations["비상금 통장"]

    # 부채 상환
    if debt_priority and debt_total > 0:
        debt_alloc = remaining * 0.30
        allocations["부채 상환"] = round(debt_alloc)
        remaining -= debt_alloc

    # 청년미래적금
    if youth_savings_ok and remaining >= youth_savings_amount:
        allocations["청년미래적금"] = youth_savings_amount
        remaining -= youth_savings_amount

    # ISA / 투자
    invest_alloc = remaining * 0.60
    allocations["ISA / 투자"] = round(invest_alloc)
    remaining -= invest_alloc

    # 자유 지출
    allocations["자유 지출"] = max(0, round(remaining))

    result["allocations"] = allocations
    result["monthly_income"] = monthly_income
    result["fixed_expense"] = fixed_expense
    return result


def get_gemini_portfolio_explanation(profile: dict, portfolio_key: str) -> dict:
    """Gemini API로 포트폴리오 장단점 생성"""
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

{{
  "fit_reason": "이런 분께 맞아요 — 위 사용자 프로필을 반영한 1문장 (50자 이내)",
  "pros": ["장점 1 (30자 이내)", "장점 2 (30자 이내)"],
  "cons": ["단점/주의사항 1 (30자 이내)", "단점/주의사항 2 (30자 이내)"]
}}
"""
        response = model.generate_content(prompt)
        text = response.text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        return {
            "fit_reason": f"{PORTFOLIOS[portfolio_key]['type']} 투자자에게 적합한 포트폴리오예요.",
            "pros": ["장기 분산 투자 효과", "검증된 거장의 전략 기반"],
            "cons": ["시장 상황에 따라 수익률 변동 가능", "정기 리밸런싱 필요"],
        }


def get_gemini_chat_response(messages: list, profile: dict,
                              split_result: dict, selected_portfolio: str) -> str:
    """페이지4 챗봇 — Dynamic Prompting"""
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
- 나이: {profile.get('age')}세 / 직업: {profile.get('job_type')} / 성별: {profile.get('gender')}
- 월 수입: {fmt(profile.get('monthly_income', 0))} / 월 고정지출: {fmt(profile.get('fixed_expense', 0))}
- 부채: {'있음 (' + fmt(profile.get('debt_total', 0)) + ', 금리 ' + str(profile.get('debt_rate', 0)) + '%)' if profile.get('debt_total', 0) > 0 else '없음'}
- 현재 비상금: {fmt(profile.get('emergency_current', 0))} / 목표: {fmt(split_result.get('emergency_target', 0))}
- 3년 목표 저축액: {fmt(profile.get('goal_3y', 0))}

[통장 쪼개기 결과]
{alloc_str}

[선택한 포트폴리오]
{port_name} ({port.get('type', '')})

[답변 원칙]
1. 2026년 한국 세법 기준으로 정확하게 답변하세요.
2. 위 수치를 적극 활용해 구체적으로 설명하세요.
3. 사회초년생 눈높이로 쉽게 설명하세요.
4. 투자 권유가 아닌 교육·정보 제공임을 명심하세요.
5. 답변은 간결하게 핵심만, 필요시 이모지 활용.
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
        "page": "onboarding",
        "profile": {},
        "assets": {},
        "monthly_income_list": [0] * 12,
        "monthly_expense_list": [0] * 12,
        "matched_policies": [],
        "split_result": {},
        "selected_portfolio": None,
        "portfolio_explanations": {},
        "analysis_done": False,
        "chat_messages": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ──────────────────────────────────────────────
# 네비게이션
# ──────────────────────────────────────────────
def nav():
    pages = {
        "onboarding":   "1️⃣ 내 재무 진단",
        "dashboard":    "2️⃣ 자산 현황",
        "recommend":    "3️⃣ 맞춤 추천",
        "chatbot":      "4️⃣ AI 상담",
    }
    cols = st.columns(len(pages))
    for col, (key, label) in zip(cols, pages.items()):
        active = st.session_state.page == key
        if col.button(label, use_container_width=True,
                      type="primary" if active else "secondary"):
            st.session_state.page = key
            st.rerun()
    st.divider()

# ──────────────────────────────────────────────
# 페이지1 — 온보딩
# ──────────────────────────────────────────────
def page_onboarding():
    st.title("🛡️ SafeFolio AI")
    st.subheader("내 재무 상태를 알려주세요")
    st.caption("입력하신 정보는 분석에만 사용되며 저장되지 않아요.")

    with st.form("onboarding_form"):
        st.markdown("**기본 정보**")
        c1, c2, c3 = st.columns(3)
        age      = c1.number_input("나이", 19, 65, 27, step=1)
        gender   = c2.selectbox("성별", ["남성", "여성", "선택 안 함"])
        job_type = c3.selectbox("직업 형태", ["정규직", "계약직", "프리랜서", "무직"])

        st.markdown("**소득 정보**")
        c1, c2 = st.columns(2)
        monthly_income = c1.number_input(
            "월 세후 수입 (원)", 0, 20_000_000, 3_000_000, step=100_000, format="%d")
        bonus_yn = c2.selectbox("성과급/상여금 여부", ["없음", "분기", "반기", "연간"])
        bonus_amt = 0
        if bonus_yn != "없음":
            bonus_amt = st.number_input(
                "예상 성과급 (1회 금액, 원)", 0, 50_000_000, 3_000_000, step=500_000, format="%d")

        st.markdown("**지출 및 주거**")
        c1, c2 = st.columns(2)
        fixed_expense = c1.number_input(
            "월 고정지출 합산 (원)\n주거비·통신비·보험료 등",
            0, 10_000_000, 1_200_000, step=100_000, format="%d")
        housing = c2.selectbox("주거 형태", ["월세", "전세", "자가", "부모님 거주", "무주택"])

        st.markdown("**부채 정보**")
        debt_yn = st.selectbox("부채 여부", ["없음", "있음"])
        debt_total, debt_rate = 0, 0.0
        if debt_yn == "있음":
            c1, c2 = st.columns(2)
            debt_total = c1.number_input(
                "총 부채 금액 (원)", 0, 500_000_000, 10_000_000, step=1_000_000, format="%d")
            debt_rate  = c2.number_input("대출 금리 (%)", 0.0, 30.0, 4.5, step=0.1)

        st.markdown("**현재 비상금 및 목표**")
        c1, c2, c3 = st.columns(3)
        emergency_current = c1.number_input(
            "현재 비상금 잔액 (원)", 0, 100_000_000, 500_000, step=100_000, format="%d")
        invest_years = c2.slider("투자 기간 (년)", 1, 30, 5)
        goal_3y      = c3.number_input(
            "3년 목표 저축액 (원)", 0, 200_000_000, 30_000_000, step=1_000_000, format="%d")

        submitted = st.form_submit_button("✅ 진단 시작", use_container_width=True, type="primary")

    if submitted:
        annual_income = monthly_income * 12 + (
            bonus_amt * {"없음": 0, "분기": 4, "반기": 2, "연간": 1}[bonus_yn]
        )
        emergency_ok = emergency_current >= fixed_expense * 6

        st.session_state.profile = {
            "age": age, "gender": gender, "job_type": job_type,
            "monthly_income": monthly_income, "annual_income": annual_income,
            "bonus_yn": bonus_yn, "bonus_amt": bonus_amt,
            "fixed_expense": fixed_expense, "housing": housing,
            "debt_total": debt_total, "debt_rate": debt_rate,
            "emergency_current": emergency_current, "emergency_ok": emergency_ok,
            "invest_years": invest_years, "goal_3y": goal_3y,
        }
        st.session_state.analysis_done = False
        st.session_state.selected_portfolio = None
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

    # ── 좌측: 자산 입력 ──
    left, right = st.columns([1, 1.4], gap="large")

    with left:
        st.markdown("**💰 자산 입력**")
        with st.form("asset_form"):
            youth_savings = st.number_input("청년미래적금 (원)", 0, 50_000_000, 0, step=100_000, format="%d")
            isa_balance   = st.number_input("ISA 계좌 (원)",    0, 200_000_000, 0, step=100_000, format="%d")
            stock_balance = st.number_input("주식/ETF (원)",    0, 500_000_000, 0, step=100_000, format="%d")
            savings       = st.number_input("예적금 (원)",      0, 200_000_000, 0, step=100_000, format="%d")
            emergency     = st.number_input("비상금 통장 (원)", 0, 100_000_000,
                                            int(p.get("emergency_current", 0)),
                                            step=100_000, format="%d")

            st.markdown("**📅 월별 예상 수입 (12개월)**")
            st.caption("성과급 달은 높게 입력하세요")
            months = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"]
            inc_cols = st.columns(4)
            income_list, expense_list = [], []
            for i, m in enumerate(months):
                default_inc = p.get("monthly_income", 0)
                if p.get("bonus_yn") == "분기" and i % 3 == 2:
                    default_inc += p.get("bonus_amt", 0)
                elif p.get("bonus_yn") == "반기" and i in [5, 11]:
                    default_inc += p.get("bonus_amt", 0)
                elif p.get("bonus_yn") == "연간" and i == 11:
                    default_inc += p.get("bonus_amt", 0)
                v = inc_cols[i % 4].number_input(
                    m, 0, 50_000_000, int(default_inc), step=100_000,
                    format="%d", key=f"inc_{i}")
                income_list.append(v)

            st.markdown("**📅 월별 예상 지출 (12개월)**")
            exp_cols = st.columns(4)
            for i, m in enumerate(months):
                v = exp_cols[i % 4].number_input(
                    m, 0, 20_000_000, int(p.get("fixed_expense", 0)),
                    step=100_000, format="%d", key=f"exp_{i}")
                expense_list.append(v)

            save_btn = st.form_submit_button("📊 대시보드 업데이트", use_container_width=True, type="primary")

        if save_btn:
            st.session_state.assets = {
                "youth_savings": youth_savings, "isa": isa_balance,
                "stock": stock_balance, "savings": savings, "emergency": emergency,
            }
            st.session_state.monthly_income_list  = income_list
            st.session_state.monthly_expense_list = expense_list
            st.session_state.profile["emergency_current"] = emergency
            st.session_state.profile["emergency_ok"] = emergency >= p.get("fixed_expense", 0) * 6
            st.rerun()

    # ── 우측: 차트 ──
    with right:
        assets = st.session_state.assets
        if not assets:
            st.info("좌측에서 자산 정보를 입력하고 '대시보드 업데이트'를 눌러주세요.")
            return

        total_assets = sum(assets.values())
        total_debt   = p.get("debt_total", 0)
        net_worth    = total_assets - total_debt

        # 요약 카드
        m1, m2, m3 = st.columns(3)
        m1.metric("총 자산",  fmt(total_assets))
        m2.metric("순 자산",  fmt(net_worth), delta=fmt(-total_debt) if total_debt else None)
        m3.metric("3년 목표 달성률",
                  f"{min(net_worth / p['goal_3y'] * 100, 999):.0f}%" if p.get("goal_3y") else "—")

        # 자산 분포 파이차트
        asset_labels = {
            "youth_savings": "청년미래적금", "isa": "ISA 계좌",
            "stock": "주식/ETF", "savings": "예적금", "emergency": "비상금",
        }
        asset_df = pd.DataFrame(
            {"자산": [asset_labels[k] for k, v in assets.items() if v > 0],
             "금액": [v for v in assets.values() if v > 0]}
        )
        if not asset_df.empty:
            st.markdown("**자산 분포**")
            st.bar_chart(asset_df.set_index("자산"))

        # 자본 vs 부채 비율
        if total_debt > 0:
            st.markdown("**자본 vs 부채**")
            ratio_df = pd.DataFrame(
                {"구분": ["순자산", "부채"],
                 "금액": [max(net_worth, 0), total_debt]}
            )
            st.bar_chart(ratio_df.set_index("구분"))

        # 월별 저축률 복합 차트
        inc_list = st.session_state.monthly_income_list
        exp_list = st.session_state.monthly_expense_list
        if any(v > 0 for v in inc_list):
            st.markdown("**월별 예상 수입·지출·저축률**")
            sav_list  = [max(inc - exp, 0) for inc, exp in zip(inc_list, exp_list)]
            rate_list = [s / i * 100 if i > 0 else 0 for s, i in zip(sav_list, inc_list)]
            monthly_df = pd.DataFrame({
                "수입": inc_list, "지출": exp_list, "저축": sav_list,
            }, index=months)
            st.bar_chart(monthly_df)

            rate_df = pd.DataFrame({"저축률 (%)": rate_list}, index=months)
            st.line_chart(rate_df)

        # 비상금 현황
        emg_target = p.get("fixed_expense", 0) * 6
        emg_current = assets.get("emergency", 0)
        emg_pct = min(emg_current / emg_target * 100, 100) if emg_target > 0 else 0
        st.markdown("**비상금 현황**")
        st.progress(int(emg_pct), text=f"목표 {fmt(emg_target)} 중 {fmt(emg_current)} 달성 ({emg_pct:.0f}%)")


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
            p = st.session_state.profile
            matched = match_policies(p)
            split   = calc_account_split(p, matched)
            risk    = calc_risk_profile({**p, "emergency_ok": split["emergency_ok"]})
            st.session_state.matched_policies  = matched
            st.session_state.split_result      = split
            st.session_state.risk_profile      = risk
            st.session_state.analysis_done     = True
            st.session_state.portfolio_explanations = {}
        st.rerun()

    if not st.session_state.analysis_done:
        st.info("'분석 시작' 버튼을 눌러주세요.")
        return

    tab1, tab2, tab3 = st.tabs(["① 청년 정책 매칭", "② 통장 쪼개기", "③ 포트폴리오 추천"])

    # ── 탭① 청년 정책 매칭 ──
    with tab1:
        st.markdown("### 🏛️ 내가 받을 수 있는 청년 정책")
        for m in st.session_state.matched_policies:
            policy  = m["policy"]
            eligible = m["eligible"]
            conflict = m.get("conflict", False)

            if eligible and not conflict:
                badge = "✅ 가입 가능"
                color = "#d4edda"
                border = "#28a745"
            elif conflict:
                badge = "⚠️ 중복 불가"
                color = "#fff3cd"
                border = "#ffc107"
            else:
                badge = "❌ 해당 없음"
                color = "#f8d7da"
                border = "#dc3545"

            st.markdown(f"""
<div style='background:{color}; border-left:4px solid {border};
     padding:12px 16px; border-radius:6px; margin-bottom:10px;'>
  <b>{policy['name']}</b> &nbsp; <span style='font-size:0.85em'>{badge}</span><br/>
  <span style='font-size:0.9em'>{policy['benefit']}</span>
  {f"<br/><span style='font-size:0.8em; color:#856404'>⚠️ 청년미래적금 가입 시 중복 불가</span>" if conflict else ""}
  {f"<br/><span style='font-size:0.8em; color:#6c757d'>{policy['note']}</span>" if policy.get('note') else ""}
</div>
""", unsafe_allow_html=True)

    # ── 탭② 통장 쪼개기 ──
    with tab2:
        st.markdown("### 💳 내 월급 쪼개기 플랜")
        split = st.session_state.split_result
        p     = st.session_state.profile

        if split.get("fixed_warning"):
            st.error(f"⚠️ 고정지출 비율이 {split['fixed_ratio']*100:.0f}%로 50%를 초과해요. 고정지출 점검이 필요해요.")

        if not split.get("emergency_ok"):
            st.warning(f"📌 비상금 목표 {fmt(split['emergency_target'])} 중 {fmt(p.get('emergency_current',0))} 보유 중. 부족분 {fmt(split['emergency_gap'])}을 먼저 채워요.")

        alloc = split.get("allocations", {})
        monthly = split.get("monthly_income", 0)

        # 도넛차트 데이터
        labels = list(alloc.keys()) + ["고정지출"]
        values = list(alloc.values()) + [split.get("fixed_expense", 0)]
        chart_df = pd.DataFrame({"항목": labels, "금액": values})
        st.bar_chart(chart_df.set_index("항목"))

        # 상세 테이블
        st.markdown("**배분 상세**")
        rows = [{"항목": k,
                 "금액": fmt(v),
                 "비율": f"{v/monthly*100:.1f}%" if monthly > 0 else "—"}
                for k, v in alloc.items()]
        rows.append({"항목": "고정지출",
                     "금액": fmt(split.get("fixed_expense", 0)),
                     "비율": f"{split['fixed_ratio']*100:.1f}%"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # 성과급 처리 안내
        if p.get("bonus_amt", 0) > 0:
            emg_ok = split.get("emergency_ok")
            st.info(
                f"💡 **성과급 {fmt(p['bonus_amt'])} 처리 방법**\n\n"
                + ("➡️ 비상금이 아직 부족해요. **전액 비상금 통장**에 넣으세요."
                   if not emg_ok
                   else f"➡️ 비상금 충족! **{fmt(int(p['bonus_amt']*0.7))} 투자** + **{fmt(int(p['bonus_amt']*0.3))} 자유**")
            )

    # ── 탭③ 포트폴리오 추천 ──
    with tab3:
        st.markdown("### 📈 나에게 맞는 포트폴리오 후보")
        risk = st.session_state.get("risk_profile", "C")
        order = {"A": 0, "B": 1, "C": 2}
        if risk == "A": order = {"A": 0, "C": 1, "B": 2}
        elif risk == "B": order = {"B": 0, "C": 1, "A": 2}
        sorted_keys = sorted(PORTFOLIOS.keys(), key=lambda k: order[k])

        for key in sorted_keys:
            port = PORTFOLIOS[key]
            is_recommended = key == risk
            with st.expander(
                f"{port['emoji']} **{port['name']}** ({port['type']})"
                + (" ⭐ 추천" if is_recommended else ""),
                expanded=is_recommended
            ):
                # 자산 비율 바차트
                asset_df = pd.DataFrame(port["assets"]).set_index("name")[["ratio"]]
                asset_df.columns = ["비율 (%)"]
                st.bar_chart(asset_df)

                st.caption(f"📚 근거: {port['basis']}")

                # Gemini 장단점 (캐시)
                if key not in st.session_state.portfolio_explanations:
                    with st.spinner("AI 분석 중..."):
                        exp = get_gemini_portfolio_explanation(
                            st.session_state.profile, key)
                        st.session_state.portfolio_explanations[key] = exp

                exp = st.session_state.portfolio_explanations.get(key, {})
                if exp:
                    st.success(f"✅ {exp.get('fit_reason', '')}")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**👍 장점**")
                        for pro in exp.get("pros", []):
                            st.markdown(f"• {pro}")
                    with c2:
                        st.markdown("**⚠️ 주의사항**")
                        for con in exp.get("cons", []):
                            st.markdown(f"• {con}")

                if st.button(f"이 포트폴리오 선택하기", key=f"sel_{key}", type="primary"):
                    st.session_state.selected_portfolio = key
                    st.rerun()

        # ISA 계좌 배치 가이드 (선택 후)
        if st.session_state.selected_portfolio:
            sel = st.session_state.selected_portfolio
            port = PORTFOLIOS[sel]
            st.divider()
            st.markdown(f"### 📋 내 포트폴리오 계좌 배치 가이드")
            st.caption(f"선택: {port['emoji']} {port['name']}")
            isa_map = PORTFOLIO_ISA_MAP.get(sel, [])
            isa_df  = pd.DataFrame(isa_map)[["name", "account", "reason"]]
            isa_df.columns = ["자산", "담을 계좌", "이유"]
            st.dataframe(isa_df, use_container_width=True, hide_index=True)
            st.info("💡 ISA 연간 납입 한도는 ₩20,000,000이에요. 초과분은 일반 계좌를 활용하세요.")


# ──────────────────────────────────────────────
# 페이지4 — 에듀테크 챗봇
# ──────────────────────────────────────────────
def page_chatbot():
    st.subheader("💬 AI 재무 비서 상담")

    if not st.session_state.profile:
        st.warning("먼저 '1️⃣ 내 재무 진단' 탭에서 정보를 입력해주세요.")
        return

    port_name = ""
    if st.session_state.selected_portfolio:
        port_name = PORTFOLIOS[st.session_state.selected_portfolio]["name"]
    st.caption(
        f"현재 분석 기준: 월수입 {fmt(st.session_state.profile.get('monthly_income',0))} "
        + (f"| 선택 포트폴리오: {port_name}" if port_name else "| 포트폴리오 미선택")
    )

    if not st.session_state.chat_messages:
        emg_ok = st.session_state.profile.get("emergency_ok", False)
        intro = (
            f"안녕하세요! 2026년 세법 기반 **SafeFolio AI**입니다. 🛡️\n\n"
            f"월 수입 **{fmt(st.session_state.profile.get('monthly_income',0))}** 기준으로 "
            f"맞춤 분석이 완료됐어요.\n\n"
            f"비상금 상태: {'✅ 목표 달성' if emg_ok else '⚠️ 목표 미달성, 먼저 채우는 걸 추천해요'}\n\n"
            "ISA 절세 전략, 통장 쪼개기 원리, 청년 정책 등 궁금한 점을 질문해보세요!"
        )
        st.session_state.chat_messages = [{"role": "assistant", "content": intro}]

    chat_box = st.container(height=450)
    with chat_box:
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if prompt := st.chat_input("질문을 입력하세요 (예: 왜 ISA에 ETF를 먼저 담아야 해요?)"):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.spinner("답변 생성 중..."):
            reply = get_gemini_chat_response(
                st.session_state.chat_messages,
                st.session_state.profile,
                st.session_state.split_result,
                st.session_state.selected_portfolio or "",
            )
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()


# ──────────────────────────────────────────────
# 메인 라우터
# ──────────────────────────────────────────────
nav()
page_map = {
    "onboarding": page_onboarding,
    "dashboard":  page_dashboard,
    "recommend":  page_recommend,
    "chatbot":    page_chatbot,
}
page_map[st.session_state.page]()

st.divider()
st.caption("⚠️ 본 서비스는 교육 목적이며 투자 권유가 아닙니다. 실제 투자 결정 전 전문가와 상담하세요.")
