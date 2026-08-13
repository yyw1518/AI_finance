import streamlit as st

st.set_page_config(
    page_title="AI Finance",
    page_icon="💳"
)

st.title("💳 AI Finance")
st.subheader("나에게 가장 유리한 소비를 찾아주는 AI 금융 서비스")

st.write(
    "쿠폰과 결제 혜택을 비교하고, "
    "현재 나의 소비 여력까지 고려해 합리적인 소비 결정을 도와줍니다."
)

price = st.number_input(
    "구매하려는 상품 가격을 입력하세요",
    min_value=0,
    step=1000
)

if st.button("분석하기"):
    st.success(f"상품 가격은 {price:,.0f}원입니다.")
  
