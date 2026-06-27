import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="SafeFolio AI", layout="wide", page_icon="🛡️")

# ──────────────────────────────────────────────
# 세금 계산 함수
# ──────────────────────────────────────────────

DIVIDEND_TAX_RATE = 0.154  # 배당소득세 15.4% (소득세 14% + 지방소득세 1.4%)

def calc_capital_gain_tax(profit: float, account_type: str) -> float:
    """매도 시점 자본 이득세 계산"""
    if profit <= 0:
        return 0.0
    if account_type == "일반(해외직투)":
        taxable = max(0.0, profit - 2_500_000)   # 250만원 기본공제
        return taxable * 0.22
    elif account_type == "ISA(중개형)":
        taxable = max(0.0, profit - 5_000_000)   # 500만원 비과세 (일반형 기준)
        return taxable * 0.099
    return 0.0


# ──────────────────────────────────────────────
# 핵심 시뮬레이션 — Tax Drag 반영
# ──────────────────────────────────────────────

def simulate_with_tax_drag(
    initial_capital: float,
    monthly_inv: float,
    years: int,
    dividend_yield: float,       # 배당 수익률 (연, 소수점)
    capital_gain_rate: float,    # 자본 상승률 (연, 소수점)
    account_type: str,
) -> dict:
    """
    매년 배당세를 즉시 차감(Tax Drag 반영)하고,
    자본 이득세는 최종 매도 시점에 한 번 계산합니다.
    """
    capital = float(initial_capital)
    total_invested = float(initial_capital)

    # ISA 계좌에서는 배당세 없음 (계좌 내 배당은 비과세 처리)
    apply_dividend_tax = (account_type == "일반(해외직투)")

    # 월 단위 비율 환산
    monthly_capital_rate = (1 + capital_gain_rate) ** (1 / 12) - 1
    monthly_dividend_rate = dividend_yield / 12

    yearly_snapshots = []  # 연도별 자산 추적

    for year in range(1, years + 1):
        for _ in range(12):
            # ① 이번 달 배당금 발생
            dividend = capital * monthly_dividend_rate

            # ② 배당세 즉시 차감 (Tax Drag 핵심)
            if apply_dividend_tax:
                dividend_after_tax = dividend * (1 - DIVIDEND_TAX_RATE)
            else:
                dividend_after_tax = dividend  # ISA: 비과세

            # ③ 자본 상승 적용 (배당 제외한 가격 상승분)
            capital = capital * (1 + monthly_capital_rate)

            # ④ 세후 배당금 재투자 + 월 추가 납입
            capital += dividend_after_tax + monthly_inv
            total_invested += monthly_inv

        yearly_snapshots.append(round(capital))

    # 최종 자본 이득세 (매도 시점)
    total_principal = initial_capital + monthly_inv * years * 12
    capital_gain = max(0.0, capital - total_principal)
    capital_gain_tax = calc_capital_gain_tax(capital_gain, account_type)
    after_tax_capital = capital - capital_gain_tax

    return {
        "total_principal": total_principal,
        "pre_tax_capital": capital,
        "capital_gain_tax": capital_gain_tax,
        "after_tax_capital": after_tax_capital,
        "yearly_snapshots": yearly_snapshots,
    }


# ──────────────────────────────────────────────
# UI
# ──────────────────────────────────────────────

st.title("SafeFolio AI: 한국형 자산 방어 및 배분 비서 🛡️")
st.caption("배당세 Tax Drag · ISA 절세 시뮬레이터 | 2026년 세법 기준")

col1, col2 = st.columns([1.1, 0.9], gap="large")

# ── 왼쪽: 시뮬레이션 ──
with col1:
    st.subheader("📊 포트폴리오 & 절세 시뮬레이션")

    c_left, c_right = st.columns(2)
    with c_left:
        initial_inv = st.number_input(
            "초기 투자금 (원)", min_value=0, max_value=500_000_000,
            value=10_000_000, step=1_000_000, format="%d"
        )
        years = st.slider("투자 기간 (년)", 1, 30, 10)
    with c_right:
        monthly_inv = st.number_input(
            "월 추가 납입금 (원)", min_value=0, max_value=10_000_000,
            value=1_500_000, step=100_000, format="%d"
        )

    st.divider()
    st.markdown("**수익률 설정** — 배당 수익률과 자본 상승률을 따로 입력하세요")

    rc1, rc2 = st.columns(2)
    with rc1:
        dividend_yield = st.slider(
            "배당 수익률 (연, %)\n즉시 현금화 → 배당세 15.4% 즉시 차감",
            0.0, 10.0, 3.5, step=0.1
        ) / 100
    with rc2:
        capital_gain_rate = st.slider(
            "자본 상승률 (연, %)\n미실현 이익 → 매도 시점에 과세",
            0.0, 20.0, 5.0, step=0.1
        ) / 100

    total_return = dividend_yield + capital_gain_rate
    st.info(
        f"📌 **총 기대 수익률 E(R) = {total_return*100:.1f}%**  "
        f"(배당 {dividend_yield*100:.1f}% + 자본 상승 {capital_gain_rate*100:.1f}%)"
    )

    # 두 계좌 모두 계산
    result_normal = simulate_with_tax_drag(
        initial_inv, monthly_inv, years, dividend_yield, capital_gain_rate, "일반(해외직투)"
    )
    result_isa = simulate_with_tax_drag(
        initial_inv, monthly_inv, years, dividend_yield, capital_gain_rate, "ISA(중개형)"
    )

    principal = result_normal["total_principal"]
    pre_tax   = result_normal["pre_tax_capital"]
    after_normal = result_normal["after_tax_capital"]
    after_isa    = result_isa["after_tax_capital"]
    isa_benefit  = after_isa - after_normal

    # 막대 차트
    chart_df = pd.DataFrame(
        {"금액 (원)": [principal, pre_tax, after_normal, after_isa]},
        index=["투자 원금", "세전 총자산", f"세후 — 일반계좌", f"세후 — ISA 계좌"]
    )
    st.bar_chart(chart_df)

    # 연도별 자산 추이 (라인 차트)
    with st.expander("📈 연도별 자산 추이 보기"):
        line_df = pd.DataFrame({
            "일반 계좌": result_normal["yearly_snapshots"],
            "ISA 계좌":  result_isa["yearly_snapshots"],
        }, index=range(1, years + 1))
        line_df.index.name = "투자 연도"
        st.line_chart(line_df)

    # 요약 카드
    m1, m2, m3 = st.columns(3)
    m1.metric("총 납입 원금", f"{principal:,.0f} 원")
    m2.metric("세전 총자산", f"{pre_tax:,.0f} 원", f"+{pre_tax - principal:,.0f} 원")
    m3.metric(
        f"ISA 절세 효과 ({years}년)",
        f"{isa_benefit:,.0f} 원",
        delta_color="normal"
    )

    st.caption(
        "⚠️ 본 시뮬레이션은 교육 목적이며 투자 권유가 아닙니다. "
        "실제 세금은 개인 상황에 따라 다를 수 있습니다."
    )


# ── 오른쪽: AI 챗봇 (Gemini 연동 + Dynamic Prompting) ──
with col2:
    st.subheader("💬 AI 재무 비서 상담")

    import google.generativeai as genai

    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-2.0-flash")

    # ── Dynamic Prompting: 슬라이더 값을 시스템 프롬프트에 주입 ──
    # (col1에서 계산된 변수들을 그대로 활용)
    system_prompt = f"""
당신은 한국 사회초년생을 위한 자산 관리 AI 비서 'SafeFolio AI'입니다.
현재 사용자가 좌측 시뮬레이터에 입력한 값은 다음과 같습니다:

[현재 시뮬레이션 컨텍스트]
- 초기 투자금: {initial_inv:,.0f}원
- 월 추가 납입금: {monthly_inv:,.0f}원
- 투자 기간: {years}년
- 배당 수익률: {dividend_yield*100:.1f}% (즉시 현금화, 배당세 15.4% 즉시 차감)
- 자본 상승률: {capital_gain_rate*100:.1f}% (미실현 이익, 매도 시 과세)
- 총 기대 수익률 E(R): {total_return*100:.1f}%

[시뮬레이션 결과]
- 총 납입 원금: {principal:,.0f}원
- 세전 총자산: {pre_tax:,.0f}원
- 세후 자산 (일반 계좌): {after_normal:,.0f}원
- 세후 자산 (ISA 계좌): {after_isa:,.0f}원
- ISA 절세 효과: {isa_benefit:,.0f}원

[답변 원칙]
1. 2026년 한국 세법 기준으로 정확하게 답변하세요.
2. 위 시뮬레이션 수치를 적극적으로 활용해서 구체적으로 설명하세요.
3. 전문 용어는 쉽게 풀어서 설명하세요 (대상: 자산 관리 초보자).
4. 투자 권유가 아닌 정보 제공임을 명심하세요.
5. 답변은 간결하게, 핵심만 짚어주세요.
"""

    def get_gemini_response(chat_history: list, user_msg: str) -> str:
        try:
            # 대화 히스토리를 Gemini 형식으로 변환
            gemini_history = []
            for msg in chat_history:
                role = "user" if msg["role"] == "user" else "model"
                gemini_history.append({"role": role, "parts": [msg["content"]]})

            chat = model.start_chat(history=gemini_history)
            # 첫 메시지에 시스템 프롬프트 주입
            full_msg = f"{system_prompt}\n\n사용자 질문: {user_msg}" if not gemini_history else user_msg
            response = chat.send_message(full_msg)
            return response.text
        except Exception as e:
            return f"⚠️ API 오류가 발생했어요: {str(e)}\n\nGemini API 키와 인터넷 연결을 확인해주세요."

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "안녕하세요! 2026년 세법을 반영한 **SafeFolio AI**입니다. 🛡️\n\n"
                    f"현재 시뮬레이터 기준으로 {years}년 후 ISA 절세 효과는 "
                    f"**{isa_benefit:,.0f}원**이에요.\n\n"
                    "배당세, ISA 절세 전략, Tax Drag 등 궁금한 점을 물어보세요!"
                ),
            }
        ]

    # 채팅 히스토리 출력
    chat_container = st.container(height=480)
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if prompt := st.chat_input("질문을 입력하세요 (예: 나 월급 300만원인데 어떻게 해?)"):
        st.session_state.messages.append({"role": "user", "content": prompt})

        # 시스템 프롬프트 제외한 순수 대화 히스토리만 전달
        chat_history = [m for m in st.session_state.messages[1:-1]]

        with st.spinner("답변 생성 중..."):
            response = get_gemini_response(chat_history, prompt)

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()
