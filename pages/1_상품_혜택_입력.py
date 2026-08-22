import base64
import json

import pandas as pd
import streamlit as st
from google import genai


# =========================================================
# 페이지 설정
# =========================================================
st.set_page_config(
    page_title="상품·혜택 AI 자동분석",
    page_icon="📸",
    layout="wide",
)

st.title("📸 상품 · 혜택 AI 자동분석")
st.write(
    "장바구니·상품 화면과 쿠폰·카드·통신사·간편결제 혜택 캡처를 올리면 "
    "Gemini가 조건을 읽어 상품과 혜택 정보를 자동으로 정리합니다."
)
st.info(
    "AI가 사진에 없는 조건을 추측하지 않도록 설계했습니다. "
    "분석 결과에서 '확인 필요' 항목만 직접 확인한 뒤 저장하면 됩니다."
)


# =========================================================
# 설정
# =========================================================
MODEL_NAME = "gemini-3-flash-preview"
MAX_IMAGES = 6
MAX_INLINE_BYTES = 18 * 1024 * 1024  # 18MB: API 20MB inline 한도보다 여유 있게


# =========================================================
# Gemini 클라이언트
# =========================================================
def get_gemini_client():
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        return genai.Client(api_key=api_key)
    except Exception:
        return None


# =========================================================
# JSON Schema
# =========================================================
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "store_name": {
            "type": "string",
            "description": "사진에서 확인되는 구매처 또는 브랜드. 확인되지 않으면 빈 문자열.",
        },
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "price": {"type": "number"},
                    "quantity": {"type": "integer"},
                    "price_known": {"type": "boolean"},
                },
                "required": ["name", "price", "quantity", "price_known"],
                "additionalProperties": False,
            },
        },
        "benefits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "issuer": {"type": "string"},
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
                    "discount_type": {
                        "type": "string",
                        "enum": ["percent", "fixed", "points", "unknown"],
                    },
                    "value": {"type": "number"},
                    "value_known": {"type": "boolean"},
                    "min_purchase": {"type": "number"},
                    "min_purchase_known": {"type": "boolean"},
                    "max_discount": {"type": "number"},
                    "max_discount_known": {"type": "boolean"},
                    "stack_coupon": {
                        "type": "string",
                        "enum": ["possible", "not_possible", "unknown"],
                    },
                    "stack_membership": {
                        "type": "string",
                        "enum": ["possible", "not_possible", "unknown"],
                    },
                    "stack_payment": {
                        "type": "string",
                        "enum": ["possible", "not_possible", "unknown"],
                    },
                    "channel": {
                        "type": "string",
                        "enum": ["online", "offline", "both", "unknown"],
                    },
                    "expiry": {"type": "string"},
                    "usage_limit": {"type": "string"},
                    "reuse_type": {
                        "type": "string",
                        "enum": ["single_use", "reusable", "unknown"],
                    },
                    "min_purchase_basis": {
                        "type": "string",
                        "enum": ["starting_price", "before_benefit", "unknown"],
                    },
                    "required_payment_method": {"type": "string"},
                    "excluded_items": {"type": "string"},
                    "raw_conditions": {"type": "string"},
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                },
                "required": [
                    "name",
                    "issuer",
                    "category",
                    "discount_type",
                    "value",
                    "value_known",
                    "min_purchase",
                    "min_purchase_known",
                    "max_discount",
                    "max_discount_known",
                    "stack_coupon",
                    "stack_membership",
                    "stack_payment",
                    "channel",
                    "expiry",
                    "usage_limit",
                    "reuse_type",
                    "min_purchase_basis",
                    "required_payment_method",
                    "excluded_items",
                    "raw_conditions",
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
# 이미지 분석 프롬프트
# =========================================================
ANALYSIS_PROMPT = """
너는 한국의 쇼핑·결제 혜택을 구조화하는 분석기다.
사용자가 올린 여러 장의 스크린샷에서 구매 상품과 결제 혜택을 읽어 JSON으로 정리하라.

[가장 중요한 원칙]
- 사진에 실제로 보이는 정보만 사용한다.
- 사진에 없는 조건은 절대 추측하지 않는다.
- 중복 가능 여부가 명시되지 않으면 반드시 unknown이다.
- 숫자가 보이지 않으면 해당 known 필드를 false로 하고 숫자값은 0으로 둔다.
- 같은 혜택의 앞/뒤 조건을 여러 사진으로 올렸다면 명백히 동일한 혜택일 때만 하나로 합친다.
- 한 사진에 여러 혜택이 있으면 각각 별도 혜택으로 추출한다.
- 이미지가 잘렸거나 글자가 흐리거나 조건을 확실히 판단하기 어려운 부분은 warnings에 적는다.
- warnings는 사용자에게 직접 보여주는 안내 문구이므로 반드시 친절한 존댓말로 작성한다.
- "~함", "~기재함", "~확인됨" 같은 보고서체나 반말은 사용하지 않는다.
- 예: "일부 이미지에서 상세 조건을 확인하기 어려워, 확인 가능한 혜택을 기준으로 분석했습니다."

[상품]
- 장바구니, 상품 상세, 주문 화면에 상품명·가격·수량이 보이면 products에 넣는다.
- 가격을 확실히 못 읽으면 price=0, price_known=false.
- 상품 화면이 없으면 products는 빈 배열이어도 된다.

[혜택 분류]
- 쇼핑몰/브랜드 쿠폰: coupon
- SKT/KT/LG U+ 등 통신사 또는 멤버십: membership
- 신용/체크카드 즉시할인·청구할인: card
- 카카오페이/네이버페이/토스페이 등: easy_pay
- 포인트 사용/적립: point

[할인값]
- 20% 할인: discount_type=percent, value=20
- 5,000원 할인: discount_type=fixed, value=5000
- 포인트 사용/적립: discount_type=points
- 종류 자체가 불명확하면 discount_type=unknown

[최소금액 / 최대할인]
- '4만원 이상 구매 시': min_purchase=40000, min_purchase_known=true
- '최대 1만원': max_discount=10000, max_discount_known=true
- 조건이 없다고 명확히 보이는 경우 0과 known=true
- 화면에 관련 정보가 없으면 0과 known=false

[중복]
- stack_coupon: 다른 쿠폰과 중복 가능 여부
- stack_membership: 멤버십과 중복 가능 여부
- stack_payment: 카드/간편결제 등 결제혜택과 중복 가능 여부
- 명시되어 있지 않으면 unknown

[채널]
- 온라인 전용: online
- 오프라인 전용: offline
- 온·오프라인 모두: both
- 확인 불가: unknown

[사용횟수 / 재사용]
- '1회 사용', '기간 중 1회': usage_limit에 그대로 요약하고 reuse_type=single_use
- '1일 1회', '월 1회' 역시 usage_limit에 정확히 적는다.
- 여러 결제 건에서 반복 사용할 수 있다고 명확히 확인되는 경우만 reuse_type=reusable
- 재사용 여부가 보이지 않으면 unknown

[최소금액 기준]
- 혜택 적용 전 최초 결제금액 기준이라고 명확히 보이면 starting_price
- 다른 할인 적용 후 실제 결제금액 기준이라고 명확히 보이면 before_benefit
- 불명확하면 unknown

[기타]
- 특정 카드/결제수단 필수 조건은 required_payment_method에 적는다.
- 일부 브랜드/상품 제외는 excluded_items에 적는다.
- 선착순, 특정 요일, 앱 전용, 첫 결제, 특정 카드만 가능 등 계산에 영향을 주는 문구는 raw_conditions에 빠뜨리지 않는다.
- expiry는 가능하면 YYYY-MM-DD 형식. 날짜를 정확히 읽을 수 없으면 보이는 문구 그대로 적는다.
- confidence는 핵심 조건이 모두 선명하면 high, 일부 불명확하면 medium, 많이 잘렸거나 흐리면 low.
"""


# =========================================================
# Gemini 호출
# =========================================================
def analyze_images(uploaded_files):
    client = get_gemini_client()

    if client is None:
        raise RuntimeError(
            "GEMINI_API_KEY가 없습니다. Streamlit Settings → Secrets에 GEMINI_API_KEY를 추가해주세요."
        )

    selected_files = uploaded_files[:MAX_IMAGES]
    total_bytes = sum(len(file.getvalue()) for file in selected_files)

    if total_bytes > MAX_INLINE_BYTES:
        raise RuntimeError(
            "업로드한 이미지의 총 용량이 큽니다. 이미지 수를 줄이거나 캡처 크기를 줄여 다시 시도해주세요."
        )

    interaction_input = [
        {
            "type": "text",
            "text": ANALYSIS_PROMPT,
        }
    ]

    for index, image in enumerate(selected_files, start=1):
        mime_type = image.type or "image/png"
        encoded = base64.b64encode(image.getvalue()).decode("utf-8")

        interaction_input.append(
            {
                "type": "text",
                "text": f"이미지 {index}: {image.name}",
            }
        )
        interaction_input.append(
            {
                "type": "image",
                "data": encoded,
                "mime_type": mime_type,
            }
        )

    interaction = client.interactions.create(
        model=MODEL_NAME,
        input=interaction_input,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": EXTRACTION_SCHEMA,
        },
        store=False,
    )

    return json.loads(interaction.output_text)


# =========================================================
# 표시 변환 함수
# =========================================================
CATEGORY_TO_KR = {
    "coupon": "쿠폰",
    "membership": "통신사/멤버십",
    "card": "카드",
    "easy_pay": "간편결제",
    "point": "포인트",
    "other": "기타",
}
KR_TO_CATEGORY = {value: key for key, value in CATEGORY_TO_KR.items()}

DISCOUNT_TO_KR = {
    "percent": "정률(%)",
    "fixed": "정액(원)",
    "points": "포인트/적립",
    "unknown": "확인 필요",
}
KR_TO_DISCOUNT = {value: key for key, value in DISCOUNT_TO_KR.items()}

STACK_TO_KR = {
    "possible": "가능",
    "not_possible": "불가",
    "unknown": "확인 필요",
}
KR_TO_STACK = {value: key for key, value in STACK_TO_KR.items()}

CHANNEL_TO_KR = {
    "online": "온라인",
    "offline": "오프라인",
    "both": "온·오프라인",
    "unknown": "확인 필요",
}
KR_TO_CHANNEL = {value: key for key, value in CHANNEL_TO_KR.items()}

REUSE_TO_KR = {
    "single_use": "1회만 사용",
    "reusable": "분할결제 재사용 가능",
    "unknown": "확인 필요",
}
KR_TO_REUSE = {value: key for key, value in REUSE_TO_KR.items()}

BASIS_TO_KR = {
    "starting_price": "결제 시작 금액",
    "before_benefit": "혜택 적용 직전 금액",
    "unknown": "확인 필요",
}
KR_TO_BASIS = {value: key for key, value in BASIS_TO_KR.items()}


def ai_products_to_df(products):
    rows = []
    for product in products:
        rows.append(
            {
                "상품명": product.get("name", ""),
                "가격": product.get("price", 0),
                "수량": product.get("quantity", 1),
                "가격확인": "확인" if product.get("price_known", False) else "확인 필요",
            }
        )

    if not rows:
        rows = [{"상품명": "", "가격": 0, "수량": 1, "가격확인": "확인 필요"}]

    return pd.DataFrame(rows)


def ai_benefits_to_df(benefits):
    rows = []

    for benefit in benefits:
        min_purchase_display = benefit.get("min_purchase", 0) if benefit.get("min_purchase_known", False) else 0
        max_discount_display = benefit.get("max_discount", 0) if benefit.get("max_discount_known", False) else 0

        rows.append(
            {
                "혜택명": benefit.get("name", ""),
                "분류": CATEGORY_TO_KR.get(benefit.get("category"), "기타"),
                "제공사": benefit.get("issuer", ""),
                "할인방식": DISCOUNT_TO_KR.get(benefit.get("discount_type"), "확인 필요"),
                "할인값": benefit.get("value", 0),
                "할인값확인": "확인" if benefit.get("value_known", False) else "확인 필요",
                "최소결제금액": min_purchase_display,
                "최소금액확인": "확인" if benefit.get("min_purchase_known", False) else "확인 필요",
                "최대할인금액": max_discount_display,
                "최대할인확인": "확인" if benefit.get("max_discount_known", False) else "확인 필요",
                "쿠폰중복": STACK_TO_KR.get(benefit.get("stack_coupon"), "확인 필요"),
                "멤버십중복": STACK_TO_KR.get(benefit.get("stack_membership"), "확인 필요"),
                "카드/결제중복": STACK_TO_KR.get(benefit.get("stack_payment"), "확인 필요"),
                "사용채널": CHANNEL_TO_KR.get(benefit.get("channel"), "확인 필요"),
                "유효기간": benefit.get("expiry", ""),
                "이용횟수": benefit.get("usage_limit", ""),
                "분할결제재사용": REUSE_TO_KR.get(benefit.get("reuse_type"), "확인 필요"),
                "최소금액기준": BASIS_TO_KR.get(benefit.get("min_purchase_basis"), "확인 필요"),
                "필수결제수단": benefit.get("required_payment_method", ""),
                "제외대상": benefit.get("excluded_items", ""),
                "기타조건": benefit.get("raw_conditions", ""),
                "AI확신도": benefit.get("confidence", "low"),
            }
        )

    if not rows:
        rows = [
            {
                "혜택명": "",
                "분류": "쿠폰",
                "제공사": "",
                "할인방식": "확인 필요",
                "할인값": 0,
                "할인값확인": "확인 필요",
                "최소결제금액": 0,
                "최소금액확인": "확인 필요",
                "최대할인금액": 0,
                "최대할인확인": "확인 필요",
                "쿠폰중복": "확인 필요",
                "멤버십중복": "확인 필요",
                "카드/결제중복": "확인 필요",
                "사용채널": "확인 필요",
                "유효기간": "",
                "이용횟수": "",
                "분할결제재사용": "확인 필요",
                "최소금액기준": "확인 필요",
                "필수결제수단": "",
                "제외대상": "",
                "기타조건": "",
                "AI확신도": "low",
            }
        ]

    return pd.DataFrame(rows)


def label_to_bool(value):
    if value == "가능":
        return True
    if value == "불가":
        return False
    return None


def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def clean_number(value):
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# =========================================================
# 1. 이미지 업로드
# =========================================================
st.header("1️⃣ 사진 업로드")
st.write(
    "장바구니/상품 화면과 내가 가진 쿠폰·통신사·카드·간편결제 혜택 캡처를 함께 올려주세요. "
    "상품 화면이 없으면 분석 후 상품 표에서 직접 추가할 수 있습니다."
)

uploaded_files = st.file_uploader(
    "상품·혜택 캡처 업로드",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
    help=f"한 번에 최대 {MAX_IMAGES}장까지 분석합니다.",
)

if uploaded_files:
    if len(uploaded_files) > MAX_IMAGES:
        st.warning(f"현재는 앞의 {MAX_IMAGES}장만 분석합니다.")

    preview_files = uploaded_files[:MAX_IMAGES]
    preview_cols = st.columns(3)

    for idx, image in enumerate(preview_files):
        with preview_cols[idx % 3]:
            st.image(image, caption=image.name, width="stretch")

st.caption(
    "개인정보 보호를 위해 카드번호·이름·계좌번호 등 분석에 필요 없는 정보는 가리고 올리는 것을 권장합니다."
)

st.divider()


# =========================================================
# 2. AI 분석
# =========================================================
st.header("2️⃣ Gemini AI 자동 분석")

if st.button(
    "✨ 사진에서 상품·혜택 자동 추출",
    type="primary",
    width="stretch",
):
    if not uploaded_files:
        st.warning("먼저 사진을 1장 이상 올려주세요.")
    else:
        with st.spinner("Gemini가 상품과 혜택 조건을 읽고 있습니다..."):
            try:
                result = analyze_images(uploaded_files)
                st.session_state["gemini_analysis_result"] = result
                st.session_state["gemini_products"] = result.get("products", [])
                st.session_state["gemini_benefits"] = result.get("benefits", [])
                st.session_state["gemini_warnings"] = result.get("warnings", [])
                st.session_state["benefit_working_df"] = ai_benefits_to_df(result.get("benefits", []))
                st.session_state["product_working_df"] = ai_products_to_df(result.get("products", []))

                detected_store = result.get("store_name", "").strip()
                if detected_store:
                    st.session_state["gemini_store_name"] = detected_store

                st.success(
                    f"✅ 상품 {len(result.get('products', []))}개, "
                    f"혜택 {len(result.get('benefits', []))}개를 찾았습니다."
                )

            except Exception as error:
                message = str(error)

                if "429" in message or "RESOURCE_EXHAUSTED" in message:
                    st.error(
                        "Gemini 무료 API 사용 한도에 도달했습니다. 잠시 후 다시 시도하거나 다음 한도 갱신 후 다시 시도해주세요."
                    )
                elif "API_KEY" in message or "401" in message or "403" in message:
                    st.error(
                        "Gemini API 키를 확인해주세요. Streamlit Secrets의 GEMINI_API_KEY 값이 올바른지 확인하면 됩니다."
                    )
                else:
                    st.error("사진 분석 중 오류가 발생했습니다.")

                with st.expander("오류 상세 보기"):
                    st.code(message)


# =========================================================
# 3. 분석 결과 확인/수정
# =========================================================
if "gemini_analysis_result" in st.session_state:
    st.divider()
    st.header("3️⃣ AI 분석 결과 확인")

    warnings = st.session_state.get("gemini_warnings", [])
    if warnings:
        st.warning("AI가 확실히 읽지 못한 부분이 있습니다.")
        for warning in warnings:
            st.write(f"- {warning}")

    st.write(
        "AI가 읽은 결과입니다. **확인 필요** 항목이나 잘못 읽은 숫자만 수정해주세요."
    )

    store_name = st.text_input(
        "구매처",
        value=st.session_state.get(
            "gemini_store_name",
            st.session_state.get("store_name", ""),
        ),
        placeholder="예: 올리브영",
    )

    # ---------------- 상품 ----------------
    st.subheader("🛍️ 상품")

    if "product_working_df" not in st.session_state:
        st.session_state["product_working_df"] = ai_products_to_df(st.session_state.get("gemini_products", []))
    product_df = st.session_state["product_working_df"].copy()

    edited_products = st.data_editor(
        product_df,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key="gemini_product_editor",
        column_config={
            "상품명": st.column_config.TextColumn("상품명"),
            "가격": st.column_config.NumberColumn(
                "가격",
                min_value=0,
                step=1000,
                format="localized",
            ),
            "수량": st.column_config.NumberColumn(
                "수량",
                min_value=1,
                step=1,
                format="%d",
            ),
            "가격확인": st.column_config.SelectboxColumn(
                "가격확인",
                options=["확인", "확인 필요"],
            ),
        },
    )

    valid_products_preview = edited_products[
        edited_products["가격"].fillna(0) > 0
    ].copy()

    if not valid_products_preview.empty:
        preview_total = (
            valid_products_preview["가격"].fillna(0)
            * valid_products_preview["수량"].fillna(1)
        ).sum()
        st.success(f"🧾 상품 총액: **{preview_total:,.0f}원**")

    # ---------------- 혜택 ----------------
    st.subheader("🎟️ 혜택")

    if "benefit_working_df" not in st.session_state:
        st.session_state["benefit_working_df"] = ai_benefits_to_df(st.session_state.get("gemini_benefits", []))

    benefit_df = st.session_state["benefit_working_df"].copy()

    if "삭제" not in benefit_df.columns:
        benefit_df.insert(0, "삭제", False)

    edited_benefits = st.data_editor(
        benefit_df,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key="gemini_benefit_editor",
        column_order=[
            "삭제", "혜택명", "분류", "제공사", "할인방식", "할인값",
            "최소결제금액", "최대할인금액", "사용채널", "유효기간"
        ],
        column_config={
            "삭제": st.column_config.CheckboxColumn("삭제", default=False),
            "혜택명": st.column_config.TextColumn("혜택명"),
            "분류": st.column_config.SelectboxColumn("분류", options=list(CATEGORY_TO_KR.values())),
            "제공사": st.column_config.TextColumn("제공사"),
            "할인방식": st.column_config.SelectboxColumn("할인방식", options=list(DISCOUNT_TO_KR.values())),
            "할인값": st.column_config.NumberColumn("할인값", min_value=0, format="localized"),
            "최소결제금액": st.column_config.NumberColumn("최소결제금액", min_value=0, step=1000, format="localized"),
            "최대할인금액": st.column_config.NumberColumn("최대할인금액", min_value=0, step=1000, format="localized"),
            "사용채널": st.column_config.SelectboxColumn("사용채널", options=list(CHANNEL_TO_KR.values())),
            "유효기간": st.column_config.TextColumn("유효기간"),
        },
    )

    if st.button("🗑️ 선택한 혜택 삭제"):
        delete_mask = edited_benefits["삭제"].fillna(False).astype(bool)
        remaining = edited_benefits.loc[~delete_mask].copy()
        remaining = remaining.drop(columns=["삭제"], errors="ignore").reset_index(drop=True)
        st.session_state["benefit_working_df"] = remaining
        st.session_state.pop("gemini_benefit_editor", None)
        st.rerun()

    st.caption(
        "기본 표에는 소비자가 확인할 핵심 정보만 표시합니다. "
        "중복 여부·필수 결제수단·제외대상·기타 조건은 계산용 데이터로 그대로 보존됩니다."
    )

    edited_benefits = edited_benefits.loc[
        ~edited_benefits["삭제"].fillna(False).astype(bool)
    ].drop(columns=["삭제"], errors="ignore")

    st.caption(
        "'확인 필요'는 AI가 사진에서 해당 조건을 확인하지 못했다는 뜻입니다. "
        "확인하지 않은 조건을 임의로 '가능'으로 바꾸지 않는 것이 안전합니다."
    )

    st.divider()

    # =====================================================
    # 4. 최적화 설정 / 저장
    # =====================================================
    st.header("4️⃣ 저장 후 최적 결제 계산")

    allow_split_payment = st.checkbox(
        "상품을 나누어 결제하는 경우까지 비교",
        value=st.session_state.get("allow_split_payment", True),
    )

    st.session_state["product_working_df"] = edited_products.copy()
    st.session_state["benefit_working_df"] = edited_benefits.copy()

    if st.button(
        "💾 확인한 정보 저장",
        type="primary",
        width="stretch",
    ):
        products_to_save = []

        for index, row in edited_products.iterrows():
            price = clean_number(row.get("가격", 0))
            quantity = int(clean_number(row.get("수량", 1)) or 1)
            name = clean_text(row.get("상품명", ""))

            if price <= 0:
                continue

            if not name:
                name = f"상품 {index + 1}"

            products_to_save.append(
                {
                    "id": f"product_{index}",
                    "name": name,
                    "price": price,
                    "quantity": quantity,
                    "total": price * quantity,
                    "price_known": row.get("가격확인") == "확인",
                }
            )

        benefits_to_save = []

        for index, row in edited_benefits.iterrows():
            name = clean_text(row.get("혜택명", ""))
            if not name:
                continue

            value_known = row.get("할인값확인") == "확인"
            min_known = row.get("최소금액확인") == "확인"
            max_known = row.get("최대할인확인") == "확인"

            extra_condition_notes = []
            raw_conditions = clean_text(row.get("기타조건", ""))

            if raw_conditions:
                extra_condition_notes.append(raw_conditions)
            if not value_known:
                extra_condition_notes.append("AI 확인 필요: 할인값 미확인")
            if not min_known:
                extra_condition_notes.append("AI 확인 필요: 최소결제금액 미확인")
            if not max_known:
                extra_condition_notes.append("AI 확인 필요: 최대할인금액 미확인")
            if row.get("분할결제재사용") == "확인 필요":
                extra_condition_notes.append("AI 확인 필요: 분할결제 재사용 여부 미확인")
            if row.get("최소금액기준") == "확인 필요":
                extra_condition_notes.append("AI 확인 필요: 최소금액 판단 기준 미확인")

            combined_conditions = " | ".join(extra_condition_notes)

            category_label = row.get("분류", "기타")
            discount_label = row.get("할인방식", "확인 필요")
            channel_label = row.get("사용채널", "확인 필요")

            benefits_to_save.append(
                {
                    "id": f"benefit_{index}",
                    "name": name,
                    "issuer": clean_text(row.get("제공사", "")),
                    "category": KR_TO_CATEGORY.get(category_label, "other"),
                    "category_label": category_label,
                    "discount_type": KR_TO_DISCOUNT.get(discount_label, "unknown"),
                    "discount_type_label": discount_label,
                    "value": clean_number(row.get("할인값", 0)),
                    "value_known": value_known,
                    "min_purchase": clean_number(row.get("최소결제금액", 0)),
                    "min_purchase_known": min_known,
                    "max_discount": clean_number(row.get("최대할인금액", 0)),
                    "max_discount_known": max_known,
                    "stack_coupon": label_to_bool(row.get("쿠폰중복", "확인 필요")),
                    "stack_coupon_label": row.get("쿠폰중복", "확인 필요"),
                    "stack_membership": label_to_bool(row.get("멤버십중복", "확인 필요")),
                    "stack_membership_label": row.get("멤버십중복", "확인 필요"),
                    "stack_payment": label_to_bool(row.get("카드/결제중복", "확인 필요")),
                    "stack_payment_label": row.get("카드/결제중복", "확인 필요"),
                    "channel": KR_TO_CHANNEL.get(channel_label, "unknown"),
                    "channel_label": channel_label,
                    "expiry": clean_text(row.get("유효기간", "")),
                    "usage_limit": clean_text(row.get("이용횟수", "")),
                    "reuse_type": KR_TO_REUSE.get(
                        row.get("분할결제재사용", "확인 필요"), "unknown"
                    ),
                    "reuse_label": row.get("분할결제재사용", "확인 필요"),
                    "min_purchase_basis": KR_TO_BASIS.get(
                        row.get("최소금액기준", "확인 필요"), "unknown"
                    ),
                    "min_purchase_basis_label": row.get("최소금액기준", "확인 필요"),
                    "required_payment_method": clean_text(row.get("필수결제수단", "")),
                    "excluded_items": clean_text(row.get("제외대상", "")),
                    "conditions": combined_conditions,
                    "confidence": clean_text(row.get("AI확신도", "low")),
                }
            )

        if not products_to_save:
            st.error(
                "가격이 확인된 상품이 없습니다. 상품 표에서 상품명·가격을 확인하거나 직접 입력해주세요."
            )
        elif not benefits_to_save:
            st.error("혜택이 없습니다. 혜택을 최소 1개 이상 확인해주세요.")
        else:
            st.session_state["store_name"] = store_name
            st.session_state["products"] = products_to_save
            st.session_state["benefits"] = benefits_to_save
            st.session_state["allow_split_payment"] = allow_split_payment
            st.session_state["benefit_input_completed"] = True

            uncertain_count = sum(
                1
                for benefit in benefits_to_save
                if (
                    benefit["stack_coupon"] is None
                    or benefit["stack_membership"] is None
                    or benefit["stack_payment"] is None
                    or benefit["reuse_type"] == "unknown"
                    or benefit["min_purchase_basis"] == "unknown"
                    or not benefit["value_known"]
                    or not benefit["min_purchase_known"]
                    or not benefit["max_discount_known"]
                )
            )

            st.success(
                f"✅ 상품 {len(products_to_save)}개, 혜택 {len(benefits_to_save)}개를 저장했습니다."
            )

            if uncertain_count:
                st.warning(
                    f"조건 확인이 필요한 혜택이 {uncertain_count}개 있습니다. "
                    "현재 2번 페이지에서는 이런 항목이 포함된 조합을 확정안과 구분해 처리합니다."
                )

            st.write(
                "이제 왼쪽 메뉴에서 **2_최적_결제_추천** 페이지로 이동하세요."
            )

else:
    st.divider()
    st.caption(
        "사진을 업로드한 뒤 '사진에서 상품·혜택 자동 추출'을 누르면 분석 결과가 여기에 표시됩니다."
    )
