import streamlit as st
import pandas as pd
import numpy as np

api_key = st.secrets["GEMINI_API_KEY"]
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


# ── 오른쪽: AI 챗봇 ──
with col2:
    st.subheader("💬 AI 재무 비서 상담")

    # 세법 지식 베이스 (RAG 연동 전 임시 룰 기반)
    TAX_KB = {
        "isa": (
            "**ISA(개인종합자산관리계좌)** 는 2026년 기준:\n"
            "- 일반형: 연 2,000만원 납입, 최대 1억원 / **500만원 비과세**, 초과분 9.9% 분리과세\n"
            "- 서민형·농어민형: 비과세 한도 **1,000만원**\n"
            "- 계좌 내 배당·이자는 비과세 (Tax Drag 없음!)\n"
            "- 의무 가입 기간: 3년\n\n"
            "👉 배당 ETF를 ISA에 담으면 배당세 15.4%가 매년 빠져나가지 않아서 복리 효과가 훨씬 커집니다."
        ),
        "배당": (
            "**배당소득세** 는 15.4% (소득세 14% + 지방소득세 1.4%)가 **지급 시점에 원천징수**됩니다.\n\n"
            "이게 왜 중요하냐면 — 세금으로 빠져나간 돈은 재투자가 안 되기 때문에 복리 효과가 줄어드는 "
            "**'Tax Drag(조세 저항)'** 이 발생해요.\n\n"
            "예: 배당 수익률 3.5%짜리 ETF → 실제 손에 쥐는 건 **3.5% × (1 − 0.154) = 약 2.96%**"
        ),
        "etf": (
            "**배당 성장 ETF** 주요 종목 (참고용):\n"
            "- **SCHD**: 미국 고배당+배당성장, 약 3.5% 배당\n"
            "- **VIG**: 배당 성장 ETF, 약 1.8% 배당 / 자본 상승 위주\n"
            "- **ACE 미국배당다우존스**: 국내 상장 SCHD 추종, 월 배당\n\n"
            "ISA 계좌에 국내 상장 ETF(ACE, SOL 등)를 담으면 배당세 절약 가능!"
        ),
        "tax drag": (
            "**Tax Drag(조세 저항)** 이란 배당세가 매년 복리 운용 원금을 갉아먹는 현상입니다.\n\n"
            "직관적인 예시:\n"
            "- 1,000만원 투자, 배당 수익률 3.5%, 10년\n"
            "- Tax Drag 없을 때: 약 1,411만원\n"
            "- Tax Drag 있을 때 (15.4% 매년 차감): 약 1,349만원\n"
            "- 차이: **약 62만원** — 10년이면 꽤 큰 금액이죠!\n\n"
            "이 앱의 시뮬레이터가 이 효과를 반영하고 있어요."
        ),
    }

    def get_ai_response(user_msg: str) -> str:
        msg = user_msg.lower()
        for keyword, answer in TAX_KB.items():
            if keyword in msg:
                return answer
        # 폴백 응답
        return (
            "좋은 질문이에요! 현재 저는 ISA 세제, 배당소득세, Tax Drag, ETF 관련 질문에 "
            "답변드릴 수 있어요.\n\n"
            "예) 'ISA 계좌 장점 알려줘', '배당세가 뭐야', 'Tax Drag 설명해줘', 'ETF 추천해줘'\n\n"
            "*(추후 RAG 연동 시 실시간 세법 문서 기반으로 더 정확한 답변이 가능해집니다)*"
        )

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "안녕하세요! 2026년 세법을 반영한 **SafeFolio AI**입니다. 🛡️\n\n"
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

    if prompt := st.chat_input("질문을 입력하세요 (예: ISA 장점이 뭐야?)"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        response = get_ai_response(prompt)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()
