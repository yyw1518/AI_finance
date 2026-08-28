import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from urllib import request, parse, error

import streamlit as st


# =========================================================
# 기본 설정
# =========================================================
st.set_page_config(
    page_title="소비 판단",
    page_icon="💰",
    layout="wide",
)

CURRENT_MONTH = datetime.now().strftime("%Y-%m")
CURRENT_MONTH_LABEL = datetime.now().strftime("%Y년 %m월")

optimized_price = int(
    st.session_state.get(
        "optimized_final_price",
        st.session_state.get("final_payment", 0),
    )
    or 0
)
original_price = int(st.session_state.get("original_total_price", 0) or 0)
total_benefit = int(st.session_state.get("optimized_total_benefit", 0) or 0)


def money(value):
    return f"{int(round(value)):,}원"


def parse_money_input(value):
    text = str(value).replace(",", "").replace("원", "").strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 0


# =========================================================
# 익명 사용자 키
# - 로그인 없는 MVP에서도 사용자별 월 데이터를 분리하기 위한 키
# - URL query parameter에 유지되므로 새로고침 후에도 같은 사용자를 식별 가능
# =========================================================
def get_user_key():
    try:
        params = st.query_params
        existing = params.get("u")
    except Exception:
        existing = None

    if isinstance(existing, list):
        existing = existing[0] if existing else None

    if existing:
        return str(existing)

    new_key = uuid.uuid4().hex[:20]

    try:
        st.query_params["u"] = new_key
    except Exception:
        pass

    return new_key


USER_KEY = get_user_key()


# =========================================================
# 저장소
# 1순위: Supabase
# 2순위: 로컬 JSON (개발/해커톤 데모용)
#
# Supabase 사용 시 Streamlit secrets 예시:
# [supabase]
# url = "https://xxxx.supabase.co"
# key = "YOUR_ANON_KEY"
#
# 필요한 테이블:
# monthly_finance
# - user_key text
# - year_month text
# - usable_money bigint
# - spent_so_far bigint
# - essential_remaining bigint
# - updated_at timestamptz
# UNIQUE(user_key, year_month)
# =========================================================
LOCAL_DATA_PATH = Path("data/monthly_finance.json")


def get_supabase_config():
    try:
        cfg = st.secrets.get("supabase", {})
        url = str(cfg.get("url", "")).rstrip("/")
        key = str(cfg.get("key", ""))
        if url and key:
            return url, key
    except Exception:
        pass

    return None, None


def supabase_request(method, endpoint, payload=None, extra_headers=None):
    url, key = get_supabase_config()

    if not url or not key:
        raise RuntimeError("Supabase not configured")

    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    if extra_headers:
        headers.update(extra_headers)

    req = request.Request(
        f"{url}/rest/v1/{endpoint}",
        data=body,
        headers=headers,
        method=method,
    )

    with request.urlopen(req, timeout=8) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else None


def load_from_supabase():
    query = (
        "monthly_finance"
        f"?user_key=eq.{parse.quote(USER_KEY)}"
        f"&year_month=eq.{parse.quote(CURRENT_MONTH)}"
        "&select=usable_money,spent_so_far,essential_remaining"
        "&limit=1"
    )

    rows = supabase_request("GET", query)

    if rows:
        return rows[0]

    return None


def save_to_supabase(data):
    payload = {
        "user_key": USER_KEY,
        "year_month": CURRENT_MONTH,
        "usable_money": int(data["usable_money"]),
        "spent_so_far": int(data["spent_so_far"]),
        "essential_remaining": int(data["essential_remaining"]),
        "updated_at": datetime.now().isoformat(),
    }

    supabase_request(
        "POST",
        "monthly_finance?on_conflict=user_key,year_month",
        payload=[payload],
        extra_headers={
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )


def read_local_store():
    if not LOCAL_DATA_PATH.exists():
        return {}

    try:
        return json.loads(LOCAL_DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_local_store(store):
    LOCAL_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    temp_path = LOCAL_DATA_PATH.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(store, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(LOCAL_DATA_PATH)


def load_from_local():
    store = read_local_store()
    return (
        store
        .get(USER_KEY, {})
        .get(CURRENT_MONTH)
    )


def save_to_local(data):
    store = read_local_store()
    store.setdefault(USER_KEY, {})
    store[USER_KEY][CURRENT_MONTH] = {
        "usable_money": int(data["usable_money"]),
        "spent_so_far": int(data["spent_so_far"]),
        "essential_remaining": int(data["essential_remaining"]),
        "updated_at": datetime.now().isoformat(),
    }
    write_local_store(store)


def load_monthly_data():
    supabase_url, supabase_key = get_supabase_config()

    if supabase_url and supabase_key:
        try:
            data = load_from_supabase()
            return data, "supabase"
        except Exception:
            # 외부 저장소 일시 오류가 나도 페이지 자체는 사용할 수 있게
            pass

    return load_from_local(), "local"


def save_monthly_data(data):
    supabase_url, supabase_key = get_supabase_config()

    if supabase_url and supabase_key:
        try:
            save_to_supabase(data)
            return "supabase"
        except Exception:
            # 저장 실패 시 로컬에도 한 번 저장
            save_to_local(data)
            return "local"

    save_to_local(data)
    return "local"


# =========================================================
# 이번 달 저장 데이터 불러오기
# =========================================================
month_data, storage_mode = load_monthly_data()
month_data = month_data or {}

default_usable = int(month_data.get("usable_money", 0) or 0)
default_spent = int(month_data.get("spent_so_far", 0) or 0)
default_essential = int(month_data.get("essential_remaining", 0) or 0)


# =========================================================
# 심사용 데모 금융정보 자동 입력
# =========================================================
if st.session_state.get("demo_mode", False):

    demo_finance = st.session_state.get(
        "demo_finance",
        {}
    )

    default_usable = int(
        demo_finance.get(
            "usable_money",
            700000
        )
    )

    default_spent = int(
        demo_finance.get(
            "spent_so_far",
            300000
        )
    )

    default_essential = int(
        demo_finance.get(
            "essential_remaining",
            200000
        )
    )

# =========================================================
# 화면
# =========================================================
st.title("💰 이 소비, 지금 해도 괜찮을까?")

if optimized_price > 0:
    st.write(
        f"앞에서 찾은 **최적 결제금액 {money(optimized_price)}**을 기준으로 "
        "이번 달 자금에 얼마나 여유가 남는지 확인합니다."
    )
else:
    st.warning(
        "앞 페이지에서 최적 결제금액을 찾은 뒤 이용하면 더 정확하게 판단할 수 있습니다."
    )

st.info(
    f"📅 **{CURRENT_MONTH_LABEL} 금융 정보**를 한 번 입력하면 "
    "이번 달에는 다시 입력하지 않아도 됩니다."
)

if month_data:
    st.caption("💾 이번 달에 저장한 값을 불러왔습니다.")


# =========================================================
# 1. 최적 결제 요약
# =========================================================
if optimized_price > 0:
    st.subheader("1️⃣ 앞에서 찾은 최적 결제")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "상품 총액",
            money(original_price if original_price > 0 else optimized_price),
        )

    with col2:
        st.metric(
            "최적 결제금액",
            money(optimized_price),
        )

    with col3:
        st.metric(
            "혜택으로 절약",
            money(
                total_benefit
                if total_benefit > 0
                else max(0, original_price - optimized_price)
            ),
        )

    st.divider()


# =========================================================
# 2. 이번 달 금융 상황 — 딱 3개만
# =========================================================
st.subheader("2️⃣ 이번 달 금융 상황")
st.caption("이번 달 기준으로 아래 세 가지만 입력해주세요.")

c1, c2 = st.columns(2)

with c1:
    usable_money_text = st.text_input(
        "이번 달 쓸 수 있는 돈",
        value=f"{default_usable:,}",
        help="월급·용돈·생활비 등 이번 달에 실제로 사용할 수 있는 총 금액입니다.",
        placeholder="예: 1,000,000",
    )
    usable_money = parse_money_input(usable_money_text)
    st.caption(f"입력 금액: **{money(usable_money)}**")

    spent_so_far_text = st.text_input(
        "지금까지 쓴 돈",
        value=f"{default_spent:,}",
        help="이번 달 시작일부터 지금까지 이미 사용한 금액입니다.",
        placeholder="예: 400,000",
    )
    spent_so_far = parse_money_input(spent_so_far_text)
    st.caption(f"입력 금액: **{money(spent_so_far)}**")

with c2:
    essential_remaining_text = st.text_input(
        "앞으로 꼭 나갈 돈",
        value=f"{default_essential:,}",
        help="이번 달 남은 기간에 반드시 지출해야 하는 교통비·통신비·월세·식비 등의 금액입니다.",
        placeholder="예: 200,000",
    )
    essential_remaining = parse_money_input(essential_remaining_text)
    st.caption(f"입력 금액: **{money(essential_remaining)}**")

    # 입력과 동시에 사용자가 현재 상태를 이해할 수 있도록 간단한 미리보기
    disposable_before = (
        usable_money
        - spent_so_far
        - essential_remaining
    )

    st.metric(
        "현재 자유롭게 쓸 수 있는 돈",
        money(max(disposable_before, 0)),
        delta=(
            None
            if disposable_before >= 0
            else f"{money(abs(disposable_before))} 부족"
        ),
        delta_color="inverse",
    )


# =========================================================
# 분석 + 월별 저장
# =========================================================
st.write("")

if st.session_state.get("demo_mode", False):

    st.info(
        "🧪 심사용 샘플 금융정보를 기준으로 "
        "소비 판단 결과를 자동 계산합니다."
    )

    analyze = True

else:

    analyze = st.button(
        "✨ 저장하고 이 소비 분석하기",
        type="primary",
        use_container_width=True,
    )


if analyze:
    data = {
        "usable_money": usable_money,
        "spent_so_far": spent_so_far,
        "essential_remaining": essential_remaining,
    }

    # 데모 모드에서는 샘플 금융정보를 실제 저장소에 저장하지 않음
    if st.session_state.get("demo_mode", False):
        save_mode = "demo"
    else:
        save_mode = save_monthly_data(data)

    # 같은 세션에서도 즉시 재사용
    st.session_state["monthly_finance"] = {
        "year_month": CURRENT_MONTH,
        **data,
    }

    st.divider()
    st.subheader("3️⃣ 소비 판단")

    available_before = (
        usable_money
        - spent_so_far
        - essential_remaining
    )

    available_after = available_before - optimized_price

    if usable_money <= 0:
        st.warning(
            "이번 달 쓸 수 있는 돈을 입력하면 소비 가능 여부를 판단할 수 있습니다."
        )

    elif spent_so_far + essential_remaining > usable_money:
        shortage = (
            spent_so_far
            + essential_remaining
            - usable_money
        )

        st.error(
            "🔴 지금은 추가 소비보다 필수 지출을 먼저 확보하는 편이 좋습니다."
        )

        st.write(
            f"현재 입력 기준으로 이미 쓴 돈과 앞으로 꼭 나갈 돈이 "
            f"이번 달 가용금액을 **{money(shortage)} 초과**합니다."
        )

    elif optimized_price <= 0:
        st.warning(
            "최적 결제금액이 없어 현재 구매에 대한 판단을 계산할 수 없습니다."
        )

    elif available_after < 0:
        shortage = abs(available_after)

        st.error(
            "🔴 이 구매를 하면 이번 달 예정된 필수 지출까지 감당하기 어렵습니다."
        )

        a, b, c = st.columns(3)

        a.metric(
            "구매 전 자유자금",
            money(available_before)
        )

        b.metric(
            "이번 구매",
            money(optimized_price)
        )

        c.metric(
            "부족 금액",
            money(shortage)
        )

    else:
        use_ratio = (
            optimized_price / available_before * 100
            if available_before > 0
            else 0
        )

        st.success(
            "🟢 현재 입력한 이번 달 계획 안에서는 결제 가능한 소비입니다."
        )

        a, b, c = st.columns(3)

        a.metric(
            "구매 전 자유자금",
            money(available_before),
        )

        b.metric(
            "이번 구매",
            money(optimized_price),
        )

        c.metric(
            "구매 후 남는 돈",
            money(available_after),
        )

        st.progress(
            min(max(use_ratio / 100, 0.0), 1.0)
        )

        st.caption(
            f"이번 구매는 현재 자유자금의 **{use_ratio:.1f}%**를 사용합니다."
        )

        if total_benefit > 0:
            st.write(
                f"최적 결제를 사용하면 정가 기준보다 **{money(total_benefit)}**의 "
                "혜택을 확보하면서 구매할 수 있습니다."
            )

    # 저장 안내
    if save_mode == "demo":

        st.caption(
            "🧪 현재 결과는 심사용 샘플 금융정보를 이용한 결과입니다."
        )

    elif save_mode == "supabase":

        st.caption(
            f"💾 {CURRENT_MONTH_LABEL} 입력값이 저장되었습니다. "
            "이번 달에 다시 방문하면 자동으로 불러옵니다."
        )

    else:

        st.caption(
            f"💾 {CURRENT_MONTH_LABEL} 입력값을 저장했습니다. "
            "현재 MVP 환경에서는 앱 서버가 재배포되면 "
            "로컬 저장값이 초기화될 수 있습니다."
        )

    # 4번 페이지에서 그대로 사용
    st.session_state["finance_available_before_purchase"] = available_before
    st.session_state["finance_available_after_purchase"] = available_after
    st.session_state["finance_purchase_price"] = optimized_price
