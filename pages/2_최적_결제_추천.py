import itertools
from datetime import date, datetime

import pandas as pd
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
    "1번 페이지에서 저장한 상품·혜택 정보를 바탕으로 "
    "중복 불가 조합을 제외하고, 한 번 결제와 분할 결제를 비교합니다."
)


# =========================================================
# 입력 데이터 확인
# =========================================================
products = st.session_state.get("products", [])
benefits = st.session_state.get("benefits", [])
allow_split_payment = st.session_state.get(
    "allow_split_payment",
    True
)
store_name = st.session_state.get(
    "store_name",
    ""
)


if not products:

    st.warning(
        "먼저 **1_상품_혜택_입력** 페이지에서 "
        "상품 정보를 저장해주세요."
    )

    st.stop()


if not benefits:

    st.warning(
        "먼저 **1_상품_혜택_입력** 페이지에서 "
        "혜택 정보를 저장해주세요."
    )

    st.stop()


# =========================================================
# MVP 계산 한도
# =========================================================
MAX_EXHAUSTIVE_BENEFITS = 12
MAX_EXHAUSTIVE_PRODUCTS = 5


# =========================================================
# 사용자 설정
# =========================================================
st.subheader("⚙️ 계산 기준")


col_a, col_b = st.columns(2)


with col_a:

    purchase_channel = st.selectbox(
        "이번 구매 채널",
        [
            "오프라인",
            "온라인"
        ],
        help=(
            "온라인/오프라인 전용 혜택 조건을 "
            "계산에 반영합니다."
        ),
    )


with col_b:

    min_purchase_basis = st.selectbox(
        "최소 결제금액 판단 기준",
        [
            "혜택 적용 직전 금액",
            "결제 시작 금액"
        ],
        help=(
            "혜택마다 최소 구매금액 판단 기준이 "
            "다를 수 있어 MVP에서는 사용자가 "
            "직접 선택하도록 합니다."
        ),
    )


st.caption(
    "※ 중복 여부·제외대상·기타조건처럼 자동으로 확정하기 어려운 조건은 "
    "확정 최적안과 별도로 표시합니다."
)


# =========================================================
# 기본 함수
# =========================================================
def money(value):

    return f"{safe_float(value):,.0f}원"


def safe_float(
    value,
    default=0.0
):

    try:

        if value is None:
            return default

        return float(value)

    except (
        TypeError,
        ValueError
    ):

        return default


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


def normalize_category(
    benefit
):

    return benefit.get(
        "category",
        "other"
    )


def relation_value(
    value
):

    if value is True:
        return "confirmed"

    if value is False:
        return "invalid"

    return "uncertain"


def merge_status(
    *statuses
):

    if "invalid" in statuses:
        return "invalid"

    if "uncertain" in statuses:
        return "uncertain"

    return "confirmed"


# =========================================================
# 상품 / 결제 그룹
# =========================================================
def product_line_total(
    product
):

    if "total" in product:

        return safe_float(
            product.get("total")
        )


    quantity = product.get(
        "quantity",
        1
    )

    try:

        quantity = int(quantity)

    except (
        TypeError,
        ValueError
    ):

        quantity = 1


    return (
        safe_float(
            product.get("price")
        )
        * quantity
    )


def group_subtotal(
    group_indices
):

    return sum(
        product_line_total(
            products[i]
        )
        for i in group_indices
    )


def group_product_names(
    group_indices
):

    names = []


    for i in group_indices:

        product = products[i]

        name = product.get(
            "name",
            f"상품 {i + 1}"
        )


        try:

            quantity = int(
                product.get(
                    "quantity",
                    1
                )
            )

        except (
            TypeError,
            ValueError
        ):

            quantity = 1


        if quantity > 1:

            names.append(
                f"{name} × {quantity}"
            )

        else:

            names.append(
                name
            )


    return names


# =========================================================
# 상품 분할 조합 생성
# =========================================================
def set_partitions(
    items
):

    if not items:

        yield []

        return


    first = items[0]


    for smaller in set_partitions(
        items[1:]
    ):

        yield (
            [[first]]
            + [
                group[:]
                for group
                in smaller
            ]
        )


        for i in range(
            len(smaller)
        ):

            new_partition = [
                group[:]
                for group
                in smaller
            ]


            new_partition[i] = (
                [first]
                + new_partition[i]
            )


            yield new_partition


def canonical_partition(
    partition
):

    normalized_groups = [
        tuple(
            sorted(group)
        )
        for group
        in partition
    ]


    return tuple(
        sorted(
            normalized_groups
        )
    )


def generate_partitions():

    n = len(products)

    all_indices = list(
        range(n)
    )


    if (
        not allow_split_payment
        or n == 1
    ):

        return [
            (
                tuple(all_indices),
            )
        ]


    if n <= MAX_EXHAUSTIVE_PRODUCTS:

        seen = set()

        results = []


        for partition in set_partitions(
            all_indices
        ):

            key = canonical_partition(
                partition
            )


            if key not in seen:

                seen.add(
                    key
                )

                results.append(
                    key
                )


        return results


    results = set()


    # 전체 한 번 결제
    results.add(
        (
            tuple(all_indices),
        )
    )


    # 전부 개별 결제
    results.add(
        tuple(
            (i,)
            for i in all_indices
        )
    )


    # 한 상품만 따로 결제
    for i in all_indices:

        rest = tuple(
            j
            for j in all_indices
            if j != i
        )


        if rest:

            results.add(
                canonical_partition(
                    [
                        (i,),
                        rest
                    ]
                )
            )


    return list(
        results
    )


# =========================================================
# 혜택 중복 가능 여부
# =========================================================

# 실제 결제수단
# 한 번의 결제건에서는 카드/간편결제 중 하나만 사용할 수 있음
PAYMENT_METHODS = {
    "card",
    "easy_pay",
}

# 포인트는 결제수단 자체가 아니므로 별도 취급
PAYMENT_RELATED = {
    "card",
    "easy_pay",
    "point",
}


def pair_compatibility(
    a,
    b
):

    ca = normalize_category(a)
    cb = normalize_category(b)

    # 1) 한 결제건에서 실제 결제수단은 1개만 허용
    # 카드+카드, 카드+간편결제, 간편결제+간편결제 모두 제외
    if (
        ca in PAYMENT_METHODS
        and cb in PAYMENT_METHODS
    ):
        return "invalid"

    # 2) 멤버십은 한 결제건에서 하나만 허용
    if (
        ca == "membership"
        and cb == "membership"
    ):
        return "invalid"

    # 3) 쿠폰 + 쿠폰
    if (
        ca == "coupon"
        and cb == "coupon"
    ):
        return merge_status(
            relation_value(
                a.get("stack_coupon")
            ),
            relation_value(
                b.get("stack_coupon")
            ),
        )

    # 4) 쿠폰 + 멤버십
    if {
        ca,
        cb
    } == {
        "coupon",
        "membership"
    }:
        coupon = (
            a
            if ca == "coupon"
            else b
        )
        membership = (
            b
            if ca == "coupon"
            else a
        )

        return merge_status(
            relation_value(
                coupon.get("stack_membership")
            ),
            relation_value(
                membership.get("stack_coupon")
            ),
        )

    # 5) 쿠폰 + 카드/간편결제/포인트
    if (
        ca == "coupon"
        and cb in PAYMENT_RELATED
    ) or (
        cb == "coupon"
        and ca in PAYMENT_RELATED
    ):
        coupon = (
            a
            if ca == "coupon"
            else b
        )
        payment_related = (
            b
            if ca == "coupon"
            else a
        )

        return merge_status(
            relation_value(
                coupon.get("stack_payment")
            ),
            relation_value(
                payment_related.get("stack_coupon")
            ),
        )

    # 6) 멤버십 + 카드/간편결제/포인트
    if (
        ca == "membership"
        and cb in PAYMENT_RELATED
    ) or (
        cb == "membership"
        and ca in PAYMENT_RELATED
    ):
        membership = (
            a
            if ca == "membership"
            else b
        )
        payment_related = (
            b
            if ca == "membership"
            else a
        )

        return merge_status(
            relation_value(
                membership.get("stack_payment")
            ),
            relation_value(
                payment_related.get("stack_membership")
            ),
        )

    # 7) 포인트 + 카드/간편결제
    # 포인트는 결제수단 자체가 아니므로 조건에 따라 동시 사용 가능
    if (
        ca == "point"
        and cb in PAYMENT_METHODS
    ) or (
        cb == "point"
        and ca in PAYMENT_METHODS
    ):
        point = (
            a
            if ca == "point"
            else b
        )
        payment_method = (
            b
            if ca == "point"
            else a
        )

        return merge_status(
            relation_value(
                point.get("stack_payment")
            ),
            relation_value(
                payment_method.get("stack_payment")
            ),
        )

    # 8) 포인트 + 포인트는 정보가 명확할 때까지 확인 필요
    if (
        ca == "point"
        and cb == "point"
    ):
        return "uncertain"

    return "uncertain"


def subset_compatibility(
    selected_benefits
):

    status = "confirmed"


    for a, b in itertools.combinations(
        selected_benefits,
        2
    ):

        pair_status = pair_compatibility(
            a,
            b
        )


        if pair_status == "invalid":

            return "invalid"


        if pair_status == "uncertain":

            status = "uncertain"


    return status


# =========================================================
# 채널 / 유효기간 / 자유문구 조건
# =========================================================
def channel_status(
    benefit
):

    label = str(
        benefit.get(
            "channel_label",
            "확인 필요"
        )
    ).strip()


    if label == "온·오프라인":

        return "confirmed"


    if label == "오프라인":

        return (
            "confirmed"
            if purchase_channel
            == "오프라인"
            else "invalid"
        )


    if label == "온라인":

        return (
            "confirmed"
            if purchase_channel
            == "온라인"
            else "invalid"
        )


    return "uncertain"


def expiry_status(
    benefit
):

    raw = str(
        benefit.get(
            "expiry",
            ""
        )
    ).strip()


    if not raw:

        return "confirmed"


    try:

        expiry_date = datetime.strptime(
            raw,
            "%Y-%m-%d"
        ).date()


        if expiry_date < date.today():

            return "invalid"


        return "confirmed"


    except ValueError:

        return "uncertain"


def text_condition_status(
    benefit
):

    excluded = str(
        benefit.get(
            "excluded_items",
            ""
        )
    ).strip()


    conditions = str(
        benefit.get(
            "conditions",
            ""
        )
    ).strip()


    if excluded:

        return "uncertain"


    if conditions:

        return "uncertain"


    return "confirmed"


def individual_benefit_status(
    benefit
):

    return merge_status(

        channel_status(
            benefit
        ),

        expiry_status(
            benefit
        ),

        text_condition_status(
            benefit
        ),
    )


# =========================================================
# 할인 계산
# =========================================================
def calculate_discount(
    current_price,
    starting_price,
    benefit
):

    discount_type = benefit.get(
        "discount_type",
        "unknown"
    )


    value = safe_float(
        benefit.get(
            "value"
        )
    )


    min_purchase = safe_float(
        benefit.get(
            "min_purchase"
        )
    )


    max_discount = safe_float(
        benefit.get(
            "max_discount"
        )
    )


    if (
        min_purchase_basis
        == "혜택 적용 직전 금액"
    ):

        basis_price = current_price

    else:

        basis_price = starting_price


    if basis_price < min_purchase:

        return None


    if discount_type == "percent":

        discount = (
            current_price
            * value
            / 100
        )


    elif discount_type in {
        "fixed",
        "points"
    }:

        discount = value


    else:

        return None


    if max_discount > 0:

        discount = min(
            discount,
            max_discount
        )


    discount = min(
        discount,
        current_price
    )


    if discount <= 0:

        return None


    return round(
        discount
    )


CATEGORY_PRIORITY = {
    "coupon": 1,
    "membership": 2,
    "point": 3,
    "easy_pay": 4,
    "card": 5,
    "other": 6,
}


def candidate_orders(
    selected_benefits
):

    coupons = [
        benefit
        for benefit
        in selected_benefits
        if normalize_category(
            benefit
        ) == "coupon"
    ]


    others = [
        benefit
        for benefit
        in selected_benefits
        if normalize_category(
            benefit
        ) != "coupon"
    ]


    others = sorted(

        others,

        key=lambda benefit:
        CATEGORY_PRIORITY.get(
            normalize_category(
                benefit
            ),
            99
        ),
    )


    if len(coupons) <= 1:

        yield (
            coupons
            + others
        )

        return


    if len(coupons) <= 5:

        for coupon_order in itertools.permutations(
            coupons
        ):

            yield (
                list(
                    coupon_order
                )
                + others
            )

        return


    coupons = sorted(

        coupons,

        key=lambda benefit:
        safe_float(
            benefit.get(
                "value"
            )
        ),

        reverse=True,
    )


    yield (
        coupons
        + others
    )


def apply_benefit_subset(
    starting_price,
    selected_benefits
):

    if not selected_benefits:

        return {
            "final_price":
                round(
                    starting_price
                ),

            "steps":
                [],
        }


    best = None


    for ordered_benefits in candidate_orders(
        selected_benefits
    ):

        current_price = (
            starting_price
        )

        steps = []

        valid = True


        for benefit in ordered_benefits:

            discount = calculate_discount(
                current_price,
                starting_price,
                benefit
            )


            if discount is None:

                valid = False

                break


            before = current_price

            current_price -= discount


            steps.append(
                {
                    "benefit_id":
                        benefit.get(
                            "id"
                        ),

                    "name":
                        benefit.get(
                            "name",
                            "혜택"
                        ),

                    "category":
                        benefit.get(
                            "category_label",
                            benefit.get(
                                "category",
                                ""
                            )
                        ),

                    "before":
                        round(
                            before
                        ),

                    "discount":
                        round(
                            discount
                        ),

                    "after":
                        round(
                            current_price
                        ),
                }
            )


        if valid:

            candidate = {
                "final_price":
                    round(
                        current_price
                    ),

                "steps":
                    steps,
            }


            if (
                best is None
                or
                candidate[
                    "final_price"
                ]
                <
                best[
                    "final_price"
                ]
            ):

                best = candidate


    return best


# =========================================================
# 결제 그룹별 가능한 혜택
# =========================================================
original_benefit_count = len(benefits)

if original_benefit_count > MAX_EXHAUSTIVE_BENEFITS:
    benefits = sorted(
        benefits,
        key=benefit_priority_score,
        reverse=True,
    )[:MAX_EXHAUSTIVE_BENEFITS]

    st.warning(
        f"혜택이 {original_benefit_count}개라 계산량이 매우 커질 수 있어 "
        f"조건이 명확하고 혜택값이 큰 {MAX_EXHAUSTIVE_BENEFITS}개를 우선 비교합니다. "
        "불필요한 혜택을 1번 페이지에서 삭제하면 더 정확히 비교할 수 있습니다."
    )

benefit_count = len(benefits)


def calculate_group_plans(
    group_indices
):

    starting_price = (
        group_subtotal(
            group_indices
        )
    )


    plans = []


    for mask in range(
        1 << benefit_count
    ):

        selected_indices = [
            i
            for i
            in range(
                benefit_count
            )
            if mask
            & (
                1 << i
            )
        ]


        selected = [
            benefits[i]
            for i
            in selected_indices
        ]


        compatibility = (
            subset_compatibility(
                selected
            )
        )


        if compatibility == "invalid":

            continue


        status = compatibility

        skip = False


        for benefit in selected:

            benefit_status = (
                individual_benefit_status(
                    benefit
                )
            )


            if benefit_status == "invalid":

                skip = True

                break


            if benefit_status == "uncertain":

                status = "uncertain"


        if skip:

            continue


        applied = (
            apply_benefit_subset(
                starting_price,
                selected
            )
        )


        if applied is None:

            continue


        plans.append(
            {
                "mask":
                    mask,

                "status":
                    status,

                "starting_price":
                    round(
                        starting_price
                    ),

                "final_price":
                    applied[
                        "final_price"
                    ],

                "savings":
                    round(
                        starting_price
                        -
                        applied[
                            "final_price"
                        ]
                    ),

                "steps":
                    applied[
                        "steps"
                    ],

                "benefit_names":
                    [
                        benefit.get(
                            "name",
                            "혜택"
                        )
                        for benefit
                        in selected
                    ],
            }
        )


    return plans


# =========================================================
# 분할 결제 최적화
# =========================================================
group_plan_cache = {}


def get_group_plans(
    group_key
):

    group_key = tuple(
        sorted(
            group_key
        )
    )


    if group_key not in group_plan_cache:

        group_plan_cache[
            group_key
        ] = calculate_group_plans(
            group_key
        )


    return group_plan_cache[
        group_key
    ]


def keep_top_k(
    options,
    k=3
):

    unique = {}


    for option in sorted(
        options,
        key=lambda x:
        x[
            "total_price"
        ]
    ):

        signature = tuple(
            (
                tuple(
                    choice[
                        "group"
                    ]
                ),

                choice[
                    "plan"
                ][
                    "mask"
                ],

                choice[
                    "plan"
                ][
                    "final_price"
                ],
            )

            for choice
            in option[
                "choices"
            ]
        )


        if signature not in unique:

            unique[
                signature
            ] = option


        if len(
            unique
        ) >= k:

            break


    return list(
        unique.values()
    )


def best_k_for_partition(
    partition,
    allow_uncertain=False,
    k=3
):

    states = {
        0: [
            {
                "total_price":
                    0,

                "choices":
                    [],

                "uncertain_count":
                    0,
            }
        ]
    }


    for group in partition:

        group = tuple(
            sorted(
                group
            )
        )


        group_plans = (
            get_group_plans(
                group
            )
        )


        if allow_uncertain:

            available_plans = [
                plan
                for plan
                in group_plans
                if plan[
                    "status"
                ]
                in {
                    "confirmed",
                    "uncertain"
                }
            ]


        else:

            available_plans = [
                plan
                for plan
                in group_plans
                if plan[
                    "status"
                ]
                == "confirmed"
            ]


        new_states = {}


        for (
            used_mask,
            state_options
        ) in states.items():


            for state in state_options:


                for plan in available_plans:


                    if (
                        used_mask
                        & plan[
                            "mask"
                        ]
                    ):

                        continue


                    new_mask = (
                        used_mask
                        |
                        plan[
                            "mask"
                        ]
                    )


                    candidate = {
                        "total_price":
                            state[
                                "total_price"
                            ]
                            +
                            plan[
                                "final_price"
                            ],

                        "choices":
                            state[
                                "choices"
                            ]
                            +
                            [
                                {
                                    "group":
                                        group,

                                    "plan":
                                        plan,
                                }
                            ],

                        "uncertain_count":
                            state[
                                "uncertain_count"
                            ]
                            +
                            (
                                1
                                if plan[
                                    "status"
                                ]
                                == "uncertain"
                                else 0
                            ),
                    }


                    bucket = (
                        new_states.setdefault(
                            new_mask,
                            []
                        )
                    )


                    bucket.append(
                        candidate
                    )


                    new_states[
                        new_mask
                    ] = keep_top_k(
                        bucket,
                        k
                    )


        states = new_states


    all_options = []


    for state_options in states.values():

        all_options.extend(
            state_options
        )


    return keep_top_k(
        all_options,
        k
    )


# =========================================================
# 전체 탐색
# =========================================================
total_original_price = round(
    sum(
        product_line_total(
            product
        )
        for product
        in products
    )
)


partitions = generate_partitions()


if (
    allow_split_payment
    and
    len(products)
    > MAX_EXHAUSTIVE_PRODUCTS
):

    st.warning(
        f"상품 종류가 {MAX_EXHAUSTIVE_PRODUCTS}개를 초과하여 "
        "계산량을 줄이기 위해 "
        "**전체 결제 / 전부 개별 결제 / 한 상품만 분리** "
        "패턴을 비교합니다."
    )


try:

    with st.spinner(
        "가능한 결제 조합과 분할 결제를 비교하고 있습니다..."
    ):

        confirmed_candidates = []

        uncertain_candidates = []


        for partition in partitions:


            confirmed = (
                best_k_for_partition(
                    partition,
                    allow_uncertain=False,
                    k=3,
                )
            )


            for option in confirmed:

                option[
                    "partition"
                ] = partition

                confirmed_candidates.append(
                    option
                )


            mixed = (
                best_k_for_partition(
                    partition,
                    allow_uncertain=True,
                    k=3,
                )
            )


            for option in mixed:

                if (
                    option[
                        "uncertain_count"
                    ]
                    > 0
                ):

                    option[
                        "partition"
                    ] = partition

                    uncertain_candidates.append(
                        option
                    )


except Exception as error:

    st.error(
        "최적 결제 조합을 계산하는 중 오류가 발생했습니다."
    )

    st.exception(
        error
    )

    st.stop()


# =========================================================
# 전체 TOP 3
# =========================================================
def plan_signature(
    option
):

    return tuple(
        (
            tuple(
                choice[
                    "group"
                ]
            ),

            choice[
                "plan"
            ][
                "mask"
            ],
        )

        for choice
        in option[
            "choices"
        ]
    )


def global_top_k(
    candidates,
    k=3
):

    seen = set()

    results = []


    for option in sorted(
        candidates,
        key=lambda x:
        x[
            "total_price"
        ]
    ):

        signature = (
            plan_signature(
                option
            )
        )


        if signature in seen:

            continue


        seen.add(
            signature
        )


        results.append(
            option
        )


        if len(
            results
        ) >= k:

            break


    return results


top_confirmed = global_top_k(
    confirmed_candidates,
    3
)


# 확정안보다 저렴할 가능성이 있는 후보만 표시
if top_confirmed:

    confirmed_best_price = (
        top_confirmed[
            0
        ][
            "total_price"
        ]
    )


    cheaper_uncertain = [
        option
        for option
        in uncertain_candidates
        if option[
            "total_price"
        ]
        <
        confirmed_best_price
    ]


else:

    cheaper_uncertain = (
        uncertain_candidates
    )


top_uncertain = global_top_k(
    cheaper_uncertain,
    3
)


# =========================================================
# 결과 표시
# =========================================================
def payment_style_text(
    option
):

    payment_count = len(
        option[
            "choices"
        ]
    )


    if payment_count == 1:

        return "한 번에 결제"


    return (
        f"{payment_count}회 분할 결제"
    )


def display_plan(
    option,
    rank,
    uncertain=False
):

    final_price = round(
        option[
            "total_price"
        ]
    )


    total_saving = (
        total_original_price
        -
        final_price
    )


    title = (
        f"{'⚠️' if uncertain else '🏆'} "
        f"{rank}위 — "
        f"{payment_style_text(option)} "
        f"→ **{money(final_price)}**"
    )


    with st.expander(
        title,
        expanded=(
            rank == 1
            and not uncertain
        )
    ):

        metric1, metric2, metric3 = (
            st.columns(3)
        )


        with metric1:

            st.metric(
                "상품 총액",
                money(
                    total_original_price
                )
            )


        with metric2:

            st.metric(
                "예상 최종 결제금액",
                money(
                    final_price
                )
            )


        with metric3:

            st.metric(
                "예상 절약",
                money(
                    total_saving
                )
            )


        if uncertain:

            st.warning(
                "이 방안에는 중복 여부·제외대상·기타조건 등 "
                "확인이 필요한 혜택이 포함되어 있습니다."
            )


        st.markdown(
            "#### 실제 결제 순서"
        )


        for payment_no, choice in enumerate(
            option[
                "choices"
            ],
            start=1
        ):

            group = choice[
                "group"
            ]

            plan = choice[
                "plan"
            ]


            names = (
                group_product_names(
                    group
                )
            )


            st.markdown(
                f"**결제 {payment_no}. "
                f"{' + '.join(names)}** "
                f"({money(plan['starting_price'])})"
            )


            if not plan[
                "steps"
            ]:

                st.write(
                    "→ 적용 혜택 없음"
                )


            else:

                for step_no, step in enumerate(
                    plan[
                        "steps"
                    ],
                    start=1
                ):

                    st.write(
                        f"{step_no}) "
                        f"**{step['name']}** 적용 "
                        f": {money(step['before'])} "
                        f"→ -{money(step['discount'])} "
                        f"→ **{money(step['after'])}**"
                    )


            st.write(
                "→ 이 결제 건 최종금액: "
                f"**{money(plan['final_price'])}**"
            )


        st.markdown(
            "#### 사용 혜택"
        )


        used_names = []


        for choice in option[
            "choices"
        ]:

            for name in choice[
                "plan"
            ][
                "benefit_names"
            ]:

                if name not in used_names:

                    used_names.append(
                        name
                    )


        if used_names:

            st.write(
                " · ".join(
                    used_names
                )
            )


        else:

            st.write(
                "적용 혜택 없음"
            )


# =========================================================
# 확정 가능한 최적 결제안
# =========================================================
st.divider()

st.header(
    "🏆 확정 가능한 최적 결제안 TOP 3"
)


if top_confirmed:

    summary_rows = []


    for rank, option in enumerate(
        top_confirmed,
        start=1
    ):

        final_price = round(
            option[
                "total_price"
            ]
        )


        summary_rows.append(
            {
                "순위":
                    rank,

                "결제 방식":
                    payment_style_text(
                        option
                    ),

                "예상 최종금액":
                    final_price,

                "총 절약금액":
                    total_original_price
                    -
                    final_price,
            }
        )


    summary_df = pd.DataFrame(summary_rows)
    summary_display_df = summary_df.copy()
    summary_display_df["예상 최종금액"] = summary_display_df["예상 최종금액"].apply(money)
    summary_display_df["총 절약금액"] = summary_display_df["총 절약금액"].apply(money)

    st.dataframe(
        summary_display_df,
        hide_index=True,
        width="stretch",
    )


    for rank, option in enumerate(
        top_confirmed,
        start=1
    ):

        display_plan(
            option,
            rank,
            uncertain=False
        )


    # 3페이지 전달
    best = top_confirmed[0]


    st.session_state[
        "best_payment_plan"
    ] = best


    st.session_state[
        "optimized_final_price"
    ] = round(
        best[
            "total_price"
        ]
    )


    st.session_state[
        "original_total_price"
    ] = (
        total_original_price
    )


else:

    st.error(
        "현재 입력 조건으로 확정 가능한 "
        "결제안을 만들지 못했습니다."
    )


# =========================================================
# 조건 확인 필요 후보
# =========================================================
st.divider()

st.header(
    "🔎 조건 확인 시 더 저렴할 수 있는 후보"
)


if top_uncertain:

    st.write(
        "아래 방안은 일부 혜택의 조건이 명확하지 않지만, "
        "조건이 충족될 경우 현재 확정 최적안보다 "
        "더 저렴할 가능성이 있습니다."
    )


    for rank, option in enumerate(
        top_uncertain,
        start=1
    ):

        display_plan(
            option,
            rank,
            uncertain=True
        )


else:

    st.success(
        "확정 최적안보다 더 저렴한 "
        "조건 확인 필요 후보는 없습니다."
    )


# =========================================================
# 다음 페이지 안내
# =========================================================
st.divider()


if top_confirmed:

    best_price = round(
        top_confirmed[
            0
        ][
            "total_price"
        ]
    )


    st.success(
        "✅ 현재 확정 가능한 최저 예상 결제금액은 "
        f"**{money(best_price)}**입니다."
    )


    st.write(
        "최적 결제 결과를 저장했습니다. "
        "이제 **3_소비_판단** 페이지로 이동하면 "
        "해당 결제금액을 기준으로 소비 가능 여부를 "
        "분석할 수 있습니다."
    )
