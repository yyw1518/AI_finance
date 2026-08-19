import base64
import json
from typing import Any

import pandas as pd
import streamlit as st
from openai import OpenAI


# =========================================================
# 페이지 설정
# =========================================================
st.set_page_config(
    page_title="상품·혜택 자동 분석",
    page_icon="📸",
    layout="wide",
)

st.title("📸 상품 · 혜택 자동 분석")
st.write(
    "구매 화면과 내가 가진 쿠폰·카드·통신사·간편결제 혜택을 캡처해서 올리면 "
    "AI가 상품 정보와 혜택 조건을 자동으로 읽어 정리합니다."
)
st.info(
    "AI가 읽은 내용은 바로 계산에 사용하지 않습니다. "
    "분석 결과를 한 번 확인·수정한 뒤 저장하면 2번 페이지의 최적 결제 계산에 사용됩니다."
)


# =========================================================
# 기본 설정
# =========================================================
MODEL_NAME = "gpt-5.6-luna"
MAX_IMAGES = 6

CATEGORY_LABELS = {
    "coupon": "쿠폰",
    "membership": "통신사/멤버십",
    "card": "카드",
    "easy_pay": "간편결제",
    "point": "포인트",
    "other": "기타",
}
CATEGORY_VALUES = {v: k for k, v in CATEGORY_LABELS.items()}

DISCOUNT_LABELS = {
    "percent": "정률(%)",
    "fixed": "정액(원)",
    "points": "포인트/적립",
    "unknown": "확인 필요",
}
DISCOUNT_VALUES = {v: k for k, v in DISCOUNT_LABELS.items()}

CHANNEL_LABELS = {
    "online": "온라인",
    "offline": "오프라인",
    "both": "온·오프라인",
    "unknown": "확인 필요",
}
CHANNEL_VALUES = {v: k for k, v in CHANNEL_LABELS.items()}

BASIS_LABELS = {
    "original": "결제 시작 금액",
    "current": "혜택 적용 직전 금액",
    "unknown": "확인 필요",
}
BASIS_VALUES = {v: k for k, v in BASIS_LABELS.items()}


# =========================================================
# AI Structured Output 스키마
# =========================================================
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "store_name": {
            "type": ["string", "null"],
        },
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "price": {"type": ["number", "null"]},
                    "quantity": {"type": ["integer", "null"]},
                },
                "required": ["name", "price", "quantity"],
                "additionalProperties": False,
            },
        },
        "benefits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
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
                    "issuer": {"type": ["string", "null"]},
                    "discount_type": {
                        "type": "string",
                        "enum": ["percent", "fixed", "points", "unknown"],
                    },
                    "value": {"type": ["number", "null"]},
                    "min_purchase": {"type": ["number", "null"]},
                    "max_discount": {"type": ["number", "null"]},
                    "minimum_basis": {
                        "type": "string",
                        "enum": ["original", "current", "unknown"],
                    },
                    "stack_coupon": {"type": ["boolean", "null"]},
                    "stack_membership": {"type": ["boolean", "null"]},
                    "stack_payment": {"type": ["boolean", "null"]},
                    "channel": {
                        "type": "string",
                        "enum": ["online", "offline", "both", "unknown"],
                    },
                    "expiry": {"type": ["string", "null"]},
                    "usage_limit": {"type": ["string", "null"]},
                    "reusable": {"type": ["boolean", "null"]},
                    "excluded_items": {"type": ["string", "null"]},
                    "required_payment_method": {"type": ["string", "null"]},
                    "conditions": {"type": "string"},
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
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
                    "minimum_basis",
                    "stack_coupon",
                    "stack_membership",
                    "stack_payment",
                    "channel",
                    "expiry",
                    "usage_limit",
                    "reusable",
                    "excluded_items",
                    "required_payment_method",
                    "conditions",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["store_name", "products", "benefits", "warnings"],
    "additionalProperties": False,
}


# =========================================================
# 공통 함수
# =========================================================
def get_client():
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except Exception:
        return None

    if not api_key:
        return None

    return OpenAI(api_key=api_key)


def image_to_data_url(uploaded_file):
    mime_type = uploaded_file.type or "image/png"
    encoded = base64.b64encode(uploaded_file.getvalue()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def bool_to_label(value):
    if value is True:
        return "가능"
    if value is False:
        return "불가"
    return "확인 필요"


def label_to_bool(value):
    if value == "가능":
        return True
    if value == "불가":
        return False
    return None


def reusable_to_label(value):
    if value is True:
        return "재사용 가능"
    if value is False:
        return "1회 사용"
    return "확인 필요"


def label_to_reusable(value):
    if value == "재사용 가능":
        return True
    if value == "1회 사용":
        return False
    return None


def clean_text(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def optional_number(value):
    if value is None or pd.isna(value) or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def page2_number(value):
    """현재 2번 페이지와 호환되도록 미확인 숫자는 0으로 저장."""
    number = optional_number(value)
    return 0.0 if number is None else number


def analyze_images(uploaded_files):
    client = get_client()
    if client is None:
        raise RuntimeError(
            "Streamlit Secrets에서 OPENAI_API_KEY를 찾을 수 없습니다."
        )

    instructions = """
너는 한국의 쇼핑/결제 혜택 캡처를 분석하는 데이터 추출 AI다.
사용자가 올린 모든 이미지를 함께 보고 구매 정보와 사용 가능한 혜택을 구조화한다.

[가장 중요한 원칙]
- 이미지에 보이는 내용만 추출한다.
- 보이지 않거나 확실하지 않은 조건은 절대 추측하지 않는다.
- 불확실한 숫자/중복 여부/사용 횟수는 null 또는 unknown으로 둔다.
- 같은 혜택이 여러 이미지에 반복되어 있으면 하나로 합친다.
- 서로 다른 혜택은 반드시 별개의 benefit으로 분리한다.

[상품 정보]
- 장바구니/결제예정 화면에 상품명, 가격, 수량이 보이면 products로 추출한다.
- 할인 전 상품 단가를 알 수 있으면 price에 넣는다.
- 수량이 보이지 않으면 quantity=null로 둔다.
- 혜택 캡처만 있고 상품 정보가 없다면 products=[]로 둔다.

[혜택 분류]
- 쇼핑몰/브랜드 할인쿠폰: coupon
- SKT/KT/LG U+ 등 통신사 및 멤버십: membership
- 신용/체크카드 즉시할인 또는 청구할인: card
- 카카오페이/네이버페이/토스페이 등: easy_pay
- 포인트 사용/적립: point

[숫자 변환]
- 20% 할인 -> discount_type=percent, value=20
- 5천원 할인 -> discount_type=fixed, value=5000
- 4만원 이상 구매 -> min_purchase=40000
- 최대 1만원 할인 -> max_discount=10000
- '한도 없음'이 명시되면 max_discount=0
- 표시가 없으면 max_discount=null. 임의로 0으로 두지 않는다.

[중복 사용]
- '쿠폰 중복 불가'가 명시되면 stack_coupon=false
- '멤버십과 중복 가능'이 명시되면 stack_membership=true
- 카드/간편결제와 중복 여부가 명시되면 stack_payment에 기록한다.
- 명시되지 않았으면 null이다. 관행을 근거로 추측하지 않는다.

[분할결제/사용횟수]
- 1회 사용, 1일 1회, 월 1회, 계정당 1회 등의 문구는 usage_limit에 그대로 요약한다.
- 여러 결제 건에서 반복 사용 가능함이 명확하면 reusable=true.
- 1회성임이 명확하면 reusable=false.
- 불명확하면 reusable=null.

[최소금액 기준]
- 할인 적용 전 최초 결제금액 기준임이 명확하면 minimum_basis=original.
- 앞선 할인 적용 후 실제 결제금액 기준임이 명확하면 minimum_basis=current.
- 알 수 없으면 unknown.

[채널/기간/제외조건]
- 온라인 전용/오프라인 전용/온오프라인 모두 여부를 channel에 기록한다.
- 유효기간이 날짜로 명확하면 YYYY-MM-DD 형식으로 expiry에 기록한다.
- 일부 브랜드/상품 제외 조건은 excluded_items에 기록한다.
- 특정 카드/결제수단이 필수이면 required_payment_method에 기록한다.
- 선착순, 특정 회원등급, 앱 전용, 행사상품 제외 등 나머지 조건은 conditions에 적는다.

[confidence]
- high: 핵심 할인조건과 적용조건을 충분히 읽을 수 있음
- medium: 할인 핵심은 읽히지만 일부 조건이 빠지거나 불명확함
- low: 이미지가 흐리거나 잘렸거나 핵심 조건을 확정하기 어려움

혜택 화면이 아닌 이미지이거나 중요한 조건이 잘린 경우 warnings에 알려라.
"""

    content = [{"type": "input_text", "text": instructions}]

    for idx, file in enumerate(uploaded_files, start=1):
        content.append(
            {
                "type": "input_text",
                "text": f"이미지 {idx} 파일명: {file.name}",
            }
        )
        content.append(
            {
                "type": "input_image",
                "image_url": image_to_data_url(file),
                "detail": "original",
            }
        )

    response = client.responses.create(
        model=MODEL_NAME,
        input=[{"role": "user", "content": content}],
        text={
            "format": {
                "type": "json_schema",
                "name": "shopping_benefit_extraction",
                "schema": EXTRACTION_SCHEMA,
                "strict": True,
            }
        },
    )

    return json.loads(response.output_text)


# =========================================================
# AI 결과 ↔ 표 변환
# =========================================================
def products_to_df(products):
    rows = []
    for item in products:
        rows.append(
            {
                "상품명": item.get("name", ""),
                "가격": item.get("price"),
                "수량": item.get("quantity") or 1,
            }
        )

    if not rows:
        rows = [{"상품명": "", "가격": None, "수량": 1}]

    return pd.DataFrame(rows)


def benefits_to_df(benefits):
    rows = []

    for item in benefits:
        rows.append(
            {
                "혜택명": item.get("name", ""),
                "분류": CATEGORY_LABELS.get(item.get("category"), "기타"),
                "제공사": item.get("issuer") or "",
                "할인방식": DISCOUNT_LABELS.get(
                    item.get("discount_type"), "확인 필요"
                ),
                "할인값": item.get("value"),
                "최소결제금액": item.get("min_purchase"),
                "최대할인금액": item.get("max_discount"),
                "최소금액기준": BASIS_LABELS.get(
                    item.get("minimum_basis"), "확인 필요"
                ),
                "쿠폰중복": bool_to_label(item.get("stack_coupon")),
                "멤버십중복": bool_to_label(item.get("stack_membership")),
                "카드/결제중복": bool_to_label(item.get("stack_payment")),
                "사용채널": CHANNEL_LABELS.get(item.get("channel"), "확인 필요"),
                "유효기간": item.get("expiry") or "",
                "이용횟수": item.get("usage_limit") or "",
                "분할결제 재사용": reusable_to_label(item.get("reusable")),
                "제외대상": item.get("excluded_items") or "",
                "필수결제수단": item.get("required_payment_method") or "",
                "기타조건": item.get("conditions") or "",
                "AI확신도": item.get("confidence", "low"),
            }
        )

    if not rows:
        rows = [
            {
                "혜택명": "",
                "분류": "쿠폰",
                "제공사": "",
                "할인방식": "확인 필요",
                "할인값": None,
                "최소결제금액": None,
                "최대할인금액": None,
                "최소금액기준": "확인 필요",
                "쿠폰중복": "확인 필요",
                "멤버십중복": "확인 필요",
                "카드/결제중복": "확인 필요",
                "사용채널": "확인 필요",
                "유효기간": "",
                "이용횟수": "",
                "분할결제 재사용": "확인 필요",
                "제외대상": "",
                "필수결제수단": "",
                "기타조건": "",
                "AI확신도": "low",
            }
        ]

    return pd.DataFrame(rows)


def saved_products_to_df():
    saved = st.session_state.get("products", [])
    if not saved:
        return products_to_df([])

    return pd.DataFrame(
        [
            {
                "상품명": item.get("name", ""),
                "가격": item.get("price"),
                "수량": item.get("quantity", 1),
            }
            for item in saved
        ]
    )


def saved_benefits_to_df():
    saved = st.session_state.get("benefits", [])
    if not saved:
        return benefits_to_df([])

    rows = []
    for item in saved:
        rows.append(
            {
                "혜택명": item.get("name", ""),
                "분류": item.get(
                    "category_label",
                    CATEGORY_LABELS.get(item.get("category"), "기타"),
                ),
                "제공사": item.get("issuer", ""),
                "할인방식": item.get(
                    "discount_type_label",
                    DISCOUNT_LABELS.get(item.get("discount_type"), "확인 필요"),
                ),
                "할인값": item.get("value"),
                "최소결제금액": item.get("min_purchase"),
                "최대할인금액": item.get("max_discount"),
                "최소금액기준": BASIS_LABELS.get(
                    item.get("minimum_basis", "unknown"), "확인 필요"
                ),
                "쿠폰중복": item.get(
                    "stack_coupon_label", bool_to_label(item.get("stack_coupon"))
                ),
                "멤버십중복": item.get(
                    "stack_membership_label",
                    bool_to_label(item.get("stack_membership")),
                ),
                "카드/결제중복": item.get(
                    "stack_payment_label", bool_to_label(item.get("stack_payment"))
                ),
                "사용채널": item.get("channel_label", "확인 필요"),
                "유효기간": item.get("expiry", ""),
                "이용횟수": item.get("usage_limit", ""),
                "분할결제 재사용": reusable_to_label(item.get("reusable")),
                "제외대상": item.get("excluded_items", ""),
                "필수결제수단": item.get("required_payment_method", ""),
                "기타조건": item.get("conditions", ""),
                "AI확신도": item.get("confidence", "low"),
            }
        )

    return pd.DataFrame(rows)


# =========================================================
# 1. 이미지 업로드
# =========================================================
st.header("1️⃣ 구매 화면 · 혜택 캡처 업로드")
st.write(
    "장바구니/결제예정 화면과 쿠폰·카드·멤버십·간편결제 혜택 캡처를 "
    "한 번에 여러 장 올려주세요. 상품 정보가 캡처에 없으면 분석 후 표에서 직접 추가할 수 있습니다."
)

uploaded_files = st.file_uploader(
    "캡처 이미지 선택",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
    help=f"현재 MVP에서는 한 번에 최대 {MAX_IMAGES}장까지 분석합니다.",
)

if uploaded_files:
    if len(uploaded_files) > MAX_IMAGES:
        st.warning(
            f"{len(uploaded_files)}장이 선택되었습니다. 비용과 처리시간을 줄이기 위해 "
            f"앞의 {MAX_IMAGES}장만 분석합니다."
        )

    preview_files = uploaded_files[:MAX_IMAGES]
    cols = st.columns(min(3, len(preview_files)))

    for idx, file in enumerate(preview_files):
        with cols[idx % len(cols)]:
            st.image(file, caption=file.name, width="stretch")


# =========================================================
# 2. AI 자동 분석
# =========================================================
st.divider()
st.header("2️⃣ AI 자동 분석")

api_available = get_client() is not None
if not api_available:
    st.warning(
        "OPENAI_API_KEY가 연결되어 있지 않습니다. "
        "사진 자동 분석은 사용할 수 없지만 아래 표는 직접 입력할 수 있습니다."
    )

if st.button(
    "✨ 사진에서 상품·혜택 자동 추출",
    type="primary",
    use_container_width=True,
):
    if not uploaded_files:
        st.warning("먼저 이미지를 1장 이상 업로드해주세요.")
    elif not api_available:
        st.error("Streamlit Secrets의 OPENAI_API_KEY 설정을 확인해주세요.")
    else:
        with st.spinner(
            "AI가 상품, 할인율, 최소금액, 최대할인, 중복조건, 사용횟수 등을 읽고 있습니다..."
        ):
            try:
                result = analyze_images(uploaded_files[:MAX_IMAGES])

                st.session_state["ai_store_name"] = result.get("store_name") or ""
                st.session_state["ai_product_rows"] = products_to_df(
                    result.get("products", [])
                ).to_dict("records")
                st.session_state["ai_benefit_rows"] = benefits_to_df(
                    result.get("benefits", [])
                ).to_dict("records")
                st.session_state["ai_warnings"] = result.get("warnings", [])
                st.session_state["ai_analysis_done"] = True

                st.success(
                    f"✅ 상품 {len(result.get('products', []))}개, "
                    f"혜택 {len(result.get('benefits', []))}개를 찾았습니다."
                )
                st.rerun()

            except Exception as error:
                message = str(error)
                if "429" in message or "quota" in message.lower():
                    st.error(
                        "OpenAI API 사용 한도 또는 결제 상태 때문에 분석하지 못했습니다. "
                        "아래 표는 직접 입력할 수 있습니다."
                    )
                else:
                    st.error("이미지 분석 중 오류가 발생했습니다.")
                st.code(message)


# =========================================================
# 3. 분석 결과 확인·수정
# =========================================================
st.divider()
st.header("3️⃣ 분석 결과 확인 · 수정")

warnings = st.session_state.get("ai_warnings", [])
if warnings:
    st.warning("AI가 확인이 필요하다고 판단한 내용이 있습니다.")
    for warning in warnings:
        st.write(f"- {warning}")

if st.session_state.get("ai_analysis_done"):
    ai_store = st.session_state.get("ai_store_name", "")
    initial_product_df = pd.DataFrame(
        st.session_state.get("ai_product_rows", [])
    )
    initial_benefit_df = pd.DataFrame(
        st.session_state.get("ai_benefit_rows", [])
    )
else:
    ai_store = ""
    initial_product_df = saved_products_to_df()
    initial_benefit_df = saved_benefits_to_df()

store_default = ai_store or st.session_state.get("store_name", "올리브영")
store_name = st.text_input("구매처", value=store_default)

st.subheader("🛍️ 상품")
st.caption(
    "장바구니 화면을 함께 올렸다면 AI가 자동으로 채웁니다. "
    "상품 정보가 캡처에 없으면 여기서 상품명·가격·수량만 추가해주세요."
)

edited_products = st.data_editor(
    initial_product_df,
    num_rows="dynamic",
    hide_index=True,
    width="stretch",
    key="ai_product_editor",
    column_config={
        "상품명": st.column_config.TextColumn("상품명"),
        "가격": st.column_config.NumberColumn(
            "가격", min_value=0, step=1000, format="%d원"
        ),
        "수량": st.column_config.NumberColumn(
            "수량", min_value=1, step=1, format="%d"
        ),
    },
)

valid_product_mask = edited_products["가격"].fillna(0) > 0
valid_products_df = edited_products[valid_product_mask].copy()

if not valid_products_df.empty:
    total_price = (
        valid_products_df["가격"].fillna(0)
        * valid_products_df["수량"].fillna(1)
    ).sum()
    st.success(f"🧾 상품 총액: **{total_price:,.0f}원**")

st.subheader("🎟️ AI가 읽은 혜택")
st.info(
    "'확인 필요'는 AI가 사진만으로 확정하지 못한 조건입니다. "
    "사진을 확인해서 알 수 있으면 직접 수정하고, 모르면 그대로 두세요."
)

edited_benefits = st.data_editor(
    initial_benefit_df,
    num_rows="dynamic",
    hide_index=True,
    width="stretch",
    key="ai_benefit_editor",
    column_config={
        "혜택명": st.column_config.TextColumn("혜택명"),
        "분류": st.column_config.SelectboxColumn(
            "분류", options=list(CATEGORY_VALUES.keys())
        ),
        "제공사": st.column_config.TextColumn("제공사"),
        "할인방식": st.column_config.SelectboxColumn(
            "할인방식", options=list(DISCOUNT_VALUES.keys())
        ),
        "할인값": st.column_config.NumberColumn("할인값", min_value=0),
        "최소결제금액": st.column_config.NumberColumn(
            "최소결제금액", min_value=0, step=1000, format="%d원"
        ),
        "최대할인금액": st.column_config.NumberColumn(
            "최대할인금액", min_value=0, step=1000, format="%d원"
        ),
        "최소금액기준": st.column_config.SelectboxColumn(
            "최소금액기준", options=list(BASIS_VALUES.keys())
        ),
        "쿠폰중복": st.column_config.SelectboxColumn(
            "쿠폰중복", options=["가능", "불가", "확인 필요"]
        ),
        "멤버십중복": st.column_config.SelectboxColumn(
            "멤버십중복", options=["가능", "불가", "확인 필요"]
        ),
        "카드/결제중복": st.column_config.SelectboxColumn(
            "카드/결제중복", options=["가능", "불가", "확인 필요"]
        ),
        "사용채널": st.column_config.SelectboxColumn(
            "사용채널", options=list(CHANNEL_VALUES.keys())
        ),
        "분할결제 재사용": st.column_config.SelectboxColumn(
            "분할결제 재사용",
            options=["재사용 가능", "1회 사용", "확인 필요"],
        ),
        "AI확신도": st.column_config.SelectboxColumn(
            "AI확신도", options=["high", "medium", "low"]
        ),
    },
)


# =========================================================
# 4. 저장 데이터 생성
# =========================================================
def build_products(df):
    results = []

    for index, row in df.iterrows():
        price = optional_number(row.get("가격"))
        if price is None or price <= 0:
            continue

        quantity = optional_number(row.get("수량"))
        quantity = int(quantity) if quantity and quantity >= 1 else 1

        name = clean_text(row.get("상품명")) or f"상품 {index + 1}"

        results.append(
            {
                "id": f"product_{index}",
                "name": name,
                "price": float(price),
                "quantity": quantity,
                "total": float(price) * quantity,
            }
        )

    return results


def build_benefits(df):
    results = []

    for index, row in df.iterrows():
        name = clean_text(row.get("혜택명"))
        if not name:
            continue

        discount_label = clean_text(row.get("할인방식")) or "확인 필요"
        discount_type = DISCOUNT_VALUES.get(discount_label, "unknown")

        min_purchase_raw = optional_number(row.get("최소결제금액"))
        max_discount_raw = optional_number(row.get("최대할인금액"))
        value_raw = optional_number(row.get("할인값"))

        conditions = clean_text(row.get("기타조건"))
        unknown_notes = []

        # 현재 2번 페이지가 null 숫자를 직접 처리하지 않기 때문에
        # 미확인 핵심조건은 0으로 넘기되 conditions에 표시하여 '확인 필요 후보'로 보낸다.
        if discount_type == "unknown" or value_raw is None:
            unknown_notes.append("할인 방식 또는 할인값 확인 필요")

        if min_purchase_raw is None:
            unknown_notes.append("최소 결제금액 확인 필요")

        if discount_type == "percent" and max_discount_raw is None:
            unknown_notes.append("최대 할인한도 확인 필요")

        basis_label = clean_text(row.get("최소금액기준")) or "확인 필요"
        minimum_basis = BASIS_VALUES.get(basis_label, "unknown")
        if minimum_basis == "unknown":
            unknown_notes.append("최소 결제금액 적용 기준 확인 필요")

        required_payment = clean_text(row.get("필수결제수단"))
        if required_payment:
            unknown_notes.append(f"필수 결제수단: {required_payment}")

        if unknown_notes:
            note_text = " / ".join(unknown_notes)
            conditions = f"{conditions} / {note_text}".strip(" / ")

        category_label = clean_text(row.get("분류")) or "기타"
        category = CATEGORY_VALUES.get(category_label, "other")

        channel_label = clean_text(row.get("사용채널")) or "확인 필요"

        results.append(
            {
                "id": f"benefit_{index}",
                "name": name,
                "category": category,
                "category_label": category_label,
                "issuer": clean_text(row.get("제공사")),
                "discount_type": discount_type,
                "discount_type_label": discount_label,
                "value": page2_number(value_raw),
                "min_purchase": page2_number(min_purchase_raw),
                "max_discount": page2_number(max_discount_raw),
                "minimum_basis": minimum_basis,
                "stack_coupon": label_to_bool(row.get("쿠폰중복")),
                "stack_coupon_label": clean_text(row.get("쿠폰중복"))
                or "확인 필요",
                "stack_membership": label_to_bool(row.get("멤버십중복")),
                "stack_membership_label": clean_text(row.get("멤버십중복"))
                or "확인 필요",
                "stack_payment": label_to_bool(row.get("카드/결제중복")),
                "stack_payment_label": clean_text(row.get("카드/결제중복"))
                or "확인 필요",
                "channel": CHANNEL_VALUES.get(channel_label, "unknown"),
                "channel_label": channel_label,
                "expiry": clean_text(row.get("유효기간")),
                "usage_limit": clean_text(row.get("이용횟수")),
                "reusable": label_to_reusable(row.get("분할결제 재사용")),
                "excluded_items": clean_text(row.get("제외대상")),
                "required_payment_method": required_payment,
                "conditions": conditions,
                "confidence": clean_text(row.get("AI확신도")) or "low",
            }
        )

    return results


# =========================================================
# 5. 저장
# =========================================================
st.divider()
st.header("4️⃣ 확인한 정보 저장")

allow_split_payment = st.checkbox(
    "상품을 나누어 결제하는 경우까지 비교",
    value=st.session_state.get("allow_split_payment", True),
    help="체크하면 2번 페이지에서 묶음결제와 분할결제를 함께 비교합니다.",
)

if st.button(
    "💾 상품·혜택 저장하고 최적 결제 계산 준비",
    type="primary",
    use_container_width=True,
):
    products_to_save = build_products(edited_products)
    benefits_to_save = build_benefits(edited_benefits)

    if not products_to_save:
        st.error(
            "상품 가격을 확인할 수 없습니다. 장바구니/결제 화면을 함께 올리거나 "
            "상품 표에 가격을 최소 1개 입력해주세요."
        )
    elif not benefits_to_save:
        st.error("분석된 혜택이 없습니다. 혜택 캡처를 다시 올리거나 표에 혜택을 추가해주세요.")
    else:
        st.session_state["store_name"] = store_name
        st.session_state["products"] = products_to_save
        st.session_state["benefits"] = benefits_to_save
        st.session_state["allow_split_payment"] = allow_split_payment
        st.session_state["benefit_input_completed"] = True

        uncertain = sum(
            1
            for benefit in benefits_to_save
            if (
                benefit.get("stack_coupon") is None
                or benefit.get("stack_membership") is None
                or benefit.get("stack_payment") is None
                or benefit.get("channel") == "unknown"
                or benefit.get("conditions")
            )
        )

        st.success(
            f"✅ 상품 {len(products_to_save)}개와 혜택 {len(benefits_to_save)}개를 저장했습니다."
        )

        if uncertain:
            st.warning(
                f"조건 확인이 필요한 혜택이 {uncertain}개 있습니다. "
                "2번 페이지에서는 확정 가능한 추천안과 조건 확인 필요 후보를 구분해서 보여줍니다."
            )

        st.write("이제 왼쪽 메뉴에서 **2_최적_결제_추천**으로 이동하세요.")


# =========================================================
# 개발용 상태 요약
# =========================================================
if st.session_state.get("benefit_input_completed"):
    with st.expander("📋 현재 저장 상태 보기"):
        st.write(f"구매처: **{st.session_state.get('store_name', '-')}**")
        st.write(f"상품: **{len(st.session_state.get('products', []))}개**")
        st.write(f"혜택: **{len(st.session_state.get('benefits', []))}개**")
