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
# 데모 표시 설정
# True  = 샘플 이미지 데모 표시
# False = 데모 숨김
# =========================================================
SHOW_DEMO = True

st.session_state["show_demo"] = SHOW_DEMO


# 데모를 OFF하면 이전 데모 상태도 초기화
if not SHOW_DEMO:
    st.session_state["demo_mode"] = False
    st.session_state["demo_image_mode"] = False
    st.session_state.pop("auto_run_demo_analysis", None)
    st.session_state.pop("demo_finance", None)


if SHOW_DEMO:

    st.subheader("🧪 빠른 기능 체험")

    st.write(
        "샘플 장바구니·쿠폰·결제혜택 이미지를 이용해 "
        "Gemini 분석부터 최적 결제 추천까지 직접 확인할 수 있습니다."
    )

    if st.button(
        "🚀 샘플 이미지로 전체 기능 체험",
        type="primary",
        use_container_width=True,
    ):

        # 데모 모드 시작
        st.session_state["demo_mode"] = True
        st.session_state["demo_image_mode"] = True

        # 1번 페이지에 들어가자마자 Gemini 자동 분석
        st.session_state["auto_run_demo_analysis"] = True

        # 3번 소비 판단용 샘플 금융정보
        st.session_state["demo_finance"] = {
            "usable_money": 700000,
            "spent_so_far": 300000,
            "essential_remaining": 200000,
        }

        # 1번 상품·혜택 분석 페이지로 이동
        st.switch_page(
            "pages/1_상품_혜택_입력.py"
        )


if st.button(
    "📸 직접 상품·혜택 입력하기",
    use_container_width=True,
):

    st.session_state["demo_mode"] = False
    st.session_state["demo_image_mode"] = False

    st.session_state.pop(
        "auto_run_demo_analysis",
        None,
    )

    st.session_state.pop(
        "demo_finance",
        None,
    )

    st.switch_page(
        "pages/1_상품_혜택_입력.py"
    )
