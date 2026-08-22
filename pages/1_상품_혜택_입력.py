import base64
import json
import re

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
                    "brand": {"type": "string"},
                    "price": {"type": "number"},
                    "quantity": {"type": "integer"},
                    "price_known": {"type": "boolean"},
                },
                "required": ["name", "brand", "price", "quantity", "price_known"],
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
                    "eligible_brands": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "이 혜택이 적용되는 브랜드 목록. 전체 적용이면 빈 배열.",
                    },
                    "eligible_items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "특정 상품/상품군에만 적용되는 경우 대상명. 전체 적용이면 빈 배열.",
                    },
                    "excluded_items": {"type": "string"},
                    "exclusive_group": {"type": "string"},
                    "exclusive_group_reason": {"type": "string"},
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
                    "eligible_brands",
                    "eligible_items",
                    "excluded_items",
                    "exclusive_group",
                    "exclusive_group_reason",
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
        "benefit_relations": {
            "type": "array",
            "description": (
                "추출된 혜택끼리의 중복 가능/불가 관계. "
                "모든 조합을 억지로 채우지 말고 판단 근거가 있는 관계만 작성."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "benefit_a_name": {"type": "string"},
                    "benefit_b_name": {"type": "string"},
                    "relation": {
                        "type": "string",
                        "enum": ["possible", "not_possible", "unknown"],
                    },
                    "reason": {"type": "string"},
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                },
                "required": [
                    "benefit_a_name",
                    "benefit_b_name",
                    "relation",
                    "reason",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["store_name", "products", "benefits", "warnings", "benefit_relations"],
    "additionalProperties": False,
}


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
- "이 쿠폰은 라운드랩에만 적용돼"라면 해당 쿠폰의 eligible_brands=["라운드랩"].
- "A 쿠폰은 B 상품에만 적용돼"라면 eligible_items에 B를 넣는다.
- "A 쿠폰은 다른 쿠폰과 중복 안 돼"라면 stack_coupon="not_possible".
- "A 쿠폰은 카드 할인과 중복돼"라면 stack_payment="possible".
- "A 혜택과 B 혜택은 같이 못 써"라면 relation_updates에 두 혜택 관계를 not_possible로 넣는다.
- 사용자가 말하지 않은 속성은 빈 배열/빈 문자열/no_change로 둔다.
- 사용자가 어떤 혜택을 가리키는지 합리적으로 특정할 수 없으면 benefit_updates에 억지로 넣지 말고 summary에서 다시 확인이 필요하다고 안내한다.
- summary는 사용자에게 직접 보여줄 짧은 존댓말 문장으로 작성한다.
"""


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
- 이미지가 잘렸거나 글자가 흐리면 warnings에 적는다.
- warnings는 사용자에게 직접 보여주는 문구이므로 반드시 친절한 존댓말로 작성한다.
- "~함", "~기재함", "~확인됨" 같은 보고서체는 사용하지 않는다.

[상품]
- 장바구니, 상품 상세, 주문 화면에 상품명·브랜드·가격·수량이 보이면 products에 넣는다.
- 상품명 앞/위에 브랜드명이 따로 보이면 brand에 분리해서 적는다.
- 브랜드를 확실히 알 수 없으면 brand는 빈 문자열로 둔다.
- 가격을 확실히 못 읽으면 price=0, price_known=false.
- 상품 화면이 없으면 products는 빈 배열이어도 된다.


[브랜드/상품 한정 혜택 - 매우 중요]
- "OOO 브랜드 20% 쿠폰", "라운드랩 전용", "일부 브랜드 전용", "특정 브랜드 상품에만 적용"처럼
  적용 대상이 제한된 혜택은 반드시 eligible_brands에 대상 브랜드를 넣는다.
- 특정 상품명/상품군에만 적용되면 eligible_items에 넣는다.
- "전 상품", "전체 상품"처럼 전체 적용이면 eligible_brands와 eligible_items는 빈 배열로 둔다.
- 적용 대상이 브랜드인지 상품인지 애매하면 사진 문구를 raw_conditions에도 남긴다.
- 브랜드별 쿠폰은 해당 브랜드 상품 금액에만 할인율/최소금액/최대할인을 계산해야 한다.
- 예: 장바구니에 A브랜드 40,000원 + B브랜드 30,000원이 있고 A브랜드 전용 20% 쿠폰이라면
  쿠폰 계산 기준 금액은 전체 70,000원이 아니라 A브랜드 대상 상품 금액 40,000원이다.

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
- 동일 이벤트 안에서 결제금액 구간에 따라 3천P/5천P 또는 4천원/6천원/9천원처럼
  하나만 선택되는 단계형 혜택이라면 각각 별도 혜택으로 추출하되 같은 exclusive_group 값을 부여한다.
- exclusive_group은 사진 속 이벤트 구조를 근거로 판단하고, 근거가 부족하면 빈 문자열로 둔다.
- exclusive_group_reason에는 "동일 이벤트의 금액대별 택1 혜택"처럼 짧게 이유를 적는다.

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


[혜택 간 관계 분석 - 매우 중요]
혜택을 모두 추출한 뒤, 반드시 전체 혜택 목록을 서로 비교하여 관계를 한 번 더 분석한다.

1. 같은 이벤트의 금액대별 혜택
- 예: 6만원 이상 3천P / 9만원 이상 5천P
- 예: 5만원 이상 4천원 / 7만원 이상 6천원 / 9만원 이상 9천원
- 같은 이벤트에서 구매금액 구간에 따라 혜택 하나가 결정되는 구조라면 동시에 더하지 않는다.
- 각 혜택에 같은 exclusive_group을 부여하고, benefit_relations에도 not_possible 관계를 기록한다.

2. 같은 쿠폰끼리
- 화면이나 조건에서 '쿠폰 중복 불가', '쿠폰 1장 사용', '타 쿠폰과 중복 불가'가 확인되면 not_possible.
- 반대로 중복 가능이 명시된 경우에만 possible.
- 아무 근거가 없으면 unknown.

3. 결제수단 혜택
- 카드/간편결제 혜택이 결제수단을 하나 선택해야 하는 구조라면 동시에 사용할 수 없는 관계로 판단한다.
- 동일 결제서비스의 금액대별 보상은 단계형인지 확인하고 단계형이면 not_possible.
- 단순히 제공사가 같다는 이유만으로 임의 판단하지 않는다.

4. 쿠폰 + 카드/간편결제/멤버십
- 조건 문구나 이벤트 설명을 종합해 함께 적용 가능한지 판단한다.
- 문구에 직접 쓰여 있지 않더라도 동일 화면의 구조, '결제 혜택', '쿠폰 적용 후 결제' 등의 문맥으로
  판단 근거가 충분하면 medium confidence로 추론할 수 있다.
- 근거가 부족하면 unknown으로 둔다.

5. benefit_relations
- 모든 가능한 쌍을 나열할 필요는 없다.
- 계산 결과에 영향을 줄 가능성이 있고, 판단 근거가 있는 관계를 중심으로 작성한다.
- reason은 사용자에게 보여도 이해할 수 있게 짧은 존댓말 문장으로 작성한다.
- confidence=high: 화면 문구가 직접 뒷받침함
- confidence=medium: 이벤트 구조상 합리적으로 판단 가능함
- confidence=low: 추론 근거가 약함

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



def interpret_user_condition(note, benefit_df, product_df):
    client = get_gemini_client()

    if client is None:
        raise RuntimeError("GEMINI_API_KEY가 없습니다.")

    benefit_names = [
        str(name).strip()
        for name in benefit_df.get("혜택명", []).tolist()
        if str(name).strip()
    ]

    products_context = []
    for _, row in product_df.iterrows():
        products_context.append({
            "name": str(row.get("상품명", "")).strip(),
            "brand": str(row.get("브랜드", "")).strip(),
        })

    interaction = client.interactions.create(
        model=MODEL_NAME,
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


def stack_code_to_label(value):
    return {
        "possible": "가능",
        "not_possible": "불가",
        "unknown": "확인 필요",
    }.get(value)


def apply_condition_to_editor_df(benefit_df, result):
    updated = benefit_df.copy()

    for update in result.get("benefit_updates", []):
        target = str(update.get("target_benefit_name", "")).strip()
        if not target:
            continue

        matches = updated.index[
            updated["혜택명"].astype(str).str.strip() == target
        ].tolist()

        # exact match 실패 시 부분 일치 1개일 때만
        if not matches:
            partial = updated.index[
                updated["혜택명"].astype(str).str.contains(
                    re.escape(target),
                    case=False,
                    na=False,
                )
            ].tolist()
            if len(partial) == 1:
                matches = partial

        if len(matches) != 1:
            continue

        idx = matches[0]

        brands = update.get("eligible_brands", []) or []
        items = update.get("eligible_items", []) or []
        excluded = str(update.get("excluded_items", "")).strip()
        required_payment = str(
            update.get("required_payment_method", "")
        ).strip()

        if brands:
            updated.at[idx, "적용브랜드"] = ", ".join(brands)

        if "적용상품" in updated.columns and items:
            updated.at[idx, "적용상품"] = ", ".join(items)

        if excluded:
            updated.at[idx, "제외대상"] = excluded

        if required_payment:
            updated.at[idx, "필수결제수단"] = required_payment

        for source_key, column_name in [
            ("stack_coupon", "쿠폰중복"),
            ("stack_membership", "멤버십중복"),
            ("stack_payment", "카드/결제중복"),
        ]:
            value = update.get(source_key, "no_change")
            label = stack_code_to_label(value)
            if label is not None:
                updated.at[idx, column_name] = label

    return updated


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
                "브랜드": product.get("brand", ""),
                "가격": product.get("price", 0),
                "수량": product.get("quantity", 1),
                "가격확인": "확인" if product.get("price_known", False) else "확인 필요",
            }
        )

    if not rows:
        rows = [{"상품명": "", "브랜드": "", "가격": 0, "수량": 1, "가격확인": "확인 필요"}]

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
                "적용브랜드": ", ".join(benefit.get("eligible_brands", []) or []),
                "적용상품": ", ".join(benefit.get("eligible_items", []) or []),
                "제외대상": benefit.get("excluded_items", ""),
                "택일그룹": benefit.get("exclusive_group", ""),
                "택일그룹근거": benefit.get("exclusive_group_reason", ""),
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
                "적용브랜드": "",
                "적용상품": "",
                "제외대상": "",
                "택일그룹": "",
                "택일그룹근거": "",
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


def split_list_text(value):
    text = clean_text(value)
    if not text:
        return []

    separators = [",", "/", "|", "·"]
    parts = [text]

    for sep in separators:
        new_parts = []
        for part in parts:
            new_parts.extend(part.split(sep))
        parts = new_parts

    return [part.strip() for part in parts if part.strip()]


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
                st.session_state["gemini_ai_relations_raw"] = result.get(
                    "benefit_relations", []
                )
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
            "브랜드": st.column_config.TextColumn(
                "브랜드",
                help="브랜드 전용 쿠폰 계산에 사용합니다."
            ),
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
            "삭제", "혜택명", "분류", "제공사", "적용브랜드", "할인방식", "할인값",
            "최소결제금액", "최대할인금액", "사용채널", "유효기간"
        ],
        column_config={
            "삭제": st.column_config.CheckboxColumn("삭제", default=False),
            "혜택명": st.column_config.TextColumn("혜택명"),
            "분류": st.column_config.SelectboxColumn("분류", options=list(CATEGORY_TO_KR.values())),
            "제공사": st.column_config.TextColumn("제공사"),
            "적용브랜드": st.column_config.TextColumn(
                "적용브랜드",
                help="브랜드 전용 혜택이면 대상 브랜드가 표시됩니다. 여러 개면 쉼표로 구분합니다."
            ),
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

    with st.expander("✏️ AI에게 추가 조건 알려주기"):
        st.caption(
            "AI가 놓친 쿠폰 적용 조건을 알고 있다면 평소 말하듯 적어주세요. "
            "예: '8월 브랜드 쿠폰은 라운드랩 제품에만 적용 가능해.'"
        )

        user_condition_note = st.text_area(
            "추가 조건",
            placeholder=(
                "예) 9천원 쿠폰은 닥터지 제품에만 적용 가능해\n"
                "예) 첫구매 쿠폰은 다른 쿠폰이랑 중복 안 돼"
            ),
            key="input_user_condition_note",
            label_visibility="collapsed",
        )

        if st.button(
            "✨ 조건을 AI에 반영",
            key="apply_user_condition_page1",
        ):
            if not user_condition_note.strip():
                st.warning("추가 조건을 입력해주세요.")
            else:
                with st.spinner("추가 조건을 이해하고 있습니다..."):
                    try:
                        condition_result = interpret_user_condition(
                            user_condition_note,
                            edited_benefits,
                            edited_products,
                        )

                        updated_df = apply_condition_to_editor_df(
                            edited_benefits,
                            condition_result,
                        )

                        st.session_state["benefit_working_df"] = (
                            updated_df.copy()
                        )

                        # 혜택 간 직접 관계도 이름 기준으로 임시 저장
                        relation_notes = st.session_state.get(
                            "pending_user_relation_notes",
                            [],
                        )
                        relation_notes.extend(
                            condition_result.get(
                                "relation_updates",
                                [],
                            )
                        )
                        st.session_state[
                            "pending_user_relation_notes"
                        ] = relation_notes

                        st.session_state[
                            "last_user_condition_summary"
                        ] = condition_result.get(
                            "summary",
                            "추가 조건을 반영했습니다.",
                        )

                        st.session_state.pop(
                            "gemini_benefit_editor",
                            None,
                        )
                        st.rerun()

                    except Exception as error:
                        st.error("추가 조건을 반영하지 못했습니다.")
                        with st.expander("오류 상세 보기"):
                            st.code(str(error))

    if st.session_state.get("last_user_condition_summary"):
        st.success(st.session_state["last_user_condition_summary"])

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
                    "brand": clean_text(row.get("브랜드", "")),
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
                    "eligible_brands": split_list_text(row.get("적용브랜드", "")),
                    "eligible_items": split_list_text(row.get("적용상품", "")),
                    "excluded_items": clean_text(row.get("제외대상", "")),
                    "exclusive_group": clean_text(row.get("택일그룹", "")),
                    "exclusive_group_reason": clean_text(row.get("택일그룹근거", "")),
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
            # Gemini가 판단한 혜택 간 관계를 계산용 relation map으로 변환
            name_to_ids = {}
            for benefit in benefits_to_save:
                name_to_ids.setdefault(benefit["name"], []).append(benefit["id"])

            ai_relation_map = {}
            ai_relation_meta = {}

            for relation in st.session_state.get("gemini_ai_relations_raw", []):
                a_name = clean_text(relation.get("benefit_a_name", ""))
                b_name = clean_text(relation.get("benefit_b_name", ""))
                relation_value = clean_text(relation.get("relation", "unknown"))
                confidence = clean_text(relation.get("confidence", "low"))
                reason = clean_text(relation.get("reason", ""))

                # 같은 이름이 여러 개면 모호하므로 자동 반영하지 않음
                if (
                    a_name in name_to_ids
                    and b_name in name_to_ids
                    and len(name_to_ids[a_name]) == 1
                    and len(name_to_ids[b_name]) == 1
                ):
                    a_id = name_to_ids[a_name][0]
                    b_id = name_to_ids[b_name][0]
                    key = "||".join(sorted([a_id, b_id]))

                    # high/medium만 자동 판단에 활용, low는 사용자 확인 대상으로 남김
                    if confidence in {"high", "medium"} and relation_value in {
                        "possible",
                        "not_possible",
                    }:
                        ai_relation_map[key] = relation_value

                    ai_relation_meta[key] = {
                        "source": "ai",
                        "relation": relation_value,
                        "confidence": confidence,
                        "reason": reason,
                        "a_name": a_name,
                        "b_name": b_name,
                    }

            st.session_state["ai_benefit_relations"] = ai_relation_map
            st.session_state["ai_benefit_relation_meta"] = ai_relation_meta

            # 새 상품/혜택 분석을 저장하면 이전 구매에서 사용자가 답한 관계는 초기화
            # 사용자 자연어로 직접 알려준 혜택 간 관계를 ID 기준으로 변환
            user_relation_map = {}

            for relation in st.session_state.get(
                "pending_user_relation_notes",
                [],
            ):
                a_name = clean_text(
                    relation.get("benefit_a_name", "")
                )
                b_name = clean_text(
                    relation.get("benefit_b_name", "")
                )
                relation_value = clean_text(
                    relation.get("relation", "")
                )

                if (
                    a_name in name_to_ids
                    and b_name in name_to_ids
                    and len(name_to_ids[a_name]) == 1
                    and len(name_to_ids[b_name]) == 1
                    and relation_value in {
                        "possible",
                        "not_possible",
                    }
                ):
                    key = "||".join(
                        sorted([
                            name_to_ids[a_name][0],
                            name_to_ids[b_name][0],
                        ])
                    )
                    user_relation_map[key] = relation_value

            st.session_state["benefit_relations"] = user_relation_map

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
            ai_relation_count = len(
                st.session_state.get("ai_benefit_relations", {})
            )
            if ai_relation_count:
                st.caption(
                    f"AI가 혜택 간 중복·택일 관계 {ai_relation_count}건도 함께 판단해 저장했습니다."
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
