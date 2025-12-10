import streamlit as st
from openai import OpenAI
import os
import json
from json import JSONDecodeError
from uuid import uuid4

# ------------------------------------------------------------
# 기본 설정
# ------------------------------------------------------------

st.set_page_config(page_title="시각화 마스터", page_icon="📝", layout="centered")

api_key = os.getenv("GPT_API_KEY")
client = OpenAI(api_key=api_key)

CONFIG_PATH = "config.json"

# ------------------------------------------------------------
# 기본 스타일
# ------------------------------------------------------------

st.markdown(
    """
    <style>
    textarea {
        font-size: 0.8rem !important;
        line-height: 1.3 !important;
    }
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

# ------------------------------------------------------------
# 기본 세션값 설정
# ------------------------------------------------------------

st.session_state.setdefault("history", [])
st.session_state.setdefault("current_input", "")
st.session_state.setdefault("last_output", "")
st.session_state.setdefault("model_choice", "gpt-4o-mini")

# 지침 관련
st.session_state.setdefault("instruction_sets", [])
st.session_state.setdefault("active_instruction_set_id", None)
st.session_state.setdefault("show_instruction_editor", False)
st.session_state.setdefault("edit_mode", False)  # True = 수정, False = 추가

# ------------------------------------------------------------
# 기본 지침 세팅 (최초 실행 시)
# ------------------------------------------------------------

DEFAULT_INST = {
    "inst_role": """너의 역할은 한국어 대본을 사실적 이미지 생성용 영어 프롬프트로 변환하는 전문가다.""",
    "inst_tone": """톤은 중립적이며, 묘사는 사실 기반으로만 확장한다.""",
    "inst_style_wrapper": """Shot on high-resolution digital cinema camera, 16:9 aspect ratio, realistic lighting.""",
    "inst_structure": """스크립트-투-이미지 출력은 제목 → 분석 → 스타일 래퍼 → 문장별 변환 순서로 구성한다.""",
    "inst_depth": """원문의 의미를 벗어나지 않는 선에서 구체적 시각 요소를 추가한다.""",
    "inst_forbidden": """망상적·판타지적 묘사 금지, 원문 왜곡 금지, 스타일 래퍼 누락 금지.""",
    "inst_format": """최종 출력은 한국어 원문 + 스타일 래퍼로 시작하는 영어 프롬프트의 2줄 세트 구조를 유지한다.""",
    "inst_user_intent": """사용자가 입력한 원문 의미를 훼손하지 않는 범위에서 시각화한다."""
}

for key, val in DEFAULT_INST.items():
    st.session_state.setdefault(key, val)

# ------------------------------------------------------------
# config.json 로드 / 저장 / 초기화
# ------------------------------------------------------------

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except JSONDecodeError:
        return

    # inst_* 값 로드
    for key in DEFAULT_INST.keys():
        if key in data:
            st.session_state[key] = data[key]

    # history
    hist = data.get("history")
    if isinstance(hist, list):
        st.session_state.history = hist[-5:]

    # 지침 set
    if isinstance(data.get("instruction_sets"), list):
        st.session_state.instruction_sets = data["instruction_sets"]
    if "active_instruction_set_id" in data:
        st.session_state.active_instruction_set_id = data["active_instruction_set_id"]


def save_config():
    data = {key: st.session_state[key] for key in DEFAULT_INST.keys()}
    data["history"] = st.session_state.history[-5:]
    data["instruction_sets"] = st.session_state.get("instruction_sets", [])
    data["active_instruction_set_id"] = st.session_state.get("active_instruction_set_id")

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def reset_config():
    if os.path.exists(CONFIG_PATH):
        os.remove(CONFIG_PATH)

    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.rerun()


# ------------------------------------------------------------
# config 최초 로드
# ------------------------------------------------------------

if "config_loaded" not in st.session_state:
    load_config()
    st.session_state.config_loaded = True

# ------------------------------------------------------------
# 기본 지침 set 생성
# ------------------------------------------------------------

if not st.session_state.instruction_sets:
    default_set = {
        "id": "default",
        "name": "기본 지침",
        **{key: st.session_state[key] for key in DEFAULT_INST.keys()}
    }
    st.session_state.instruction_sets = [default_set]
    st.session_state.active_instruction_set_id = "default"
    save_config()

# ------------------------------------------------------------
# 사이드바: 지침 set 선택 + 추가/편집/삭제
# ------------------------------------------------------------

with st.sidebar:
    st.markdown("<div class='sidebar-top'>", unsafe_allow_html=True)

    st.markdown("### 🎛 지침 set")

    inst_sets = st.session_state.instruction_sets
    active_id = st.session_state.active_instruction_set_id

    # -------------------------------
    # 1) 지침 set 선택 radio
    # -------------------------------
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
            key="select_instruction_set",
            label_visibility="collapsed",
        )

        selected_set = inst_sets[selected_index]

        # 선택 변경 시 active 변경
        if selected_set.get("id") != active_id:
            st.session_state.active_instruction_set_id = selected_set.get("id")

            # inst_* 값도 즉시 반영
            for k in DEFAULT_INST.keys():
                if k in selected_set:
                    st.session_state[k] = selected_set[k]

            save_config()
            st.rerun()

    # -------------------------------
    # 2) 지침 버튼 3개 (추가/편집/삭제)
    # -------------------------------
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("➕ 추가"):
            st.session_state.show_instruction_editor = True
            st.session_state.edit_mode = False  # 추가 모드
            st.rerun()

    with col2:
        if st.button("✏️ 편집"):
            st.session_state.show_instruction_editor = True
            st.session_state.edit_mode = True  # 편집 모드
            st.rerun()

    with col3:
        if st.button("🗑 삭제"):
            if active_id:
                new_list = [s for s in inst_sets if s.get("id") != active_id]
                st.session_state.instruction_sets = new_list

                # 삭제 후 active 재설정
                if new_list:
                    st.session_state.active_instruction_set_id = new_list[0]["id"]

                    # inst_* 값 적용
                    for k in DEFAULT_INST.keys():
                        if k in new_list[0]:
                            st.session_state[k] = new_list[0][k]
                else:
                    st.session_state.active_instruction_set_id = None

                save_config()
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # ------------------------------------------------------------
    # 설정 관련 영역
    # ------------------------------------------------------------

    st.markdown("<div class='sidebar-bottom'>", unsafe_allow_html=True)
    st.markdown("### ⚙️ 설정")

    # GPT 모델 선택
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

    # config 내보내기/불러오기
    with st.expander("💾 config.json 내보내기 / 불러오기", expanded=False):

        export_data = {
            **{key: st.session_state[key] for key in DEFAULT_INST.keys()},
            "history": st.session_state.history[-5:],
            "instruction_sets": st.session_state.get("instruction_sets", []),
            "active_instruction_set_id": st.session_state.get("active_instruction_set_id"),
        }

        export_json = json.dumps(export_data, ensure_ascii=False, indent=2)
        st.download_button(
            "⬇️ config.json 내보내기",
            data=export_json.encode("utf-8"),
            file_name="config.json",
            mime="application/json",
            use_container_width=True,
        )

        st.markdown("---")

        uploaded = st.file_uploader("config.json 불러오기", type=["json"])
        if uploaded:
            try:
                raw = uploaded.read().decode("utf-8")
                new_data = json.loads(raw)
            except Exception:
                st.error("JSON 파일 오류. 올바른 config.json인지 확인해주세요.")
            else:
                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    f.write(raw)

                if "config_loaded" in st.session_state:
                    del st.session_state["config_loaded"]
                load_config()

                st.success("config.json 불러오기 완료!")
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ------------------------------------------------------------
# 메인 화면에서 지침 set 추가 / 편집 에디터
# ------------------------------------------------------------

if st.session_state.show_instruction_editor:

    mode = "지침 set 수정" if st.session_state.edit_mode else "새 지침 set 추가"
    st.markdown(f"## ✨ {mode}")

    # 편집 모드면 active set 데이터 불러오기
    if st.session_state.edit_mode and st.session_state.active_instruction_set_id:
        active_set = next(
            (s for s in st.session_state.instruction_sets
             if s["id"] == st.session_state.active_instruction_set_id),
            None
        )
    else:
        active_set = None

    # 입력 값 준비
    def v(key):
        if active_set:
            return active_set.get(key, "")
        return ""

    with st.form("instruction_editor_form"):

        name = st.text_input("지침 set 이름", value=v("name") if active_set else "")

        role = st.text_area("1. 역할 지침", value=v("inst_role"), height=80)
        tone = st.text_area("2. 톤 & 스타일 지침", value=v("inst_tone"), height=80)
        style = st.text_area("공통 스타일 래퍼 (영어 한 문장)", value=v("inst_style_wrapper"), height=60)
        struct = st.text_area("3. 콘텐츠 구성 지침", value=v("inst_structure"), height=80)
        depth = st.text_area("4. 정보 밀도 & 조사 심도 지침", value=v("inst_depth"), height=80)
        forbid = st.text_area("5. 금지 지침", value=v("inst_forbidden"), height=80)
        fmt = st.text_area("6. 출력 형식 지침", value=v("inst_format"), height=80)
        intent = st.text_area("7. 사용자 요청 반영 지침", value=v("inst_user_intent"), height=80)

        colA, colB = st.columns(2)
        with colA:
            submitted = st.form_submit_button("💾 저장")
        with colB:
            cancelled = st.form_submit_button("취소")

        if cancelled:
            st.session_state.show_instruction_editor = False
            st.rerun()

        if submitted:
            if not name.strip():
                st.error("지침 set 이름을 입력해주세요.")
            else:
                if st.session_state.edit_mode:
                    # -------------------------
                    # 편집 모드 → 기존 set 업데이트
                    # -------------------------
                    for s in st.session_state.instruction_sets:
                        if s["id"] == active_set["id"]:
                            s["name"] = name.strip()
                            s["inst_role"] = role.strip()
                            s["inst_tone"] = tone.strip()
                            s["inst_style_wrapper"] = style.strip()
                            s["inst_structure"] = struct.strip()
                            s["inst_depth"] = depth.strip()
                            s["inst_forbidden"] = forbid.strip()
                            s["inst_format"] = fmt.strip()
                            s["inst_user_intent"] = intent.strip()
                            break

                    # inst_* 즉시 반영
                    for k in DEFAULT_INST.keys():
                        st.session_state[k] = active_set[k]

                else:
                    # -------------------------
                    # 추가 모드 → 새로운 set 생성
                    # -------------------------
                    new_id = str(uuid4())
                    new_set = {
                        "id": new_id,
                        "name": name.strip(),
                        "inst_role": role.strip(),
                        "inst_tone": tone.strip(),
                        "inst_style_wrapper": style.strip(),
                        "inst_structure": struct.strip(),
                        "inst_depth": depth.strip(),
                        "inst_forbidden": forbid.strip(),
                        "inst_format": fmt.strip(),
                        "inst_user_intent": intent.strip(),
                    }

                    st.session_state.instruction_sets.append(new_set)
                    st.session_state.active_instruction_set_id = new_id

                    # inst_* 값도 즉시 반영
                    for k in DEFAULT_INST.keys():
                        st.session_state[k] = new_set.get(k, st.session_state[k])

                save_config()
                st.session_state.show_instruction_editor = False
                st.rerun()


# ------------------------------------------------------------
# GPT 변환 로직
# ------------------------------------------------------------

def run_generation():
    topic = st.session_state.current_input.strip()
    if not topic:
        return

    # 최근 입력 업데이트
    hist = st.session_state.history
    if topic in hist:
        hist.remove(topic)
    hist.append(topic)
    st.session_state.history = hist[-5:]
    save_config()

    # 시스템 메시지 구성
    sys_parts = [
        st.session_state.inst_role,
        st.session_state.inst_tone,
        st.session_state.inst_structure,
        st.session_state.inst_depth,
        st.session_state.inst_forbidden,
        st.session_state.inst_format,
        st.session_state.inst_user_intent,
        f"[공통 스타일 래퍼]\n{st.session_state.inst_style_wrapper}",
    ]

    system_text = "\n\n".join(p.strip() for p in sys_parts if isinstance(p, str) and p.strip())

    user_text = (
        "위 지침을 모두 엄격하게 따르며 아래 대본을 Script-to-Image 형식으로 변환해줘.\n\n"
        f"{topic}"
    )

    with st.spinner("🎬 시각화 프롬프트 생성 중..."):
        res = client.chat.completions.create(
            model=st.session_state.model_choice,
            messages=[
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_text},
            ],
            max_tokens=900,
        )

    st.session_state.last_output = res.choices[0].message.content


# ------------------------------------------------------------
# 메인 화면 UI — ScriptKing 스타일
# ------------------------------------------------------------

# 상단 로고 + 제목
st.markdown(
    """<div style='text-align:center;'>
        <div style='
            width:100px; height:100px;
            border-radius:50%;
            background:#93c5fd;
            display:flex; align-items:center; justify-content:center;
            font-size:40px; margin:auto;
            color:#111827; font-weight:bold;
            box-shadow:0 3px 8px rgba(0,0,0,0.08);
        '>N</div>
        <h1 style='margin-top:26px; margin-bottom:6px;'>시각화 마스터</h1>
    </div>""",
    unsafe_allow_html=True,
)

# 최근 입력 목록
if st.session_state.history:
    items = st.session_state.history[-5:]
    html_items = ""
    for h in items:
        html_items += f"""
        <div style='
            font-size:0.85rem;
            color:#797979;
            margin-bottom:4px;
        '>{h}</div>
        """

    st.markdown(
        f"""
        <div style="
            max-width:460px;
            margin:64px auto 72px auto;
        ">
            <div style="margin-left:100px; text-align:left;">
                <div style="font-size:0.8rem; color:#9ca3af; margin-bottom:10px;">
                    최근
                </div>
                {html_items}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
        <div style="
            max-width:460px;
            margin:64px auto 72px auto;
        ">
            <div style="margin-left:100px; font-size:0.8rem; color:#d1d5db; text-align:left;">
                최근 입력이 없습니다.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# 입력창
pad1, center, pad2 = st.columns([1, 7, 1])
with center:
    st.markdown(
        "<div style='color:#BDC6D2; font-size:0.9rem; margin-bottom:10px; text-align:center;'>대본을 붙여넣으면 자동으로 시각화해드립니다.</div>",
        unsafe_allow_html=True,
    )

    st.text_input(
        label="주제 입력",
        key="current_input",
        placeholder="여기에 대본을 붙여넣고 엔터하세요.",
        label_visibility="collapsed",
        on_change=run_generation,
    )

st.markdown("<div style='height:32px;'></div>", unsafe_allow_html=True)

# 결과 출력
if st.session_state.last_output:
    st.subheader("📄 생성된 시각화 프롬프트")
    st.write(st.session_state.last_output)

