 if discount is None:
                valid = False
                break

            before = current_price
            current_price -= discount

            steps.append({
                "benefit_id": benefit.get("id"),
                "name": benefit.get("name", "혜택"),
                "category": benefit.get("category_label", benefit.get("category", "")),
                "before": round(before),
                "discount": round(discount),
                "after": round(current_price),
            })

        if valid:
            candidate = {
                "final_price": round(current_price),
                "steps": steps,
            }

            if best is None or candidate["final_price"] < best["final_price"]:
                best = candidate

    return best


# =========================================================
# 한 결제 그룹에서 가능한 혜택 조합 계산
# =========================================================
benefit_count = len(benefits)


def calculate_group_plans(group_indices):
    starting_price = group_subtotal(group_indices)

    plans = []

    # 모든 혜택 subset 비교
    for mask in range(1 << benefit_count):
        selected_indices = [
            i for i in range(benefit_count)
            if mask & (1 << i)
        ]

        selected = [benefits[i] for i in selected_indices]

        # 혜택끼리 중복 여부
        compatibility = subset_compatibility(selected)

        if compatibility == "invalid":
            continue

        status = compatibility

        # 개별 혜택 조건
        skip = False
        for benefit in selected:
            b_status = individual_benefit_status(benefit)

            if b_status == "invalid":
                skip = True
                break

            if b_status == "uncertain":
                status = "uncertain"

        if skip:
            continue

        applied = apply_benefit_subset(starting_price, selected)

        # 선택한 혜택이 최소금액 등을 충족하지 못하면 제외
        if applied is None:
            continue

        plans.append({
            "mask": mask,
            "status": status,
            "starting_price": round(starting_price),
            "final_price": applied["final_price"],
            "savings": round(starting_price - applied["final_price"]),
            "steps": applied["steps"],
            "benefit_names": [b.get("name", "혜택") for b in selected],
        })

    # 같은 mask/status라면 최저가 하나만 유지
    best_by_key = {}

    for plan in plans:
        key = (plan["mask"], plan["status"])
        old = best_by_key.get(key)

        if old is None or plan["final_price"] < old["final_price"]:
            best_by_key[key] = plan

    return list(best_by_key.values())


# =========================================================
# 한 분할안에서 각 결제 그룹에 혜택을 중복 사용하지 않도록 최적화
# =========================================================
group_plan_cache = {}


def get_group_plans(group_key):
    group_key = tuple(sorted(group_key))

    if group_key not in group_plan_cache:
        group_plan_cache[group_key] = calculate_group_plans(group_key)

    return group_plan_cache[group_key]


def keep_top_k(options, k=3):
    unique = {}
    for option in sorted(options, key=lambda x: x["total_price"]):
        signature = tuple(
            (
                tuple(choice["group"]),
                choice["plan"]["mask"],
                choice["plan"]["final_price"],
            )
            for choice in option["choices"]
        )

        if signature not in unique:
            unique[signature] = option

        if len(unique) >= k:
            break

    return list(unique.values())


def best_k_for_partition(partition, allow_uncertain=False, k=3):
    # used benefit mask -> 상위 k개
    states = {
        0: [{
            "total_price": 0,
            "choices": [],
            "uncertain_count": 0,
        }]
    }

    for group in partition:
        group = tuple(sorted(group))
        group_plans = get_group_plans(group)

        if allow_uncertain:
            available_plans = [
                p for p in group_plans
                if p["status"] in {"confirmed", "uncertain"}
            ]
        else:
            available_plans = [
                p for p in group_plans
                if p["status"] == "confirmed"
            ]

        new_states = {}

        for used_mask, state_options in states.items():
            for state in state_options:
                for plan in available_plans:
                    # 하나의 혜택을 여러 결제 건에서 재사용하지 않음
                    if used_mask & plan["mask"]:
                        continue

                    new_mask = used_mask | plan["mask"]

                    candidate = {
                        "total_price": state["total_price"] + plan["final_price"],
                        "choices": state["choices"] + [{
                            "group": group,
                            "plan": plan,
                        }],
                        "uncertain_count": (
                            state["uncertain_count"]
                            + (1 if plan["status"] == "uncertain" else 0)
                        ),
                    }

                    bucket = new_states.setdefault(new_mask, [])
                    bucket.append(candidate)
                    new_states[new_mask] = keep_top_k(bucket, k)

        states = new_states

    all_options = []

    for state_options in states.values():
        all_options.extend(state_options)

    return keep_top_k(all_options, k)


# =========================================================
# 전체 탐색
# =========================================================
total_original_price = round(
    sum(product_line_total(p) for p in products)
)

partitions = generate_partitions()

if allow_split_payment and len(products) > MAX_EXHAUSTIVE_PRODUCTS:
    st.warning(
        f"상품 종류가 {MAX_EXHAUSTIVE_PRODUCTS}개를 초과해 계산량을 줄이기 위해 "
        "**전체 결제 / 전부 개별 결제 / 한 상품만 분리** 패턴을 비교합니다."
    )

with st.spinner("가능한 결제 조합과 분할 결제를 비교하고 있습니다..."):
    confirmed_candidates = []
    uncertain_candidates = []

    for partition in partitions:
        confirmed = best_k_for_partition(
            partition,
            allow_uncertain=False,
            k=3,
        )

        for option in confirmed:
            option["partition"] = partition
            confirmed_candidates.append(option)

        mixed = best_k_for_partition(
            partition,
            allow_uncertain=True,
            k=3,
        )

        for option in mixed:
            if option["uncertain_count"] > 0:
                option["partition"] = partition
                uncertain_candidates.append(option)


def plan_signature(option):
    return tuple(
        (
            tuple(choice["group"]),
            choice["plan"]["mask"],
        )
        for choice in option["choices"]
    )


def global_top_k(candidates, k=3):
    seen = set()
    results = []

    for option in sorted(candidates, key=lambda x: x["total_price"]):
        sig = plan_signature(option)

        if sig in seen:
            continue

        seen.add(sig)
        results.append(option)

        if len(results) >= k:
            break

    return results


top_confirmed = global_top_k(confirmed_candidates, 3)
top_uncertain = global_top_k(uncertain_candidates, 3)


# =========================================================
# 결과 표시 함수
# =========================================================
def payment_style_text(option):
    payment_count = len(option["choices"])

    if payment_count == 1:
        return "한 번에 결제"

    return f"{payment_count}회 분할 결제"


def display_plan(option, rank, uncertain=False):
    final_price = round(option["total_price"])
    total_saving = total_original_price - final_price

    title = (
        f"{'⚠️' if uncertain else '🏆'} "
        f"{rank}위 — {payment_style_text(option)} "
        f"→ **{money(final_price)}**"
    )

    with st.expander(title, expanded=(rank == 1 and not uncertain)):
        metric1, metric2, metric3 = st.columns(3)

        with metric1:
            st.metric("상품 총액", money(total_original_price))

        with metric2:
            st.metric("예상 최종 결제금액", money(final_price))

        with metric3:
            st.metric("예상 절약", money(total_saving))

        if uncertain:
            st.warning(
                "이 방안에는 **중복 여부·제외대상·기타조건 등 확인이 필요한 혜택**이 포함되어 있습니다. "
                "실제 결제 전 조건을 확인해주세요."
            )

        st.markdown("#### 실제 결제 순서")

        for payment_no, choice in enumerate(option["choices"], start=1):
            group = choice["group"]
            plan = choice["plan"]

            names = group_product_names(group)

            st.markdown(
                f"**결제 {payment_no}. "
                f"{' + '.join(names)}** "
                f"({money(plan['starting_price'])})"
            )

            if not plan["steps"]:
                st.write("→ 적용 혜택 없음")

            else:
                for step_no, step in enumerate(plan["steps"], start=1):
                    st.write(
                        f"{step_no}) **{step['name']}** 적용 "
                        f": {money(step['before'])} → "
                        f"-{money(step['discount'])} → "
                        f"**{money(step['after'])}**"
                    )

            st.write(
                f"→ 이 결제 건 최종금액: **{money(plan['final_price'])}**"
            )

        st.markdown("#### 사용 혜택")

        used_names = []

        for choice in option["choices"]:
            for name in choice["plan"]["benefit_names"]:
                if name not in used_names:
                    used_names.append(name)
