import streamlit as st
from openai import OpenAI
import os
import json
from json import JSONDecodeError
from uuid import uuid4

st.set_page_config(page_title="시각화 마스터", page_icon="📝", layout="centered")

api_key = os.getenv("GPT_API_KEY")
client = OpenAI(api_key=api_key)

CONFIG_PATH = "config.json"

st.markdown(
    """
    <style>
    textarea {
        font-size: 0.8rem !important;
        line-height: 1.3 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------- 기본 세션값 ---------
st.session_state.setdefault("history", [])
st.session_state.setdefault("current_input", "")
st.session_state.setdefault("last_output", "")
st.session_state.setdefault("model_choice", "gpt-4o-mini")

# 지침 set 관련 세션값
st.session_state.setdefault("instruction_sets", [])
st.session_state.setdefault("active_instruction_set_id", None)

# ===== 기본 지침 값 세팅 (한 줄 간단 버전) =====
st.session_state.setdefault(
    "inst_role",
    "너는 한국어 대본을 이미지 시각화용 영어 프롬프트로 변환해 주는 도우미야."
)

st.session_state.setdefault(
    "inst_tone",
    "전체 톤은 차분하고 사실적이며, 과장 없이 담백하게 묘사해줘."
)

st.session_state.setdefault(
    "inst_structure",
    "제목, 간단한 분석, 그리고 문장별로 [한국어 원문] / [영어 이미지 프롬프트] 순서로 정리해줘."
)

st.session_state.setdefault(
    "inst_depth",
    "원문 의미를 벗어나지 않는 범위에서 장면, 분위기, 구도를 조금 더 구체적으로 묘사해줘."
)

st.session_state.setdefault(
    "inst_forbidden",
    "원문 의미를 왜곡하거나 과도한 판타지·초현실적 요소를 추가하면 안 돼."
)

st.session_state.setdefault(
    "inst_format",
    "섹션별로 줄바꿈을 잘 넣어서 사람이 읽기 편한 블록 형식으로 출력해줘."
)

st.session_state.setdefault(
    "inst_user_intent",
    "사용자가 요청한 장르나 스타일이 있다면, 충돌되지 않는 선에서 최대한 반영해줘."
)

# 공통 스타일 래퍼(실제 한 문장, 간단 버전)
st.session_state.setdefault(
    "inst_style_wrapper",
    "Shot on high-resolution digital cinema camera, 16:9 aspect ratio, cinematic realism."
)


def load_config():
    """config.json에서 설정값 로드"""
    if not os.path.exists(CONFIG_PATH):
        return
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except JSONDecodeError:
        return

    # 기존 지침 필드
    if isinstance(data.get("inst_role"), str):
        st.session_state.inst_role = data["inst_role"]
    elif isinstance(data.get("role_instruction"), str):
        st.session_state.inst_role = data["role_instruction"]

    for key in [
        "inst_tone",
        "inst_structure",
        "inst_depth",
        "inst_forbidden",
        "inst_format",
        "inst_user_intent",
        "inst_style_wrapper",
    ]:
        if isinstance(data.get(key), str):
            setattr(st.session_state, key, data[key])

    # history
    hist = data.get("history")
    if isinstance(hist, list):
        st.session_state.history = hist[-5:]

    # 지침 set 관련
    if isinstance(data.get("instruction_sets"), list):
        st.session_state.instruction_sets = data["instruction_sets"]
    if "active_instruction_set_id" in data:
        st.session_state.active_instruction_set_id = data["active_instruction_set_id"]


def save_config():
    """현재 세션값을 config.json으로 저장"""
    data = {
        "inst_role": st.session_state.inst_role,
        "inst_tone": st.session_state.inst_tone,
        "inst_structure": st.session_state.inst_structure,
        "inst_depth": st.session_state.inst_depth,
        "inst_forbidden": st.session_state.inst_forbidden,
        "inst_format": st.session_state.inst_format,
        "inst_user_intent": st.session_state.inst_user_intent,
        "inst_style_wrapper": st.session_state.inst_style_wrapper,
        "history": st.session_state.history[-5:],
        "instruction_sets": st.session_state.get("instruction_sets", []),
        "active_instruction_set_id": st.session_state.get("active_instruction_set_id"),
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def reset_config():
    """config.json 및 세션 전체 초기화"""
    if os.path.exists(CONFIG_PATH):
        os.remove(CONFIG_PATH)

    for key in [
        "inst_role",
        "inst_tone",
        "inst_structure",
        "inst_depth",
        "inst_forbidden",
        "inst_format",
        "inst_user_intent",
        "inst_style_wrapper",
        "history",
        "current_input",
        "last_output",
        "model_choice",
        "instruction_sets",
        "active_instruction_set_id",
    ]:
        if key in st.session_state:
            del st.session_state[key]

    if "config_loaded" in st.session_state:
        del st.session_state["config_loaded"]

    st.rerun()


def apply_instruction_set(set_obj: dict):
    """선택된 지침 set을 현재 지침(inst_*)에 적용"""
    for key in [
        "inst_role",
        "inst_tone",
        "inst_structure",
        "inst_depth",
        "inst_forbidden",
        "inst_format",
        "inst_user_intent",
        "inst_style_wrapper",
    ]:
        if key in set_obj:
            setattr(st.session_state, key, set_obj.get(key, ""))
    save_config()


def ensure_active_set_applied():
    """매 렌더링마다 active set 내용이 inst_*에 반영되도록 보정"""
    sets = st.session_state.get("instruction_sets", [])
    active_id = st.session_state.get("active_instruction_set_id")
    if not sets or not active_id:
        return
    active_set = next((s for s in sets if s.get("id") == active_id), None)
    if active_set:
        for key in [
            "inst_role",
            "inst_tone",
            "inst_structure",
            "inst_depth",
            "inst_forbidden",
            "inst_format",
            "inst_user_intent",
            "inst_style_wrapper",
        ]:
            if key in active_set:
                setattr(st.session_state, key, active_set.get(key, ""))


# --------- config 최초 로드 ---------
if "config_loaded" not in st.session_state:
    load_config()
    st.session_state.config_loaded = True

# 지침 set이 없다면 현재 지침으로 기본 set 생성
if not st.session_state.instruction_sets:
    default_set = {
        "id": "default",
        "name": "기본 지침",
        "inst_role": st.session_state.inst_role,
        "inst_tone": st.session_state.inst_tone,
        "inst_structure": st.session_state.inst_structure,
        "inst_depth": st.session_state.inst_depth,
        "inst_forbidden": st.session_state.inst_forbidden,
        "inst_format": st.session_state.inst_format,
        "inst_user_intent": st.session_state.inst_user_intent,
        "inst_style_wrapper": st.session_state.inst_style_wrapper,
    }
    st.session_state.instruction_sets = [default_set]
    st.session_state.active_instruction_set_id = "default"
    save_config()
else:
    ensure_active_set_applied()

# 메인 영역 폭 넓게 조정 + 인풋 스타일
st.markdown(
    """
    <style>
    .block-container {
        max-width: 900px;
        padding-top: 4.5rem;
    }
    [data-testid="stSidebar"] > div:first-child {
        display: flex;
        flex-direction: column;
        height: 100%;
    }
    .sidebar-top {
        flex-grow: 1;
    }
    .sidebar-bottom {
        margin-top: auto;
        padding-top: 16px;
    }

    div[data-testid="stTextInput"] input[aria-label="주제 입력"] {
        background-color: #f9fafb !important;
        border: 2px solid #4f46e5 !important;
        border-radius: 999px !important;
        padding: 14px 20px !important;
        font-size: 0.95rem !important;
        box-shadow: 0 0 0 1px rgba(79, 70, 229, 0.18);
    }
    div[data-testid="stTextInput"] input[aria-label="주제 입력"]::placeholder {
        color: #9ca3af;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def run_generation():
    topic = st.session_state.current_input.strip()
    if not topic:
        return

    hist = st.session_state.history
    if topic in hist:
        hist.remove(topic)
    hist.append(topic)
    st.session_state.history = hist[-5:]
    save_config()

    system_parts = [
        st.session_state.inst_role,
        st.session_state.inst_tone,
        st.session_state.inst_structure,
        st.session_state.inst_depth,
        st.session_state.inst_forbidden,
        st.session_state.inst_format,
        st.session_state.inst_user_intent,
        f"[공통 스타일 래퍼]\n{st.session_state.inst_style_wrapper}",
    ]
    system_text = "\n\n".join(
        part.strip() for part in system_parts if isinstance(part, str) and part.strip()
    )

    user_text = (
        "위 지침을 모두 따르면서, 아래 한국어 대본을 "
        "스크립트-투-이미지 시각화용 출력 형식으로 변환해줘.\n\n"
        "대본:\n"
        f"{topic}"
    )

    with st.spinner("🎬 대본을 시각화용 프롬프트로 변환하는 중입니다..."):
        res = client.chat.completions.create(
            model=st.session_state.model_choice,
            messages=[
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_text},
            ],
            max_tokens=800,
        )

    st.session_state.last_output = res.choices[0].message.content


# -------- 사이드바 --------
with st.sidebar:
    st.markdown("<div class='sidebar-top'>", unsafe_allow_html=True)

    # ===== 지침 set 섹션 =====
    st.markdown("### 🎛 지침 set")

    inst_sets = st.session_state.instruction_sets
    active_id = st.session_state.active_instruction_set_id
    active_set = None

    if inst_sets:
        names = [s.get("name", f"셋 {i+1}") for i, s in enumerate(inst_sets)]

        active_index = 0
        for i, s in enumerate(inst_sets):
            if s.get("id") == active_id:
                active_index = i
                break

        selected_index = st.radio(
            "지침 set 선택",
            options=list(range(len(inst_sets))),
            format_func=lambda i: names[i],
            index=active_index,
            label_visibility="collapsed",
        )

        selected_set = inst_sets[selected_index]
        active_set = selected_set

        if selected_set.get("id") != active_id:
            st.session_state.active_instruction_set_id = selected_set.get("id")
            apply_instruction_set(selected_set)
            st.rerun()
    else:
        st.info("지침 set이 없습니다.")
        active_set = None

    # ===== 지침 set 관리 (추가 / 편집 / 삭제) =====
    st.markdown("### 🧩 지침 관리")

    action = st.radio(
        "지침 관리",
        ["추가", "편집", "삭제"],
        horizontal=True,
        label_visibility="collapsed",
    )

    # --- 지침 set 추가 ---
    if action == "추가":
        with st.form("add_instruction_set_form_sidebar"):
            set_name = st.text_input("지침 set 이름", placeholder="예: 다큐 시각화 기본셋 / 애니메이션 셋 등")

            role_txt = st.text_area("1. 역할 지침", "", height=80)
            tone_txt = st.text_area("2. 톤 & 스타일 지침", "", height=80)
            style_wrap_txt = st.text_area(
                "공통 스타일 래퍼 (영어 한 문장)",
                "",
                height=60,
                placeholder=(
                    "Shot on high-resolution digital cinema camera, 16:9 aspect ratio, cinematic realism."
                ),
            )
            struct_txt = st.text_area("3. 콘텐츠 구성 지침", "", height=80)
            depth_txt = st.text_area("4. 정보 밀도 & 조사 심도 지침", "", height=80)
            forbid_txt = st.text_area("5. 금지 지침", "", height=80)
            format_txt = st.text_area("6. 출력 형식 지침", "", height=80)
            intent_txt = st.text_area("7. 사용자 요청 반영 지침", "", height=80)

            submitted = st.form_submit_button("💾 새 지침 set 저장")

            if submitted:
                if not set_name.strip():
                    st.error("지침 set 이름을 입력해주세요.")
                else:
                    new_id = str(uuid4())
                    new_set = {
                        "id": new_id,
                        "name": set_name.strip(),
                        "inst_role": role_txt.strip(),
                        "inst_tone": tone_txt.strip(),
                        "inst_style_wrapper": style_wrap_txt.strip(),
                        "inst_structure": struct_txt.strip(),
                        "inst_depth": depth_txt.strip(),
                        "inst_forbidden": forbid_txt.strip(),
                        "inst_format": format_txt.strip(),
                        "inst_user_intent": intent_txt.strip(),
                    }
                    st.session_state.instruction_sets.append(new_set)
                    st.session_state.active_instruction_set_id = new_id

                    apply_instruction_set(new_set)
                    save_config()
                    st.success("✅ 새 지침 set이 저장되었습니다.")
                    st.rerun()

    # --- 지침 set 편집 ---
    elif action == "편집":
        if not active_set:
            st.info("편집할 지침 set이 없습니다.")
        else:
            with st.form("edit_instruction_set_form_sidebar"):
                set_name = st.text_input(
                    "지침 set 이름",
                    value=active_set.get("name", ""),
                )

                role_txt = st.text_area(
                    "1. 역할 지침",
                    value=active_set.get("inst_role", ""),
                    height=80,
                )
                tone_txt = st.text_area(
                    "2. 톤 & 스타일 지침",
                    value=active_set.get("inst_tone", ""),
                    height=80,
                )
                style_wrap_txt = st.text_area(
                    "공통 스타일 래퍼 (영어 한 문장)",
                    value=active_set.get("inst_style_wrapper", ""),
                    height=60,
                )
                struct_txt = st.text_area(
                    "3. 콘텐츠 구성 지침",
                    value=active_set.get("inst_structure", ""),
                    height=80,
                )
                depth_txt = st.text_area(
                    "4. 정보 밀도 & 조사 심도 지침",
                    value=active_set.get("inst_depth", ""),
                    height=80,
                )
                forbid_txt = st.text_area(
                    "5. 금지 지침",
                    value=active_set.get("inst_forbidden", ""),
                    height=80,
                )
                format_txt = st.text_area(
                    "6. 출력 형식 지침",
                    value=active_set.get("inst_format", ""),
                    height=80,
                )
                intent_txt = st.text_area(
                    "7. 사용자 요청 반영 지침",
                    value=active_set.get("inst_user_intent", ""),
                    height=80,
                )

                submitted = st.form_submit_button("💾 현재 지침 set 수정 저장")

                if submitted:
                    active_set["name"] = set_name.strip() or active_set.get("name", "")
                    active_set["inst_role"] = role_txt.strip()
                    active_set["inst_tone"] = tone_txt.strip()
                    active_set["inst_style_wrapper"] = style_wrap_txt.strip()
                    active_set["inst_structure"] = struct_txt.strip()
                    active_set["inst_depth"] = depth_txt.strip()
                    active_set["inst_forbidden"] = forbid_txt.strip()
                    active_set["inst_format"] = format_txt.strip()
                    active_set["inst_user_intent"] = intent_txt.strip()

                    # 리스트에 다시 반영
                    for i, s in enumerate(st.session_state.instruction_sets):
                        if s.get("id") == active_set.get("id"):
                            st.session_state.instruction_sets[i] = active_set
                            break

                    apply_instruction_set(active_set)
                    save_config()
                    st.success("✅ 지침 set이 수정되었습니다.")
                    st.rerun()

    # --- 지침 set 삭제 ---
    elif action == "삭제":
        sets = st.session_state.instruction_sets
        if not sets:
            st.info("삭제할 지침 set이 없습니다.")
        elif len(sets) == 1:
            st.info("마지막 남은 지침 set은 삭제할 수 없습니다.")
        else:
            names = [s.get("name", f"셋 {i+1}") for i, s in enumerate(sets)]
            del_index = st.selectbox(
                "삭제할 지침 set 선택",
                options=list(range(len(sets))),
                format_func=lambda i: names[i],
                label_visibility="collapsed",
                key="delete_instruction_set_select_sidebar",
            )
            if st.button("선택한 지침 set 삭제", use_container_width=True):
                delete_id = sets[del_index].get("id")
                st.session_state.instruction_sets = [
                    s for s in sets if s.get("id") != delete_id
                ]
                # active 처리
                if delete_id == st.session_state.active_instruction_set_id:
                    if st.session_state.instruction_sets:
                        st.session_state.active_instruction_set_id = (
                            st.session_state.instruction_sets[0].get("id")
                        )
                        apply_instruction_set(st.session_state.instruction_sets[0])
                    else:
                        st.session_state.active_instruction_set_id = None
                save_config()
                st.rerun()

    st.markdown("</div><div class='sidebar-bottom'>", unsafe_allow_html=True)

    # ===== 설정 섹션 =====
    st.markdown("### ⚙️ 설정")

    with st.expander("GPT 모델 선택", expanded=False):
        model = st.selectbox(
            "",
            ["gpt-4o-mini", "gpt-4o", "gpt-4.1"],
            index=["gpt-4o-mini", "gpt-4o", "gpt-4.1"].index(
                st.session_state.model_choice
            ),
            label_visibility="collapsed",
        )
        st.session_state.model_choice = model

    # config 초기화
    with st.expander("🧹 설정 초기화 (config.json)", expanded=False):
        st.caption("모든 지침, 최근 입력, config.json 파일을 초기화합니다. 되돌릴 수 없습니다.")
        if st.button("config.json 초기화", use_container_width=True):
            reset_config()

    # config 내보내기 / 불러오기
    with st.expander("💾 config.json 내보내기 / 불러오기", expanded=False):
        st.caption("현재 설정을 파일로 저장하거나, 기존 config.json 파일을 불러올 수 있습니다.")

        export_data = {
            "inst_role": st.session_state.inst_role,
            "inst_tone": st.session_state.inst_tone,
            "inst_structure": st.session_state.inst_structure,
            "inst_depth": st.session_state.inst_depth,
            "inst_forbidden": st.session_state.inst_forbidden,
            "inst_format": st.session_state.inst_format,
            "inst_user_intent": st.session_state.inst_user_intent,
            "inst_style_wrapper": st.session_state.inst_style_wrapper,
            "history": st.session_state.history[-5:],
            "instruction_sets": st.session_state.get("instruction_sets", []),
            "active_instruction_set_id": st.session_state.get("active_instruction_set_id"),
        }
        export_json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
        st.download_button(
            "⬇️ config.json 내보내기",
            data=export_json_str.encode("utf-8"),
            file_name="config.json",
            mime="application/json",
            use_container_width=True,
        )

        st.markdown("---")

        uploaded_file = st.file_uploader(
            "config.json 불러오기", type=["json"], help="이전 백업한 config.json 파일을 업로드하세요."
        )

        if uploaded_file is not None:
            try:
                raw = uploaded_file.read().decode("utf-8")
                new_data = json.loads(raw)
            except Exception:
                st.error("❌ JSON 파일을 읽는 중 오류가 발생했습니다. 올바른 config.json인지 확인해주세요.")
            else:
                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    f.write(raw)

                if "config_loaded" in st.session_state:
                    del st.session_state["config_loaded"]
                load_config()
                ensure_active_set_applied()

                if not st.session_state.instruction_sets:
                    default_set = {
                        "id": "default",
                        "name": "기본 지침",
                        "inst_role": st.session_state.inst_role,
                        "inst_tone": st.session_state.inst_tone,
                        "inst_structure": st.session_state.inst_structure,
                        "inst_depth": st.session_state.inst_depth,
                        "inst_forbidden": st.session_state.inst_forbidden,
                        "inst_format": st.session_state.inst_format,
                        "inst_user_intent": st.session_state.inst_user_intent,
                        "inst_style_wrapper": st.session_state.inst_style_wrapper,
                    }
                    st.session_state.instruction_sets = [default_set]
                    st.session_state.active_instruction_set_id = "default"
                    save_config()

                st.success("✅ config.json이 성공적으로 불러와졌습니다. 설정이 적용됩니다.")
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# -------- 메인 상단: visualking 제목 + separator + 현재 지침 이름 --------
inst_sets = st.session_state.instruction_sets
active_id = st.session_state.active_instruction_set_id
active_set = None
if inst_sets:
    active_set = next((s for s in inst_sets if s.get("id") == active_id), inst_sets[0])
active_set_name = active_set.get("name", "활성 지침 없음") if active_set else "활성 지침 없음"

st.markdown(
    f"""
    <div style="text-align:right; font-size:1.1rem; font-weight:600; margin-bottom:4px;">
        visualking
    </div>
    <hr style="border:none; border-top:1px solid #e5e7eb; margin:4px 0 16px 0;" />
    <div style="text-align:center; font-size:0.95rem; color:#4b5563; margin-bottom:24px;">
        {active_set_name}
    </div>
    """,
    unsafe_allow_html=True,
)

# -------- div2: 최근 입력 --------
if st.session_state.history:
    items = st.session_state.history[-5:]
    html_items = ""
    for h in items:
        html_items += f"""
<div style="
    font-size:0.85rem;
    color:#797979;
    margin-bottom:4px;
">{h}</div>
"""
    st.markdown(
        f"""<div style="
    max-width:460px;
    margin:32px auto 40px auto;
">
  <div style="margin-left:100px; text-align:left;">
    <div style="font-size:0.8rem; color:#9ca3af; margin-bottom:10px;">
      최근
    </div>
    {html_items}
  </div>
</div>""",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """<div style="
    max-width:460px;
    margin:32px auto 40px auto;
">
  <div style="margin-left:100px; font-size:0.8rem; color:#d1d5db; text-align:left;">
    최근 입력이 없습니다.
  </div>
</div>""",
        unsafe_allow_html=True,
    )

# -------- div3: 입력 영역 --------
pad_left, center_col, pad_right = st.columns([1, 7, 1])

with center_col:
    st.markdown(
        "<div style='color:#BDC6D2; font-size:0.9rem; margin-bottom:10px; text-align:center;'>대본을 붙여넣어주세요, 자동으로 시각화해드립니다.</div>",
        unsafe_allow_html=True,
    )

    st.text_input(
        label="주제 입력",
        key="current_input",
        placeholder="여기에 대본 붙여넣기 (엔터 시 변환)",
        label_visibility="collapsed",
        on_change=run_generation,
    )

st.markdown("<div style='height:32px;'></div>", unsafe_allow_html=True)

# -------- 결과 --------
if st.session_state.last_output:
    st.subheader("📄 생성된 스크립트-투-이미지 프롬프트")
    st.write(st.session_state.last_output)
