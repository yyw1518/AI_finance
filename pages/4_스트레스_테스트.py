import streamlit as st


# =========================================================
# 페이지 설정
# =========================================================
st.set_page_config(
    page_title="금융 스트레스 테스트",
    page_icon="⚠️",
    layout="wide",
)

st.title("⚠️ 예상치 못한 일이 생겨도 괜찮을까?")

st.write(
    "앞에서 계산한 구매 후 남는 돈을 기준으로, "
    "갑작스러운 지출이나 이번 달 가용금액 감소가 생겼을 때 "
    "얼마나 여유가 남는지 확인합니다."
)

st.info(
    "이 테스트는 미래를 예측하는 기능이 아니라, "
    "현재 소비 결정이 예상치 못한 상황에 얼마나 취약한지 확인하는 간단한 시뮬레이션입니다."
)


# =========================================================
# 1. 3번 페이지 데이터 불러오기
# =========================================================
monthly_finance = st.session_state.get("monthly_finance", {})

usable_money = int(monthly_finance.get("usable_money", 0) or 0)
spent_so_far = int(monthly_finance.get("spent_so_far", 0) or 0)
essential_remaining = int(monthly_finance.get("essential_remaining", 0) or 0)

purchase_price = int(
    st.session_state.get(
        "finance_purchase_price",
        st.session_state.get(
            "optimized_final_price",
            st.session_state.get("final_payment", 0),
        ),
    )
    or 0
)

available_before_purchase = st.session_state.get(
    "finance_available_before_purchase"
)

available_after_purchase = st.session_state.get(
    "finance_available_after_purchase"
)

if available_before_purchase is None and usable_money > 0:
    available_before_purchase = (
        usable_money
        - spent_so_far
        - essential_remaining
    )

if (
    available_after_purchase is None
    and available_before_purchase is not None
    and purchase_price > 0
):
    available_after_purchase = (
        available_before_purchase
        - purchase_price
    )


def money(value):
    return f"{int(round(value)):,}원"


def money_options(min_value, max_value, step=10_000):
    values = list(range(int(min_value), int(max_value) + 1, int(step)))
    if not values:
        values = [int(min_value)]
    return values


def money_select_slider(label, min_value, max_value, value, step=10_000, help=None):
    options = money_options(min_value, max_value, step)
    nearest = min(options, key=lambda x: abs(x - int(value)))
    return st.select_slider(
        label,
        options=options,
        value=nearest,
        format_func=lambda x: f"{x:,}원",
        help=help,
    )


# 3번 소비 판단을 완료했는지 새 구조 기준으로 확인
analysis_ready = (
    isinstance(monthly_finance, dict)
    and usable_money > 0
    and available_after_purchase is not None
    and purchase_price > 0
)

if not analysis_ready:
    st.warning(
        "먼저 **3_소비_판단** 페이지에서 "
        "**저장하고 이 소비 분석하기**를 눌러주세요."
    )
    st.stop()


# =========================================================
# 2. 현재 상태
# =========================================================
st.header("1️⃣ 현재 상태")

c1, c2, c3 = st.columns(3)

with c1:
    st.metric(
        "이번 구매",
        money(purchase_price),
    )

with c2:
    st.metric(
        "구매 전 자유자금",
        money(available_before_purchase),
    )

with c3:
    st.metric(
        "구매 후 남는 돈",
        money(available_after_purchase),
    )

if available_after_purchase < 0:
    st.error(
        "현재 입력값 기준으로는 이미 구매 후 잔액이 부족합니다. "
        "스트레스 테스트보다 구매 규모 조정이 우선입니다."
    )
    st.stop()

st.divider()


# =========================================================
# 3. 스트레스 상황 선택
# =========================================================
st.header("2️⃣ 만약 이런 일이 생긴다면?")

stress_scenario = st.radio(
    "테스트할 상황을 선택해주세요.",
    [
        "💸 갑작스러운 지출",
        "📉 이번 달 쓸 수 있는 돈 감소",
        "⚡ 둘 다 발생",
    ],
    horizontal=True,
)

income_drop = 0
unexpected_expense = 0


if stress_scenario == "💸 갑작스러운 지출":
    unexpected_expense = money_select_slider(
        "예상치 못한 지출이 얼마나 생긴다고 가정할까요?",
        min_value=10_000,
        max_value=max(500_000, usable_money),
        value=min(100_000, max(10_000, usable_money)),
        step=10_000,
        help="예: 병원비, 수리비, 교통비, 갑작스러운 모임비 등",
    )

elif stress_scenario == "📉 이번 달 쓸 수 있는 돈 감소":
    drop_rate = st.slider(
        "이번 달 쓸 수 있는 돈이 얼마나 줄어든다고 가정할까요?",
        min_value=5,
        max_value=100,
        value=20,
        step=5,
        format="%d%%",
        help="월급·용돈·생활비 등 이번 달 실제 가용금액이 예상보다 줄어드는 상황입니다.",
    )

    income_drop = round(
        usable_money * drop_rate / 100
    )

    st.caption(
        f"현재 입력한 {money(usable_money)}에서 "
        f"약 **{money(income_drop)}** 감소하는 상황입니다."
    )

else:
    col_a, col_b = st.columns(2)

    with col_a:
        drop_rate = st.slider(
            "가용금액 감소율",
            min_value=5,
            max_value=100,
            value=20,
            step=5,
            format="%d%%",
        )

        income_drop = round(
            usable_money * drop_rate / 100
        )

        st.caption(
            f"가용금액 **-{money(income_drop)}**"
        )

    with col_b:
        unexpected_expense = money_select_slider(
            "추가 지출",
            min_value=10_000,
            max_value=max(500_000, usable_money),
            value=min(100_000, max(10_000, usable_money)),
            step=10_000,
        )

st.write("")

run_test = st.button(
    "⚡ 스트레스 테스트 실행",
    type="primary",
    use_container_width=True,
)


# =========================================================
# 4. 테스트 계산
# =========================================================
if run_test:
    # 구매를 이미 실행한 상태를 기준으로 충격을 추가 적용
    stressed_balance = (
        available_after_purchase
        - income_drop
        - unexpected_expense
    )

    # 구매하지 않았다면 같은 충격에서 얼마나 남는지
    balance_without_purchase = (
        available_before_purchase
        - income_drop
        - unexpected_expense
    )

    st.divider()
    st.header("3️⃣ 결과")

    if stressed_balance >= 0:
        st.success(
            f"🟢 **이 상황은 감당 가능합니다.**\n\n"
            f"충격이 발생해도 **{money(stressed_balance)}**이 남습니다."
        )
    else:
        shortage = abs(stressed_balance)

        st.error(
            f"🔴 **이 상황에서는 자금이 부족합니다.**\n\n"
            f"현재 소비 후 같은 상황이 발생하면 "
            f"**{money(shortage)} 부족**합니다."
        )

    # =====================================================
    # 5. 충격 전후 흐름
    # =====================================================
    st.subheader("💥 돈의 흐름")

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric(
            "구매 후",
            money(available_after_purchase),
        )

    with m2:
        st.metric(
            "가용금액 감소",
            f"-{money(income_drop)}",
        )

    with m3:
        st.metric(
            "추가 지출",
            f"-{money(unexpected_expense)}",
        )

    with m4:
        st.metric(
            "충격 후",
            money(stressed_balance),
        )

    # =====================================================
    # 6. 한 줄 해석
    # =====================================================
    total_shock = income_drop + unexpected_expense

    if available_after_purchase > 0:
        shock_ratio = (
            total_shock / available_after_purchase * 100
        )
    else:
        shock_ratio = 0

    if stressed_balance >= 0:
        st.caption(
            f"이번 충격은 구매 후 남아 있던 돈의 "
            f"**{shock_ratio:.1f}%**를 사용합니다."
        )
    else:
        st.caption(
            "구매 후 남는 돈보다 충격 규모가 더 커서 "
            "현재 월간 자금 범위를 벗어납니다."
        )

    # =====================================================
    # 7. 이 구매가 없었다면?
    # =====================================================
    st.subheader("🧮 이 구매가 없었다면?")

    compare1, compare2 = st.columns(2)

    with compare1:
        st.metric(
            "구매하지 않았을 경우",
            money(balance_without_purchase),
        )

    with compare2:
        st.metric(
            "현재 구매 후",
            money(stressed_balance),
            delta=f"-{money(purchase_price)}",
            delta_color="inverse",
        )

    if balance_without_purchase >= 0 and stressed_balance < 0:
        st.warning(
            "이 충격 자체는 원래 감당 가능하지만, "
            "이번 구매 이후에는 자금이 부족해집니다."
        )
    elif stressed_balance >= 0:
        st.write(
            f"이번 구매 때문에 같은 스트레스 상황에서 사용할 수 있는 여유자금이 "
            f"**{money(purchase_price)}** 줄어듭니다."
        )
    else:
        st.write(
            "구매 여부와 관계없이 현재 설정한 충격이 큰 편입니다. "
            "다만 구매를 하지 않았을 때보다 부족 폭은 줄어듭니다."
        )

    # =====================================================
    # 8. 다음 판단을 위한 요약
    # =====================================================
    st.subheader("🔎 한눈에 보기")

    if stressed_balance >= 0:
        st.write(
            f"현재 구매 후 **{stress_scenario}** 상황이 발생해도 "
            f"**{money(stressed_balance)}**이 남습니다."
        )
    else:
        st.write(
            f"현재 구매 후 **{stress_scenario}** 상황이 발생하면 "
            f"**{money(abs(stressed_balance))}**이 부족합니다."
        )

    # =====================================================
    # 9. 결과 저장
    # =====================================================
    st.session_state["stress_scenario"] = stress_scenario
    st.session_state["stress_income_drop"] = income_drop
    st.session_state["stress_unexpected_expense"] = unexpected_expense
    st.session_state["stress_balance"] = stressed_balance
    st.session_state["stress_status"] = (
        "감당 가능"
        if stressed_balance >= 0
        else "자금 부족"
    )
    st.session_state["stress_status_code"] = (
        "safe"
        if stressed_balance >= 0
        else "danger"
    )
    st.session_state["stress_test_completed"] = True
