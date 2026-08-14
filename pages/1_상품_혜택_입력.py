import pandas as pd
import streamlit as st


# =========================================================
# 페이지 설정
# =========================================================
st.set_page_config(
    page_title="상품·혜택 입력",
    page_icon="📸",
    layout="wide",
)

st.title("📸 상품 · 혜택 입력")

st.write(
    "구매할 상품을 입력하고, 내가 가진 쿠폰·카드·통신사·간편결제 "
    "혜택 캡처를 올린 뒤 이미지의 조건을 표에 입력해주세요."
)

st.info(
    "현재 MVP에서는 혜택 이미지를 참고하여 직접 입력합니다. "
    "저장된 정보는 다음 페이지의 최적 결제 조합 계산에 사용됩니다."
)


# =========================================================
# 1. 구매 상품 입력
# =========================================================
st.header("1️⃣ 구매 상품")

store_name = st.text_input(
    "구매처",
    value=st.session_state.get("store_name", "올리브영"),
    placeholder="예: 올리브영"
)


# 기존 상품 정보 불러오기
if "products" in st.session_state:

    product_rows = []

    for product in st.session_state["products"]:

        product_rows.append({
            "상품명": product.get("name", ""),
            "가격": product.get("price", 0),
            "수량": product.get("quantity", 1),
        })

else:

    product_rows = [
        {
            "상품명": "",
            "가격": 0,
            "수량": 1,
        }
    ]


product_df = pd.DataFrame(product_rows)


edited_products = st.data_editor(
    product_df,
    num_rows="dynamic",
    width="stretch",
    hide_index=True,
    key="product_editor",

    column_config={

        "상품명": st.column_config.TextColumn(
            "상품명",
            help="구매하려는 상품 이름"
        ),

        "가격": st.column_config.NumberColumn(
            "가격",
            min_value=0,
            step=1000,
            format="%d원",
        ),

        "수량": st.column_config.NumberColumn(
            "수량",
            min_value=1,
            step=1,
            format="%d",
        ),
    }
)


valid_products = edited_products[
    edited_products["가격"].fillna(0) > 0
].copy()


if not valid_products.empty:

    total_product_price = (
        valid_products["가격"].fillna(0)
        *
        valid_products["수량"].fillna(1)
    ).sum()

    st.success(
        f"🧾 현재 상품 총액: **{total_product_price:,.0f}원**"
    )


st.divider()


# =========================================================
# 2. 혜택 이미지 업로드
# =========================================================
st.header("2️⃣ 내가 가진 혜택 캡처")

st.write(
    "쿠폰함, 카드 혜택, 통신사 멤버십, 간편결제 이벤트 등의 "
    "캡처를 여러 장 올릴 수 있습니다."
)


uploaded_files = st.file_uploader(
    "혜택 이미지 업로드",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
)


if uploaded_files:

    st.success(
        f"총 {len(uploaded_files)}장의 이미지를 업로드했습니다."
    )

    # 최대 3열로 미리보기
    preview_columns = st.columns(3)

    for index, image in enumerate(uploaded_files):

        with preview_columns[index % 3]:

            st.image(
                image,
                caption=image.name,
                width="stretch"
            )


st.divider()


# =========================================================
# 3. 혜택 정보 직접 입력
# =========================================================
st.header("3️⃣ 혜택 조건 입력")

st.write(
    "위 캡처를 보면서 혜택별 조건을 입력해주세요. "
    "혜택이 여러 개라면 표 아래의 **+ 버튼으로 행을 추가**할 수 있습니다."
)

st.warning(
    "중복 가능 여부가 캡처에 적혀 있지 않다면 "
    "'확인 필요'로 선택해주세요."
)


# 기존 저장 데이터
if "benefits" in st.session_state:

    benefit_rows = []

    for benefit in st.session_state["benefits"]:

        benefit_rows.append({

            "혜택명":
                benefit.get("name", ""),

            "분류":
                benefit.get("category_label", "쿠폰"),

            "제공사":
                benefit.get("issuer", ""),

            "할인방식":
                benefit.get("discount_type_label", "정률(%)"),

            "할인값":
                benefit.get("value", 0),

            "최소결제금액":
                benefit.get("min_purchase", 0),

            "최대할인금액":
                benefit.get("max_discount", 0),

            "쿠폰중복":
                benefit.get("stack_coupon_label", "확인 필요"),

            "멤버십중복":
                benefit.get("stack_membership_label", "확인 필요"),

            "카드/결제중복":
                benefit.get("stack_payment_label", "확인 필요"),

            "사용채널":
                benefit.get("channel_label", "확인 필요"),

            "유효기간":
                benefit.get("expiry", ""),

            "이용횟수":
                benefit.get("usage_limit", ""),

            "제외대상":
                benefit.get("excluded_items", ""),

            "기타조건":
                benefit.get("conditions", ""),
        })

else:

    benefit_rows = [
        {
            "혜택명": "",
            "분류": "쿠폰",
            "제공사": "",
            "할인방식": "정률(%)",
            "할인값": 0,
            "최소결제금액": 0,
            "최대할인금액": 0,
            "쿠폰중복": "확인 필요",
            "멤버십중복": "확인 필요",
            "카드/결제중복": "확인 필요",
            "사용채널": "확인 필요",
            "유효기간": "",
            "이용횟수": "",
            "제외대상": "",
            "기타조건": "",
        }
    ]


benefit_df = pd.DataFrame(benefit_rows)


edited_benefits = st.data_editor(
    benefit_df,
    num_rows="dynamic",
    width="stretch",
    hide_index=True,
    key="benefit_editor",

    column_config={

        "혜택명":
            st.column_config.TextColumn(
                "혜택명",
                help="예: 올리브영 20% 쿠폰"
            ),

        "분류":
            st.column_config.SelectboxColumn(
                "분류",
                options=[
                    "쿠폰",
                    "통신사/멤버십",
                    "카드",
                    "간편결제",
                    "포인트",
                    "기타",
                ],
            ),

        "제공사":
            st.column_config.TextColumn(
                "제공사",
                help="예: 올리브영, SKT, 신한카드"
            ),

        "할인방식":
            st.column_config.SelectboxColumn(
                "할인방식",
                options=[
                    "정률(%)",
                    "정액(원)",
                    "포인트/적립",
                ],
            ),

        "할인값":
            st.column_config.NumberColumn(
                "할인값",
                min_value=0,
                help=(
                    "20% 할인이라면 20, "
                    "5,000원 할인이라면 5000"
                ),
            ),

        "최소결제금액":
            st.column_config.NumberColumn(
                "최소결제금액",
                min_value=0,
                step=1000,
                format="%d원",
            ),

        "최대할인금액":
            st.column_config.NumberColumn(
                "최대할인금액",
                min_value=0,
                step=1000,
                format="%d원",
                help="제한이 없으면 0"
            ),

        "쿠폰중복":
            st.column_config.SelectboxColumn(
                "쿠폰중복",
                options=[
                    "가능",
                    "불가",
                    "확인 필요",
                ],
            ),

        "멤버십중복":
            st.column_config.SelectboxColumn(
                "멤버십중복",
                options=[
                    "가능",
                    "불가",
                    "확인 필요",
                ],
            ),

        "카드/결제중복":
            st.column_config.SelectboxColumn(
                "카드/결제중복",
                options=[
                    "가능",
                    "불가",
                    "확인 필요",
                ],
            ),

        "사용채널":
            st.column_config.SelectboxColumn(
                "사용채널",
                options=[
                    "온라인",
                    "오프라인",
                    "온·오프라인",
                    "확인 필요",
                ],
            ),

        "유효기간":
            st.column_config.TextColumn(
                "유효기간",
                help="예: 2026-08-31"
            ),

        "이용횟수":
            st.column_config.TextColumn(
                "이용횟수",
                help="예: 1일 1회, 월 1회"
            ),

        "제외대상":
            st.column_config.TextColumn(
                "제외대상",
                help="예: 일부 브랜드 제외"
            ),

        "기타조건":
            st.column_config.TextColumn(
                "기타조건",
                help="기타 중요한 조건"
            ),
    },
)


st.caption(
    "예: 정률(%) + 할인값 20 = 20% 할인 / "
    "정액(원) + 할인값 5000 = 5,000원 할인"
)


st.divider()


# =========================================================
# 4. 결제 최적화 설정
# =========================================================
st.header("4️⃣ 결제 최적화 설정")

allow_split_payment = st.checkbox(
    "상품을 나누어 결제하는 경우까지 비교",
    value=st.session_state.get(
        "allow_split_payment",
        True
    ),
    help=(
        "체크하면 모든 상품을 한 번에 결제하는 방식뿐 아니라 "
        "상품별·묶음별 분할 결제도 비교합니다."
    )
)


st.divider()


# =========================================================
# 변환 함수
# =========================================================
def convert_stack(value):

    if value == "가능":
        return True

    if value == "불가":
        return False

    return None


def convert_category(value):

    mapping = {
        "쿠폰": "coupon",
        "통신사/멤버십": "membership",
        "카드": "card",
        "간편결제": "easy_pay",
        "포인트": "point",
        "기타": "other",
    }

    return mapping.get(
        value,
        "other"
    )


def convert_discount_type(value):

    mapping = {
        "정률(%)": "percent",
        "정액(원)": "fixed",
        "포인트/적립": "points",
    }

    return mapping.get(
        value,
        "unknown"
    )


# =========================================================
# 5. 저장
# =========================================================
st.header("5️⃣ 입력 정보 저장")


if st.button(
    "💾 상품·혜택 정보 저장",
    type="primary",
    width="stretch",
):

    # -------------------------------
    # 상품 저장
    # -------------------------------
    products_to_save = []

    for index, row in valid_products.iterrows():

        product_name = str(
            row.get("상품명", "")
        ).strip()

        if not product_name:
            product_name = f"상품 {index + 1}"

        products_to_save.append({

            "id":
                f"product_{index}",

            "name":
                product_name,

            "price":
                float(row["가격"]),

            "quantity":
                int(row["수량"]),

            "total":
                float(row["가격"])
                *
                int(row["수량"]),
        })


    # -------------------------------
    # 혜택 저장
    # -------------------------------
    benefits_to_save = []

    for index, row in edited_benefits.iterrows():

        benefit_name = str(
            row.get("혜택명", "")
        ).strip()

        if not benefit_name:
            continue


        benefits_to_save.append({

            "id":
                f"benefit_{index}",

            "name":
                benefit_name,

            "category":
                convert_category(
                    row["분류"]
                ),

            "category_label":
                row["분류"],

            "issuer":
                str(
                    row.get(
                        "제공사",
                        ""
                    )
                ).strip(),

            "discount_type":
                convert_discount_type(
                    row["할인방식"]
                ),

            "discount_type_label":
                row["할인방식"],

            "value":
                float(
                    row.get(
                        "할인값",
                        0
                    )
                    or 0
                ),

            "min_purchase":
                float(
                    row.get(
                        "최소결제금액",
                        0
                    )
                    or 0
                ),

            "max_discount":
                float(
                    row.get(
                        "최대할인금액",
                        0
                    )
                    or 0
                ),

            "stack_coupon":
                convert_stack(
                    row[
                        "쿠폰중복"
                    ]
                ),

            "stack_coupon_label":
                row[
                    "쿠폰중복"
                ],

            "stack_membership":
                convert_stack(
                    row[
                        "멤버십중복"
                    ]
                ),

            "stack_membership_label":
                row[
                    "멤버십중복"
                ],

            "stack_payment":
                convert_stack(
                    row[
                        "카드/결제중복"
                    ]
                ),

            "stack_payment_label":
                row[
                    "카드/결제중복"
                ],

            "channel_label":
                row[
                    "사용채널"
                ],

            "expiry":
                str(
                    row.get(
                        "유효기간",
                        ""
                    )
                ).strip(),

            "usage_limit":
                str(
                    row.get(
                        "이용횟수",
                        ""
                    )
                ).strip(),

            "excluded_items":
                str(
                    row.get(
                        "제외대상",
                        ""
                    )
                ).strip(),

            "conditions":
                str(
                    row.get(
                        "기타조건",
                        ""
                    )
                ).strip(),
        })


    # -------------------------------
    # 검증
    # -------------------------------
    if len(products_to_save) == 0:

        st.error(
            "가격이 입력된 상품이 최소 1개 이상 필요합니다."
        )


    elif len(benefits_to_save) == 0:

        st.error(
            "혜택을 최소 1개 이상 입력해주세요."
        )


    else:

        st.session_state[
            "store_name"
        ] = store_name

        st.session_state[
            "products"
        ] = products_to_save

        st.session_state[
            "benefits"
        ] = benefits_to_save

        st.session_state[
            "allow_split_payment"
        ] = allow_split_payment

        st.session_state[
            "benefit_input_completed"
        ] = True


        unknown_count = sum(

            1

            for benefit
            in benefits_to_save

            if (
                benefit[
                    "stack_coupon"
                ] is None

                or

                benefit[
                    "stack_membership"
                ] is None

                or

                benefit[
                    "stack_payment"
                ] is None
            )
        )


        st.success(
            f"✅ 상품 {len(products_to_save)}개, "
            f"혜택 {len(benefits_to_save)}개를 저장했습니다."
        )


        if unknown_count > 0:

            st.warning(
                f"중복 여부가 '확인 필요'인 혜택이 "
                f"{unknown_count}개 있습니다. "
                "2번 페이지에서는 이런 조합을 확정 가능한 "
                "최적안과 구분해서 처리합니다."
            )


        st.write(
            "이제 왼쪽 메뉴에서 "
            "**2_최적_결제_추천** 페이지로 이동하세요."
        )
