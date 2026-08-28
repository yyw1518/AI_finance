import streamlit as st


# =========================================================
# 페이지 설정
# =========================================================
st.set_page_config(
    page_title="AI 맞춤형 소비·결제 서비스",
    page_icon="💳",
    layout="wide",
)


# =========================================================
# 페이지 경로
# ⚠️ 실제 pages 폴더의 파일명과 정확히 맞춰주세요.
# =========================================================
PAGE1 = "pages/1_상품_혜택_입력.py"
PAGE2 = "pages/2_최적_결제_추천.py"


# =========================================================
# 심사용 데모 데이터
# =========================================================
def load_demo_data():

    # -----------------------------------------------------
    # 샘플 상품
    # -----------------------------------------------------
    products = [
        {
            "id": "product_0",
            "name": "라운드랩 자작나무 수분 토너",
            "brand": "라운드랩",
            "seller": "올리브영",
            "category": "스킨케어",
            "price": 45000,
            "quantity": 1,
            "total": 45000,
            "price_known": True,
        },

        {
            "id": "product_1",
            "name": "닥터지 레드 블레미쉬 크림",
            "brand": "닥터지",
            "seller": "올리브영",
            "category": "스킨케어",
            "price": 39000,
            "quantity": 1,
            "total": 39000,
            "price_known": True,
        },

        {
            "id": "product_2",
            "name": "롬앤 틴트",
            "brand": "롬앤",
            "seller": "올리브영",
            "category": "메이크업",
            "price": 18000,
            "quantity": 1,
            "total": 18000,
            "price_known": True,
        },
    ]


    # -----------------------------------------------------
    # 샘플 혜택
    # -----------------------------------------------------
    benefits = [

        # ① 라운드랩 브랜드 쿠폰
        {
            "id": "benefit_0",

            "name": "라운드랩 20% 할인쿠폰",
            "issuer": "올리브영",

            "category": "coupon",
            "category_label": "쿠폰",

            "discount_type": "percent",
            "discount_type_label": "정률(%)",

            "value": 20,
            "value_known": True,

            "min_purchase": 30000,
            "min_purchase_known": True,

            "max_discount": 10000,
            "max_discount_known": True,

            "stack_coupon": False,
            "stack_coupon_label": "불가",

            "stack_membership": None,
            "stack_membership_label": "확인 필요",

            "stack_payment": True,
            "stack_payment_label": "가능",

            "channel": "online",
            "channel_label": "온라인",

            "expiry": "2026-12-31",

            "usage_limit": "1회",

            "reuse_type": "single_use",
            "reuse_label": "1회만 사용",

            "min_purchase_basis": "starting_price",
            "min_purchase_basis_label": "결제 시작 금액",

            "required_payment_method": "",

            "scope_type": "brand",
            "scope_targets": ["라운드랩"],
            "scope_confidence": "high",

            "eligible_brands": ["라운드랩"],
            "eligible_items": [],

            "excluded_items": "",

            "exclusive_group": "",
            "exclusive_group_reason": "",

            "conditions": "라운드랩 상품 3만원 이상 구매 시 20% 할인",

            "confidence": "high",
        },


        # ② 닥터지 브랜드 쿠폰
        {
            "id": "benefit_1",

            "name": "닥터지 15% 할인쿠폰",
            "issuer": "올리브영",

            "category": "coupon",
            "category_label": "쿠폰",

            "discount_type": "percent",
            "discount_type_label": "정률(%)",

            "value": 15,
            "value_known": True,

            "min_purchase": 30000,
            "min_purchase_known": True,

            "max_discount": 8000,
            "max_discount_known": True,

            "stack_coupon": False,
            "stack_coupon_label": "불가",

            "stack_membership": None,
            "stack_membership_label": "확인 필요",

            "stack_payment": True,
            "stack_payment_label": "가능",

            "channel": "online",
            "channel_label": "온라인",

            "expiry": "2026-12-31",

            "usage_limit": "1회",

            "reuse_type": "single_use",
            "reuse_label": "1회만 사용",

            "min_purchase_basis": "starting_price",
            "min_purchase_basis_label": "결제 시작 금액",

            "required_payment_method": "",

            "scope_type": "brand",
            "scope_targets": ["닥터지"],
            "scope_confidence": "high",

            "eligible_brands": ["닥터지"],
            "eligible_items": [],

            "excluded_items": "",

            "exclusive_group": "",
            "exclusive_group_reason": "",

            "conditions": "닥터지 상품 3만원 이상 구매 시 15% 할인",

            "confidence": "high",
        },


        # ③ 장바구니 쿠폰
        {
            "id": "benefit_2",

            "name": "7만원 이상 5천원 쿠폰",
            "issuer": "올리브영",

            "category": "coupon",
            "category_label": "쿠폰",

            "discount_type": "fixed",
            "discount_type_label": "정액(원)",

            "value": 5000,
            "value_known": True,

            "min_purchase": 70000,
            "min_purchase_known": True,

            "max_discount": 0,
            "max_discount_known": True,

            "stack_coupon": False,
            "stack_coupon_label": "불가",

            "stack_membership": None,
            "stack_membership_label": "확인 필요",

            "stack_payment": True,
            "stack_payment_label": "가능",

            "channel": "online",
            "channel_label": "온라인",

            "expiry": "2026-12-31",

            "usage_limit": "1회",

            "reuse_type": "single_use",
            "reuse_label": "1회만 사용",

            "min_purchase_basis": "starting_price",
            "min_purchase_basis_label": "결제 시작 금액",

            "required_payment_method": "",

            "scope_type": "cart",
            "scope_targets": [],
            "scope_confidence": "high",

            "eligible_brands": [],
            "eligible_items": [],

            "excluded_items": "",

            "exclusive_group": "",
            "exclusive_group_reason": "",

            "conditions": "7만원 이상 구매 시 5천원 할인",

            "confidence": "high",
        },


        # ④ 간편결제 적립
        {
            "id": "benefit_3",

            "name": "네이버페이 3천P 적립",
            "issuer": "네이버페이",

            "category": "easy_pay",
            "category_label": "간편결제",

            "discount_type": "points",
            "discount_type_label": "포인트/적립",

            "value": 3000,
            "value_known": True,

            "min_purchase": 50000,
            "min_purchase_known": True,

            "max_discount": 0,
            "max_discount_known": True,

            "stack_coupon": True,
            "stack_coupon_label": "가능",

            "stack_membership": None,
            "stack_membership_label": "확인 필요",

            "stack_payment": False,
            "stack_payment_label": "불가",

            "channel": "online",
            "channel_label": "온라인",

            "expiry": "2026-12-31",

            "usage_limit": "1회",

            "reuse_type": "single_use",
            "reuse_label": "1회만 사용",

            "min_purchase_basis": "starting_price",
            "min_purchase_basis_label": "결제 시작 금액",

            "required_payment_method": "네이버페이",

            "scope_type": "cart",
            "scope_targets": [],
            "scope_confidence": "high",

            "eligible_brands": [],
            "eligible_items": [],

            "excluded_items": "",

            "exclusive_group": "",
            "exclusive_group_reason": "",

            "conditions": "5만원 이상 네이버페이 결제 시 3천P 적립",

            "confidence": "high",
        },
    ]


    # -----------------------------------------------------
    # 기존 서비스가 읽는 session_state에 저장
    # -----------------------------------------------------
    st.session_state["products"] = products
    st.session_state["benefits"] = benefits

    st.session_state["store_name"] = "올리브영"

    # 분할결제 비교 활성화
    st.session_state["allow_split_payment"] = True

    # 기존 중복관계 초기화
    st.session_state["benefit_relations"] = {}
    st.session_state["ai_benefit_relations"] = {}
    st.session_state["ai_benefit_relation_meta"] = {}

    # -----------------------------------------------------
    # 심사용 모드 표시
    # -----------------------------------------------------
    st.session_state["demo_mode"] = True


    # -----------------------------------------------------
    # 소비 판단용 샘플 금융정보
    # -----------------------------------------------------
    st.session_state["demo_finance"] = {
        "usable_money": 700000,
        "spent_so_far": 300000,
        "essential_remaining": 200000,
    }


# =========================================================
# 첫 화면
# =========================================================
st.title("💳 AI 맞춤형 소비·결제 서비스")

st.write(
    "복잡한 쿠폰·결제 혜택을 분석하여 최적의 결제 방법을 찾고, "
    "개인의 재정 상황을 바탕으로 현재 소비가 적절한지까지 판단합니다."
)

st.divider()


# =========================================================
# 심사용 데모
# =========================================================
st.subheader("🧪 빠른 기능 체험")

st.write(
    "심사를 위한 샘플 데이터를 준비했습니다. "
    "버튼 한 번으로 최적 결제 추천 기능을 바로 확인할 수 있습니다."
)

if st.button(
    "🚀 심사용 데모 실행",
    type="primary",
    use_container_width=True,
):

    load_demo_data()

    # 바로 2번 페이지로 이동
    st.switch_page(PAGE2)


st.write("")


# =========================================================
# 일반 사용자
# =========================================================
if st.button(
    "📸 직접 상품·혜택 입력하기",
    use_container_width=True,
):

    st.session_state["demo_mode"] = False

    st.switch_page(PAGE1)
