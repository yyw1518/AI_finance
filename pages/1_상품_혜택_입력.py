import base64
import json

import pandas as pd
import streamlit as st
from openai import OpenAI


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
    "구매할 상품을 입력하고, 내가 가진 쿠폰·통신사·카드·간편결제 "
    "혜택을 캡처해서 올리면 AI가 할인 조건을 자동으로 읽어 정리합니다."
)

st.info(
    "AI 분석 결과를 바로 사용하지 않고, 사용자가 한 번 확인·수정한 뒤 저장합니다."
)


# =========================================================
# 기본 함수
# =========================================================
def get_openai_client():

    try:
        api_key = st.secrets["OPENAI_API_KEY"]

        return OpenAI(
            api_key=api_key
        )

    except Exception:
        return None


def image_to_data_url(uploaded_file):

    mime_type = uploaded_file.type or "image/png"

    encoded_image = base64.b64encode(
        uploaded_file.getvalue()
    ).decode("utf-8")

    return (
        f"data:{mime_type};"
        f"base64,{encoded_image}"
    )


# ---------------------------------------------------------
# True / False / None 변환
# ---------------------------------------------------------
def stack_to_text(value):

    if value is True:
        return "가능"

    if value is False:
        return "불가"

    return "확인 필요"


def text_to_stack(value):

    value = str(value).strip()

    if value == "가능":
        return True

    if value == "불가":
        return False

    return None


# ---------------------------------------------------------
# 카테고리 변환
# ---------------------------------------------------------
def category_to_korean(value):

    mapping = {
        "coupon": "쿠폰",
        "membership": "통신사/멤버십",
        "card": "카드",
        "easy_pay": "간편결제",
        "point": "포인트",
        "other": "기타",
    }

    return mapping.get(
        value,
        "기타"
    )


def korean_to_category(value):

    mapping = {
        "쿠폰": "coupon",
        "통신사/멤버십": "membership",
        "카드": "card",
        "간편결제": "easy_pay",
        "포인트": "point",
        "기타": "other",
    }

    return mapping.get(
        str(value).strip(),
        "other"
    )


# ---------------------------------------------------------
# 할인 방식 변환
# ---------------------------------------------------------
def discount_to_korean(value):

    mapping = {
        "percent": "정률(%)",
        "fixed": "정액(원)",
        "points": "포인트/적립",
        "unknown": "확인 필요",
    }

    return mapping.get(
        value,
        "확인 필요"
    )


def korean_to_discount(value):

    mapping = {
        "정률(%)": "percent",
        "정액(원)": "fixed",
        "포인트/적립": "points",
        "확인 필요": "unknown",
    }

    return mapping.get(
        str(value).strip(),
        "unknown"
    )


# ---------------------------------------------------------
# 사용 채널
# ---------------------------------------------------------
def channel_to_korean(value):

    mapping = {
        "online": "온라인",
        "offline": "오프라인",
        "both": "온·오프라인",
        "unknown": "확인 필요",
    }

    return mapping.get(
        value,
        "확인 필요"
    )


def korean_to_channel(value):

    mapping = {
        "온라인": "online",
        "오프라인": "offline",
        "온·오프라인": "both",
        "확인 필요": "unknown",
    }

    return mapping.get(
        str(value).strip(),
        "unknown"
    )


def clean_number(value):

    if pd.isna(value):
        return None

    return float(value)


def clean_text(value):

    if pd.isna(value):
        return None

    text = str(value).strip()

    if not text:
        return None

    return text


# =========================================================
# AI가 반환할 데이터 형식
# =========================================================
BENEFIT_SCHEMA = {

    "type": "object",

    "properties": {

        "benefits": {

            "type": "array",

            "items": {

                "type": "object",

                "properties": {

                    "name": {
                        "type": "string"
                    },

                    "category": {
                        "type": "string",
                        "enum": [
                            "coupon",
                            "membership",
                            "card",
                            "easy_pay",
                            "point",
                            "other",
                        ],
                    },

                    "issuer": {
                        "type": "string"
                    },

                    "discount_type": {
                        "type": "string",
                        "enum": [
                            "percent",
                            "fixed",
                            "points",
                            "unknown",
                        ],
                    },

                    "value": {
                        "type": [
                            "number",
                            "null"
                        ]
                    },

                    "min_purchase": {
                        "type": [
                            "number",
                            "null"
                        ]
                    },

                    "max_discount": {
                        "type": [
                            "number",
                            "null"
                        ]
                    },

                    "stack_coupon": {
                        "type": [
                            "boolean",
                            "null"
                        ]
                    },

                    "stack_membership": {
                        "type": [
                            "boolean",
                            "null"
                        ]
                    },

                    "stack_payment": {
                        "type": [
                            "boolean",
                            "null"
                        ]
                    },

                    "channel": {
                        "type": "string",
                        "enum": [
                            "online",
                            "offline",
                            "both",
                            "unknown",
                        ],
                    },

                    "expiry": {
                        "type": [
                            "string",
                            "null"
                        ]
                    },

                    "usage_limit": {
                        "type": [
                            "string",
                            "null"
                        ]
                    },

                    "excluded_items": {
                        "type": [
                            "string",
                            "null"
                        ]
                    },

                    "raw_conditions": {
                        "type": "string"
                    },

                    "confidence": {
                        "type": "string",
                        "enum": [
                            "high",
                            "medium",
                            "low",
                        ],
                    },
                },

                "required": [
                    "name",
                    "category",
                    "issuer",
                    "discount_type",
                    "value",
                    "min_purchase",
                    "max_discount",
                    "stack_coupon",
                    "stack_membership",
                    "stack_payment",
                    "channel",
                    "expiry",
                    "usage_limit",
                    "excluded_items",
                    "raw_conditions",
                    "confidence",
                ],

                "additionalProperties": False,
            },
        },

        "warnings": {

            "type": "array",

            "items": {
                "type": "string"
            },
        },
    },

    "required": [
        "benefits",
        "warnings"
    ],

    "additionalProperties": False,
}


# =========================================================
# AI 이미지 분석
# =========================================================
def analyze_benefit_images(
    uploaded_files
):

    client = get_openai_client()

    if client is None:

        raise RuntimeError(
            "OPENAI_API_KEY가 설정되지 않았습니다."
        )


    prompt = """
너는 한국의 쇼핑·결제 혜택 화면을 분석하는 AI다.

사용자가 올린 이미지에서 다음과 같은 혜택을 찾아 각각 구분해라.

- 쇼핑몰 쿠폰
- 브랜드 쿠폰
- 통신사 멤버십 할인
- 카드 즉시할인
- 카드 청구할인
- 간편결제 할인
- 포인트 또는 적립 혜택

반드시 다음 규칙을 지켜라.

1. 이미지에 실제로 적힌 내용만 사용한다.

2. 보이지 않는 조건은 절대 추측하지 않는다.

3. 중복 사용 여부가 이미지에 명확히 적혀 있지 않다면 null로 둔다.

4. 20% 할인은 value=20으로 저장한다.

5. 5천원 할인은 value=5000으로 저장한다.

6. 최소 구매금액과 최대 할인금액은 원 단위 숫자로 저장한다.

7. '5만원 이상 구매 시'는 min_purchase=50000이다.

8. '최대 1만원 할인'은 max_discount=10000이다.

9. 카드 청구할인도 card로 분류한다.

10. SKT, KT, LG U+ 등의 멤버십은 membership으로 분류한다.

11. 카카오페이, 네이버페이, 토스페이 등의 혜택은 easy_pay로 분류한다.

12. 한 이미지에 여러 혜택이 있다면 각각 별도로 추출한다.

13. 다음과 같은 조건은 반드시 raw_conditions에 남긴다.
- 일부 브랜드 제외
- 특정 상품 제외
- 온라인 전용
- 오프라인 전용
- 선착순
- 1일 1회
- 월 1회
- 특정 카드만 가능
- 특정 결제수단만 가능
- 쿠폰 중복 불가

14. 중복 여부가 불분명하면 절대로 가능하다고 가정하지 않는다.

15. 이미지가 흐리거나 조건이 잘려 있으면 warnings에 적는다.

16. 이미지가 혜택 화면이 아니면 혜택을 만들어내지 말고 warnings에 적는다.

17. issuer를 확인할 수 없다면 빈 문자열로 둔다.

18. 조건 설명이 없다면 raw_conditions는 빈 문자열로 둔다.

19. confidence:
high = 핵심 조건이 명확함
medium = 일부 조건이 불명확함
low = 이미지가 흐리거나 정보가 부족함
"""


    content = [

        {
            "type": "input_text",
            "text": prompt
        }
    ]


    for image in uploaded_files:

        content.append(

            {
                "type": "input_image",

                "image_url":
                    image_to_data_url(
                        image
                    ),

                "detail": "high",
            }
        )


    response = client.responses.create(

        model="gpt-5.6-luna",

        input=[

            {
                "role": "user",
                "content": content,
            }
        ],

        text={

            "format": {

                "type": "json_schema",

                "name":
                    "benefit_extraction",

                "schema":
                    BENEFIT_SCHEMA,

                "strict": True,
            }
        },
    )


    return json.loads(
        response.output_text
    )


# =========================================================
# AI 결과 → 표 변환
# =========================================================
def benefits_to_dataframe(
    benefits
):

    rows = []


    for item in benefits:

        rows.append(

            {

                "혜택명":
                    item.get(
                        "name",
                        ""
                    ),

                "분류":
                    category_to_korean(
                        item.get(
                            "category"
                        )
                    ),

                "제공사/브랜드":
                    item.get(
                        "issuer",
                        ""
                    ),

                "할인방식":
                    discount_to_korean(
                        item.get(
                            "discount_type"
                        )
                    ),

                "할인값":
                    item.get(
                        "value"
                    ),

                "최소결제금액":
                    item.get(
                        "min_purchase"
                    ),

                "최대할인금액":
                    item.get(
                        "max_discount"
                    ),

                "쿠폰중복":
                    stack_to_text(
                        item.get(
                            "stack_coupon"
                        )
                    ),

                "멤버십중복":
                    stack_to_text(
                        item.get(
                            "stack_membership"
                        )
                    ),

                "카드/결제중복":
                    stack_to_text(
                        item.get(
                            "stack_payment"
                        )
                    ),

                "사용채널":
                    channel_to_korean(
                        item.get(
                            "channel"
                        )
                    ),

                "유효기간":
                    item.get(
                        "expiry"
                    ),

                "이용횟수/한도":
                    item.get(
                        "usage_limit"
                    ),

                "제외대상":
                    item.get(
                        "excluded_items"
                    ),

                "기타조건":
                    item.get(
                        "raw_conditions",
                        ""
                    ),

                "AI확신도":
                    item.get(
                        "confidence",
                        "low"
                    ),
            }
        )


    return pd.DataFrame(
        rows
    )


# =========================================================
# 수정된 표 → 2번 페이지용 데이터
# =========================================================
def dataframe_to_benefits(
    df
):

    benefits = []


    for index, row in df.iterrows():

        name = str(
            row.get(
                "혜택명",
                ""
            )
        ).strip()


        if not name:
            continue


        benefits.append(

            {

                "id":
                    f"benefit_{index}",

                "name":
                    name,

                "category":
                    korean_to_category(
                        row.get(
                            "분류"
                        )
                    ),

                "issuer":
                    clean_text(
                        row.get(
                            "제공사/브랜드"
                        )
                    ),

                "discount_type":
                    korean_to_discount(
                        row.get(
                            "할인방식"
                        )
                    ),

                "value":
                    clean_number(
                        row.get(
                            "할인값"
                        )
                    ),

                "min_purchase":
                    clean_number(
                        row.get(
                            "최소결제금액"
                        )
                    ),

                "max_discount":
                    clean_number(
                        row.get(
                            "최대할인금액"
                        )
                    ),

                "stack_coupon":
                    text_to_stack(
                        row.get(
                            "쿠폰중복"
                        )
                    ),

                "stack_membership":
                    text_to_stack(
                        row.get(
                            "멤버십중복"
                        )
                    ),

                "stack_payment":
                    text_to_stack(
                        row.get(
                            "카드/결제중복"
                        )
                    ),

                "channel":
                    korean_to_channel(
                        row.get(
                            "사용채널"
                        )
                    ),

                "expiry":
                    clean_text(
                        row.get(
                            "유효기간"
                        )
                    ),

                "usage_limit":
                    clean_text(
                        row.get(
                            "이용횟수/한도"
                        )
                    ),

                "excluded_items":
                    clean_text(
                        row.get(
                            "제외대상"
                        )
                    ),

                "raw_conditions":
                    clean_text(
                        row.get(
                            "기타조건"
                        )
                    )
                    or "",

                "confidence":
                    str(
                        row.get(
                            "AI확신도",
                            "low"
                        )
                    ),
            }
        )


    return benefits


# =========================================================
# 1. 구매 상품
# =========================================================
st.header(
    "1️⃣ 구매할 상품"
)


store_name = st.text_input(

    "구매처",

    value=st.session_state.get(
        "store_name",
        "올리브영"
    ),

    placeholder=
        "예: 올리브영",
)


# 기존 상품 데이터
if "products" in st.session_state:

    old_products = []

    for product in st.session_state[
        "products"
    ]:

        old_products.append(

            {

                "상품명":
                    product.get(
                        "name",
                        ""
                    ),

                "가격":
                    product.get(
                        "price",
                        0
                    ),

                "수량":
                    product.get(
                        "quantity",
                        1
                    ),
            }
        )

else:

    old_products = [

        {

            "상품명": "",

            "가격": 0,

            "수량": 1,
        }
    ]


product_df = pd.DataFrame(
    old_products
)


edited_products = st.data_editor(

    product_df,

    num_rows="dynamic",

    use_container_width=True,

    hide_index=True,

    key="product_editor",

    column_config={

        "상품명":
            st.column_config.TextColumn(
                "상품명"
            ),

        "가격":
            st.column_config.NumberColumn(
                "가격",
                min_value=0,
                step=1000,
                format="%d원",
            ),

        "수량":
            st.column_config.NumberColumn(
                "수량",
                min_value=1,
                step=1,
                format="%d",
            ),
    },
)


valid_products = edited_products[
    edited_products[
        "가격"
    ].fillna(0) > 0
].copy()


if not valid_products.empty:

    total_price = (

        valid_products[
            "가격"
        ].fillna(0)

        *

        valid_products[
            "수량"
        ].fillna(1)

    ).sum()


    st.success(
        f"🧾 상품 총액: "
        f"**{total_price:,.0f}원**"
    )


st.divider()


# =========================================================
# 2. 혜택 이미지 업로드
# =========================================================
st.header(
    "2️⃣ 내가 가진 혜택 캡처"
)


st.write(
    "쿠폰함, 카드 혜택, 통신사 멤버십, 간편결제 이벤트 등의 "
    "캡처 이미지를 올려주세요."
)


uploaded_files = st.file_uploader(

    "혜택 이미지 업로드",

    type=[
        "png",
        "jpg",
        "jpeg",
        "webp"
    ],

    accept_multiple_files=True,

    help=
        "여러 장을 한 번에 "
        "선택할 수 있습니다.",
)


if uploaded_files:

    st.caption(
        f"총 {len(uploaded_files)}장의 "
        "이미지를 선택했습니다."
    )


    preview_count = min(
        3,
        len(uploaded_files)
    )


    preview_columns = st.columns(
        preview_count
    )


    for index, image in enumerate(
        uploaded_files
    ):

        with preview_columns[
            index % preview_count
        ]:

            st.image(

                image,

                caption=image.name,

                use_container_width=True,
            )


    if len(uploaded_files) > 8:

        st.warning(
            "현재 MVP에서는 한 번에 "
            "앞의 8장까지만 분석합니다."
        )


st.divider()


# =========================================================
# 3. AI 분석
# =========================================================
st.header(
    "3️⃣ AI 혜택 분석"
)


if st.button(

    "✨ 업로드한 혜택 자동 분석",

    type="primary",

    use_container_width=True,
):


    if not uploaded_files:

        st.warning(
            "먼저 혜택 이미지를 "
            "1장 이상 올려주세요."
        )


    else:

        files_to_analyze = (
            uploaded_files[:8]
        )


        with st.spinner(
            "AI가 할인율, 최소금액, "
            "최대할인, 중복조건 등을 "
            "확인하고 있습니다..."
        ):

            try:

                result = (
                    analyze_benefit_images(
                        files_to_analyze
                    )
                )


                st.session_state[
                    "ai_extracted_benefits"
                ] = result[
                    "benefits"
                ]


                st.session_state[
                    "ai_benefit_warnings"
                ] = result[
                    "warnings"
                ]


                st.success(

                    "✅ 총 "

                    f"{len(result['benefits'])}"

                    "개의 혜택을 찾았습니다."
                )


            except Exception as error:

                st.error(
                    "혜택 이미지 분석에 "
                    "실패했습니다."
                )

                st.code(
                    str(error)
                )


# =========================================================
# 4. AI 분석 결과 확인
# =========================================================
if (
    "ai_extracted_benefits"
    in st.session_state
):


    st.divider()


    st.header(
        "4️⃣ AI가 읽은 혜택 확인"
    )


    warnings = st.session_state.get(
        "ai_benefit_warnings",
        []
    )


    if warnings:

        st.warning(
            "⚠️ 확인이 필요한 내용"
        )


        for warning in warnings:

            st.write(
                f"- {warning}"
            )


    st.write(
        "AI가 잘못 읽은 내용이 있다면 "
        "**표에서 직접 수정해주세요.**"
    )


    st.info(
        "'확인 필요'라고 표시된 중복 조건은 "
        "AI가 임의로 중복 가능하다고 판단하지 않은 항목입니다."
    )


    benefit_df = (
        benefits_to_dataframe(

            st.session_state[
                "ai_extracted_benefits"
            ]
        )
    )


    edited_benefits = (
        st.data_editor(

            benefit_df,

            num_rows="dynamic",

            use_container_width=True,

            hide_index=True,

            key="benefit_editor",

            column_config={


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


                "할인방식":
                    st.column_config.SelectboxColumn(

                        "할인방식",

                        options=[

                            "정률(%)",

                            "정액(원)",

                            "포인트/적립",

                            "확인 필요",
                        ],
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


                "AI확신도":
                    st.column_config.SelectboxColumn(

                        "AI확신도",

                        options=[
                            "high",
                            "medium",
                            "low",
                        ],
                    ),


                "할인값":
                    st.column_config.NumberColumn(

                        "할인값",

                        min_value=0,
                    ),


                "최소결제금액":
                    st.column_config.NumberColumn(

                        "최소결제금액",

                        min_value=0,

                        format="%d원",
                    ),


                "최대할인금액":
                    st.column_config.NumberColumn(

                        "최대할인금액",

                        min_value=0,

                        format="%d원",
                    ),
            },
        )
    )


    st.caption(
        "예: 할인방식이 정률(%)이고 할인값이 20이면 20% 할인, "
        "정액(원)이고 할인값이 5000이면 5,000원 할인입니다."
    )


    # =====================================================
    # 5. 저장
    # =====================================================
    st.divider()


    st.header(
        "5️⃣ 상품 · 혜택 저장"
    )


    if st.button(

        "💾 확인한 정보 저장",

        type="primary",

        use_container_width=True,
    ):


        products_to_save = []


        for index, row in (
            valid_products.iterrows()
        ):


            product_name = str(
                row[
                    "상품명"
                ]
            ).strip()


            if not product_name:

                product_name = (
                    f"상품 {index + 1}"
                )


            products_to_save.append(

                {

                    "id":
                        f"product_{index}",

                    "name":
                        product_name,

                    "price":
                        float(
                            row["가격"]
                        ),

                    "quantity":
                        int(
                            row["수량"]
                        ),

                    "total":
                        float(
                            row["가격"]
                        )
                        *
                        int(
                            row["수량"]
                        ),
                }
            )


        if not products_to_save:

            st.error(
                "가격이 입력된 상품이 "
                "최소 1개 이상 필요합니다."
            )


        else:

            benefits_to_save = (
                dataframe_to_benefits(
                    edited_benefits
                )
            )


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

                f"✅ 상품 "
                f"{len(products_to_save)}개와 "

                f"혜택 "
                f"{len(benefits_to_save)}개를 "

                "저장했습니다."
            )


            if unknown_count > 0:

                st.warning(

                    "중복 조건이 확인되지 않은 "
                    f"혜택이 {unknown_count}개 있습니다. "

                    "2번 페이지에서는 이런 혜택을 "
                    "임의로 중복 가능 처리하지 않고 "
                    "별도로 표시하도록 만들겠습니다."
                )


            st.write(
                "이제 왼쪽 메뉴에서 "
                "**2_최적_결제_추천**으로 이동하세요."
            )


else:

    st.divider()

    st.caption(
        "혜택 이미지를 AI로 분석하면 "
        "여기에 결과가 표시됩니다."
    )
