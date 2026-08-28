import itertools
import json
from datetime import date, datetime

import streamlit as st
from google import genai


# =========================================================
# 사용자 추가 조건 해석
# =========================================================

USER_CONDITION_SCHEMA = {
    "type": "object",
    "properties": {
        "benefit_updates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "target_benefit_name": {"type": "string"},
                    "scope_type": {
                        "type": "string",
                        "enum": ["cart", "brand", "product", "seller", "category", "unknown", "no_change"],
                    },
                    "scope_targets": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "eligible_brands": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "eligible_items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "excluded_items": {"type": "string"},
                    "required_payment_method": {"type": "string"},
                    "stack_coupon": {
                        "type": "string",
                        "enum": ["possible", "not_possible", "unknown", "no_change"],
                    },
                    "stack_membership": {
                        "type": "string",
                        "enum": ["possible", "not_possible", "unknown", "no_change"],
                    },
                    "stack_payment": {
                        "type": "string",
                        "enum": ["possible", "not_possible", "unknown", "no_change"],
                    },
                },
                "required": [
                    "target_benefit_name",
                    "scope_type",
                    "scope_targets",
                    "eligible_brands",
                    "eligible_items",
                    "excluded_items",
                    "required_payment_method",
                    "stack_coupon",
                    "stack_membership",
                    "stack_payment",
                ],
                "additionalProperties": False,
            },
        },
        "relation_updates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "benefit_a_name": {"type": "string"},
                    "benefit_b_name": {"type": "string"},
                    "relation": {
                        "type": "string",
                        "enum": ["possible", "not_possible"],
                    },
                },
                "required": [
                    "benefit_a_name",
                    "benefit_b_name",
                    "relation",
                ],
                "additionalProperties": False,
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["benefit_updates", "relation_updates", "summary"],
    "additionalProperties": False,
}


def user_condition_prompt(note, benefit_names, products_context):
    return f"""
너는 쇼핑 혜택 조건을 구조화하는 분석기다.

사용자가 이미 AI가 분석한 혜택에 대해 추가 조건을 자연어로 알려준다.
사용자의 말은 AI 분석보다 우선하는 확정 정보로 취급한다.

[현재 혜택명]
{json.dumps(benefit_names, ensure_ascii=False)}

[현재 상품/브랜드]
{json.dumps(products_context, ensure_ascii=False)}

[사용자 추가 조건]
{note}

규칙:
- target_benefit_name은 반드시 현재 혜택명 중 가장 알맞은 이름을 그대로 사용한다.
- "이 쿠폰은 라운드랩에만 적용돼" -> scope_type="brand", scope_targets=["라운드랩"].
- "A 쿠폰은 B 상품에만 적용돼" -> scope_type="product", scope_targets=["B"].
- "OO스토어 상품에만 적용돼" -> scope_type="seller", scope_targets=["OO스토어"].
- "스킨케어에만 적용돼" -> scope_type="category", scope_targets=["스킨케어"].
- "장바구니 전체에 적용돼" -> scope_type="cart", scope_targets=[].
- "A 쿠폰은 다른 쿠폰과 중복 안 돼"라면 stack_coupon="not_possible".
- "A 쿠폰은 카드 할인과 중복돼"라면 stack_payment="possible".
- "A 혜택과 B 혜택은 같이 못 써"라면 relation_updates에 두 혜택 관계를 not_possible로 넣는다.
- 사용자가 말하지 않은 속성은 빈 배열/빈 문자열/no_change로 둔다.
- 사용자가 어떤 혜택을 가리키는지 합리적으로 특정할 수 없으면 benefit_updates에 억지로 넣지 말고 summary에서 다시 확인이 필요하다고 안내한다.
- summary는 사용자에게 직접 보여줄 짧은 존댓말 문장으로 작성한다.
"""


GEMINI_CONDITION_MODEL = "gemini-3-flash-preview"


def get_condition_client():
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def interpret_condition_on_result(note, current_benefits, current_products):
    client = get_condition_client()

    if client is None:
        raise RuntimeError("GEMINI_API_KEY가 없습니다.")

    benefit_names = [
        str(b.get("name", "")).strip()
        for b in current_benefits
        if str(b.get("name", "")).strip()
    ]

    products_context = [
        {
            "name": str(p.get("name", "")).strip(),
            "brand": str(p.get("brand", "")).strip(),
        }
        for p in current_products
    ]

    interaction = client.interactions.create(
        model=GEMINI_CONDITION_MODEL,
        input=[
            {
                "type": "text",
                "text": user_condition_prompt(
                    note,
                    benefit_names,
                    products_context,
                ),
            }
        ],
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": USER_CONDITION_SCHEMA,
        },
        store=False,
    )

    return json.loads(interaction.output_text)


def apply_condition_to_saved_benefits(
    current_benefits,
    result,
):
    updated = [dict(b) for b in current_benefits]

    for update in result.get("benefit_updates", []):
        target = str(
            update.get("target_benefit_name", "")
        ).strip()

        matches = [
            i
            for i, benefit in enumerate(updated)
            if str(benefit.get("name", "")).strip() == target
        ]

        if len(matches) != 1:
            continue

        i = matches[0]
        benefit = updated[i]

        scope_type = update.get("scope_type", "no_change")
        scope_targets = update.get("scope_targets", []) or []
        brands = update.get("eligible_brands", []) or []
        items = update.get("eligible_items", []) or []

        if scope_type != "no_change":
            benefit["scope_type"] = scope_type
            benefit["scope_targets"] = scope_targets
            benefit["scope_confidence"] = "high"

            # legacy compatibility
            benefit["eligible_brands"] = (
                scope_targets if scope_type == "brand" else []
            )
            benefit["eligible_items"] = (
                scope_targets if scope_type == "product" else []
            )

        excluded = str(
            update.get("excluded_items", "")
        ).strip()
        required_payment = str(
            update.get("required_payment_method", "")
        ).strip()

        if brands:
            benefit["eligible_brands"] = brands

        if items:
            benefit["eligible_items"] = items

        if excluded:
            benefit["excluded_items"] = excluded

        if required_payment:
            benefit[
                "required_payment_method"
            ] = required_payment

        for source_key, target_key in [
            ("stack_coupon", "stack_coupon"),
            ("stack_membership", "stack_membership"),
            ("stack_payment", "stack_payment"),
        ]:
            value = update.get(source_key, "no_change")

            if value == "possible":
                benefit[target_key] = True
            elif value == "not_possible":
                benefit[target_key] = False
            elif value == "unknown":
                benefit[target_key] = None

    return updated


def relation_updates_to_map(
    relation_updates,
    current_benefits,
):
    name_to_ids = {}

    for benefit in current_benefits:
        name_to_ids.setdefault(
            benefit.get("name", ""),
            [],
        ).append(benefit.get("id"))

    relations = st.session_state.get(
        "benefit_relations",
        {},
    ).copy()

    for relation in relation_updates:
        a_name = relation.get("benefit_a_name", "")
        b_name = relation.get("benefit_b_name", "")
        value = relation.get("relation")

        if (
            a_name in name_to_ids
            and b_name in name_to_ids
            and len(name_to_ids[a_name]) == 1
            and len(name_to_ids[b_name]) == 1
        ):
            key = "||".join(
                sorted([
                    str(name_to_ids[a_name][0]),
                    str(name_to_ids[b_name][0]),
                ])
            )

            if value in {"possible", "not_possible"}:
                relations[key] = value

    return relations


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
    raw = str(benefit.get("category", "other") or "other").strip().lower()
    aliases = {
        "쿠폰": "coupon",
        "coupon": "coupon",
        "결제": "payment",
        "결제혜택": "payment",
        "payment": "payment",
        "간편결제": "payment",
        "포인트": "payment",
        "points": "payment",
        "멤버십": "membership",
        "membership": "membership",
        "배송": "shipping",
        "shipping": "shipping",
        "기타": "other",
        "other": "other",
    }
    return aliases.get(raw, raw or "other")


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


def normalize_text(value):
    return str(value or "").strip().lower().replace(" ", "")


def fuzzy_target_match(value, targets):
    value = normalize_text(value)
    if not value:
        return False

    normalized_targets = [
        normalize_text(target)
        for target in targets
        if normalize_text(target)
    ]

    return any(
        value == target
        or target in value
        or value in target
        for target in normalized_targets
    )


def benefit_scope(benefit):
    scope_type = str(
        benefit.get("scope_type", "")
    ).strip().lower()
    scope_targets = benefit.get("scope_targets", []) or []

    # 이전 데이터와 호환
    if not scope_type or scope_type == "unknown":
        legacy_brands = benefit.get("eligible_brands", []) or []
        legacy_items = benefit.get("eligible_items", []) or []

        if legacy_brands:
            return "brand", legacy_brands
        if legacy_items:
            return "product", legacy_items

    return scope_type or "cart", scope_targets


def benefit_target_indices(group_indices, benefit):
    """플랫폼과 무관한 공통 scope 기준으로 실제 적용 상품을 찾는다."""
    scope_type, targets = benefit_scope(benefit)

    if scope_type == "cart":
        return list(group_indices)

    if scope_type == "unknown":
        # 범위를 모르는 혜택은 전체 적용으로 확정하지 않음.
        return []

    matched = []

    for i in group_indices:
        product = products[i]

        if scope_type == "brand":
            candidate = product.get("brand", "")
        elif scope_type == "product":
            candidate = product.get("name", "")
        elif scope_type == "seller":
            candidate = product.get("seller", "")
        elif scope_type == "category":
            candidate = product.get("category", "")
        else:
            candidate = ""

        if fuzzy_target_match(candidate, targets):
            matched.append(i)

    return matched


def benefit_target_subtotal(group_indices, benefit):
    return sum(
        product_line_total(products[i])
        for i in benefit_target_indices(
            group_indices,
            benefit,
        )
    )


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
# 자동 판단 정책
# =========================================================
# 1. 사용자 직접 확인 > AI의 명시적 관계 판단 > 구조화된 명시 조건 순으로 신뢰합니다.
# 2. unknown을 임의로 possible/not_possible로 확정하지 않습니다.
# 3. 서로 다른 필수 결제수단, 동일 exclusive_group 등 논리적으로 명확한 경우만 자동 제외합니다.
# 4. 불확실성은 기본적으로 보수적으로 유지합니다.
# 5. 사용자 질문은 현재 최적 결과를 실제로 바꿀 수 있을 때만 최대 1개 노출합니다.


# =========================================================
# 혜택 간 중복 가능 여부
# =========================================================
PAYMENT_METHODS = {"card", "easy_pay", "payment"}
PAYMENT_RELATED = {"card", "easy_pay", "payment", "point"}


def relation_key(a, b):
    ids = sorted([str(a.get("id", "")), str(b.get("id", ""))])
    return "||".join(ids)


def relation_key(a, b):
    ids = sorted([str(a.get("id", "")), str(b.get("id", ""))])
    return "||".join(ids)


def pair_compatibility(a, b):
    key = relation_key(a, b)

    # 0) 사용자가 직접 확인한 답이 최우선
    user_relations = st.session_state.get("benefit_relations", {})
    user_relation = user_relations.get(key)

    if user_relation == "possible":
        return "confirmed"
    if user_relation == "not_possible":
        return "invalid"

    # 1) Gemini가 전체 혜택을 비교해 판단한 관계
    ai_relations = st.session_state.get("ai_benefit_relations", {})
    ai_relation = ai_relations.get(key)

    if ai_relation == "possible":
        return "confirmed"
    if ai_relation == "not_possible":
        return "invalid"

    # 2) AI가 같은 택일 그룹으로 묶은 경우
    group_a = str(a.get("exclusive_group", "")).strip()
    group_b = str(b.get("exclusive_group", "")).strip()

    if group_a and group_b and group_a == group_b:
        return "invalid"

    ca = normalize_category(a)
    cb = normalize_category(b)

    # 특정 플랫폼명을 하드코딩하지 않고, 명시된 결제수단 문자열 자체를 비교합니다.
    required_a = str(a.get("required_payment_method", "")).strip()
    required_b = str(b.get("required_payment_method", "")).strip()

    if (
        required_a
        and required_b
        and required_a.lower() != required_b.lower()
    ):
        return "invalid"

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
    # required_payment_method가 있으면 '불확실성'이 아니라 명시 조건으로 취급합니다.
    # 실제 추천 문구에서 해당 결제수단을 안내하면 되므로 사용자에게 재확인하지 않습니다.

    excluded_items = str(benefit.get("excluded_items", "")).strip()
    if excluded_items:
        # 제외상품 문구는 단순 문자열 유사도만으로 자동 확정하지 않습니다.
        # 실제 적용 대상(scope)에서 명확히 제외된 정보가 구조화되어 있지 않다면
        # 내부 불확실성으로만 남기고, 최적 결과를 바꾸는 경우에만 질문 후보가 됩니다.
        status = "uncertain"
        reasons.append(
            f"{name}: 제외 상품 조건이 있어 보수적으로 처리했습니다."
        )

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


def calculate_effect(
    current_price,
    starting_price,
    benefit,
    target_starting_price=None,
    target_current_price=None,
):
    discount_type = benefit.get("discount_type", "unknown")
    value = safe_float(benefit.get("value"))
    min_purchase = safe_float(benefit.get("min_purchase"))
    max_discount = safe_float(benefit.get("max_discount"))

    # 브랜드/상품 한정 혜택이면 대상 상품 금액만 계산 기준으로 사용
    effective_starting = (
        starting_price
        if target_starting_price is None
        else target_starting_price
    )
    effective_current = (
        current_price
        if target_current_price is None
        else target_current_price
    )

    if effective_starting <= 0:
        return None

    basis = benefit.get("min_purchase_basis", "unknown")

    if basis == "starting_price":
        basis_price = effective_starting
    elif basis == "before_benefit":
        basis_price = effective_current
    else:
        basis_price = effective_current

    if basis_price < min_purchase:
        return None

    immediate_discount = 0
    reward_value = 0

    if discount_type == "percent":
        immediate_discount = effective_current * (value / 100)

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

    immediate_discount = min(immediate_discount, effective_current, current_price)

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


def apply_benefit_subset(starting_price, selected_benefits, group_indices):
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
            target_starting_price = benefit_target_subtotal(
                group_indices,
                benefit,
            )

            # 이전 할인 적용 뒤 해당 대상 상품군에 남아 있을 것으로 보는 금액.
            # 전체 결제금액 감소 비율을 대상 금액에도 동일하게 적용하는 MVP 근사치.
            ratio = (
                current_price / starting_price
                if starting_price > 0
                else 1
            )
            target_current_price = round(
                target_starting_price * ratio
            )

            effect = calculate_effect(
                current_price,
                starting_price,
                benefit,
                target_starting_price=target_starting_price,
                target_current_price=target_current_price,
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
                    "scope_type": benefit_scope(benefit)[0],
                    "scope_targets": benefit_scope(benefit)[1],
                    "eligible_brands": benefit.get("eligible_brands", []) or [],
                    "eligible_items": benefit.get("eligible_items", []) or [],
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

        applied = apply_benefit_subset(
            starting_price,
            selected,
            group_indices,
        )

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
        round(option["payment_price"]),
        round(option["reward_value"]),
        round(option["effective_cost"]),
        tuple(sorted(used_ids)),
        len(option["choices"]),
    )


def visible_result_signature(option):
    """사용자 화면에서 사실상 같은 추천안은 하나만 남긴다."""
    return (
        round(option["payment_price"]),
        round(option["reward_value"]),
        round(total_original_price - option["effective_cost"]),
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
    seen_logic = set()
    seen_visible = set()

    for option in sorted(
        candidates,
        key=lambda x: (
            x["effective_cost"],
            x["uncertain_count"],
            len(x["choices"]),
            x["payment_price"],
        ),
    ):
        logic_sig = option_signature(option)
        visible_sig = (
            round(option["payment_price"]),
            round(option["reward_value"]),
            round(total_original_price - option["effective_cost"]),
            len(option["choices"]),
        )

        if logic_sig in seen_logic or visible_sig in seen_visible:
            continue

        seen_logic.add(logic_sig)
        seen_visible.add(visible_sig)
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


# AI가 적용 범위를 모르는 혜택이 있으면 계산에 무리하게 포함하지 않음
unknown_scope_benefits = [
    benefit
    for benefit in benefits
    if benefit_scope(benefit)[0] == "unknown"
]

if unknown_scope_benefits:
    with st.expander(
        f"AI가 보수적으로 처리한 적용 범위 {len(unknown_scope_benefits)}개"
    ):
        st.caption(
            "적용 대상을 확정하기 어려운 혜택은 자동으로 보수적으로 처리했습니다. "
            "추천 결과가 실제 조건과 다를 때만 수정하시면 됩니다."
        )
        for benefit in unknown_scope_benefits[:5]:
            st.write(f"- {benefit.get('name', '혜택')}")

# =========================================================
# 실제 조건과 다른 부분 수정
# =========================================================
with st.expander("✏️ 실제 조건과 다른 부분 수정"):
    st.caption(
        "추천 결과에서 AI가 놓친 쿠폰·결제 조건이 있다면 알려주세요. "
        "조건을 반영한 뒤 최적 결제 방법을 바로 다시 계산합니다."
    )

    correction_note = st.text_area(
        "수정할 실제 조건",
        placeholder=(
            "예) 9천원 쿠폰은 닥터지 제품에만 적용 가능해\n"
            "예) 이 쿠폰은 네이버페이 혜택과 중복이 안 돼"
        ),
        key="page2_condition_correction",
        label_visibility="collapsed",
    )

    if st.button(
        "🔄 조건 반영 후 다시 계산",
        key="apply_page2_condition",
    ):
        if not correction_note.strip():
            st.warning("실제 조건을 입력해주세요.")
        else:
            with st.spinner("조건을 이해하고 다시 계산하고 있습니다..."):
                try:
                    result = interpret_condition_on_result(
                        correction_note,
                        st.session_state.get("benefits", []),
                        st.session_state.get("products", []),
                    )

                    updated_benefits = apply_condition_to_saved_benefits(
                        st.session_state.get("benefits", []),
                        result,
                    )

                    st.session_state["benefits"] = updated_benefits
                    st.session_state["benefit_relations"] = (
                        relation_updates_to_map(
                            result.get("relation_updates", []),
                            updated_benefits,
                        )
                    )

                    notes = st.session_state.get(
                        "user_condition_history",
                        [],
                    )
                    notes.append({
                        "text": correction_note.strip(),
                        "summary": result.get("summary", ""),
                    })
                    st.session_state[
                        "user_condition_history"
                    ] = notes

                    st.session_state[
                        "last_page2_condition_summary"
                    ] = result.get(
                        "summary",
                        "조건을 반영했습니다.",
                    )

                    st.rerun()

                except Exception as error:
                    st.error("조건을 반영하지 못했습니다.")
                    with st.expander("오류 상세 보기"):
                        st.code(str(error))

if st.session_state.get("last_page2_condition_summary"):
    st.success(
        "✅ " + st.session_state[
            "last_page2_condition_summary"
        ]
    )


# =========================================================
# 2. 실제 결제 방법 — 분할결제 포함
# =========================================================
st.subheader("💳 이렇게 결제하세요")

if len(best_option["choices"]) == 1:
    st.write("**추천 방식: 한 번에 결제**")
else:
    st.write(
        f"**추천 방식: {len(best_option['choices'])}회 분할 결제**"
    )
    st.caption(
        "상품을 나누어 결제했을 때 쿠폰·결제혜택 조건을 더 유리하게 활용할 수 있어 "
        "분할 결제가 최적안으로 선택되었습니다."
    )

for payment_no, choice in enumerate(best_option["choices"], start=1):
    plan = choice["plan"]
    names = group_product_names(choice["group"])

    with st.container(border=True):
        if len(best_option["choices"]) == 1:
            st.markdown(
                f"### 한 번에 {money(plan['starting_price'])} 결제"
            )
        else:
            st.markdown(
                f"### 결제 {payment_no} · {money(plan['starting_price'])}"
            )

        if len(names) <= 2:
            st.caption(" · ".join(names))
        else:
            st.caption(" · ".join(names[:2]) + f" 외 {len(names) - 2}개")

        if plan["steps"]:
            for step in plan["steps"]:
                if step["discount"] > 0:
                    target_label = ""
                    scope_type = step.get("scope_type", "cart")
                    scope_targets = step.get("scope_targets", []) or []

                    scope_names = {
                        "brand": "브랜드",
                        "product": "상품",
                        "seller": "판매자",
                        "category": "카테고리",
                    }

                    if scope_type in scope_names and scope_targets:
                        target_label = (
                            f" ({scope_names[scope_type]}: "
                            f"{', '.join(scope_targets)} 대상)"
                        )

                    st.write(
                        f"→ **{step['name']}**{target_label} · {money(step['discount'])} 할인"
                    )
                elif step["reward"] > 0:
                    st.write(
                        f"→ **{step['name']}** · {step['reward']:,.0f}P 적립"
                    )
        else:
            st.write("→ 적용 혜택 없음")

        result_text = f"**실제 결제 {money(plan['payment_price'])}**"

        if plan["reward_value"] > 0:
            result_text += f" · **{plan['reward_value']:,.0f}P 적립 예상**"

        st.markdown(result_text)

# 분할 결제인 경우 전체 합계를 한 번 더 짧게 보여줌
if len(best_option["choices"]) > 1:
    st.info(
        f"분할 결제 합계 **{money(final_payment)}**"
        + (
            f" · 총 적립 예상 **{reward_value:,.0f}P**"
            if reward_value > 0 else ""
        )
    )


# =========================================================
# 3. 결과를 실제로 바꿀 수 있는 조건만 최대 1개 확인
# =========================================================
best_confirmed_option = ranked_confirmed[0] if ranked_confirmed else None

decision_gain = 0
if best_confirmed_option is not None:
    decision_gain = max(
        0,
        round(
            best_confirmed_option["effective_cost"]
            - best_option["effective_cost"]
        ),
    )

pair_questions = []
seen_pair_keys = set()

# 현재 1위안이 불확실하고, 그 불확실성을 허용했을 때 실제로 더 이득인 경우에만 질문 후보 생성
if (
    best_option.get("uncertain_count", 0) > 0
    and decision_gain > 0
):
    for pair in best_option.get("uncertain_pairs", []):
        key = "||".join(
            sorted([
                str(pair["a_id"]),
                str(pair["b_id"]),
            ])
        )
        if key and key not in seen_pair_keys:
            seen_pair_keys.add(key)
            pair_questions.append(pair)

critical_question_shown = False

# 질문은 최대 1개만 노출
if pair_questions:
    pair = pair_questions[0]
    key = "||".join(
        sorted([
            str(pair["a_id"]),
            str(pair["b_id"]),
        ])
    )
    current_value = st.session_state.get(
        "benefit_relations",
        {},
    ).get(key)

    st.warning(
        f"⚠️ 이 조건 하나에 따라 최대 {money(decision_gain)} 차이가 날 수 있어 확인이 필요합니다."
    )

    answer = st.radio(
        f"**{pair['a_name']}**과 **{pair['b_name']}**을 함께 사용할 수 있나요?",
        ["잘 모르겠어요", "중복 가능", "중복 불가"],
        horizontal=True,
        key=f"critical_relation_{key}",
    )

    critical_question_shown = True

    new_value = None
    if answer == "중복 가능":
        new_value = "possible"
    elif answer == "중복 불가":
        new_value = "not_possible"

    if new_value is not None and new_value != current_value:
        relations = st.session_state.get(
            "benefit_relations",
            {},
        ).copy()
        relations[key] = new_value
        st.session_state["benefit_relations"] = relations
        st.rerun()

    if answer == "잘 모르겠어요":
        if best_confirmed_option is not None:
            st.caption(
                f"몰라도 괜찮습니다. 확실한 조건만 사용하면 "
                f"**{money(best_confirmed_option['payment_price'])}**에 결제할 수 있습니다."
            )
        else:
            st.caption(
                "몰라도 괜찮습니다. 불확실한 혜택은 보수적으로 제외하고 판단합니다."
            )

# 관계 질문이 없거나 결과 차이가 없다면 확인사항을 사용자에게 쏟아내지 않음
if not critical_question_shown:
    if best_option.get("uncertain_count", 0) == 0:
        st.success("✅ 현재 입력 정보 기준으로 바로 적용 가능한 결제안입니다.")
    elif decision_gain <= 0:
        st.success(
            "✅ 일부 세부 조건이 불확실하지만 최적 결제 결과에는 영향을 주지 않습니다."
        )
    else:
        st.caption(
            "AI가 세부 조건을 보수적으로 반영했습니다. "
            "결과를 바꿀 정도로 중요한 확인사항은 없습니다."
        )

# 세부 불확실성은 기본 화면에 나열하지 않고, 필요할 때만 확인할 수 있게 숨김
all_uncertain_reasons = unique_text(
    best_option.get("uncertain_reasons", [])
)

if all_uncertain_reasons:
    with st.expander("AI가 보수적으로 처리한 세부 조건 보기"):
        st.caption(
            "아래 항목은 참고용입니다. 현재 추천을 사용하기 위해 모두 확인할 필요는 없습니다."
        )
        for reason in all_uncertain_reasons[:8]:
            st.write(f"- {reason}")


# =========================================================
# 5. 다른 방법 — 필요할 때만
# =========================================================
confirmed_alternative = None

for option in ranked_confirmed:
    if visible_result_signature(option) != visible_result_signature(best_option):
        confirmed_alternative = option
        break

alternatives = []
seen_alt = {visible_result_signature(best_option)}

for option in ranked_options[1:]:
    sig = visible_result_signature(option)

    if sig in seen_alt:
        continue

    seen_alt.add(sig)
    alternatives.append(option)

    if len(alternatives) >= 2:
        break

if confirmed_alternative is not None or alternatives:
    with st.expander("🔄 다른 결제 방법 보기"):
        if (
            best_option["uncertain_count"] > 0
            and confirmed_alternative is not None
        ):
            alt_immediate = total_immediate_saving(confirmed_alternative)
            alt_reward = round(confirmed_alternative["reward_value"])

            st.markdown("**🛡️ 조건 확인 없이 선택 가능한 대안**")
            st.write(
                f"실제 결제 **{money(confirmed_alternative['payment_price'])}** · "
                f"즉시 할인 **{money(alt_immediate)}**"
                + (
                    f" · 적립 **{alt_reward:,.0f}P**"
                    if alt_reward > 0 else ""
                )
            )
            st.divider()

        for idx, option in enumerate(alternatives, start=1):
            alt_immediate = total_immediate_saving(option)
            alt_reward = round(option["reward_value"])

            st.markdown(f"**대안 {idx}**")
            st.write(
                f"**{payment_style_text(option)}** · "
                f"실제 결제 **{money(option['payment_price'])}** · "
                f"즉시 할인 **{money(alt_immediate)}**"
                + (
                    f" · 적립 **{alt_reward:,.0f}P**"
                    if alt_reward > 0 else ""
                )
            )


# =========================================================
# 5. 계산 근거 — 필요할 때만
# =========================================================
with st.expander("🤖 AI가 판단한 혜택 관계 보기"):
    relation_meta = st.session_state.get("ai_benefit_relation_meta", {})

    if not relation_meta:
        st.write("AI가 별도로 확정한 혜택 간 관계가 없습니다.")
    else:
        shown = 0
        for meta in relation_meta.values():
            if meta.get("confidence") not in {"high", "medium"}:
                continue
            relation_text = (
                "중복 가능"
                if meta.get("relation") == "possible"
                else "동시 사용 불가"
                if meta.get("relation") == "not_possible"
                else "확인 필요"
            )
            st.write(
                f"- **{meta.get('a_name')} + {meta.get('b_name')}**: "
                f"{relation_text} · {meta.get('reason', '')} "
                f"({meta.get('confidence')} confidence)"
            )
            shown += 1
            if shown >= 5:
                break

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
    st.write(
        f"- 총 혜택 가치(즉시 할인 + 적립): "
        f"**{money(total_benefit)} ({percent(benefit_rate)})**"
    )

    if allow_split_payment and len(products) > 1:
        st.write(
            f"- 결제 방식 비교: **한 번 결제 + 분할 결제 조합 비교 완료**"
        )


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
