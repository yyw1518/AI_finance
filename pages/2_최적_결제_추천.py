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
MAX_BENEFITS = 8
MAX_EXHAUSTIVE_PRODUCTS = 5


if len(benefits) > MAX_BENEFITS:

    st.error(
        f"현재 MVP는 혜택 **{MAX_BENEFITS}개까지** "
        "전수 비교하도록 설정되어 있습니다. "
        "1번 페이지에서 가장 관련 있는 혜택만 남겨주세요."
    )

    st.stop()


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
# =========================================================
# 혜택 중복 가능 여부
# =========================================================

# 실제 결제수단
# 한 번의 결제건에서는 이 중 하나만 사용할 수 있음
PAYMENT_METHODS = {
    "card",
    "easy_pay",
}

# 결제와 관련해 중복 조건을 확인해야 하는 혜택
# 포인트는 결제수단 자체가 아니므로 PAYMENT_METHODS에는 넣지 않음
PAYMENT_RELATED = {
    "card",
    "easy_pay",
    "point",
}


def pair_compatibility(a, b):

    ca = normalize_category(a)
    cb = normalize_category(b)

    # -----------------------------------------------------
    # 1. 가장 중요한 규칙
    # 한 결제건에서 결제수단은 무조건 1개만 사용
    # -----------------------------------------------------
    if (
        ca in PAYMENT_METHODS
        and cb in PAYMENT_METHODS
    ):
        return "invalid"

    # 예:
    # 신한카드 + 현대카드 → 불가
    # 신한카드 + 카카오페이 → 불가
    # 카카오페이 + 네이버페이 → 불가


    # -----------------------------------------------------
    # 2. 멤버십은 한 결제건에서 하나만 사용
    # -----------------------------------------------------
    if (
        ca == "membership"
        and cb == "membership"
    ):
        return "invalid"


    # -----------------------------------------------------
    # 3. 쿠폰 + 쿠폰
    # -----------------------------------------------------
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


    # -----------------------------------------------------
    # 4. 쿠폰 + 멤버십
    # -----------------------------------------------------
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
                coupon.get(
                    "stack_membership"
                )
            ),

            relation_value(
                membership.get(
                    "stack_coupon"
                )
            ),
        )


    # -----------------------------------------------------
    # 5. 쿠폰 + 카드/간편결제/포인트
    # -----------------------------------------------------
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
                coupon.get(
                    "stack_payment"
                )
            ),

            relation_value(
                payment_related.get(
                    "stack_coupon"
                )
            ),
        )


    # -----------------------------------------------------
    # 6. 멤버십 + 카드/간편결제/포인트
    # -----------------------------------------------------
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
                membership.get(
                    "stack_payment"
                )
            ),

            relation_value(
                payment_related.get(
                    "stack_membership"
                )
            ),
        )


    # -----------------------------------------------------
    # 7. 포인트 + 카드/간편결제
    # 포인트는 결제수단 자체가 아니므로
    # 조건에 따라 같이 사용할 수 있음
    # -----------------------------------------------------
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
                point.get(
                    "stack_payment"
                )
            ),

            relation_value(
                payment_method.get(
                    "stack_payment"
                )
            ),
        )


    # -----------------------------------------------------
    # 8. 포인트 + 포인트
    # 명확한 정보 없이는 중복 여부를 확정하지 않음
    # -----------------------------------------------------
    if (
        ca == "point"
        and cb == "point"
    ):
        return "uncertain"


    # -----------------------------------------------------
    # 9. 기타 혜택
    # -----------------------------------------------------
    return "uncertain"
