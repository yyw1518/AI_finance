import itertools
from collections import Counter
from functools import lru_cache

import streamlit as st
from openai import OpenAI


# --------------------------------------------------
# 1. 기본 페이지 설정
# --------------------------------------------------
st.set_page_config(
    page_title="AI Finance",
    page_icon="💳",
    layout="wide",
)

st.title("💳 AI Finance")
st.subheader("혜택은 최대로, 소비는 현명하게")
st.write(
    "여러 상품과 여러 쿠폰·멤버십·카드 혜택을 함께 비교하고, "
    "필요하면 상품을 나눠 결제하는 경우까지 계산해 가장 유리한 조합을 찾습니다."
)
st.info(
    "현재 버전은 공모전 MVP 데모입니다. 아래 카드·멤버십 혜택은 예시 데이터이며, "
    "실서비스에서는 실제 제휴/약관 데이터로 교체해야 합니다."
)


# --------------------------------------------------
# 2. 데모 혜택 데이터
#    min_basis = original: 할인 전 주문금액 기준
#    min_basis = current : 앞선 할인 적용 후 결제금액 기준
# --------------------------------------------------
TELCO_BENEFITS = {
    "멤버십 5% 할인 (데모)": {
        "source_id": "telco_1",
        "name": "멤버십 5% 할인 (데모)",
        "category": "telco",
        "discount_type": "percent",
        "value": 5,
        "max_discount": 3000,
        "min_purchase": 10000,
        "min_basis": "current",
        "stage": 2,
        "stack_with": {"coupon", "card"},
    },
    "멤버십 3,000원 할인 (데모)": {
        "source_id": "telco_2",
        "name": "멤버십 3,000원 할인 (데모)",
        "category": "telco",
        "discount_type": "fixed",
        "value": 3000,
        "max_discount": 3000,
        "min_purchase": 30000,
        "min_basis": "current",
        "stage": 2,
        "stack_with": {"card"},  # 쿠폰과 중복 불가 예시
    },
}

CARD_BENEFITS = {
    "A카드 5% 할인 (데모)": {
        "source_id": "card_1",
        "name": "A카드 5% 할인 (데모)",
        "category": "card",
        "discount_type": "percent",
        "value": 5,
        "max_discount": 5000,
        "min_purchase": 20000,
        "min_basis": "current",
        "stage": 3,
        "stack_with": {"coupon", "telco"},
    },
    "B카드 3,000원 할인 (데모)": {
        "source_id": "card_2",
        "name": "B카드 3,000원 할인 (데모)",
        "category": "card",
        "discount_type": "fixed",
        "value": 3000,
        "max_discount": 3000,
        "min_purchase": 30000,
        "min_basis": "current",
        "stage": 3,
        "stack_with": {"coupon", "telco"},
    },
    "C카드 7% 할인 (데모)": {
        "source_id": "card_3",
        "name": "C카드 7% 할인 (데모)",
        "category": "card",
        "discount_type": "percent",
        "value": 7,
        "max_discount": 4000,
        "min_purchase": 40000,
        "min_basis": "current",
        "stage": 3,
        "stack_with": {"coupon"},  # 멤버십과 중복 불가 예시
    },
}

CATEGORY_LABEL = {
    "coupon": "쿠폰",
    "telco": "멤버십",
    "card": "카드",
}


# --------------------------------------------------
# 3. 할인/중복 조건 계산 함수
# --------------------------------------------------
def calculate_discount(base_price, benefit):
    if benefit["discount_type"] == "percent":
        discount = base_price * (benefit["value"] / 100)
    else:
        discount = benefit["value"]

    max_discount = benefit.get("max_discount", 0)
    if max_discount and max_discount > 0:
        discount = min(discount, max_discount)

    return max(0, min(round(discount), round(base_price)))


def benefits_are_compatible(benefits):
    """같은 주문에 함께 적용 가능한 혜택 조합인지 확인."""
    categories = [b["category"] for b in benefits]

    # 한 번의 결제에는 카드 1개, 멤버십 1개만 적용하는 것으로 가정
    if categories.count("card") > 1:
        return False
    if categories.count("telco") > 1:
        return False

    # 모든 혜택 쌍이 서로 중복 적용을 허용해야 함
    for i in range(len(benefits)):
        for j in range(i + 1, len(benefits)):
            a = benefits[i]
            b = benefits[j]
            if b["category"] not in a["stack_with"]:
                return False
            if a["category"] not in b["stack_with"]:
                return False

    return True


def apply_benefits_to_order(original_total, benefits):
    """한 주문에 혜택을 순서대로 적용. 조건 불충족이면 None 반환."""
    if not benefits_are_compatible(benefits):
        return None

    current_price = round(original_total)
    steps = []

    for benefit in sorted(benefits, key=lambda x: x["stage"]):
        minimum_base = (
            original_total
            if benefit["min_basis"] == "original"
            else current_price
        )

        if minimum_base < benefit["min_purchase"]:
            return None

        discount = calculate_discount(current_price, benefit)
        if discount <= 0:
            return None

        current_price -= discount
        steps.append(
            {
                "name": benefit["name"],
                "category": benefit["category"],
                "discount": discount,
                "after": current_price,
            }
        )

    return {
        "final_price": round(current_price),
        "steps": steps,
    }


def benefit_terms_text(benefit):
    if benefit["discount_type"] == "percent":
        discount_text = f'{benefit["value"]}% 할인'
    else:
        discount_text = f'{benefit["value"]:,.0f}원 할인'

    max_text = (
        f' / 최대 {benefit["max_discount"]:,.0f}원'
        if benefit.get("max_discount", 0)
        else ""
    )
    basis_text = (
        "할인 전 금액"
        if benefit["min_basis"] == "original"
        else "적용 시점 결제금액"
    )

    stack_labels = [CATEGORY_LABEL[c] for c in benefit["stack_with"]]
    stack_text = ", ".join(stack_labels) if stack_labels else "중복 불가"

    return (
        f'{discount_text}{max_text} / 최소 {benefit["min_purchase"]:,.0f}원 '
        f'({basis_text} 기준) / 중복 가능: {stack_text}'
    )


# --------------------------------------------------
# 4. 상품 분할 조합 생성
# --------------------------------------------------
def generate_partitions(item_count, max_orders):
    """상품 인덱스를 최대 max_orders개의 결제 묶음으로 나누는 모든 경우 생성."""
    groups = []

    def backtrack(item_index):
        if item_index == item_count:
            yield tuple(tuple(group) for group in groups)
            return

        # 기존 결제 묶음에 추가
        for group_index in range(len(groups)):
            groups[group_index].append(item_index)
            yield from backtrack(item_index + 1)
            groups[group_index].pop()

        # 새 결제 묶음 생성
        if len(groups) < max_orders:
            groups.append([item_index])
            yield from backtrack(item_index + 1)
            groups.pop()

    yield from backtrack(0)


# --------------------------------------------------
# 5. 주문 하나에서 가능한 혜택 조합 생성
# --------------------------------------------------
def build_order_options(order_total, benefits):
    coupon_indices = [i for i, b in enumerate(benefits) if b["category"] == "coupon"]
    telco_indices = [i for i, b in enumerate(benefits) if b["category"] == "telco"]
    card_indices = [i for i, b in enumerate(benefits) if b["category"] == "card"]

    # 쿠폰 부분집합: 여러 쿠폰 입력 가능. 실제 중복 가능 여부는 조건에서 다시 검증.
    coupon_choices = []
    for r in range(len(coupon_indices) + 1):
        for combo in itertools.combinations(coupon_indices, r):
            coupon_choices.append(combo)

    telco_choices = [None] + telco_indices
    card_choices = [None] + card_indices

    options_by_mask = {}

    for coupon_combo in coupon_choices:
        for telco_index in telco_choices:
            for card_index in card_choices:
                indices = list(coupon_combo)
                if telco_index is not None:
                    indices.append(telco_index)
                if card_index is not None:
                    indices.append(card_index)

                selected = [benefits[i] for i in indices]
                result = apply_benefits_to_order(order_total, selected)
                if result is None:
                    continue

                mask = 0
                for i in indices:
                    mask |= 1 << i

                option = {
                    "mask": mask,
                    "final_price": result["final_price"],
                    "steps": result["steps"],
                    "benefit_count": len(indices),
                }

                previous = options_by_mask.get(mask)
                if previous is None or option["final_price"] < previous["final_price"]:
                    options_by_mask[mask] = option

    options = list(options_by_mask.values())
    options.sort(key=lambda x: (x["final_price"], x["benefit_count"]))
    return options


# --------------------------------------------------
# 6. 한 분할안에서 혜택을 어느 주문에 배분할지 최적화
# --------------------------------------------------
def optimize_partition(partition, items, benefits, options_cache):
    order_totals = [sum(items[i]["price"] for i in group) for group in partition]

    order_options = []
    for total in order_totals:
        if total not in options_cache:
            options_cache[total] = build_order_options(total, benefits)
        order_options.append(options_cache[total])

    @lru_cache(maxsize=None)
    def solve(order_index, used_mask):
        if order_index == len(partition):
            return 0, 0, ()

        best_cost = float("inf")
        best_benefit_count = float("inf")
        best_choices = ()

        for option in order_options[order_index]:
            if option["mask"] & used_mask:
                continue

            rest_cost, rest_benefit_count, rest_choices = solve(
                order_index + 1,
                used_mask | option["mask"],
            )

            total_cost = option["final_price"] + rest_cost
            total_benefit_count = option["benefit_count"] + rest_benefit_count

            if (total_cost, total_benefit_count) < (
                best_cost,
                best_benefit_count,
            ):
                best_cost = total_cost
                best_benefit_count = total_benefit_count
                best_choices = (option,) + rest_choices

        return best_cost, best_benefit_count, best_choices

    final_cost, _, choices = solve(0, 0)

    orders = []
    for group, original_total, option in zip(partition, order_totals, choices):
        orders.append(
            {
                "item_indices": group,
                "original_total": original_total,
                "final_price": option["final_price"],
                "steps": option["steps"],
            }
        )

    return {
        "final_price": final_cost,
        "orders": orders,
    }


# --------------------------------------------------
# 7. 전체 결제 최적화: 한 번 결제 vs 분할 결제 모두 비교
# --------------------------------------------------
def find_best_payment_plan(items, benefits, allow_split, max_orders):
    item_count = len(items)
    if item_count == 0:
        return None

    options_cache = {}

    if allow_split:
        partitions = generate_partitions(item_count, max_orders)
    else:
        partitions = [(tuple(range(item_count)),)]

    best_plan = None

    for partition in partitions:
        plan = optimize_partition(partition, items, benefits, options_cache)
        score = (plan["final_price"], len(plan["orders"]))

        if best_plan is None or score < (
            best_plan["final_price"],
            len(best_plan["orders"]),
        ):
            best_plan = plan

    return best_plan


# --------------------------------------------------
# 8. 안전잔액 기반 소비 판단
# --------------------------------------------------
def evaluate_purchase(
    monthly_income,
    spent_so_far,
    upcoming_fixed_expense,
    saving_goal,
    safety_reserve,
    purchase_cost,
):
    available_before = (
        monthly_income
        - spent_so_far
        - upcoming_fixed_expense
        - saving_goal
    )
    available_after = available_before - purchase_cost
    safety_gap = available_after - safety_reserve

    if available_after < 0:
        status = "🔴 구매 연기 권장"
        reason = "구매 후 예상 잔액이 0원 미만입니다."
    elif available_after < safety_reserve:
        status = "🟡 주의 필요"
        reason = "구매 후 잔액이 설정한 안전잔액보다 낮아집니다."
    else:
        status = "🟢 구매 가능"
        reason = "구매 후에도 설정한 안전잔액을 유지할 수 있습니다."

    return {
        "available_before": available_before,
        "available_after": available_after,
        "safety_gap": safety_gap,
        "status": status,
        "reason": reason,
    }


# --------------------------------------------------
# 9. 시나리오형 스트레스 테스트
# --------------------------------------------------
def run_stress_scenarios(
    monthly_income,
    spent_so_far,
    upcoming_fixed_expense,
    saving_goal,
    safety_reserve,
    purchase_cost,
    scenarios,
):
    results = []

    for scenario in scenarios:
        stressed_income = monthly_income * (1 - scenario["income_drop_pct"] / 100)
        stressed_balance = (
            stressed_income
            - spent_so_far
            - upcoming_fixed_expense
            - saving_goal
            - purchase_cost
            - scenario["extra_expense"]
        )
        gap = stressed_balance - safety_reserve

        if stressed_balance < 0:
            status = "🔴 위험"
        elif stressed_balance < safety_reserve:
            status = "🟡 주의"
        else:
            status = "🟢 안정"

        results.append(
            {
                "시나리오": scenario["name"],
                "소득 감소": f'{scenario["income_drop_pct"]:.0f}% ',
                "추가 지출": f'{scenario["extra_expense"]:,.0f}원',
                "예상 잔액": round(stressed_balance),
                "안전자금 대비": round(gap),
                "판정": status,
            }
        )

    return results


# --------------------------------------------------
# 10. AI 결과 설명
# --------------------------------------------------
def get_ai_advice(
    store,
    original_total,
    best_plan,
    purchase_evaluation,
    stress_results,
    safety_reserve,
):
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except Exception:
        return None

    client = OpenAI(api_key=api_key)

    order_lines = []
    for order_number, order in enumerate(best_plan["orders"], start=1):
        step_names = [step["name"] for step in order["steps"]]
        order_lines.append(
            f"결제 {order_number}: 원금 {order['original_total']:,.0f}원 → "
            f"최종 {order['final_price']:,.0f}원 / 혜택 {step_names}"
        )

    stress_lines = [
        f"{row['시나리오']}: 예상 잔액 {row['예상 잔액']:,.0f}원, {row['판정']}"
        for row in stress_results
    ]

    prompt = f"""
너는 사용자의 합리적인 소비 결정을 돕는 AI 금융 의사결정 비서다.
아래 숫자는 Python 최적화 엔진이 계산한 확정 결과다.
숫자를 새로 계산하거나 변경하지 말고, 결과를 이해하기 쉽게 설명하라.

구매처: {store}
상품 총액: {original_total:,.0f}원
최적 실질 부담액: {best_plan['final_price']:,.0f}원
결제 횟수: {len(best_plan['orders'])}회
결제 계획:
{chr(10).join(order_lines)}

소비 판단: {purchase_evaluation['status']}
구매 후 예상 잔액: {purchase_evaluation['available_after']:,.0f}원
사용자가 설정한 안전잔액: {safety_reserve:,.0f}원
안전자금 대비 차이: {purchase_evaluation['safety_gap']:,.0f}원

스트레스 테스트:
{chr(10).join(stress_lines)}

다음 형식으로 짧게 답하라.
1. 추천 결제 방법과 순서
2. 왜 분할/통합 결제가 더 유리한지
3. 현재 구매 판단
4. 가장 주의해야 할 스트레스 시나리오

한국어로 명확하고 간결하게 답하라.
"""

    try:
        response = client.responses.create(
            model="gpt-5.6-luna",
            input=prompt,
        )
        return response.output_text
    except Exception as e:
        return f"AI 분석 중 오류가 발생했습니다.\n\n{e}"


# --------------------------------------------------
# 11. 사용자 입력 - 구매 정보 / 여러 상품
# --------------------------------------------------
st.divider()
st.header("🛍 1. 구매 정보")

store = st.text_input("구매처", value="올리브영")

product_count = st.number_input(
    "상품 종류 수",
    min_value=1,
    max_value=6,
    value=2,
    step=1,
)

product_lines = []
for i in range(int(product_count)):
    with st.expander(f"상품 {i + 1}", expanded=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            name = st.text_input(
                "상품명",
                value=f"상품 {i + 1}",
                key=f"product_name_{i}",
            )
        with c2:
            unit_price = st.number_input(
                "단가",
                min_value=0,
                value=25000,
                step=1000,
                key=f"product_price_{i}",
            )
        with c3:
            quantity = st.number_input(
                "수량",
                min_value=1,
                max_value=4,
                value=1,
                step=1,
                key=f"product_qty_{i}",
            )

        product_lines.append(
            {
                "name": name,
                "unit_price": int(unit_price),
                "quantity": int(quantity),
            }
        )

# 수량을 개별 상품 단위로 펼쳐서 분할 결제 계산
items = []
for line in product_lines:
    for unit_number in range(line["quantity"]):
        items.append(
            {
                "name": line["name"],
                "price": line["unit_price"],
                "unit_number": unit_number + 1,
            }
        )

original_total = sum(item["price"] for item in items)
st.metric("상품 총액", f"{original_total:,.0f}원")

allow_split = st.checkbox(
    "상품을 나눠 결제하는 경우까지 비교",
    value=True,
    help="쿠폰·카드의 최소 결제금액을 고려해 묶음 결제와 분할 결제를 모두 비교합니다.",
)

max_possible_orders = max(1, min(3, len(items)))
max_orders = st.slider(
    "최대 결제 횟수",
    min_value=1,
    max_value=max_possible_orders,
    value=max_possible_orders,
    disabled=not allow_split,
)

if len(items) > 8:
    st.warning(
        "현재 MVP에서는 분할 결제 조합 계산 속도를 위해 총 상품 수량을 8개 이하로 제한합니다. "
        "수량을 줄이거나 같은 상품을 한 묶음으로 입력해주세요."
    )


# --------------------------------------------------
# 12. 사용자 입력 - 여러 쿠폰
# --------------------------------------------------
st.header("🎟 2. 보유 쿠폰")

coupon_count = st.number_input(
    "보유 쿠폰 수",
    min_value=0,
    max_value=5,
    value=2,
    step=1,
    help="같은 종류의 쿠폰을 2장 보유했다면 쿠폰 2개로 각각 입력하세요.",
)

custom_coupons = []
for i in range(int(coupon_count)):
    with st.expander(f"쿠폰 {i + 1}", expanded=True):
        coupon_name = st.text_input(
            "쿠폰 이름",
            value=f"쿠폰 {i + 1}",
            key=f"coupon_name_{i}",
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            coupon_type = st.selectbox(
                "할인 방식",
                ["퍼센트 할인", "정액 할인"],
                key=f"coupon_type_{i}",
            )
        with c2:
            if coupon_type == "퍼센트 할인":
                coupon_value = st.number_input(
                    "할인율 (%)",
                    min_value=0,
                    max_value=100,
                    value=20,
                    key=f"coupon_value_pct_{i}",
                )
                discount_type = "percent"
            else:
                coupon_value = st.number_input(
                    "할인금액 (원)",
                    min_value=0,
                    value=5000,
                    step=1000,
                    key=f"coupon_value_fixed_{i}",
                )
                discount_type = "fixed"
        with c3:
            coupon_max = st.number_input(
                "최대 할인금액",
                min_value=0,
                value=10000,
                step=1000,
                key=f"coupon_max_{i}",
                help="정액 할인은 할인금액과 같은 값으로 두면 됩니다.",
            )

        c4, c5 = st.columns(2)
        with c4:
            coupon_min = st.number_input(
                "최소 구매금액",
                min_value=0,
                value=30000,
                step=1000,
                key=f"coupon_min_{i}",
            )
        with c5:
            min_basis_label = st.selectbox(
                "최소금액 판단 기준",
                ["할인 전 주문금액", "적용 시점 결제금액"],
                key=f"coupon_basis_{i}",
            )

        st.caption("중복 적용 조건")
        s1, s2, s3 = st.columns(3)
        with s1:
            stack_coupon = st.checkbox(
                "다른 쿠폰과 가능",
                value=False,
                key=f"stack_coupon_{i}",
            )
        with s2:
            stack_telco = st.checkbox(
                "멤버십과 가능",
                value=True,
                key=f"stack_telco_{i}",
            )
        with s3:
            stack_card = st.checkbox(
                "카드 혜택과 가능",
                value=True,
                key=f"stack_card_{i}",
            )

        stack_with = set()
        if stack_coupon:
            stack_with.add("coupon")
        if stack_telco:
            stack_with.add("telco")
        if stack_card:
            stack_with.add("card")

        custom_coupons.append(
            {
                "source_id": f"coupon_{i}",
                "name": coupon_name,
                "category": "coupon",
                "discount_type": discount_type,
                "value": float(coupon_value),
                "max_discount": int(coupon_max),
                "min_purchase": int(coupon_min),
                "min_basis": (
                    "original"
                    if min_basis_label == "할인 전 주문금액"
                    else "current"
                ),
                "stage": 1,
                "stack_with": stack_with,
            }
        )


# --------------------------------------------------
# 13. 사용자 입력 - 멤버십/카드
# --------------------------------------------------
st.header("📱 3. 보유 멤버십 및 결제수단")

selected_telcos = st.multiselect(
    "사용 가능한 멤버십 혜택",
    list(TELCO_BENEFITS.keys()),
)
selected_cards = st.multiselect(
    "보유 카드 혜택",
    list(CARD_BENEFITS.keys()),
)

if selected_telcos or selected_cards:
    st.caption("선택한 데모 혜택 조건")
    for name in selected_telcos:
        st.write(f"- **{name}**: {benefit_terms_text(TELCO_BENEFITS[name])}")
    for name in selected_cards:
        st.write(f"- **{name}**: {benefit_terms_text(CARD_BENEFITS[name])}")

benefits = list(custom_coupons)
benefits += [TELCO_BENEFITS[name].copy() for name in selected_telcos]
benefits += [CARD_BENEFITS[name].copy() for name in selected_cards]


# --------------------------------------------------
# 14. 사용자 입력 - 안전잔액 기반 금융 판단
# --------------------------------------------------
st.header("💰 4. 나의 소비 여력")
st.write("임의의 소득 비율 대신, 내가 결제 후에도 남기고 싶은 **안전자금 기준**으로 판단합니다.")

c1, c2 = st.columns(2)
with c1:
    monthly_income = st.number_input(
        "이번 달 소득",
        min_value=0,
        value=1000000,
        step=10000,
    )
    spent_so_far = st.number_input(
        "이번 달 현재까지 지출",
        min_value=0,
        value=500000,
        step=10000,
    )
    safety_reserve = st.number_input(
        "결제 후 유지하고 싶은 안전잔액",
        min_value=0,
        value=100000,
        step=10000,
        help="예상치 못한 지출에 대비해 이번 달 말까지 최소한 남겨두고 싶은 금액입니다.",
    )

with c2:
    upcoming_fixed_expense = st.number_input(
        "앞으로 예정된 필수·고정지출",
        min_value=0,
        value=200000,
        step=10000,
    )
    saving_goal = st.number_input(
        "이번 달 저축 목표",
        min_value=0,
        value=100000,
        step=10000,
    )


# --------------------------------------------------
# 15. 사용자 입력 - 시나리오형 스트레스 테스트
# --------------------------------------------------
st.header("⚠️ 5. 금융 스트레스 테스트")
st.write("구매 후 예상치 못한 상황이 생겼을 때도 안전잔액을 유지할 수 있는지 시나리오별로 확인합니다.")

scenario_defaults = [
    ("갑작스러운 추가 지출", 0, 100000),
    ("소득 감소", 20, 0),
    ("소득 감소 + 추가 지출", 20, 200000),
]

scenarios = []
for i, (default_name, default_drop, default_extra) in enumerate(scenario_defaults):
    with st.expander(f"시나리오 {i + 1}: {default_name}"):
        scenario_name = st.text_input(
            "시나리오 이름",
            value=default_name,
            key=f"scenario_name_{i}",
        )
        s1, s2 = st.columns(2)
        with s1:
            income_drop_pct = st.slider(
                "소득 감소율 (%)",
                min_value=0,
                max_value=100,
                value=default_drop,
                step=5,
                key=f"scenario_drop_{i}",
            )
        with s2:
            extra_expense = st.number_input(
                "추가 지출",
                min_value=0,
                value=default_extra,
                step=10000,
                key=f"scenario_extra_{i}",
            )

        scenarios.append(
            {
                "name": scenario_name,
                "income_drop_pct": income_drop_pct,
                "extra_expense": extra_expense,
            }
        )


# --------------------------------------------------
# 16. 분석 실행
# --------------------------------------------------
st.divider()

if st.button(
    "✨ 최적 결제 + 소비 분석하기",
    type="primary",
    use_container_width=True,
):
    if original_total <= 0:
        st.warning("상품 가격을 입력해주세요.")
    elif len(items) > 8:
        st.error("총 상품 수량을 8개 이하로 줄인 뒤 다시 분석해주세요.")
    else:
        with st.spinner("결제 조합을 비교하고 있습니다..."):
            best_plan = find_best_payment_plan(
                items=items,
                benefits=benefits,
                allow_split=allow_split,
                max_orders=max_orders if allow_split else 1,
            )

        purchase_evaluation = evaluate_purchase(
            monthly_income=monthly_income,
            spent_so_far=spent_so_far,
            upcoming_fixed_expense=upcoming_fixed_expense,
            saving_goal=saving_goal,
            safety_reserve=safety_reserve,
            purchase_cost=best_plan["final_price"],
        )

        stress_results = run_stress_scenarios(
            monthly_income=monthly_income,
            spent_so_far=spent_so_far,
            upcoming_fixed_expense=upcoming_fixed_expense,
            saving_goal=saving_goal,
            safety_reserve=safety_reserve,
            purchase_cost=best_plan["final_price"],
            scenarios=scenarios,
        )

        st.divider()
        st.header("🏆 최적 결제 결과")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("상품 총액", f"{original_total:,.0f}원")
        m2.metric("최종 실질 부담액", f'{best_plan["final_price"]:,.0f}원')
        m3.metric("총 절약", f'{original_total - best_plan["final_price"]:,.0f}원')
        m4.metric("추천 결제 횟수", f'{len(best_plan["orders"])}회')

        st.subheader("📋 추천 결제 순서")

        for order_number, order in enumerate(best_plan["orders"], start=1):
            item_counter = Counter(items[i]["name"] for i in order["item_indices"])
            item_text = ", ".join(
                f"{name} × {count}" if count > 1 else name
                for name, count in item_counter.items()
            )

            with st.container(border=True):
                st.markdown(f"### 결제 {order_number}")
                st.write(f"**상품:** {item_text}")
                st.write(f'**할인 전:** {order["original_total"]:,.0f}원')

                if order["steps"]:
                    for step_number, step in enumerate(order["steps"], start=1):
                        st.write(
                            f'{step_number}. **{step["name"]}** '
                            f'→ {step["discount"]:,.0f}원 할인 '
                            f'→ {step["after"]:,.0f}원'
                        )
                else:
                    st.write("적용 혜택 없음")

                st.success(f'이 결제의 최종 부담액: {order["final_price"]:,.0f}원')

        if len(best_plan["orders"]) > 1:
            st.info(
                f"한 번에 결제하는 것보다 혜택 최소금액과 사용 가능 횟수를 고려해 "
                f"{len(best_plan['orders'])}번으로 나눠 결제하는 편이 더 유리한 결과입니다."
            )

        st.subheader("💰 소비 가능 여부")
        st.write(f"### {purchase_evaluation['status']}")
        st.write(purchase_evaluation["reason"])

        f1, f2, f3 = st.columns(3)
        f1.metric(
            "구매 전 가용금액",
            f'{purchase_evaluation["available_before"]:,.0f}원',
        )
        f2.metric(
            "구매 후 예상 잔액",
            f'{purchase_evaluation["available_after"]:,.0f}원',
        )
        f3.metric(
            "안전자금 대비",
            f'{purchase_evaluation["safety_gap"]:,.0f}원',
        )

        st.subheader("⚠️ 시나리오별 스트레스 테스트")
        st.table(stress_results)

        worst = min(stress_results, key=lambda x: x["예상 잔액"])
        st.caption(
            f"가장 불리한 시나리오: {worst['시나리오']} / "
            f"예상 잔액 {worst['예상 잔액']:,.0f}원 / {worst['판정']}"
        )

        st.subheader("🤖 AI 맞춤 분석")
        with st.spinner("AI가 계산 결과를 설명하고 있습니다..."):
            ai_advice = get_ai_advice(
                store=store,
                original_total=original_total,
                best_plan=best_plan,
                purchase_evaluation=purchase_evaluation,
                stress_results=stress_results,
                safety_reserve=safety_reserve,
            )

        if ai_advice:
            st.write(ai_advice)
        else:
            st.info(
                "OpenAI API Key를 Streamlit Secrets에 연결하면 "
                "여기에 AI 맞춤 분석이 표시됩니다. 계산 기능은 API Key 없이도 작동합니다."
            )

        st.caption(
            "※ 실제 결제 전에는 각 쿠폰·멤버십·카드의 최신 약관, 중복 가능 여부, "
            "최소 결제금액 및 사용 횟수를 반드시 확인해야 합니다."
        )
