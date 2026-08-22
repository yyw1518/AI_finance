import itertools
from datetime import date, datetime

import streamlit as st


# =========================================================
# 페이지 설정
# =========================================================
st.set_page_config(
    page_title="최적 결제 추천",
    page_icon="💳",
    layout="wide",
)

st.title("💳 최적 결제 추천")
st.write(
    "저장한 상품과 혜택을 비교해 가장 유리한 결제 방법을 먼저 보여드립니다. "
    "확인이 필요한 조건이 있다면 결제 전에 확인할 항목만 따로 안내합니다."
)


# =========================================================
# 입력 데이터
# =========================================================
products = st.session_state.get("products", [])
benefits = st.session_state.get("benefits", [])
allow_split_payment = st.session_state.get("allow_split_payment", True)
store_name = st.session_state.get("store_name", "")

if not products:
    st.warning("먼저 **1_상품_혜택_입력** 페이지에서 상품 정보를 저장해주세요.")
    st.stop()

if not benefits:
    st.warning("먼저 **1_상품_혜택_입력** 페이지에서 혜택 정보를 저장해주세요.")
    st.stop()


# =========================================================
# 계산 한도
# =========================================================
MAX_EXHAUSTIVE_BENEFITS = 12
MAX_EXHAUSTIVE_PRODUCTS = 5


# =========================================================
# 기본 함수
# =========================================================
def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def money(value):
    return f"{safe_float(value):,.0f}원"


def percent(value):
    return f"{value:.1f}%"


def normalize_category(benefit):
    return benefit.get("category", "other")


def relation_value(value):
    if value is True:
        return "confirmed"
    if value is False:
        return "invalid"
    return "uncertain"


def merge_status(*statuses):
    if "invalid" in statuses:
        return "invalid"
    if "uncertain" in statuses:
        return "uncertain"
    return "confirmed"


def unique_text(items):
    result = []
    for item in items:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


# =========================================================
# 사용자에게 필요한 설정만 노출
# =========================================================
st.subheader("⚙️ 구매 환경")

purchase_channel = st.selectbox(
    "이번 구매 채널",
    ["온라인", "오프라인"],
    help="온라인 전용·오프라인 전용 혜택을 구분하기 위해 사용합니다.",
)

st.caption(
    "최소 결제금액 기준, 중복 여부 등은 1번 페이지에서 AI가 읽은 혜택별 조건을 "
    "자동으로 사용합니다. 확실하지 않은 조건만 결과에서 '확인 필요'로 표시합니다."
)

st.divider()


# =========================================================
# 상품 관련
# =========================================================
def product_line_total(product):
    if "total" in product:
        return safe_float(product.get("total"))

    quantity = product.get("quantity", 1)
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        quantity = 1

    return safe_float(product.get("price")) * quantity


def group_subtotal(group_indices):
    return sum(product_line_total(products[i]) for i in group_indices)


def group_product_names(group_indices):
    names = []

    for i in group_indices:
        product = products[i]
        name = product.get("name", f"상품 {i + 1}")

        try:
            quantity = int(product.get("quantity", 1))
        except (TypeError, ValueError):
            quantity = 1

        if quantity > 1:
            names.append(f"{name} × {quantity}")
        else:
            names.append(name)

    return names


total_original_price = round(sum(product_line_total(p) for p in products))


# =========================================================
# 상품 분할 경우의 수
# =========================================================
def set_partitions(items):
    if not items:
        yield []
        return

    first = items[0]

    for smaller in set_partitions(items[1:]):
        yield [[first]] + [group[:] for group in smaller]

        for i in range(len(smaller)):
            new_partition = [group[:] for group in smaller]
            new_partition[i] = [first] + new_partition[i]
            yield new_partition


def canonical_partition(partition):
    normalized_groups = [tuple(sorted(group)) for group in partition]
    return tuple(sorted(normalized_groups))


def generate_partitions():
    n = len(products)
    all_indices = list(range(n))

    if not allow_split_payment or n == 1:
        return [(tuple(all_indices),)]

    if n <= MAX_EXHAUSTIVE_PRODUCTS:
        seen = set()
        results = []

        for partition in set_partitions(all_indices):
            key = canonical_partition(partition)

            if key not in seen:
                seen.add(key)
                results.append(key)

        return results

    # 상품이 많은 경우 대표적인 분할안만 비교
    results = set()
    results.add((tuple(all_indices),))
    results.add(tuple((i,) for i in all_indices))

    for i in all_indices:
        rest = tuple(j for j in all_indices if j != i)
        if rest:
            results.add(canonical_partition([(i,), rest]))

    return list(results)


# =========================================================
# 혜택 수가 아주 많을 때 후보 축소
# =========================================================
def benefit_priority_score(benefit):
    value = safe_float(benefit.get("value", 0))
    discount_type = benefit.get("discount_type", "unknown")
    confidence = benefit.get("confidence", "low")

    score = value

    if discount_type == "percent":
        score *= 1000

    if confidence == "high":
        score += 100000
    elif confidence == "medium":
        score += 50000

    if benefit.get("value_known", False):
        score += 20000

    return score


original_benefit_count = len(benefits)

if original_benefit_count > MAX_EXHAUSTIVE_BENEFITS:
    benefits = sorted(
        benefits,
        key=benefit_priority_score,
        reverse=True,
    )[:MAX_EXHAUSTIVE_BENEFITS]

    st.info(
        f"혜택이 {original_benefit_count}개라 계산량이 매우 커질 수 있어 "
        f"혜택값과 AI 확인도가 높은 {MAX_EXHAUSTIVE_BENEFITS}개를 우선 비교합니다. "
        "1번 페이지에서 사용하지 않을 혜택을 삭제하면 더 정밀하게 비교할 수 있습니다."
    )

benefit_count = len(benefits)


# =========================================================
# 혜택 간 중복 가능 여부
# =========================================================
PAYMENT_METHODS = {"card", "easy_pay"}
PAYMENT_RELATED = {"card", "easy_pay", "point"}


def relation_key(a, b):
    ids = sorted([str(a.get("id", "")), str(b.get("id", ""))])
    return "||".join(ids)


def pair_compatibility(a, b):
    # 사용자가 직접 확인한 정보가 가장 우선
    user_relations = st.session_state.get("benefit_relations", {})
    saved = user_relations.get(relation_key(a, b))

    if saved == "possible":
        return "confirmed"
    if saved == "not_possible":
        return "invalid"

    # AI가 같은 택일 그룹으로 판단한 혜택은 함께 사용하지 않음
    group_a = str(a.get("exclusive_group", "")).strip()
    group_b = str(b.get("exclusive_group", "")).strip()

    if group_a and group_b and group_a == group_b:
        return "invalid"

    ca = normalize_category(a)
    cb = normalize_category(b)

    # 실제 결제수단은 한 결제건에서 하나
    if ca in PAYMENT_METHODS and cb in PAYMENT_METHODS:
        return "invalid"

    # 멤버십은 한 결제건에서 하나
    if ca == "membership" and cb == "membership":
        return "invalid"

    # 같은 제공사 여부
    issuer_a = str(a.get("issuer", "")).strip()
    issuer_b = str(b.get("issuer", "")).strip()
    same_issuer = bool(issuer_a and issuer_b and issuer_a == issuer_b)

    # 쿠폰 + 쿠폰
    # 둘 다 '쿠폰 중복 가능'이 명확히 확인된 경우에만 함께 사용
    if ca == "coupon" and cb == "coupon":
        a_stack = a.get("stack_coupon")
        b_stack = b.get("stack_coupon")

        if a_stack is True and b_stack is True:
            return "confirmed"

        if a_stack is False or b_stack is False:
            return "invalid"

        return "uncertain"

    # 쿠폰 + 멤버십
    if {ca, cb} == {"coupon", "membership"}:
        coupon = a if ca == "coupon" else b
        membership = b if ca == "coupon" else a

        return merge_status(
            relation_value(coupon.get("stack_membership")),
            relation_value(membership.get("stack_coupon")),
        )

    # 쿠폰 + 카드/간편결제/포인트
    if (
        ca == "coupon" and cb in PAYMENT_RELATED
    ) or (
        cb == "coupon" and ca in PAYMENT_RELATED
    ):
        coupon = a if ca == "coupon" else b
        payment_related = b if ca == "coupon" else a

        return merge_status(
            relation_value(coupon.get("stack_payment")),
            relation_value(payment_related.get("stack_coupon")),
        )

    # 멤버십 + 카드/간편결제/포인트
    if (
        ca == "membership" and cb in PAYMENT_RELATED
    ) or (
        cb == "membership" and ca in PAYMENT_RELATED
    ):
        membership = a if ca == "membership" else b
        payment_related = b if ca == "membership" else a

        return merge_status(
            relation_value(membership.get("stack_payment")),
            relation_value(payment_related.get("stack_membership")),
        )

    # 포인트 + 카드/간편결제
    if (
        ca == "point" and cb in PAYMENT_METHODS
    ) or (
        cb == "point" and ca in PAYMENT_METHODS
    ):
        point = a if ca == "point" else b
        payment_method = b if ca == "point" else a

        return merge_status(
            relation_value(point.get("stack_payment")),
            relation_value(payment_method.get("stack_payment")),
        )

    # 포인트 + 포인트
    if ca == "point" and cb == "point":
        return "uncertain"

    return "uncertain"


def get_uncertain_pairs(selected_benefits):
    pairs = []

    for a, b in itertools.combinations(selected_benefits, 2):
        if pair_compatibility(a, b) == "uncertain":
            pairs.append((a, b))

    return pairs


def subset_compatibility(selected_benefits):
    status = "confirmed"

    for a, b in itertools.combinations(selected_benefits, 2):
        pair_status = pair_compatibility(a, b)

        if pair_status == "invalid":
            return "invalid"

        if pair_status == "uncertain":
            status = "uncertain"

    return status


# =========================================================
# 개별 혜택의 확인 필요 사유
# =========================================================
def individual_benefit_check(benefit):
    status = "confirmed"
    reasons = []

    name = benefit.get("name", "혜택")

    # 사용 채널
    label = str(benefit.get("channel_label", "확인 필요")).strip()
    if label == "온라인" and purchase_channel != "온라인":
        return "invalid", [f"{name}: 온라인 전용 혜택입니다."]
    if label == "오프라인" and purchase_channel != "오프라인":
        return "invalid", [f"{name}: 오프라인 전용 혜택입니다."]

    # 유효기간
    raw_expiry = str(benefit.get("expiry", "")).strip()
    if raw_expiry:
        try:
            expiry_date = datetime.strptime(raw_expiry, "%Y-%m-%d").date()
            if expiry_date < date.today():
                return "invalid", [f"{name}: 유효기간이 지났습니다."]
        except ValueError:
            status = "uncertain"
            reasons.append(f"{name}: 유효기간을 확인해주세요.")

    # 실제 결제 가능성에 직접 영향을 주는 조건만 안내
    if not benefit.get("value_known", True):
        status = "uncertain"
        reasons.append(f"{name}: 혜택 금액을 확인해주세요.")

    required_payment = str(benefit.get("required_payment_method", "")).strip()
    if required_payment:
        status = "uncertain"
        reasons.append(f"{name}: {required_payment} 결제 조건을 확인해주세요.")

    excluded_items = str(benefit.get("excluded_items", "")).strip()
    if excluded_items:
        status = "uncertain"
        reasons.append(f"{name}: 제외 상품 여부를 확인해주세요.")

    # 중복 정보가 불명확한 경우는 조합 단계에서 한 번만 표시
    return status, reasons


# =========================================================
# 할인/적립 계산
# =========================================================
def points_are_immediate_use(benefit):
    text = " ".join(
        [
            str(benefit.get("name", "")),
            str(benefit.get("conditions", "")),
        ]
    )

    return "사용" in text and "적립" not in text


def calculate_effect(current_price, starting_price, benefit):
    discount_type = benefit.get("discount_type", "unknown")
    value = safe_float(benefit.get("value"))
    min_purchase = safe_float(benefit.get("min_purchase"))
    max_discount = safe_float(benefit.get("max_discount"))

    basis = benefit.get("min_purchase_basis", "unknown")

    if basis == "starting_price":
        basis_price = starting_price
    elif basis == "before_benefit":
        basis_price = current_price
    else:
        # 기준을 모를 때는 더 보수적으로 현재 금액 기준으로 계산하고
        # 결과는 '확인 필요'로 표시
        basis_price = current_price

    if basis_price < min_purchase:
        return None

    immediate_discount = 0
    reward_value = 0

    if discount_type == "percent":
        immediate_discount = current_price * (value / 100)

    elif discount_type == "fixed":
        immediate_discount = value

    elif discount_type == "points":
        if points_are_immediate_use(benefit):
            immediate_discount = value
        else:
            reward_value = value

    else:
        return None

    if max_discount > 0:
        if immediate_discount > 0:
            immediate_discount = min(immediate_discount, max_discount)
        elif reward_value > 0:
            reward_value = min(reward_value, max_discount)

    immediate_discount = min(immediate_discount, current_price)

    if immediate_discount <= 0 and reward_value <= 0:
        return None

    return round(immediate_discount), round(reward_value)


CATEGORY_PRIORITY = {
    "coupon": 1,
    "membership": 2,
    "point": 3,
    "easy_pay": 4,
    "card": 5,
    "other": 6,
}


def candidate_orders(selected_benefits):
    coupons = [
        b for b in selected_benefits
        if normalize_category(b) == "coupon"
    ]

    others = [
        b for b in selected_benefits
        if normalize_category(b) != "coupon"
    ]

    others = sorted(
        others,
        key=lambda b: CATEGORY_PRIORITY.get(normalize_category(b), 99),
    )

    if len(coupons) <= 1:
        yield coupons + others
        return

    if len(coupons) <= 5:
        for coupon_order in itertools.permutations(coupons):
            yield list(coupon_order) + others
        return

    coupons = sorted(
        coupons,
        key=lambda b: safe_float(b.get("value")),
        reverse=True,
    )
    yield coupons + others


def apply_benefit_subset(starting_price, selected_benefits):
    if not selected_benefits:
        return {
            "payment_price": round(starting_price),
            "reward_value": 0,
            "effective_cost": round(starting_price),
            "steps": [],
        }

    best = None

    for ordered_benefits in candidate_orders(selected_benefits):
        current_price = starting_price
        total_reward = 0
        steps = []
        valid = True

        for benefit in ordered_benefits:
            effect = calculate_effect(
                current_price,
                starting_price,
                benefit,
            )

            if effect is None:
                valid = False
                break

            immediate_discount, reward_value = effect
            before = current_price
            current_price -= immediate_discount
            total_reward += reward_value

            steps.append(
                {
                    "benefit_id": benefit.get("id"),
                    "name": benefit.get("name", "혜택"),
                    "category": benefit.get(
                        "category_label",
                        benefit.get("category", "")
                    ),
                    "before": round(before),
                    "discount": round(immediate_discount),
                    "reward": round(reward_value),
                    "after": round(current_price),
                }
            )

        if valid:
            effective_cost = round(current_price - total_reward)

            candidate = {
                "payment_price": round(current_price),
                "reward_value": round(total_reward),
                "effective_cost": effective_cost,
                "steps": steps,
            }

            if (
                best is None
                or candidate["effective_cost"] < best["effective_cost"]
                or (
                    candidate["effective_cost"] == best["effective_cost"]
                    and candidate["payment_price"] < best["payment_price"]
                )
            ):
                best = candidate

    return best


# =========================================================
# 한 결제 그룹의 가능한 혜택 조합
# =========================================================
def calculate_group_plans(group_indices):
    starting_price = group_subtotal(group_indices)
    plans = []

    for mask in range(1 << benefit_count):
        selected_indices = [
            i for i in range(benefit_count)
            if mask & (1 << i)
        ]
        selected = [benefits[i] for i in selected_indices]

        compatibility = subset_compatibility(selected)

        if compatibility == "invalid":
            continue

        status = compatibility
        reasons = []
        skip = False

        for benefit in selected:
            benefit_status, benefit_reasons = individual_benefit_check(benefit)

            if benefit_status == "invalid":
                skip = True
                break

            if benefit_status == "uncertain":
                status = "uncertain"

            reasons.extend(benefit_reasons)

        if skip:
            continue

        pair_questions = get_uncertain_pairs(selected)

        # 중복 관계가 불명확한 경우
        if compatibility == "uncertain" and selected:
            reasons.append("선택한 혜택들의 중복 적용 가능 여부를 확인해주세요.")

        applied = apply_benefit_subset(starting_price, selected)

        if applied is None:
            continue

        consumed_mask = 0

        for idx in selected_indices:
            reuse_type = benefits[idx].get("reuse_type", "unknown")

            # 명확하게 재사용 가능인 혜택만 여러 결제에 반복 허용
            if reuse_type != "reusable":
                consumed_mask |= (1 << idx)

            if reuse_type == "unknown" and len(group_indices) < len(products):
                status = "uncertain"
                reasons.append(
                    f"{benefits[idx].get('name', '혜택')}: 분할결제 재사용 여부를 확인해주세요."
                )

        plans.append(
            {
                "mask": mask,
                "consumed_mask": consumed_mask,
                "status": status,
                "starting_price": round(starting_price),
                "payment_price": applied["payment_price"],
                "reward_value": applied["reward_value"],
                "effective_cost": applied["effective_cost"],
                "immediate_saving": round(starting_price - applied["payment_price"]),
                "total_benefit": round(starting_price - applied["effective_cost"]),
                "steps": applied["steps"],
                "benefit_names": [b.get("name", "혜택") for b in selected],
                "uncertain_reasons": unique_text(reasons),
                "uncertain_pairs": [
                    {
                        "a_id": a.get("id"),
                        "a_name": a.get("name", "혜택 A"),
                        "b_id": b.get("id"),
                        "b_name": b.get("name", "혜택 B"),
                    }
                    for a, b in pair_questions
                ],
            }
        )

    return plans


group_plan_cache = {}


def get_group_plans(group_key):
    group_key = tuple(sorted(group_key))

    if group_key not in group_plan_cache:
        group_plan_cache[group_key] = calculate_group_plans(group_key)

    return group_plan_cache[group_key]


# =========================================================
# 한 분할안 전체 최적화
# =========================================================
def option_signature(option):
    used_ids = []

    for choice in option["choices"]:
        for step in choice["plan"]["steps"]:
            benefit_id = step.get("benefit_id")
            if benefit_id and benefit_id not in used_ids:
                used_ids.append(benefit_id)

    return (
        round(option["effective_cost"]),
        tuple(sorted(used_ids)),
        len(option["choices"]),
    )


def keep_top_options(options, k=10):
    unique = {}

    for option in sorted(
        options,
        key=lambda x: (
            x["effective_cost"],
            x["uncertain_count"],
            len(x["choices"]),
            x["payment_price"],
        ),
    ):
        sig = option_signature(option)

        if sig not in unique:
            unique[sig] = option

        if len(unique) >= k:
            break

    return list(unique.values())


def best_for_partition(partition, allow_uncertain=True, k=8):
    states = {
        0: [
            {
                "payment_price": 0,
                "reward_value": 0,
                "effective_cost": 0,
                "choices": [],
                "uncertain_count": 0,
                "uncertain_reasons": [],
                "uncertain_pairs": [],
            }
        ]
    }

    for group in partition:
        group = tuple(sorted(group))
        group_plans = get_group_plans(group)

        if allow_uncertain:
            available_plans = [
                p for p in group_plans
                if p["status"] in {"confirmed", "uncertain"}
            ]
        else:
            available_plans = [
                p for p in group_plans
                if p["status"] == "confirmed"
            ]

        new_states = {}

        for used_mask, state_options in states.items():
            for state in state_options:
                for plan in available_plans:
                    if used_mask & plan["consumed_mask"]:
                        continue

                    new_mask = used_mask | plan["consumed_mask"]

                    candidate = {
                        "payment_price": state["payment_price"] + plan["payment_price"],
                        "reward_value": state["reward_value"] + plan["reward_value"],
                        "effective_cost": state["effective_cost"] + plan["effective_cost"],
                        "choices": state["choices"] + [
                            {
                                "group": group,
                                "plan": plan,
                            }
                        ],
                        "uncertain_count": (
                            state["uncertain_count"]
                            + (1 if plan["status"] == "uncertain" else 0)
                        ),
                        "uncertain_reasons": unique_text(
                            state["uncertain_reasons"] + plan["uncertain_reasons"]
                        ),
                        "uncertain_pairs": state["uncertain_pairs"] + plan.get("uncertain_pairs", []),
                    }

                    bucket = new_states.setdefault(new_mask, [])
                    bucket.append(candidate)
                    new_states[new_mask] = keep_top_options(bucket, k)

        states = new_states

    all_options = []

    for state_options in states.values():
        all_options.extend(state_options)

    return keep_top_options(all_options, k)


# =========================================================
# 전체 탐색
# =========================================================
partitions = generate_partitions()

if allow_split_payment and len(products) > MAX_EXHAUSTIVE_PRODUCTS:
    st.info(
        f"상품 종류가 {MAX_EXHAUSTIVE_PRODUCTS}개를 초과해 "
        "전체 결제·개별 결제·한 상품 분리 패턴을 우선 비교합니다."
    )

all_candidates = []
confirmed_candidates = []

try:
    with st.spinner("가장 유리한 결제 방법을 계산하고 있습니다..."):
        for partition in partitions:
            mixed_options = best_for_partition(
                partition,
                allow_uncertain=True,
                k=8,
            )

            for option in mixed_options:
                option["partition"] = partition
                all_candidates.append(option)

            confirmed_options = best_for_partition(
                partition,
                allow_uncertain=False,
                k=5,
            )

            for option in confirmed_options:
                option["partition"] = partition
                confirmed_candidates.append(option)

except Exception as error:
    st.error("최적 결제 방법을 계산하는 중 오류가 발생했습니다.")
    st.exception(error)
    st.stop()


# =========================================================
# 의미 없는 중복 추천 제거
# =========================================================
def global_unique_options(candidates, k=5):
    results = []
    seen = set()

    for option in sorted(
        candidates,
        key=lambda x: (
            x["effective_cost"],
            x["uncertain_count"],
            len(x["choices"]),
            x["payment_price"],
        ),
    ):
        sig = option_signature(option)

        if sig in seen:
            continue

        seen.add(sig)
        results.append(option)

        if len(results) >= k:
            break

    return results


ranked_options = global_unique_options(all_candidates, 5)
ranked_confirmed = global_unique_options(confirmed_candidates, 3)

if not ranked_options:
    st.error("현재 조건으로 계산 가능한 결제 방법을 찾지 못했습니다.")
    st.stop()

best_option = ranked_options[0]


# =========================================================
# 추천 결과용 도우미
# =========================================================
def payment_style_text(option):
    count = len(option["choices"])

    if count == 1:
        return "한 번에 결제"

    return f"{count}회 분할 결제"


def used_benefit_names(option):
    names = []

    for choice in option["choices"]:
        for name in choice["plan"]["benefit_names"]:
            if name not in names:
                names.append(name)

    return names


def total_immediate_saving(option):
    return round(total_original_price - option["payment_price"])


def total_benefit_value(option):
    return round(total_original_price - option["effective_cost"])


# =========================================================
# 1. 핵심 결과
# =========================================================
st.header("🏆 가장 유리한 결제 방법")

final_payment = round(best_option["payment_price"])
reward_value = round(best_option["reward_value"])
immediate_saving = total_immediate_saving(best_option)
total_benefit = total_benefit_value(best_option)

benefit_rate = (
    total_benefit / total_original_price * 100
    if total_original_price > 0
    else 0
)

# 핵심 숫자는 한 줄로
c1, arrow_col, c2, c3 = st.columns([1.15, 0.18, 1.25, 1.45])

with c1:
    st.caption("상품 총액")
    st.markdown(f"## {money(total_original_price)}")

with arrow_col:
    st.markdown("<br><h2 style='text-align:center;'>→</h2>", unsafe_allow_html=True)

with c2:
    st.caption("최종 결제금액")
    st.markdown(f"## **{money(final_payment)}**")

with c3:
    st.caption("총 혜택")
    st.markdown(f"## **{money(total_benefit)}**")
    st.caption(f"{percent(benefit_rate)} 절약 효과")

if reward_value > 0:
    st.success(
        f"즉시 할인 **{money(immediate_saving)}** + "
        f"적립 예상 **{reward_value:,.0f}P**"
    )
else:
    st.success(f"총 **{money(immediate_saving)}** 절약할 수 있습니다.")


# =========================================================
# 2. 실제 결제 방법 — 짧고 따라 하기 쉽게
# =========================================================
st.subheader("💳 이렇게 결제하세요")
st.write(f"**{payment_style_text(best_option)}**")

for payment_no, choice in enumerate(best_option["choices"], start=1):
    plan = choice["plan"]
    names = group_product_names(choice["group"])

    with st.container(border=True):
        # 상품이 많을 땐 이름을 길게 헤더로 쓰지 않음
        if len(names) == 1:
            st.markdown(f"**결제 {payment_no}. {names[0]}**")
        else:
            st.markdown(f"**결제 {payment_no}. 상품 {len(names)}개 함께 결제**")
            st.caption(" · ".join(names))

        if plan["steps"]:
            for step in plan["steps"]:
                if step["discount"] > 0:
                    st.write(f"→ **{step['name']}** · {money(step['discount'])} 할인")
                elif step["reward"] > 0:
                    st.write(f"→ **{step['name']}** · {step['reward']:,.0f}P 적립")
        else:
            st.write("→ 적용 혜택 없음")

        payment_line = f"**실제 결제 {money(plan['payment_price'])}**"
        if plan["reward_value"] > 0:
            payment_line += f" · 결제 후 **{plan['reward_value']:,.0f}P 적립 예상**"

        st.markdown(payment_line)


# =========================================================
# 3. 중복 여부 직접 확인
# =========================================================
pair_questions = []
seen_pair_keys = set()

for pair in best_option.get("uncertain_pairs", []):
    key = "||".join(sorted([str(pair["a_id"]), str(pair["b_id"])]))

    if key and key not in seen_pair_keys:
        seen_pair_keys.add(key)
        pair_questions.append(pair)

if pair_questions:
    st.warning(
        "⚠️ 중복 사용 여부를 확인하면 추천을 더 정확하게 다시 계산할 수 있습니다."
    )

    for idx, pair in enumerate(pair_questions[:3]):
        key = "||".join(sorted([str(pair["a_id"]), str(pair["b_id"])]))
        current_value = st.session_state.get("benefit_relations", {}).get(key)

        default_index = 0
        if current_value == "possible":
            default_index = 1
        elif current_value == "not_possible":
            default_index = 2

        answer = st.radio(
            f"{pair['a_name']} + {pair['b_name']}",
            ["아직 모르겠어요", "중복 가능", "중복 불가"],
            index=default_index,
            horizontal=True,
            key=f"relation_{idx}_{key}",
        )

        new_value = None
        if answer == "중복 가능":
            new_value = "possible"
        elif answer == "중복 불가":
            new_value = "not_possible"

        if new_value is not None and new_value != current_value:
            relations = st.session_state.get("benefit_relations", {}).copy()
            relations[key] = new_value
            st.session_state["benefit_relations"] = relations
            st.success("확인 결과를 반영해 다시 계산합니다.")
            st.rerun()

# =========================================================
# 4. 그 밖의 확인할 조건
# =========================================================
if best_option["uncertain_count"] > 0:
    reasons = unique_text(best_option["uncertain_reasons"])

    st.warning("⚠️ 결제 전에 아래 조건만 확인해주세요.")

    for reason in reasons[:3]:
        st.write(f"- {reason}")

    if len(reasons) > 3:
        with st.expander(f"추가 확인사항 {len(reasons) - 3}개"):
            for reason in reasons[3:]:
                st.write(f"- {reason}")
else:
    st.success("✅ 현재 입력 정보 기준으로 바로 적용 가능한 결제안입니다.")


# =========================================================
# 4. 다른 방법 — 한 곳에 접어서 표시
# =========================================================
confirmed_alternative = None
for option in ranked_confirmed:
    if option_signature(option) != option_signature(best_option):
        confirmed_alternative = option
        break

alternatives = [
    option
    for option in ranked_options[1:]
    if option_signature(option) != option_signature(best_option)
][:2]

if confirmed_alternative is not None or alternatives:
    with st.expander("🔄 다른 결제 방법 보기"):
        if (
            best_option["uncertain_count"] > 0
            and confirmed_alternative is not None
        ):
            st.markdown("**조건 확인 없이 선택할 수 있는 대안**")
            st.write(
                f"{payment_style_text(confirmed_alternative)} · "
                f"결제 **{money(confirmed_alternative['payment_price'])}** · "
                f"총 혜택 **{money(total_benefit_value(confirmed_alternative))}**"
            )
            st.divider()

        for rank, option in enumerate(alternatives, start=2):
            st.write(
                f"**{rank}순위** · {payment_style_text(option)} · "
                f"결제 **{money(option['payment_price'])}** · "
                f"총 혜택 **{money(total_benefit_value(option))}**"
            )


# =========================================================
# 5. 계산 근거 — 필요할 때만
# =========================================================
with st.expander("🧮 계산 근거 보기"):
    st.write(
        "상품 묶음과 분할 결제 여부, 쿠폰·멤버십·결제 혜택의 "
        "최소 결제금액 및 중복 조건을 비교해 실질 혜택이 가장 큰 방법을 선택했습니다."
    )
    st.write(f"- 상품 총액: **{money(total_original_price)}**")
    st.write(f"- 실제 결제 예정액: **{money(final_payment)}**")
    st.write(f"- 즉시 할인: **{money(immediate_saving)}**")
    if reward_value > 0:
        st.write(f"- 적립 예상: **{reward_value:,.0f}P**")
    st.write(f"- 총 혜택 가치: **{money(total_benefit)} ({percent(benefit_rate)})**")


# =========================================================
# 7. 3번 페이지에 전달
# =========================================================
st.session_state["best_payment_plan"] = best_option
st.session_state["optimized_final_price"] = final_payment
st.session_state["original_total_price"] = total_original_price
st.session_state["optimized_reward_value"] = reward_value
st.session_state["optimized_total_benefit"] = total_benefit

st.divider()
st.success(
    f"✅ 추천 결제금액 **{money(final_payment)}**을 저장했습니다. "
    "이제 **3_소비_판단**에서 소비 여력을 확인하세요."
)
