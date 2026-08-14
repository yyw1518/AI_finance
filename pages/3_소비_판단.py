import streamlit as st


# =========================================================
# 페이지 설정
# =========================================================
st.set_page_config(
    page_title="소비 판단",
    page_icon="💰",
    layout="wide",
)

st.title("💰 소비 가능 여부 분석")

st.write(
    "앞에서 계산한 **최적 결제금액**을 기준으로 "
    "현재 나의 소득·지출·저축 계획을 함께 고려해 "
    "이번 소비가 감당 가능한 수준인지 확인합니다."
)

st.info(
    "이 페이지의 판단은 사용자가 직접 설정한 "
    "**최소 안전잔액**을 기준으로 합니다."
)


# =========================================================
# 1. 이전 페이지 데이터 불러오기
# =========================================================
optimized_final_price = st.session_state.get(
    "optimized_final_price"
)

original_total_price = st.session_state.get(
    "original_total_price"
)

best_payment_plan = st.session_state.get(
    "best_payment_plan"
)


# 2번 페이지를 거치지 않은 경우
if optimized_final_price is None:

    st.warning(
        "먼저 **2_최적_결제_추천** 페이지에서 "
        "최적 결제금액을 계산해주세요."
    )

    st.stop()


# =========================================================
# 2. 최적 결제 결과 요약
# =========================================================
st.header("1️⃣ 앞에서 찾은 최적 결제")

col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "상품 총액",
        f"{original_total_price:,.0f}원"
        if original_total_price is not None
        else "-"
    )


with col2:

    st.metric(
        "최적 결제금액",
        f"{optimized_final_price:,.0f}원"
    )


with col3:

    if original_total_price is not None:

        saving_amount = (
            original_total_price
            - optimized_final_price
        )

        st.metric(
            "혜택으로 절약",
            f"{saving_amount:,.0f}원"
        )

    else:

        st.metric(
            "혜택으로 절약",
            "-"
        )


# 결제 방식 간단 표시
if best_payment_plan:

    payment_count = len(
        best_payment_plan.get(
            "choices",
            []
        )
    )

    if payment_count <= 1:

        st.success(
            "💳 추천 방식: **한 번에 결제**"
        )

    else:

        st.success(
            f"💳 추천 방식: **{payment_count}회 분할 결제**"
        )


st.divider()


# =========================================================
# 3. 개인 금융 상황 입력
# =========================================================
st.header("2️⃣ 나의 이번 달 금융 상황")

st.write(
    "정확한 소비 판단을 위해 이번 달 기준으로 입력해주세요."
)


col_a, col_b = st.columns(2)


with col_a:

    monthly_income = st.number_input(
        "이번 달 사용 가능한 총소득",
        min_value=0,
        value=int(
            st.session_state.get(
                "monthly_income",
                1000000
            )
        ),
        step=10000,
        help=(
            "월급, 용돈, 아르바이트비 등 "
            "이번 달 실제 사용할 수 있는 소득을 입력하세요."
        ),
    )


    current_spending = st.number_input(
        "현재까지 이미 사용한 금액",
        min_value=0,
        value=int(
            st.session_state.get(
                "current_spending",
                400000
            )
        ),
        step=10000,
        help=(
            "이번 달 현재까지 이미 지출한 "
            "생활비·쇼핑비 등을 입력하세요."
        ),
    )


    saving_goal = st.number_input(
        "이번 달 저축 목표",
        min_value=0,
        value=int(
            st.session_state.get(
                "saving_goal",
                200000
            )
        ),
        step=10000,
        help=(
            "이번 달 반드시 저축하거나 "
            "투자하기로 계획한 금액입니다."
        ),
    )


with col_b:

    fixed_expense = st.number_input(
        "앞으로 예정된 필수 지출",
        min_value=0,
        value=int(
            st.session_state.get(
                "fixed_expense",
                200000
            )
        ),
        step=10000,
        help=(
            "교통비, 통신비, 월세, 식비 등 "
            "앞으로 반드시 지출해야 하는 금액입니다."
        ),
    )


    safety_reserve = st.number_input(
        "최소 안전잔액",
        min_value=0,
        value=int(
            st.session_state.get(
                "safety_reserve",
                100000
            )
        ),
        step=10000,
        help=(
            "예상하지 못한 상황에 대비해 "
            "이번 달 말까지 최소한 남겨두고 싶은 금액입니다."
        ),
    )


st.caption(
    "💡 안전잔액은 프로그램이 임의로 정하지 않고 "
    "사용자가 자신의 상황에 맞게 직접 설정합니다."
)


st.divider()


# =========================================================
# 4. 소비 가능 여부 계산 함수
# =========================================================
def evaluate_purchase(
    income,
    already_spent,
    future_fixed_expense,
    saving_target,
    reserve,
    purchase_price,
):

    # 구매 직전 실제 사용 가능한 자금
    available_before = (
        income
        - already_spent
        - future_fixed_expense
        - saving_target
    )


    # 이번 소비를 한 후 남는 자금
    available_after = (
        available_before
        - purchase_price
    )


    # 안전잔액과 비교한 여유분
    reserve_margin = (
        available_after
        - reserve
    )


    # -----------------------------
    # 판단 기준
    # -----------------------------
    if available_after < 0:

        status = "🔴 구매 연기 권장"

        status_code = "danger"

        explanation = (
            "현재 계획을 유지하면서 구매하면 "
            "이번 달 사용 가능한 자금이 부족해집니다."
        )


    elif available_after < reserve:

        status = "🟡 신중한 구매 권장"

        status_code = "warning"

        explanation = (
            "구매 자체는 가능하지만, "
            "구매 후 남는 금액이 설정한 최소 안전잔액보다 적습니다."
        )


    else:

        status = "🟢 구매 가능"

        status_code = "safe"

        explanation = (
            "구매 후에도 사용자가 설정한 "
            "최소 안전잔액을 유지할 수 있습니다."
        )


    return {
        "available_before":
            available_before,

        "available_after":
            available_after,

        "reserve_margin":
            reserve_margin,

        "status":
            status,

        "status_code":
            status_code,

        "explanation":
            explanation,
    }


# =========================================================
# 5. 분석 버튼
# =========================================================
if st.button(
    "✨ 지금 이 소비 괜찮은지 분석하기",
    type="primary",
    use_container_width=True,
):

    result = evaluate_purchase(
        income=monthly_income,
        already_spent=current_spending,
        future_fixed_expense=fixed_expense,
        saving_target=saving_goal,
        reserve=safety_reserve,
        purchase_price=optimized_final_price,
    )


    available_before = result[
        "available_before"
    ]

    available_after = result[
        "available_after"
    ]

    reserve_margin = result[
        "reserve_margin"
    ]


    # =====================================================
    # 6. 결과 표시
    # =====================================================
    st.divider()

    st.header("📊 소비 분석 결과")


    # -----------------------------------------------------
    # 핵심 판단
    # -----------------------------------------------------
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


    # -----------------------------------------------------
    # 핵심 수치
    # -----------------------------------------------------
    st.subheader("💵 구매 전·후 자금 변화")


    metric1, metric2, metric3 = st.columns(3)


    with metric1:

        st.metric(
            "구매 전 가용자금",
            f"{available_before:,.0f}원"
        )


    with metric2:

        st.metric(
            "이번 결제",
            f"-{optimized_final_price:,.0f}원"
        )


    with metric3:

        st.metric(
            "구매 후 가용자금",
            f"{available_after:,.0f}원"
        )


    # -----------------------------------------------------
    # 돈의 흐름
    # -----------------------------------------------------
    st.subheader("🔍 이번 달 돈의 흐름")


    flow_col1, flow_col2 = st.columns(2)


    with flow_col1:

        st.write("**이번 달 계획**")

        st.write(
            f"총소득: **{monthly_income:,.0f}원**"
        )

        st.write(
            f"현재까지 지출: **-{current_spending:,.0f}원**"
        )

        st.write(
            f"앞으로 예정된 필수지출: **-{fixed_expense:,.0f}원**"
        )

        st.write(
            f"저축 목표: **-{saving_goal:,.0f}원**"
        )


    with flow_col2:

        st.write("**이번 구매 반영 후**")

        st.write(
            f"구매 전 가용자금: "
            f"**{available_before:,.0f}원**"
        )

        st.write(
            f"최적 결제금액: "
            f"**-{optimized_final_price:,.0f}원**"
        )

        st.write(
            f"구매 후 남는 금액: "
            f"**{available_after:,.0f}원**"
        )

        st.write(
            f"설정한 안전잔액: "
            f"**{safety_reserve:,.0f}원**"
        )


    # -----------------------------------------------------
    # 안전잔액 비교
    # -----------------------------------------------------
    st.subheader("🛡️ 안전잔액 확인")


    if reserve_margin >= 0:

        st.success(
            f"구매 후에도 최소 안전잔액을 유지하고 "
            f"**{reserve_margin:,.0f}원**의 여유가 남습니다."
        )


    else:

        shortage = abs(
            reserve_margin
        )

        st.warning(
            f"구매 후 설정한 최소 안전잔액보다 "
            f"**{shortage:,.0f}원 부족**합니다."
        )


    # -----------------------------------------------------
    # 구매 부담 비율
    # 단순 참고 지표 — 판단 기준에는 사용하지 않음
    # -----------------------------------------------------
    st.subheader("📐 가용자금 대비 구매 비중")


    if available_before > 0:

        purchase_ratio = (
            optimized_final_price
            / available_before
            * 100
        )


        st.metric(
            "구매 전 가용자금 중 이번 소비 비중",
            f"{purchase_ratio:.1f}%"
        )


        st.caption(
            "※ 이 비율은 소비 규모를 이해하기 위한 "
            "참고 지표이며, 구매 가능 여부를 결정하는 "
            "기준으로 사용하지 않습니다."
        )


    else:

        st.info(
            "현재 계획대로라면 구매 전 가용자금이 "
            "0원 이하이므로 구매 비중을 계산하지 않습니다."
        )


    # =====================================================
    # 7. 4번 페이지에서 사용할 데이터 저장
    # =====================================================

    st.session_state[
        "monthly_income"
    ] = monthly_income

    st.session_state[
        "current_spending"
    ] = current_spending

    st.session_state[
        "fixed_expense"
    ] = fixed_expense

    st.session_state[
        "saving_goal"
    ] = saving_goal

    st.session_state[
        "safety_reserve"
    ] = safety_reserve


    st.session_state[
        "available_before_purchase"
    ] = available_before

    st.session_state[
        "available_after_purchase"
    ] = available_after

    st.session_state[
        "reserve_margin"
    ] = reserve_margin

    st.session_state[
        "purchase_status"
    ] = result["status"]

    st.session_state[
        "purchase_status_code"
    ] = result["status_code"]

    st.session_state[
        "purchase_analysis_completed"
    ] = True


    # =====================================================
    # 8. 다음 단계 안내
    # =====================================================
    st.divider()

    st.success(
        "✅ 소비 판단 결과를 저장했습니다."
    )

    st.write(
        "다음 **4_스트레스_테스트** 페이지에서는 "
        "이 소비를 한 뒤 갑작스러운 지출 증가나 "
        "소득 감소가 발생해도 버틸 수 있는지 확인합니다."
    )
  
