import streamlit as st


# =========================================================
# 페이지 설정
# =========================================================
st.set_page_config(
    page_title="금융 스트레스 테스트",
    page_icon="⚠️",
    layout="wide",
)

st.title("⚠️ 이 구매 후, 내 금융 여유는 얼마나 버틸까?")

st.write(
    "3번에서 확인한 **구매 후 남는 돈**을 기준으로, "
    "예상치 못한 상황이 생겼을 때 내 금융 여유가 얼마나 빠르게 줄어드는지 확인합니다."
)

st.info(
    "스트레스 지수는 미래를 예측하는 점수가 아니라, "
    "**선택한 충격이 구매 후 여유자금의 몇 %를 소진하는지** 보여주는 MVP 지표입니다."
)


# =========================================================
# 데이터 불러오기
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
        usable_money - spent_so_far - essential_remaining
    )

if (
    available_after_purchase is None
    and available_before_purchase is not None
    and purchase_price > 0
):
    available_after_purchase = (
        available_before_purchase - purchase_price
    )


def money(value):
    return f"{int(round(value)):,}원"


def stress_index(shock, base):
    if base <= 0:
        return 100.0 if shock > 0 else 0.0
    return (shock / base) * 100


def stress_level(index):
    if index < 30:
        return "🟢", "여유 있음"
    if index < 60:
        return "🟡", "부담 증가"
    if index < 90:
        return "🟠", "취약"
    if index <= 100:
        return "🔴", "매우 취약"
    return "🚨", "자금 부족"


def money_options(min_value, max_value, step=10_000):
    min_value = int(min_value)
    max_value = int(max_value)
    step = int(step)

    values = list(range(min_value, max_value + 1, step))
    if not values:
        values = [min_value]

    if values[-1] < max_value:
        values.append(max_value)

    return sorted(set(values))


def money_slider(label, min_value, max_value, value, step=10_000, help=None):
    options = money_options(min_value, max_value, step)
    nearest = min(options, key=lambda x: abs(x - int(value)))

    return st.select_slider(
        label,
        options=options,
        value=nearest,
        format_func=lambda x: f"{x:,}원",
        help=help,
    )


analysis_ready = (
    isinstance(monthly_finance, dict)
    and usable_money > 0
    and available_before_purchase is not None
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
# 1. 구매 후 금융 여유
# =========================================================
st.header("1️⃣ 구매 후 금융 여유")

c1, c2, c3 = st.columns(3)

with c1:
    st.metric("이번 구매", money(purchase_price))

with c2:
    st.metric("구매 전 자유자금", money(available_before_purchase))

with c3:
    st.metric("구매 후 남는 돈", money(available_after_purchase))

if available_after_purchase <= 0:
    st.error(
        "현재 구매만으로도 이번 달 자유자금이 모두 소진됩니다. "
        "추가 충격을 감당할 여유가 없습니다."
    )
    st.stop()

st.success(
    f"🛡️ 현재 구매 후 **최대 {money(available_after_purchase)}까지의 추가 충격**을 "
    "잔액 부족 없이 흡수할 수 있습니다."
)

st.divider()


# =========================================================
# 2. 기본 충격 시나리오 한눈에 보기
# =========================================================
st.header("2️⃣ 어느 정도 충격부터 위험해질까?")

st.caption(
    "아래는 구매 후 남는 돈을 기준으로 한 간단한 충격 시나리오입니다."
)

# 사용자의 구매 후 잔액에 비례한 3단계 시나리오.
# 10,000원 단위로 반올림하되 최소 10,000원.
scenario_amounts = []
for ratio in (0.25, 0.60, 1.20):
    amount = max(
        10_000,
        int(round((available_after_purchase * ratio) / 10_000) * 10_000),
    )
    scenario_amounts.append(amount)

scenario_amounts = sorted(set(scenario_amounts))

cols = st.columns(len(scenario_amounts))

for col, shock in zip(cols, scenario_amounts):
    idx = stress_index(shock, available_after_purchase)
    icon, label = stress_level(idx)
    remaining = available_after_purchase - shock

    with col:
        st.markdown(f"**충격 {money(shock)}**")
        st.metric(
            "충격 후 잔액",
            money(remaining),
        )
        st.write(f"{icon} **{label} · {idx:.1f}%**")

st.caption(
    "※ 위 금액은 개인별 구매 후 여유자금에 비례해 보여주는 예시이며, "
    "특정 미래 상황을 예측한 값은 아닙니다."
)

st.divider()


# =========================================================
# 3. 직접 스트레스 테스트
# =========================================================
st.header("3️⃣ 내 상황으로 테스트하기")

stress_scenario = st.radio(
    "어떤 상황을 가정할까요?",
    [
        "💸 갑작스러운 지출",
        "📉 이번 달 쓸 수 있는 돈 감소",
        "⚡ 둘 다 발생",
    ],
    horizontal=True,
)

income_drop = 0
unexpected_expense = 0

max_money_shock = max(
    500_000,
    usable_money,
    available_after_purchase * 2,
)

if stress_scenario == "💸 갑작스러운 지출":
    unexpected_expense = money_slider(
        "예상치 못한 지출",
        min_value=10_000,
        max_value=max_money_shock,
        value=min(100_000, max_money_shock),
        step=10_000,
        help="예: 병원비, 수리비, 갑작스러운 교통비나 생활비 등",
    )

elif stress_scenario == "📉 이번 달 쓸 수 있는 돈 감소":
    drop_rate = st.slider(
        "이번 달 쓸 수 있는 돈 감소율",
        min_value=5,
        max_value=100,
        value=20,
        step=5,
        format="%d%%",
        help="이번 달 실제 사용할 수 있는 돈이 예상보다 줄어드는 상황입니다.",
    )

    income_drop = round(usable_money * drop_rate / 100)

    st.caption(
        f"가용금액이 **{money(income_drop)} 감소**하는 상황입니다."
    )

else:
    left, right = st.columns(2)

    with left:
        drop_rate = st.slider(
            "가용금액 감소율",
            min_value=5,
            max_value=100,
            value=20,
            step=5,
            format="%d%%",
        )
        income_drop = round(usable_money * drop_rate / 100)
        st.caption(f"가용금액 **-{money(income_drop)}**")

    with right:
        unexpected_expense = money_slider(
            "추가 지출",
            min_value=10_000,
            max_value=max_money_shock,
            value=min(100_000, max_money_shock),
            step=10_000,
        )

st.write("")

run_test = st.button(
    "⚡ 스트레스 테스트 실행",
    type="primary",
    use_container_width=True,
)


# =========================================================
# 4. 결과
# =========================================================
if run_test:
    total_shock = income_drop + unexpected_expense

    stressed_balance = (
        available_after_purchase - total_shock
    )

    balance_without_purchase = (
        available_before_purchase - total_shock
    )

    after_index = stress_index(
        total_shock,
        available_after_purchase,
    )

    before_index = stress_index(
        total_shock,
        available_before_purchase,
    )

    after_icon, after_label = stress_level(after_index)
    before_icon, before_label = stress_level(before_index)

    index_change = after_index - before_index

    st.divider()
    st.header("4️⃣ 스트레스 결과")

    # -----------------------------------------------------
    # 핵심 스트레스 지수
    # -----------------------------------------------------
    st.markdown(
        f"## {after_icon} 스트레스 지수 **{after_index:.1f}% · {after_label}**"
    )

    if after_index <= 100:
        st.write(
            f"선택한 충격 **{money(total_shock)}**이 "
            f"구매 후 여유자금 **{money(available_after_purchase)}의 "
            f"{after_index:.1f}%**를 소진합니다."
        )
    else:
        st.write(
            f"선택한 충격 **{money(total_shock)}**이 구매 후 여유자금을 초과합니다."
        )

    progress_value = min(after_index / 100, 1.0)
    st.progress(progress_value)

    if stressed_balance < 0:
        st.error(
            f"🚨 충격 후 **{money(abs(stressed_balance))}이 부족**합니다."
        )
    elif after_index >= 90:
        st.error(
            f"🔴 잔액은 플러스지만 **{money(stressed_balance)}만 남아 "
            "충격 흡수 여유가 거의 없습니다.**"
        )
    elif after_index >= 60:
        st.warning(
            f"🟠 충격 후 **{money(stressed_balance)}이 남지만 "
            "금융 여유가 크게 줄어듭니다.**"
        )
    elif after_index >= 30:
        st.warning(
            f"🟡 충격 후 **{money(stressed_balance)}이 남습니다.** "
            "현재보다 부담이 커지는 상황입니다."
        )
    else:
        st.success(
            f"🟢 충격 후에도 **{money(stressed_balance)}이 남아 "
            "상대적으로 여유가 있습니다.**"
        )

    # -----------------------------------------------------
    # 돈의 흐름
    # -----------------------------------------------------
    st.subheader("💥 충격이 오면 돈은 이렇게 변합니다")

    flow1, flow2, flow3 = st.columns(3)

    with flow1:
        st.metric(
            "구매 후 여유자금",
            money(available_after_purchase),
        )

    with flow2:
        st.metric(
            "선택한 충격",
            f"-{money(total_shock)}",
        )

    with flow3:
        st.metric(
            "충격 후",
            money(stressed_balance),
        )

    st.write(
        f"**{money(available_after_purchase)} → "
        f"-{money(total_shock)} → {money(stressed_balance)}**"
    )

    # -----------------------------------------------------
    # 구매 전후 스트레스 비교
    # -----------------------------------------------------
    st.subheader("🧮 이 구매가 금융 스트레스에 미친 영향")

    compare1, compare2 = st.columns(2)

    with compare1:
        st.markdown("**이 구매가 없었다면**")
        st.metric(
            "충격 후 남는 돈",
            money(balance_without_purchase),
        )
        st.write(
            f"{before_icon} 스트레스 지수 "
            f"**{before_index:.1f}% · {before_label}**"
        )

    with compare2:
        st.markdown("**이번 구매를 한다면**")
        st.metric(
            "충격 후 남는 돈",
            money(stressed_balance),
        )
        st.write(
            f"{after_icon} 스트레스 지수 "
            f"**{after_index:.1f}% · {after_label}**"
        )

    if index_change > 0:
        st.warning(
            f"이번 구매로 같은 충격에 대한 스트레스 지수가 "
            f"**{index_change:.1f}%p 증가**합니다."
        )
    else:
        st.info(
            "현재 설정에서는 구매 전후 스트레스 지수 차이가 없습니다."
        )

    # -----------------------------------------------------
    # 핵심 결론
    # -----------------------------------------------------
    st.subheader("🔎 한눈에 보기")

    if stressed_balance < 0:
        st.write(
            f"이번 구매 후 **{stress_scenario}** 상황이 발생하면 "
            f"**{money(abs(stressed_balance))}이 부족**합니다. "
            "현재 구매가 예상치 못한 상황에 대응할 여유를 크게 줄입니다."
        )
    elif after_index >= 90:
        st.write(
            f"자금 부족까지는 아니지만 충격 후 **{money(stressed_balance)}만 남습니다.** "
            "현재 구매 후 금융 여유가 매우 취약한 상태입니다."
        )
    elif after_index >= 60:
        st.write(
            f"충격 후 **{money(stressed_balance)}이 남지만**, "
            "구매 후 여유자금의 상당 부분이 소진됩니다."
        )
    else:
        st.write(
            f"현재 설정한 충격 이후에도 **{money(stressed_balance)}이 남습니다.** "
            "다만 충격 규모를 바꿔 어느 수준부터 취약해지는지 함께 확인해보세요."
        )

    # -----------------------------------------------------
    # 결과 저장
    # -----------------------------------------------------
    st.session_state["stress_scenario"] = stress_scenario
    st.session_state["stress_total_shock"] = total_shock
    st.session_state["stress_income_drop"] = income_drop
    st.session_state["stress_unexpected_expense"] = unexpected_expense
    st.session_state["stress_balance"] = stressed_balance
    st.session_state["stress_index"] = after_index
    st.session_state["stress_index_before_purchase"] = before_index
    st.session_state["stress_index_change"] = index_change
    st.session_state["stress_status"] = after_label
    st.session_state["stress_test_completed"] = True

    st.caption(
        "※ 스트레스 지수는 공인 신용평가·재무건전성 지표가 아닙니다. "
        "선택한 충격 ÷ 해당 시점의 자유자금 × 100으로 계산한 "
        "소비 의사결정 보조용 지표입니다."
    )
