import streamlit as st


# =========================================================
# 페이지 설정
# =========================================================
st.set_page_config(
    page_title="금융 스트레스 테스트",
    page_icon="⚠️",
    layout="wide",
)

st.title("⚠️ 금융 스트레스 테스트")

st.write(
    "현재 소비를 실행한 뒤, 갑작스러운 추가지출이나 소득 감소가 발생했을 때 "
    "내 금융상태가 얼마나 버틸 수 있는지 확인합니다."
)

st.info(
    "스트레스 테스트는 미래를 예측하는 기능이 아니라, "
    "예상치 못한 상황을 가정해 현재 소비 결정의 취약성을 점검하는 도구입니다."
)


# =========================================================
# 1. 이전 페이지 데이터 불러오기
# =========================================================
purchase_analysis_completed = st.session_state.get(
    "purchase_analysis_completed",
    False
)

if not purchase_analysis_completed:

    st.warning(
        "먼저 **3_소비_판단** 페이지에서 "
        "소비 가능 여부 분석을 완료해주세요."
    )

    st.stop()


monthly_income = st.session_state.get(
    "monthly_income",
    0
)

current_spending = st.session_state.get(
    "current_spending",
    0
)

fixed_expense = st.session_state.get(
    "fixed_expense",
    0
)

saving_goal = st.session_state.get(
    "saving_goal",
    0
)

safety_reserve = st.session_state.get(
    "safety_reserve",
    0
)

available_after_purchase = st.session_state.get(
    "available_after_purchase",
    0
)

purchase_status = st.session_state.get(
    "purchase_status",
    "-"
)

optimized_final_price = st.session_state.get(
    "optimized_final_price",
    0
)


# =========================================================
# 2. 현재 소비 상태 요약
# =========================================================
st.header("1️⃣ 현재 소비 상태")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "최적 결제금액",
        f"{optimized_final_price:,.0f}원"
    )

with col2:
    st.metric(
        "구매 후 가용자금",
        f"{available_after_purchase:,.0f}원"
    )

with col3:
    st.metric(
        "최소 안전잔액",
        f"{safety_reserve:,.0f}원"
    )

with col4:
    st.metric(
        "현재 소비 판단",
        purchase_status
    )


st.divider()


# =========================================================
# 3. 스트레스 시나리오 선택
# =========================================================
st.header("2️⃣ 스트레스 상황 선택")

stress_scenario = st.radio(
    "어떤 상황을 테스트할까요?",
    [
        "생활비 쇼크",
        "소득 감소",
        "복합 쇼크",
        "직접 설정"
    ],
    horizontal=True,
)


# =========================================================
# 4. 시나리오별 충격 값 설정
# =========================================================
if stress_scenario == "생활비 쇼크":

    income_drop = 0

    unexpected_expense = st.slider(
        "예상치 못한 추가지출",
        min_value=50000,
        max_value=500000,
        value=100000,
        step=10000,
    )

    st.caption(
        "예: 병원비, 교통비, 수리비, 갑작스러운 모임비 등"
    )


elif stress_scenario == "소득 감소":

    income_drop_rate = st.slider(
        "소득 감소율",
        min_value=10,
        max_value=100,
        value=30,
        step=5,
    )

    income_drop = round(
        monthly_income
        * income_drop_rate
        / 100
    )

    unexpected_expense = 0

    st.caption(
        f"현재 소득 {monthly_income:,.0f}원 기준 "
        f"약 {income_drop:,.0f}원이 감소한다고 가정합니다."
    )


elif stress_scenario == "복합 쇼크":

    col_a, col_b = st.columns(2)

    with col_a:

        income_drop_rate = st.slider(
            "소득 감소율",
            min_value=10,
            max_value=100,
            value=30,
            step=5,
        )

        income_drop = round(
            monthly_income
            * income_drop_rate
            / 100
        )

    with col_b:

        unexpected_expense = st.slider(
            "예상치 못한 추가지출",
            min_value=50000,
            max_value=500000,
            value=200000,
            step=10000,
        )

    st.warning(
        "소득 감소와 추가지출이 동시에 발생하는 "
        "비교적 강한 스트레스 상황입니다."
    )


else:

    col_a, col_b = st.columns(2)

    with col_a:

        income_drop = st.number_input(
            "예상 소득 감소액",
            min_value=0,
            value=0,
            step=10000,
        )

    with col_b:

        unexpected_expense = st.number_input(
            "예상치 못한 추가지출",
            min_value=0,
            value=100000,
            step=10000,
        )


st.divider()


# =========================================================
# 5. 스트레스 테스트 계산
# =========================================================
def run_stress_test(
    income,
    already_spent,
    future_fixed_expense,
    saving_target,
    reserve,
    purchase_price,
    income_drop_amount,
    extra_expense,
):

    stressed_income = max(
        0,
        income - income_drop_amount
    )

    stressed_balance = (
        stressed_income
        - already_spent
        - future_fixed_expense
        - saving_target
        - purchase_price
        - extra_expense
    )

    reserve_gap = (
        stressed_balance
        - reserve
    )


    if stressed_balance < 0:

        status = "🔴 위험"

        status_code = "danger"

        explanation = (
            "충격 상황 발생 시 사용 가능한 자금이 0원 미만으로 내려갑니다."
        )


    elif stressed_balance < reserve:

        status = "🟡 주의"

        status_code = "warning"

        explanation = (
            "충격 상황은 버틸 수 있지만 최소 안전잔액을 유지하지 못합니다."
        )


    else:

        status = "🟢 안정"

        status_code = "safe"

        explanation = (
            "충격 상황 이후에도 최소 안전잔액을 유지할 수 있습니다."
        )


    return {
        "stressed_income":
            stressed_income,

        "stressed_balance":
            stressed_balance,

        "reserve_gap":
            reserve_gap,

        "status":
            status,

        "status_code":
            status_code,

        "explanation":
            explanation,
    }


# =========================================================
# 6. 분석 버튼
# =========================================================
if st.button(
    "⚡ 스트레스 테스트 실행",
    type="primary",
    use_container_width=True,
):

    result = run_stress_test(
        income=monthly_income,
        already_spent=current_spending,
        future_fixed_expense=fixed_expense,
        saving_target=saving_goal,
        reserve=safety_reserve,
        purchase_price=optimized_final_price,
        income_drop_amount=income_drop,
        extra_expense=unexpected_expense,
    )


    stressed_balance = result[
        "stressed_balance"
    ]

    reserve_gap = result[
        "reserve_gap"
    ]


    # =====================================================
    # 7. 결과
    # =====================================================
    st.divider()

    st.header("📊 스트레스 테스트 결과")


    if result["status_code"] == "safe":

        st.success(
            f"## {result['status']}\n\n"
            f"{result['explanation']}"
        )


    elif result["status_code"] == "warning":

        st.warning(
            f"## {result['status']}\n\n"
            f"{result['explanation']}"
        )


    else:

        st.error(
            f"## {result['status']}\n\n"
            f"{result['explanation']}"
        )


    # =====================================================
    # 8. 핵심 수치
    # =====================================================
    st.subheader("💥 충격 전·후 비교")

    metric1, metric2, metric3, metric4 = st.columns(4)


    with metric1:

        st.metric(
            "구매 직후 가용자금",
            f"{available_after_purchase:,.0f}원"
        )


    with metric2:

        st.metric(
            "소득 감소",
            f"-{income_drop:,.0f}원"
        )


    with metric3:

        st.metric(
            "추가지출",
            f"-{unexpected_expense:,.0f}원"
        )


    with metric4:

        st.metric(
            "충격 후 가용자금",
            f"{stressed_balance:,.0f}원"
        )


    # =====================================================
    # 9. 안전잔액 비교
    # =====================================================
    st.subheader("🛡️ 안전잔액 비교")


    if reserve_gap >= 0:

        st.success(
            f"충격 발생 후에도 최소 안전잔액을 유지하고 "
            f"**{reserve_gap:,.0f}원**의 여유가 남습니다."
        )


    else:

        shortage = abs(
            reserve_gap
        )

        st.warning(
            f"충격 발생 후 최소 안전잔액보다 "
            f"**{shortage:,.0f}원 부족**합니다."
        )


    # =====================================================
    # 10. 금융 회복력 점수
    # =====================================================
    st.subheader("📈 금융 회복력 점수")


    if safety_reserve > 0:

        resilience_ratio = (
            stressed_balance
            / safety_reserve
        )


        resilience_score = round(
            max(
                0,
                min(
                    100,
                    resilience_ratio * 100
                )
            )
        )


    else:

        if stressed_balance >= 0:

            resilience_score = 100

        else:

            resilience_score = 0


    st.progress(
        resilience_score / 100
    )


    st.write(
        f"### {resilience_score} / 100"
    )


    if resilience_score >= 100:

        st.caption(
            "충격 이후에도 설정한 안전잔액 이상을 유지합니다."
        )

    elif resilience_score >= 50:

        st.caption(
            "충격은 버틸 수 있지만 금융 여유가 크게 줄어듭니다."
        )

    else:

        st.caption(
            "충격 상황에서 금융 여유가 매우 낮은 상태입니다."
        )


    # =====================================================
    # 11. 결과 해석
    # =====================================================
    st.subheader("🔎 결과 해석")


    if result["status_code"] == "safe":

        st.write(
            "현재 소비는 선택한 스트레스 상황에서도 "
            "비교적 안정적으로 감당할 수 있습니다."
        )


    elif result["status_code"] == "warning":

        st.write(
            "현재 소비 자체는 가능하지만, "
            "예상치 못한 상황이 발생하면 안전자금이 부족해질 수 있습니다."
        )


    else:

        st.write(
            "현재 소비 후 충격 상황이 발생하면 "
            "필수지출이나 저축 계획을 유지하기 어려울 가능성이 있습니다."
        )


    # =====================================================
    # 12. 소비 전·후 스트레스 비교
    # =====================================================
    st.subheader("🧮 이 구매가 없었다면?")


    balance_without_purchase = (
        result["stressed_income"]
        - current_spending
        - fixed_expense
        - saving_goal
        - unexpected_expense
    )


    purchase_impact = (
        balance_without_purchase
        - stressed_balance
    )


    compare1, compare2 = st.columns(2)


    with compare1:

        st.metric(
            "구매하지 않았을 경우",
            f"{balance_without_purchase:,.0f}원"
        )


    with compare2:

        st.metric(
            "현재 구매 후",
            f"{stressed_balance:,.0f}원",
            delta=f"-{purchase_impact:,.0f}원"
        )


    st.caption(
        "※ 두 값의 차이는 현재 분석 중인 구매가 "
        "스트레스 상황에서 차지하는 부담을 보여줍니다."
    )


    # =====================================================
    # 13. 4페이지 결과 저장
    # =====================================================
    st.session_state[
        "stress_scenario"
    ] = stress_scenario

    st.session_state[
        "stress_income_drop"
    ] = income_drop

    st.session_state[
        "stress_unexpected_expense"
    ] = unexpected_expense

    st.session_state[
        "stress_balance"
    ] = stressed_balance

    st.session_state[
        "stress_status"
    ] = result["status"]

    st.session_state[
        "stress_status_code"
    ] = result["status_code"]

    st.session_state[
        "resilience_score"
    ] = resilience_score

    st.session_state[
        "stress_test_completed"
    ] = True


    # =====================================================
    # 14. 최종 요약
    # =====================================================
    st.divider()

    st.header("📝 최종 요약")


    st.write(
        f"현재 소비 판단은 **{purchase_status}**입니다."
    )

    st.write(
        f"선택한 **{stress_scenario}** 상황을 적용하면 "
        f"금융상태는 **{result['status']}**으로 평가됩니다."
    )

    st.write(
        f"스트레스 상황 발생 후 예상 가용자금은 "
        f"**{stressed_balance:,.0f}원**입니다."
    )


    if result["status_code"] == "safe":

        st.success(
            "현재 소비는 선택한 스트레스 상황에서도 "
            "안전잔액을 유지할 수 있습니다."
        )


    elif result["status_code"] == "warning":

        st.warning(
            "현재 소비는 가능하지만, "
            "충격 상황을 고려하면 소비 규모를 조금 줄이거나 "
            "안전자금을 더 확보하는 것이 좋습니다."
        )


    else:

        st.error(
            "현재 소비는 스트레스 상황에서 재정적 부담이 커질 수 있습니다. "
            "구매 연기 또는 소비 규모 축소를 고려해보세요."
        )
