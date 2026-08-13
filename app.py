import itertools

import streamlit as st
from openai import OpenAI


# --------------------------------------------------
# 1. 기본 페이지 설정
# --------------------------------------------------

st.set_page_config(
    page_title="AI Finance",
    page_icon="💳",
    layout="wide"
)

st.title("💳 AI Finance")
st.subheader("혜택은 최대로, 소비는 현명하게")

st.write(
    "사용 가능한 쿠폰·통신사·카드 혜택을 조합해 "
    "가장 유리한 결제 방법을 찾고, "
    "현재 나의 소비 여력까지 함께 분석합니다."
)

st.info(
    "현재 버전은 공모전 MVP용 데모입니다. "
    "카드·통신사 혜택은 실제 혜택이 아닌 예시 데이터입니다."
)


# --------------------------------------------------
# 2. 데모 혜택 데이터
# 나중에는 실제 카드/통신사/제휴 데이터로 교체
# --------------------------------------------------

TELCO_BENEFITS = {
    "통신사 멤버십 5% 할인": {
        "name": "통신사 멤버십 5% 할인",
        "category": "통신사",
        "discount_type": "percent",
        "value": 5,
        "max_discount": 3000,
        "min_purchase": 10000,
        "stage": 2,
    },

    "통신사 멤버십 3,000원 할인": {
        "name": "통신사 멤버십 3,000원 할인",
        "category": "통신사",
        "discount_type": "fixed",
        "value": 3000,
        "max_discount": 3000,
        "min_purchase": 30000,
        "stage": 2,
    },
}


CARD_BENEFITS = {
    "A카드 5% 할인": {
        "name": "A카드 5% 할인",
        "category": "카드",
        "discount_type": "percent",
        "value": 5,
        "max_discount": 5000,
        "min_purchase": 20000,
        "stage": 3,
    },

    "B카드 3,000원 할인": {
        "name": "B카드 3,000원 할인",
        "category": "카드",
        "discount_type": "fixed",
        "value": 3000,
        "max_discount": 3000,
        "min_purchase": 30000,
        "stage": 3,
    },

    "C카드 7% 할인": {
        "name": "C카드 7% 할인",
        "category": "카드",
        "discount_type": "percent",
        "value": 7,
        "max_discount": 4000,
        "min_purchase": 40000,
        "stage": 3,
    },
}


# --------------------------------------------------
# 3. 할인금액 계산 함수
# --------------------------------------------------

def calculate_discount(current_price, benefit):

    if current_price < benefit["min_purchase"]:
        return 0

    if benefit["discount_type"] == "percent":

        discount = current_price * (
            benefit["value"] / 100
        )

    else:

        discount = benefit["value"]

    max_discount = benefit.get("max_discount")

    if max_discount:
        discount = min(
            discount,
            max_discount
        )

    discount = min(
        discount,
        current_price
    )

    return round(discount)


# --------------------------------------------------
# 4. 하나의 결제 조합 계산
# --------------------------------------------------

def apply_combination(original_price, benefits):

    current_price = original_price

    result_steps = []

    # 쿠폰 → 통신사 → 카드 순으로 적용
    benefits = sorted(
        benefits,
        key=lambda x: x["stage"]
    )

    for benefit in benefits:

        discount = calculate_discount(
            current_price,
            benefit
        )

        if discount > 0:

            current_price -= discount

            result_steps.append(
                {
                    "혜택": benefit["name"],
                    "할인금액": discount,
                    "적용 후 금액": current_price,
                }
            )

    return round(current_price), result_steps


# --------------------------------------------------
# 5. 가능한 모든 결제 조합 비교
# --------------------------------------------------

def find_best_combination(
    original_price,
    coupon,
    selected_telcos,
    selected_cards
):

    coupon_options = [None]

    if coupon:
        coupon_options.append(coupon)

    telco_options = [None]

    for name in selected_telcos:
        telco_options.append(
            TELCO_BENEFITS[name]
        )

    card_options = [None]

    for name in selected_cards:
        card_options.append(
            CARD_BENEFITS[name]
        )

    results = []

    for coupon_item, telco_item, card_item in itertools.product(
        coupon_options,
        telco_options,
        card_options
    ):

        benefits = [
            item
            for item in [
                coupon_item,
                telco_item,
                card_item
            ]
            if item is not None
        ]

        final_price, steps = apply_combination(
            original_price,
            benefits
        )

        results.append(
            {
                "final_price": final_price,
                "steps": steps,
                "benefits": benefits,
            }
        )

    best_result = min(
        results,
        key=lambda x: x["final_price"]
    )

    return best_result


# --------------------------------------------------
# 6. 개인 소비 가능 여부 판단
# --------------------------------------------------

def evaluate_purchase(
    income,
    spent,
    fixed_expense,
    saving_goal,
    final_price
):

    available_before_purchase = (
        income
        - spent
        - fixed_expense
        - saving_goal
    )

    available_after_purchase = (
        available_before_purchase
        - final_price
    )

    if available_after_purchase < 0:

        status = "🔴 구매 연기 권장"

    elif available_after_purchase < income * 0.1:

        status = "🟡 주의 필요"

    else:

        status = "🟢 구매 가능"

    return (
        available_before_purchase,
        available_after_purchase,
        status
    )


# --------------------------------------------------
# 7. 금융 스트레스 테스트
# --------------------------------------------------

def stress_test(
    income,
    spent,
    fixed_expense,
    saving_goal,
    final_price,
    income_drop,
    unexpected_expense
):

    stressed_income = max(
        0,
        income - income_drop
    )

    stressed_balance = (
        stressed_income
        - spent
        - fixed_expense
        - saving_goal
        - final_price
        - unexpected_expense
    )

    if stressed_balance < 0:

        result = "🔴 위험"

    elif stressed_balance < income * 0.05:

        result = "🟡 주의"

    else:

        result = "🟢 안정"

    return stressed_balance, result


# --------------------------------------------------
# 8. OpenAI에게 결과 설명 요청
# --------------------------------------------------

def get_ai_advice(
    store,
    original_price,
    best_result,
    purchase_status,
    remaining_money,
    stress_status,
    stress_balance
):

    try:

        api_key = st.secrets["OPENAI_API_KEY"]

    except Exception:

        return None

    client = OpenAI(
        api_key=api_key
    )

    benefit_names = [
        benefit["name"]
        for benefit
        in best_result["benefits"]
    ]

    prompt = f"""
너는 사용자의 합리적인 소비 결정을 돕는 AI 금융 비서다.

다음 계산 결과를 바꾸거나 새로 계산하지 말고,
주어진 결과를 바탕으로 소비자가 이해하기 쉽게 설명해라.

구매처: {store}
원래 가격: {original_price:,.0f}원
추천 혜택 조합: {benefit_names}
최종 예상 부담액: {best_result["final_price"]:,.0f}원
총 절약 금액: {original_price - best_result["final_price"]:,.0f}원

소비 판단: {purchase_status}
구매 후 남는 금액: {remaining_money:,.0f}원

스트레스 테스트 결과: {stress_status}
스트레스 상황에서 남는 금액: {stress_balance:,.0f}원

아래 형식으로 짧고 명확하게 답해라.

1. 추천 결제 방법
2. 이 조합이 유리한 이유
3. 현재 구매에 대한 판단
4. 주의해야 할 점

한국어로 답하고 과도하게 장황하게 설명하지 마라.
"""

    try:

        response = client.responses.create(
            model="gpt-5.6-luna",
            input=prompt
        )

        return response.output_text

    except Exception as e:

        return (
            "AI 분석 중 오류가 발생했습니다.\n\n"
            f"{e}"
        )


# --------------------------------------------------
# 9. 사용자 입력 화면
# --------------------------------------------------

st.divider()

st.header("🛍 1. 구매 정보")

store = st.text_input(
    "구매처",
    value="올리브영"
)

original_price = st.number_input(
    "상품 가격",
    min_value=0,
    value=50000,
    step=1000
)


# --------------------------------------------------
# 쿠폰
# --------------------------------------------------

st.header("🎟 2. 보유 쿠폰")

use_coupon = st.checkbox(
    "사용 가능한 쿠폰이 있어요"
)

coupon = None

if use_coupon:

    coupon_name = st.text_input(
        "쿠폰 이름",
        value="올리브영 20% 쿠폰"
    )

    coupon_type = st.selectbox(
        "쿠폰 종류",
        [
            "퍼센트 할인",
            "정액 할인"
        ]
    )

    if coupon_type == "퍼센트 할인":

        coupon_value = st.number_input(
            "할인율 (%)",
            min_value=0,
            max_value=100,
            value=20
        )

        discount_type = "percent"

    else:

        coupon_value = st.number_input(
            "할인금액 (원)",
            min_value=0,
            value=5000,
            step=1000
        )

        discount_type = "fixed"

    coupon_min = st.number_input(
        "최소 구매금액",
        min_value=0,
        value=30000,
        step=1000
    )

    coupon_max = st.number_input(
        "최대 할인금액",
        min_value=0,
        value=10000,
        step=1000
    )

    coupon = {
        "name": coupon_name,
        "category": "쿠폰",
        "discount_type": discount_type,
        "value": coupon_value,
        "max_discount": coupon_max,
        "min_purchase": coupon_min,
        "stage": 1,
    }


# --------------------------------------------------
# 통신사 / 카드
# --------------------------------------------------

st.header("📱 3. 보유 멤버십 및 결제수단")

selected_telcos = st.multiselect(
    "사용 가능한 통신사·멤버십 혜택",
    list(TELCO_BENEFITS.keys())
)

selected_cards = st.multiselect(
    "보유 카드",
    list(CARD_BENEFITS.keys())
)


# --------------------------------------------------
# 개인 소비정보
# --------------------------------------------------

st.header("💰 4. 나의 소비 상황")

col1, col2 = st.columns(2)

with col1:

    income = st.number_input(
        "이번 달 소득",
        min_value=0,
        value=1000000,
        step=10000
    )

    spent = st.number_input(
        "이번 달 현재까지 지출",
        min_value=0,
        value=500000,
        step=10000
    )

with col2:

    fixed_expense = st.number_input(
        "앞으로 예정된 고정지출",
        min_value=0,
        value=200000,
        step=10000
    )

    saving_goal = st.number_input(
        "이번 달 저축 목표",
        min_value=0,
        value=200000,
        step=10000
    )


# --------------------------------------------------
# 스트레스 테스트
# --------------------------------------------------

st.header("⚠️ 5. 금융 스트레스 테스트")

col3, col4 = st.columns(2)

with col3:

    unexpected_expense = st.number_input(
        "예상치 못한 추가 지출",
        min_value=0,
        value=100000,
        step=10000
    )

with col4:

    income_drop = st.number_input(
        "예상 소득 감소",
        min_value=0,
        value=0,
        step=10000
    )


# --------------------------------------------------
# 분석 버튼
# --------------------------------------------------

st.divider()

if st.button(
    "✨ AI 최적 결제 분석하기",
    type="primary",
    use_container_width=True
):

    if original_price <= 0:

        st.warning(
            "상품 가격을 입력해주세요."
        )

    else:

        best_result = find_best_combination(
            original_price,
            coupon,
            selected_telcos,
            selected_cards
        )

        (
            available_before,
            available_after,
            purchase_status
        ) = evaluate_purchase(
            income,
            spent,
            fixed_expense,
            saving_goal,
            best_result["final_price"]
        )

        (
            stress_balance,
            stress_status
        ) = stress_test(
            income,
            spent,
            fixed_expense,
            saving_goal,
            best_result["final_price"],
            income_drop,
            unexpected_expense
        )

        st.divider()

        st.header("🏆 최적 결제 결과")

        metric1, metric2, metric3 = st.columns(3)

        with metric1:

            st.metric(
                "원래 가격",
                f'{original_price:,.0f}원'
            )

        with metric2:

            st.metric(
                "최종 예상 부담액",
                f'{best_result["final_price"]:,.0f}원'
            )

        with metric3:

            saving = (
                original_price
                - best_result["final_price"]
            )

            st.metric(
                "총 절약 금액",
                f"{saving:,.0f}원"
            )


        # 결제 순서
        st.subheader("📋 추천 결제 순서")

        if best_result["steps"]:

            for number, step in enumerate(
                best_result["steps"],
                start=1
            ):

                st.write(
                    f'**{number}. {step["혜택"]}** '
                    f'→ {step["할인금액"]:,.0f}원 할인 '
                    f'→ {step["적용 후 금액"]:,.0f}원'
                )

        else:

            st.write(
                "현재 입력된 혜택 중 "
                "적용 가능한 할인 혜택이 없습니다."
            )


        # 소비 판단
        st.subheader("💰 소비 가능 여부")

        st.write(
            f"### {purchase_status}"
        )

        st.write(
            f"구매 전 사용 가능 금액: "
            f"**{available_before:,.0f}원**"
        )

        st.write(
            f"구매 후 남는 금액: "
            f"**{available_after:,.0f}원**"
        )


        # 스트레스 테스트
        st.subheader("⚠️ 금융 스트레스 테스트")

        st.write(
            f"### {stress_status}"
        )

        st.write(
            "예상치 못한 지출 및 소득 감소 발생 후 "
            f"남는 금액: **{stress_balance:,.0f}원**"
        )


        # AI
        st.subheader("🤖 AI 맞춤 분석")

        with st.spinner(
            "AI가 결과를 분석하고 있습니다..."
        ):

            ai_advice = get_ai_advice(
                store,
                original_price,
                best_result,
                purchase_status,
                available_after,
                stress_status,
                stress_balance
            )

        if ai_advice:

            st.write(ai_advice)

        else:

            st.info(
                "OpenAI API Key를 연결하면 "
                "여기에 AI 맞춤 분석이 표시됩니다."
            )
