
import streamlit as st
from openai import OpenAI
import os
import json
from json import JSONDecodeError
st.write("현재 작업 디렉토리:", os.getcwd())
st.write("config.json 존재 여부:", os.path.exists("config.json"))

st.set_page_config(page_title="시각화 마스터", page_icon="📝", layout="centered")

LOGIN_ID_ENV = os.getenv("LOGIN_ID")
LOGIN_PW_ENV = os.getenv("LOGIN_PW")
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

st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("history", [])
st.session_state.setdefault("login_id", LOGIN_ID_ENV or "")
st.session_state.setdefault("login_pw", LOGIN_PW_ENV or "")
st.session_state.setdefault("remember_login", False)

# ===== 기본 지침 값 세팅 =====
st.session_state.setdefault(
    "inst_role",
    """너의 역할은 **한국어 대본을 이미지 시각화용 영어 프롬프트로 변환하는 전문 변환기(visualization prompt generator)**다.
항상 원문 의미를 정확히 해석하고, 의미 범위를 벗어나지 않는 사실적·현실적 묘사만 허용한다.
출력은 “스크립트-투-이미지” 목적에 최적화된 형태로 구성한다."""
)

st.session_state.setdefault(
    "inst_tone",
    """[2. 톤·스타일 지침 (Tone & Style Instructions)]

전체적인 어조는 명확·중립·사실적이다.

묘사는 감정·장면·구도 등을 구체적으로 표현하되, 과도한 창작이나 판타지는 금지한다.

시각 묘사는 장르적 성격(다큐 / 시네마틱 / 애니메이션 / 전기 등)에 일관되도록 유지한다.

[2-A. 스타일 래퍼 지침 (Style Wrapper Rules)]

아래 규칙은 이미지 프롬프트 앞에 항상 붙는 공통 스타일 문장에 관한 규칙이다.

- 대본 분석을 기반으로 단일 장르를 선택한다. (예: documentary, cinematic, animation 등)
- 선택된 장르에 맞춰 스타일 래퍼 1문장만 선언한다.
- 생성되는 모든 영어 이미지 프롬프트 문장의 가장 앞에 이 스타일 래퍼 문장을 완전히 동일하게 반복한다.
- 단 하나의 단어·쉼표도 변형·삭제 금지, 누락 금지."""
)

# 공통 스타일 래퍼(실제 한 문장)를 별도로 저장하는 필드
st.session_state.setdefault(
    "inst_style_wrapper",
    "Shot on high-resolution digital cinema camera, 16:9 aspect ratio, neutral color grading, close-up or wide shot, cinematic realism, subtle noise/grain added."
)

st.session_state.setdefault(
    "inst_structure",
    """[3. 구성 지침 (Structure / Flow)]

스크립트-투-이미지 변환 출력은 다음 순서를 반드시 따른다:

1) 제목
   - 항상 이 텍스트로 시작한다:
     ⚡ 스크립트-투-이미지 시각화 프롬프트

2) 대본 분석 요약 (2~4문장)
   - 주제 · 톤 · 정서 · 장르적 특성 포함
   - 이를 기반으로 최종 장르 선택

3) 스타일 래퍼 선언
   - 선택된 장르에 맞춘 1문장을 ‘스타일 래퍼:’ 아래 제시

4) 문장별 변환
   - 원문 대본을 자연스러운 의미 단위로 나누고
   - 각 문장은 반드시 2줄 구조로 출력:
     [한국어 원문]
     [영어 이미지 프롬프트]"""
)

st.session_state.setdefault(
    "inst_depth",
    """[4. 정보 밀도·연구 깊이 지침 (Depth Rules)]

- 원문 의미를 벗어나지 않는 범위 내에서 최대한 구체적이고 사실적인 시각 요소를 추가한다.
- 묘사는 장면·환경·빛·감정·구도·움직임 등을 자연스러운 선에서 확장한다.
- 실존 요소(장소, 시대적 분위기 등)는 왜곡 없이 표현한다.
- 지나친 해석, 상상, 상징적 장면 창조는 금지한다."""
)

st.session_state.setdefault(
    "inst_forbidden",
    """[5. 금지 지침 (Forbidden Rules)]

다음 사항은 절대 금지한다:

- 스타일 래퍼 누락
- 스타일 래퍼의 단어·구문 수정 또는 축약
- 대본 분석 없이 바로 이미지 프롬프트 생성
- 원문 의미 과장·왜곡
- 판타지/허구적 창작, 초현실적 요소 추가
- 실존 인물·단체의 왜곡
- 문장 앞뒤 형식 변경
- 문장의 두 줄 구조(한국어 → 영어 프롬프트) 무시
- 출력 순서 임의 변경"""
)

st.session_state.setdefault(
    "inst_format",
    """[6. 출력 형식 지침 (Format Rules)]

최종 출력 형식은 다음을 반드시 따른다:

1) 제목
   - ⚡ 스크립트-투-이미지 시각화 프롬프트

2) 대본 분석 요약(2~4문장)

3) 스타일 래퍼 선언부

4) 문장별 변환
   - 한국어 문장
   - 공통 스타일 래퍼로 시작하는 영어 이미지 프롬프트
     (두 줄 세트 반복)

전체 출력은 깔끔하고 구분된 블록 형태로 유지해야 한다."""
)

st.session_state.setdefault(
    "inst_user_intent",
    """[7. 사용자 요청 반영 지침 (User Intent Adaptation)]

- 사용자의 요청(장르 지정, 스타일 기조, 시각화 정도 등)을 항상 최우선으로 반영한다.
- 사용자가 특정 스타일을 요구할 경우, 선택된 장르와 충돌하지 않는 선에서 조정한다.
- 대본의 특성상 의미 단위가 길거나 짧아도, 자연스러운 문장 단위로 분리해 처리한다.
- 변환 결과는 즉시 사용 가능한 이미지 생성용 프롬프트로 제공해야 한다."""
)

st.session_state.setdefault("current_input", "")
st.session_state.setdefault("last_output", "")
st.session_state.setdefault("model_choice", "gpt-4o-mini")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except JSONDecodeError:
        return

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

    hist = data.get("history")
    if isinstance(hist, list):
        st.session_state.history = hist[-5:]

    if isinstance(data.get("login_id"), str):
        st.session_state.login_id = data["login_id"]
    if isinstance(data.get("login_pw"), str):
        st.session_state.login_pw = data["login_pw"]
    if "remember_login" in data:
        st.session_state.remember_login = bool(data["remember_login"])


def save_config():
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
        "login_id": st.session_state.login_id,
        "login_pw": st.session_state.login_pw,
        "remember_login": st.session_state.remember_login,
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def login_screen():
    # 로그인 화면도 메인과 같은 상단 위치(4.5rem 패딩)
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 420px;
            padding-top: 4.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 메인 화면과 동일한 로고 + 제목 블록
    st.markdown(
        """<div style='text-align:center;'>
        <div style='
            width:100px; height:100px;
            border-radius:50%;
            background:#93c5fd;
            display:flex; align-items:center; justify-content:center;
            font-size:40px; margin:auto;
            color:#111827; font-weight:bold;
            box-shadow: 0 3px 8px rgba(0,0,0,0.08);
        '>N</div>
        <h1 style='margin-top:26px; margin-bottom:24px;'>시각화 마스터</h1>
    </div>""",
        unsafe_allow_html=True,
    )

    default_id = st.session_state.login_id if st.session_state.remember_login else ""
    default_pw = st.session_state.login_pw if st.session_state.remember_login else ""

    with st.form(key="login_form"):
        user = st.text_input("아이디", placeholder="ID 입력", value=default_id)
        pw = st.text_input("비밀번호", type="password", placeholder="비밀번호", value=default_pw)
        remember = st.checkbox("로그인 정보 저장", value=st.session_state.remember_login)

        submitted = st.form_submit_button("로그인")
        if submitted:
            valid_id = st.session_state.login_id or LOGIN_ID_ENV or ""
            valid_pw = st.session_state.login_pw or LOGIN_PW_ENV or ""

            if user == valid_id and pw == valid_pw:
                st.session_state["logged_in"] = True
                st.session_state["remember_login"] = remember
                if remember:
                    st.session_state.login_id = user
                    st.session_state.login_pw = pw
                save_config()
                st.rerun()
            else:
                st.error("❌ 아이디 또는 비밀번호가 틀렸습니다.")


if "config_loaded" not in st.session_state:
    load_config()
    st.session_state.config_loaded = True

if not st.session_state["logged_in"]:
    login_screen()
    st.stop()

# 메인 영역 폭 넓게 조정 + div3 인풋 스타일
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

    /* div3 주제 입력창 스타일 - 높이 & 테두리 강조 */
    div[data-testid="stTextInput"] input[aria-label="주제 입력"] {
        background-color: #f9fafb !important;
        border: 2px solid #4f46e5 !important;
        border-radius: 999px !important;
        padding: 14px 20px !important;   /* 세로 패딩을 늘려서 높이 키움 */
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
        "위 1~7 지침을 모두 엄격하게 따르면서, 아래 한국어 대본을 "
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

    st.markdown("### 📘 지침")

    with st.expander("1. 역할 지침 (Role Instructions)", expanded=False):
        st.caption("한국어 대본을 이미지 시각화용 영어 프롬프트로 변환하는 역할을 정의합니다.")
        inst_role_edit = st.text_area(
            "역할 지침",
            st.session_state.inst_role,
            height=160,
            key="inst_role_edit",
        )
        if st.button("역할 지침 저장", key="save_role"):
            if inst_role_edit.strip():
                st.session_state.inst_role = inst_role_edit.strip()
                save_config()
            st.success("역할 지침이 저장되었습니다.")

    with st.expander("2. 톤 & 스타일 지침 + 공통 스타일 래퍼", expanded=False):
        st.caption("전체적인 톤/스타일 규칙과, 모든 이미지 프롬프트 앞에 붙일 공통 스타일 래퍼를 정의합니다.")

        inst_tone_edit = st.text_area(
            "톤 & 스타일 지침",
            st.session_state.inst_tone,
            height=220,
            key="inst_tone_edit",
        )

        inst_style_wrapper_edit = st.text_area(
            "공통 스타일 래퍼 (영어 한 문장)",
            st.session_state.inst_style_wrapper,
            height=80,
            key="inst_style_wrapper_edit",
            placeholder="Shot on high-resolution digital cinema camera, 16:9 aspect ratio, neutral color grading, close-up or wide shot, cinematic realism, subtle noise/grain added.",
        )

        if st.button("톤 & 스타일 / 스타일 래퍼 지침 저장", key="save_tone"):
            if inst_tone_edit.strip():
                st.session_state.inst_tone = inst_tone_edit.strip()
            if inst_style_wrapper_edit.strip():
                st.session_state.inst_style_wrapper = inst_style_wrapper_edit.strip()
            save_config()
            st.success("톤 & 스타일 / 공통 스타일 래퍼가 저장되었습니다.")

    with st.expander("3. 콘텐츠 구성 지침", expanded=False):
        st.caption("스크립트-투-이미지 출력의 전체 흐름 구조를 정의합니다.")
        inst_structure_edit = st.text_area(
            "콘텐츠 구성 지침",
            st.session_state.inst_structure,
            height=200,
            key="inst_structure_edit",
        )
        if st.button("콘텐츠 구성 지침 저장", key="save_structure"):
            if inst_structure_edit.strip():
                st.session_state.inst_structure = inst_structure_edit.strip()
                save_config()
            st.success("콘텐츠 구성 지침이 저장되었습니다.")

    with st.expander("4. 정보 밀도 & 조사 심도 지침", expanded=False):
        st.caption("얼마나 구체적이고 깊게 시각 정보를 확장할지 정의합니다.")
        inst_depth_edit = st.text_area(
            "정보 밀도 & 조사 심도 지침",
            st.session_state.inst_depth,
            height=200,
            key="inst_depth_edit",
        )
        if st.button("정보 밀도 지침 저장", key="save_depth"):
            if inst_depth_edit.strip():
                st.session_state.inst_depth = inst_depth_edit.strip()
                save_config()
            st.success("정보 밀도 지침이 저장되었습니다.")

    with st.expander("5. 금지 지침 (Forbidden Rules)", expanded=False):
        st.caption("절대 허용하지 않을 변형/스타일/출력 형식을 정의합니다.")
        inst_forbidden_edit = st.text_area(
            "금지 지침",
            st.session_state.inst_forbidden,
            height=220,
            key="inst_forbidden_edit",
        )
        if st.button("금지 지침 저장", key="save_forbidden"):
            if inst_forbidden_edit.strip():
                st.session_state.inst_forbidden = inst_forbidden_edit.strip()
                save_config()
            st.success("금지 지침이 저장되었습니다.")

    with st.expander("6. 출력 형식 지침 (Format Rules)", expanded=False):
        st.caption("최종 출력의 제목, 블록 구조, 줄 배치 등을 정의합니다.")
        inst_format_edit = st.text_area(
            "출력 형식 지침",
            st.session_state.inst_format,
            height=220,
            key="inst_format_edit",
        )
        if st.button("출력 형식 지침 저장", key="save_format"):
            if inst_format_edit.strip():
                st.session_state.inst_format = inst_format_edit.strip()
                save_config()
            st.success("출력 형식 지침이 저장되었습니다.")

    with st.expander("7. 사용자 요청 반영 지침", expanded=False):
        st.caption("사용자 요구(장르/스타일/시각화 정도 등)를 어떻게 반영할지 정의합니다.")
        inst_user_intent_edit = st.text_area(
            "사용자 요청 반영 지침",
            st.session_state.inst_user_intent,
            height=200,
            key="inst_user_intent_edit",
        )
        if st.button("사용자 요청 지침 저장", key="save_user_intent"):
            if inst_user_intent_edit.strip():
                st.session_state.inst_user_intent = inst_user_intent_edit.strip()
                save_config()
            st.success("사용자 요청 반영 지침이 저장되었습니다.")

    st.markdown("</div><div class='sidebar-bottom'>", unsafe_allow_html=True)

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

    with st.expander("👤 계정 관리", expanded=False):
        st.caption("비밀번호 변경 및 로그아웃")

        with st.form("change_password_form"):
            current_pw = st.text_input("현재 비밀번호", type="password")
            new_pw = st.text_input("새 비밀번호", type="password")
            new_pw2 = st.text_input("새 비밀번호 확인", type="password")
            pw_submitted = st.form_submit_button("비밀번호 변경")

            if pw_submitted:
                valid_pw = st.session_state.login_pw or LOGIN_PW_ENV or ""
                if current_pw != valid_pw:
                    st.error("현재 비밀번호가 올바르지 않습니다.")
                elif not new_pw:
                    st.error("새 비밀번호를 입력하세요.")
                elif new_pw != new_pw2:
                    st.error("새 비밀번호와 확인이 일치하지 않습니다.")
                else:
                    st.session_state.login_pw = new_pw
                    save_config()
                    st.success("비밀번호가 변경되었습니다.")

        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.current_input = ""
            st.session_state.last_output = ""
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# -------- div1: 상단 로고 + 타이틀 --------
st.markdown(
    """<div style='text-align:center;'>
    <div style='
        width:100px; height:100px;
        border-radius:50%;
        background:#93c5fd;
        display:flex; align-items:center; justify-content:center;
        font-size:40px; margin:auto;
        color:#111827; font-weight:bold;
        box-shadow: 0 3px 8px rgba(0,0,0,0.08);
    '>N</div>
    <h1 style='margin-top:26px; margin-bottom:6px;'>시각화 마스터</h1>
</div>""",
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
    margin:64px auto 72px auto;
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
    margin:64px auto 72px auto;
">
  <div style="margin-left:100px; font-size:0.8rem; color:#d1d5db; text-align:left;">
    최근 입력이 없습니다.
  </div>
</div>""",
        unsafe_allow_html=True,
    )

# -------- div3: 입력 영역 (가운데 정렬, 버튼 없이 on_change) --------
pad_left, center_col, pad_right = st.columns([1, 7, 1])

with center_col:
    st.markdown(
        "<div style='color:#BDC6D2; font-size:0.9rem; margin-bottom:10px; text-align:center;'>대본을 붙여넣어주세요,자동으로 시각화해드립니다</div>",
        unsafe_allow_html=True,
    )

    st.text_input(
        label="주제 입력",
        key="current_input",
        placeholder="gpt에게 시각화 부탁하기",
        label_visibility="collapsed",
        on_change=run_generation,
    )

st.markdown("<div style='height:32px;'></div>", unsafe_allow_html=True)

# -------- 결과 --------
if st.session_state.last_output:
    st.subheader("📄 생성된 스크립트-투-이미지 프롬프트")
    st.write(st.session_state.last_output)
