import streamlit as st
from openai import OpenAI
from functools import lru_cache
import itertools


# ==================================================
# 1. 기본 페이지 설정
# ==================================================

st.set_page_config(
    page_title="AI Finance",
    page_icon="💳",
    layout="wide"
)

st.title("💳 AI Finance")
st.subheader("혜택은 최대로, 소비는 현명하게")

st.write(
    "여러 상품과 쿠폰·멤버십·카드 혜택을 분석해 "
    "한 번에 결제할지, 나누어 결제할지까지 비교하고 "
    "가장 유리한 결제 방법을 찾습니다."
)

st.info(
    "현재 버전은 공모전 MVP용 데모입니다. "
    "카드·통신사 혜택은 실제 혜택이 아닌 예시 데이터입니다."
)


# ==================================================
# 2. 데모 혜택 데이터
#
# threshold_basis
# - original : 할인 전 거래금액을 최소사용금액 기준으로 판단
# - current  : 앞선 할인을 적용한 현재금액 기준으로 판단
#
# discount_basis
# - original : 최초 거래금액을 기준으로 할인율 계산
# - current  : 현재 결제금액을 기준으로 할인율 계산
#
# stage
# - 혜택 적용 순서
# ==================================================

TELCO_BENEFITS = {
    "통신사 멤버십 5% 할인": {
        "name": "통신사 멤버십 5% 할인",
        "category": "통신사",
        "discount_type": "percent",
        "value": 5,
        "max_discount": 3000,
        "min_purchase": 10000,
        "threshold_basis": "original",
        "discount_basis": "current",
        "stage": 2,
    },

    "통신사 멤버십 3,000원 할인": {
        "name": "통신사 멤버십 3,000원 할인",
        "category": "통신사",
        "discount_type": "fixed",
        "value": 3000,
        "max_discount": 3000,
        "min_purchase": 30000,
        "threshold_basis": "original",
        "discount_basis": "current",
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
        "threshold_basis": "current",
        "discount_basis": "current",
        "stage": 3,
    },

    "B카드 3,000원 할인": {
        "name": "B카드 3,000원 할인",
        "category": "카드",
        "discount_type": "fixed",
        "value": 3000,
        "max_discount": 3000,
        "min_purchase": 30000,
        "threshold_basis": "current",
        "discount_basis": "current",
        "stage": 3,
    },

    "C카드 7% 할인": {
        "name": "C카드 7% 할인",
        "category": "카드",
        "discount_type": "percent",
        "value": 7,
        "max_discount": 4000,
        "min_purchase": 40000,
        "threshold_basis": "current",
        "discount_basis": "current",
        "stage": 3,
    },
}


# ==================================================
# 3. 할인 계산
# ==================================================

def calculate_discount(
    original_price,
    current_price,
    benefit
):
    """
    하나의 혜택이 실제로 얼마 할인되는지 계산한다.
    """

    # 최소 구매금액 판단 기준
    if benefit.get(
        "threshold_basis",
        "current"
    ) == "original":

        threshold_price = original_price

    else:

        threshold_price = current_price


    if threshold_price < benefit["min_purchase"]:
        return 0


    # 퍼센트 할인 시 어떤 가격을 기준으로 할지 결정
    if benefit["discount_type"] == "percent":

        if benefit.get(
            "discount_basis",
            "current"
        ) == "original":

            discount_base = original_price

        else:

            discount_base = current_price

        discount = (
            discount_base
            * benefit["value"]
            / 100
        )

    else:

        discount = benefit["value"]


    max_discount = benefit.get(
        "max_discount"
    )

    if max_discount is not None:

        discount = min(
            discount,
            max_discount
        )


    # 결제금액보다 할인금액이 커질 수 없음
    discount = min(
        discount,
        current_price
    )

    return round(discount)


# ==================================================
# 4. 하나의 결제에 혜택 적용
# ==================================================

def apply_combination(
    original_price,
    benefits
):

    current_price = original_price
    result_steps = []


    # 데이터에 지정된 순서에 따라 적용
    sorted_benefits = sorted(
        benefits,
        key=lambda x: x.get(
            "stage",
            999
        )
    )


    for benefit in sorted_benefits:

        discount = calculate_discount(
            original_price,
            current_price,
            benefit
        )

        if discount > 0:

            current_price -= discount

            result_steps.append(
                {
                    "혜택": benefit["name"],
                    "할인금액": discount,
                    "적용 후 금액": round(
                        current_price
                    ),
                }
            )


    return (
        round(current_price),
        result_steps
    )


# ==================================================
# 5. 상품 분할 경우의 수 생성
# ==================================================

def generate_partitions(items):
    """
    상품들을 여러 결제로 나누는 모든 경우 생성.

    예:
    [A, B, C]

    ->
    [ABC]
    [A][BC]
    [B][AC]
    [C][AB]
    [A][B][C]
    """

    if not items:
        yield []
        return


    first = items[0]


    for smaller in generate_partitions(
        items[1:]
    ):

        # 새 그룹 생성
        yield [[first]] + smaller

        # 기존 그룹에 추가
        for index in range(
            len(smaller)
        ):

            new_partition = [
                group[:]
                for group in smaller
            ]

            new_partition[index] = (
                [first]
                + new_partition[index]
            )

            yield new_partition


# ==================================================
# 6. 한 거래에서 가장 좋은 혜택 찾기
# ==================================================

def find_best_for_transaction(
    transaction_price,
    coupon,
    selected_telcos,
    selected_cards
):

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


    best_result = None


    for telco, card in itertools.product(
        telco_options,
        card_options
    ):

        # 쿠폰이 다른 혜택과 중복 불가인 경우
        if (
            coupon is not None
            and not coupon.get(
                "stackable",
                True
            )
        ):

            benefits = [coupon]

        else:

            benefits = [
                benefit
                for benefit in [
                    coupon,
                    telco,
                    card
                ]
                if benefit is not None
            ]


        final_price, steps = apply_combination(
            transaction_price,
            benefits
        )


        candidate = {
            "original_price":
                transaction_price,

            "final_price":
                final_price,

            "steps":
                steps,

            "benefits":
                benefits,
        }


        if (
            best_result is None
            or final_price
            < best_result["final_price"]
        ):

            best_result = candidate


    return best_result


# ==================================================
# 7. 하나의 분할 결제 방식 최적화
#
# 쿠폰은 한 번만 사용할 수 있도록 처리
# ==================================================

def optimize_partition(
    partition,
    coupons,
    selected_telcos,
    selected_cards
):

    transaction_prices = [
        sum(
            product["price"]
            for product in group
        )
        for group in partition
    ]


    best_total = float("inf")
    best_transactions = None


    def search(
        transaction_index,
        used_coupon_indexes,
        transactions,
        running_total
    ):

        nonlocal best_total
        nonlocal best_transactions


        # 가지치기
        if running_total >= best_total:
            return


        # 모든 거래 분석 완료
        if transaction_index == len(
            partition
        ):

            best_total = running_total
            best_transactions = (
                transactions[:]
            )

            return


        group = partition[
            transaction_index
        ]

        transaction_price = (
            transaction_prices[
                transaction_index
            ]
        )


        # 쿠폰을 사용하지 않는 경우
        coupon_choices = [
            (None, None)
        ]


        # 아직 사용하지 않은 쿠폰 추가
        for coupon_index, coupon in enumerate(
            coupons
        ):

            if (
                coupon_index
                not in used_coupon_indexes
            ):

                coupon_choices.append(
                    (
                        coupon_index,
                        coupon
                    )
                )


        for (
            coupon_index,
            coupon
        ) in coupon_choices:

            result = (
                find_best_for_transaction(
                    transaction_price,
                    coupon,
                    selected_telcos,
                    selected_cards
                )
            )


            transaction_result = {
                **result,

                "products": [
                    product["name"]
                    for product in group
                ],
            }


            new_used = set(
                used_coupon_indexes
            )

            if coupon_index is not None:

                new_used.add(
                    coupon_index
                )


            search(
                transaction_index + 1,
                new_used,
                transactions
                + [transaction_result],

                running_total
                + result["final_price"]
            )


    search(
        0,
        set(),
        [],
        0
    )


    return {
        "final_price":
            best_total,

        "transactions":
            best_transactions,
    }


# ==================================================
# 8. 전체 결제 최적화
# ==================================================

def find_best_payment_plan(
    products,
    coupons,
    selected_telcos,
    selected_cards,
    max_splits
):

    original_total = sum(
        product["price"]
        for product in products
    )


    best_plan = None


    # 상품 인덱스로 partition 생성
    indexes = list(
        range(len(products))
    )


    seen_partitions = set()


    for index_partition in (
        generate_partitions(indexes)
    ):

        # 최대 분할 수 제한
        if len(
            index_partition
        ) > max_splits:

            continue


        # 중복 partition 제거
        normalized = tuple(
            sorted(
                tuple(sorted(group))
                for group
                in index_partition
            )
        )

        if normalized in seen_partitions:
            continue

        seen_partitions.add(
            normalized
        )


        partition = [

            [
                products[index]
                for index in group
            ]

            for group
            in index_partition
        ]


        result = optimize_partition(
            partition,
            coupons,
            selected_telcos,
            selected_cards
        )


        candidate = {
            "original_price":
                original_total,

            "final_price":
                result["final_price"],

            "transactions":
                result["transactions"],

            "split_count":
                len(partition),
        }


        if (
            best_plan is None
            or candidate["final_price"]
            < best_plan["final_price"]
        ):

            best_plan = candidate


    return best_plan


# ==================================================
# 9. 개인 소비 가능 여부
# ==================================================

def evaluate_purchase(
    income,
    spent,
    fixed_expense,
    saving_goal,
    safety_reserve,
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

        explanation = (
            "구매 후 가용자금이 "
            "0원 미만이 됩니다."
        )


    elif (
        available_after_purchase
        < safety_reserve
    ):

        status = "🟡 주의 필요"

        explanation = (
            "구매는 가능하지만 "
            "설정한 최소 안전잔액보다 "
            "남는 돈이 적습니다."
        )


    else:

        status = "🟢 구매 가능"

        explanation = (
            "구매 후에도 설정한 "
            "최소 안전잔액을 "
            "유지할 수 있습니다."
        )


    return (
        available_before_purchase,
        available_after_purchase,
        status,
        explanation
    )


# ==================================================
# 10. 금융 스트레스 테스트
# ==================================================

def stress_test(
    income,
    spent,
    fixed_expense,
    saving_goal,
    safety_reserve,
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


    elif stressed_balance < safety_reserve:

        result = "🟡 주의"


    else:

        result = "🟢 안정"


    return (
        stressed_balance,
        result
    )


# ==================================================
# 11. AI 설명
# ==================================================

def get_ai_advice(
    store,
    best_plan,
    purchase_status,
    remaining_money,
    safety_reserve,
    stress_name,
    stress_status,
    stress_balance
):

    try:

        api_key = st.secrets[
            "OPENAI_API_KEY"
        ]

        model_name = st.secrets[
            "OPENAI_MODEL"
        ]

    except Exception:

        return None


    client = OpenAI(
        api_key=api_key
    )


    transaction_text = ""

    for number, transaction in enumerate(
        best_plan["transactions"],
        start=1
    ):

        benefits = [
            benefit["name"]
            for benefit
            in transaction["benefits"]
        ]

        transaction_text += f"""
결제 {number}
상품: {transaction["products"]}
결제 전 금액: {transaction["original_price"]:,.0f}원
적용 혜택: {benefits}
최종 금액: {transaction["final_price"]:,.0f}원
"""


    prompt = f"""
너는 사용자의 합리적인 소비 결정을 돕는 AI 금융 비서다.

Python 최적화 엔진이 이미 모든 금액을 계산했다.
절대로 금액을 다시 계산하거나 계산 결과를 변경하지 마라.
주어진 결과를 사용자가 이해하기 쉽게 설명하는 역할만 수행한다.

구매처: {store}

원래 총 구매금액:
{best_plan["original_price"]:,.0f}원

최적 결제 후 총 금액:
{best_plan["final_price"]:,.0f}원

총 절약금액:
{best_plan["original_price"] - best_plan["final_price"]:,.0f}원

분할 결제 횟수:
{best_plan["split_count"]}회

{transaction_text}

소비 판단:
{purchase_status}

구매 후 남는 금액:
{remaining_money:,.0f}원

사용자가 설정한 최소 안전잔액:
{safety_reserve:,.0f}원

스트레스 테스트 시나리오:
{stress_name}

스트레스 테스트 결과:
{stress_status}

스트레스 상황에서 남는 금액:
{stress_balance:,.0f}원


다음 형식으로 짧고 명확하게 설명해라.

1. 추천 결제 방법
2. 왜 이 방법이 가장 유리한지
3. 현재 소비 가능 여부
4. 스트레스 테스트 해석
5. 사용자가 주의할 점

과도한 금융상품 추천은 하지 말고
한국어로 답해라.
"""


    try:

        response = client.responses.create(
            model=model_name,
            input=prompt
        )

        return response.output_text


    except Exception as e:

        return (
            "AI 분석 중 오류가 발생했습니다.\n\n"
            f"{e}"
        )


# ==================================================
# 12. 구매 정보 입력
# ==================================================

st.divider()

st.header("🛍 1. 구매 정보")

store = st.text_input(
    "구매처",
    value="올리브영"
)


product_count = st.number_input(
    "구매할 상품 개수",
    min_value=1,
    max_value=6,
    value=3,
    step=1,
    help=(
        "MVP에서는 계산량을 고려해 "
        "최대 6개까지 지원합니다."
    )
)


products = []


for i in range(
    int(product_count)
):

    col_name, col_price = st.columns(
        [2, 1]
    )


    with col_name:

        product_name = st.text_input(
            f"상품 {i + 1} 이름",
            value=f"상품 {i + 1}",
            key=f"product_name_{i}"
        )


    with col_price:

        product_price = st.number_input(
            f"상품 {i + 1} 가격",
            min_value=0,
            value=20000,
            step=1000,
            key=f"product_price_{i}"
        )


    products.append(
        {
            "name": product_name,
            "price": product_price,
        }
    )


original_total = sum(
    product["price"]
    for product in products
)


st.write(
    f"**총 상품금액: "
    f"{original_total:,.0f}원**"
)


# ==================================================
# 13. 쿠폰 입력
# ==================================================

st.header("🎟 2. 보유 쿠폰")


coupon_count = st.number_input(
    "사용 가능한 쿠폰 개수",
    min_value=0,
    max_value=5,
    value=2,
    step=1
)


coupons = []


for i in range(
    int(coupon_count)
):

    with st.expander(
        f"쿠폰 {i + 1}",
        expanded=(i == 0)
    ):

        coupon_name = st.text_input(
            "쿠폰 이름",
            value=f"쿠폰 {i + 1}",
            key=f"coupon_name_{i}"
        )


        coupon_type = st.selectbox(
            "할인 방식",
            [
                "퍼센트 할인",
                "정액 할인"
            ],
            key=f"coupon_type_{i}"
        )


        if coupon_type == "퍼센트 할인":

            coupon_value = (
                st.number_input(
                    "할인율 (%)",
                    min_value=0,
                    max_value=100,
                    value=20,
                    key=f"coupon_value_{i}"
                )
            )

            discount_type = "percent"


        else:

            coupon_value = (
                st.number_input(
                    "할인금액",
                    min_value=0,
                    value=5000,
                    step=1000,
                    key=f"coupon_value_{i}"
                )
            )

            discount_type = "fixed"


        coupon_min = st.number_input(
            "최소 구매금액",
            min_value=0,
            value=30000,
            step=1000,
            key=f"coupon_min_{i}"
        )


        coupon_max = st.number_input(
            "최대 할인금액",
            min_value=0,
            value=10000,
            step=1000,
            key=f"coupon_max_{i}"
        )


        threshold_label = st.selectbox(
            "최소 구매금액 판단 기준",
            [
                "할인 전 금액",
                "앞선 할인 적용 후 금액"
            ],
            key=f"threshold_{i}"
        )


        if (
            threshold_label
            == "할인 전 금액"
        ):

            threshold_basis = "original"

        else:

            threshold_basis = "current"


        stackable = st.checkbox(
            "다른 멤버십·카드 혜택과 중복 가능",
            value=True,
            key=f"stackable_{i}"
        )


        coupons.append(
            {
                "name":
                    coupon_name,

                "category":
                    "쿠폰",

                "discount_type":
                    discount_type,

                "value":
                    coupon_value,

                "max_discount":
                    coupon_max,

                "min_purchase":
                    coupon_min,

                "threshold_basis":
                    threshold_basis,

                "discount_basis":
                    "current",

                "stackable":
                    stackable,

                "stage":
                    1,
            }
        )


# ==================================================
# 14. 멤버십 / 카드
# ==================================================

st.header(
    "📱 3. 보유 멤버십 및 결제수단"
)


selected_telcos = st.multiselect(
    "사용 가능한 통신사·멤버십 혜택",
    list(
        TELCO_BENEFITS.keys()
    )
)


selected_cards = st.multiselect(
    "사용 가능한 카드·결제 혜택",
    list(
        CARD_BENEFITS.keys()
    )
)


max_splits = st.slider(
    "최대 몇 번까지 나누어 결제할까요?",
    min_value=1,
    max_value=min(
        3,
        len(products)
    ),
    value=min(
        2,
        len(products)
    ),
    help=(
        "상품 묶음을 나누어 결제하면 "
        "여러 쿠폰의 최소 구매금액 조건을 "
        "더 효과적으로 활용할 수 있습니다."
    )
)


# ==================================================
# 15. 소비 정보
# ==================================================

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
        value=400000,
        step=10000
    )

    safety_reserve = st.number_input(
        "반드시 남겨두고 싶은 최소 안전잔액",
        min_value=0,
        value=150000,
        step=10000,
        help=(
            "식비·교통비 등 예상하지 못한 "
            "생활비를 위해 최소한 남겨둘 금액입니다."
        )
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


# ==================================================
# 16. 금융 스트레스 테스트
# ==================================================

st.header(
    "⚠️ 5. 금융 스트레스 테스트"
)


stress_scenario = st.selectbox(
    "스트레스 상황을 선택하세요",
    [
        "생활비 쇼크",
        "소득 쇼크",
        "복합 쇼크",
        "직접 설정"
    ]
)


if stress_scenario == "생활비 쇼크":

    unexpected_expense = 100000
    income_drop = 0

    st.info(
        "예상치 못한 추가 지출 "
        "100,000원이 발생한다고 가정합니다."
    )


elif stress_scenario == "소득 쇼크":

    income_drop = round(
        income * 0.3
    )

    unexpected_expense = 0

    st.info(
        "이번 달 소득이 "
        "30% 감소한다고 가정합니다."
    )


elif stress_scenario == "복합 쇼크":

    income_drop = round(
        income * 0.3
    )

    unexpected_expense = 200000

    st.warning(
        "소득이 30% 감소하고 "
        "예상치 못한 200,000원의 "
        "추가지출이 동시에 발생한다고 "
        "가정합니다."
    )


else:

    stress_col1, stress_col2 = (
        st.columns(2)
    )


    with stress_col1:

        unexpected_expense = (
            st.number_input(
                "예상치 못한 추가지출",
                min_value=0,
                value=100000,
                step=10000
            )
        )


    with stress_col2:

        income_drop = (
            st.number_input(
                "예상 소득 감소",
                min_value=0,
                value=0,
                step=10000
            )
        )


# ==================================================
# 17. 분석 실행
# ==================================================

st.divider()


if st.button(
    "✨ AI 최적 결제 분석하기",
    type="primary",
    use_container_width=True
):

    if original_total <= 0:

        st.warning(
            "상품 가격을 입력해주세요."
        )


    else:

        with st.spinner(
            "모든 결제 조합을 분석하고 있습니다..."
        ):

            best_plan = (
                find_best_payment_plan(
                    products,
                    coupons,
                    selected_telcos,
                    selected_cards,
                    max_splits
                )
            )


        (
            available_before,
            available_after,
            purchase_status,
            purchase_explanation
        ) = evaluate_purchase(
            income,
            spent,
            fixed_expense,
            saving_goal,
            safety_reserve,
            best_plan["final_price"]
        )


        (
            stress_balance,
            stress_status
        ) = stress_test(
            income,
            spent,
            fixed_expense,
            saving_goal,
            safety_reserve,
            best_plan["final_price"],
            income_drop,
            unexpected_expense
        )


        # ==========================================
        # 결과
        # ==========================================

        st.divider()

        st.header("🏆 최적 결제 결과")


        metric1, metric2, metric3 = (
            st.columns(3)
        )


        with metric1:

            st.metric(
                "원래 총 가격",
                f'{best_plan["original_price"]:,.0f}원'
            )


        with metric2:

            st.metric(
                "최종 예상 부담액",
                f'{best_plan["final_price"]:,.0f}원'
            )


        with metric3:

            saving = (
                best_plan["original_price"]
                - best_plan["final_price"]
            )

            st.metric(
                "총 절약 금액",
                f"{saving:,.0f}원"
            )


        st.write(
            f"**추천 결제 횟수: "
            f'{best_plan["split_count"]}회**'
        )


        # ==========================================
        # 분할결제별 결과
        # ==========================================

        st.subheader(
            "📋 추천 결제 방법"
        )


        for number, transaction in enumerate(
            best_plan["transactions"],
            start=1
        ):

            with st.expander(
                f"결제 {number} "
                f"— "
                f'{transaction["final_price"]:,.0f}원',
                expanded=True
            ):

                st.write(
                    "**구매 상품:** "
                    + ", ".join(
                        transaction["products"]
                    )
                )


                st.write(
                    "할인 전 금액: "
                    f'**{transaction["original_price"]:,.0f}원**'
                )


                if transaction["steps"]:

                    for step_number, step in enumerate(
                        transaction["steps"],
                        start=1
                    ):

                        st.write(
                            f'{step_number}. '
                            f'**{step["혜택"]}** '
                            f'→ '
                            f'{step["할인금액"]:,.0f}원 할인 '
                            f'→ '
                            f'{step["적용 후 금액"]:,.0f}원'
                        )


                else:

                    st.write(
                        "적용 가능한 혜택 없음"
                    )


                st.success(
                    "최종 결제금액: "
                    f'{transaction["final_price"]:,.0f}원'
                )


        # ==========================================
        # 소비 가능 여부
        # ==========================================

        st.subheader(
            "💰 소비 가능 여부"
        )


        st.write(
            f"### {purchase_status}"
        )


        st.write(
            purchase_explanation
        )


        finance_col1, finance_col2, finance_col3 = (
            st.columns(3)
        )


        with finance_col1:

            st.metric(
                "구매 전 가용자금",
                f"{available_before:,.0f}원"
            )


        with finance_col2:

            st.metric(
                "구매 후 가용자금",
                f"{available_after:,.0f}원"
            )


        with finance_col3:

            st.metric(
                "최소 안전잔액",
                f"{safety_reserve:,.0f}원"
            )


        # ==========================================
        # 스트레스 테스트
        # ==========================================

        st.subheader(
            "⚠️ 금융 스트레스 테스트"
        )


        st.write(
            f"**시나리오: "
            f"{stress_scenario}**"
        )


        st.write(
            f"### {stress_status}"
        )


        stress_col1, stress_col2 = (
            st.columns(2)
        )


        with stress_col1:

            st.metric(
                "예상 소득 감소",
                f"{income_drop:,.0f}원"
            )


        with stress_col2:

            st.metric(
                "예상 추가지출",
                f"{unexpected_expense:,.0f}원"
            )


        st.metric(
            "스트레스 상황 발생 후 잔여자금",
            f"{stress_balance:,.0f}원"
        )


        # ==========================================
        # AI 분석
        # ==========================================

        st.subheader(
            "🤖 AI 맞춤 분석"
        )


        with st.spinner(
            "AI가 계산 결과를 설명하고 있습니다..."
        ):

            ai_advice = get_ai_advice(
                store,
                best_plan,
                purchase_status,
                available_after,
                safety_reserve,
                stress_scenario,
                stress_status,
                stress_balance
            )


        if ai_advice:

            st.write(
                ai_advice
            )


        else:

            st.info(
                "OpenAI API를 연결하면 "
                "여기에 AI 맞춤 분석이 표시됩니다."
            )
