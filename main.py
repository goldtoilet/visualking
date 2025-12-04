import streamlit as st
from openai import OpenAI
import os
import json
from json import JSONDecodeError

# -------------------------
# 기본 설정
# -------------------------
st.set_page_config(page_title="대본 마스터", page_icon="📝", layout="centered")

LOGIN_ID_ENV = os.getenv("LOGIN_ID")
LOGIN_PW_ENV = os.getenv("LOGIN_PW")
api_key = os.getenv("GPT_API_KEY")
client = OpenAI(api_key=api_key)

CONFIG_PATH = "config.json"

# -------------------------
# 공통 스타일 (textarea 폰트 작게)
# -------------------------
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

# -------------------------
# 세션 기본값
# -------------------------
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("history", [])

# 로그인 정보
st.session_state.setdefault("login_id", LOGIN_ID_ENV or "")
st.session_state.setdefault("login_pw", LOGIN_PW_ENV or "")
st.session_state.setdefault("remember_login", False)

# ❶ 역할 지침
st.session_state.setdefault(
    "inst_role",
    "너는 감성적이고 스토리텔링이 뛰어난 다큐멘터리 내레이터다."
)

# ❷ 톤 & 스타일 지침
st.session_state.setdefault(
    "inst_tone",
    "톤은 진지하고 서정적이며, 첫 문장은 강렬한 훅으로 시작한다."
)

# ❸ 콘텐츠 구성 지침
st.session_state.setdefault(
    "inst_structure",
    "인트로 → 배경 → 사건/전개 → 여운이 남는 결론 순서로 전개한다."
)

# ❹ 정보 밀도 & 조사 심도 지침
st.session_state.setdefault(
    "inst_depth",
    "사실 기반 정보를 충분히 포함하되, 사건의 핵심 원인과 결과를 반드시 드러낸다."
)

# ❺ 금지 지침
st.session_state.setdefault(
    "inst_forbidden",
    "선정적 표현, 과도한 비유, 독자에게 말을 거는 질문형 표현은 사용하지 않는다."
)

# ❻ 출력 형식 지침
st.session_state.setdefault(
    "inst_format",
    "전체 분량은 500자 이상으로 하고, 소제목 없이 자연스러운 내레이션만 생성하며, 문단 사이에는 한 줄 공백을 둔다."
)

# ❼ 사용자 요청 반영 지침
st.session_state.setdefault(
    "inst_user_intent",
    "사용자가 입력한 주제를 내러티브의 중심축으로 삼고, 배경 정보를 자연스럽게 녹여 스토리화한다."
)

st.session_state.setdefault("current_input", "")
st.session_state.setdefault("last_output", "")
st.session_state.setdefault("model_choice", "gpt-4o-mini")


# -------------------------
# 설정 JSON 로드/저장
# -------------------------
def load_config():
    if not os.path.exists(CONFIG_PATH):
        return

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except JSONDecodeError:
        return

    # 새 7개 지침
    if isinstance(data.get("inst_role"), str):
        st.session_state.inst_role = data["inst_role"]
    elif isinstance(data.get("role_instruction"), str):
        # 예전 키 호환
        st.session_state.inst_role = data["role_instruction"]

    for key in [
        "inst_tone",
        "inst_structure",
        "inst_depth",
        "inst_forbidden",
        "inst_format",
        "inst_user_intent",
    ]:
        if isinstance(data.get(key), str):
            setattr(st.session_state, key, data[key])

    hist = data.get("history")
    if isinstance(hist, list):
        st.session_state.history = hist[-5:]

    # 로그인 관련 정보
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
        "history": st.session_state.history[-5:],
        "login_id": st.session_state.login_id,
        "login_pw": st.session_state.login_pw,
        "remember_login": st.session_state.remember_login,
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if "config_loaded" not in st.session_state:
    load_config()
    st.session_state.config_loaded = True


# -------------------------
# 로그인 화면
# -------------------------
def login_screen():
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 420px;
            padding-top: 18vh;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("🔒 로그인 Required")

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


if not st.session_state["logged_in"]:
    login_screen()
    st.stop()


# -------------------------
# 메인 화면 공통 스타일
# -------------------------
st.markdown(
    """
    <style>
    .block-container {
        max-width: 620px;
        padding-top: 4.5rem;
    }
    .search-input > div > div > input {
        background-color: #eff6ff;
        border: 1px solid #60a5fa;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -------------------------
# 대본 생성 함수
# -------------------------
def run_generation():
    topic = st.session_state.current_input.strip()
    if not topic:
        return

    # 최근 검색어 관리 (중복 제거 + 마지막 5개 유지)
    hist = st.session_state.history
    if topic in hist:
        hist.remove(topic)
    hist.append(topic)
    st.session_state.history = hist[-5:]
    save_config()

    # 7개 지침을 모두 system 지침으로 합치기
    system_parts = [
        st.session_state.inst_role,
        st.session_state.inst_tone,
        st.session_state.inst_structure,
        st.session_state.inst_depth,
        st.session_state.inst_forbidden,
        st.session_state.inst_format,
        st.session_state.inst_user_intent,
    ]
    system_text = "\n\n".join(
        part.strip() for part in system_parts if isinstance(part, str) and part.strip()
    )

    user_text = f"다음 주제에 맞는 다큐멘터리 내레이션을 작성해줘.\n\n주제: {topic}"

    with st.spinner("🎬 대본을 작성하는 중입니다..."):
        res = client.chat.completions.create(
            model=st.session_state.model_choice,
            messages=[
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_text},
            ],
            max_tokens=600,
        )

    st.session_state.last_output = res.choices[0].message.content


# -------------------------
# 사이드바: 모델 + 7개 지침 + 계정 관리
# -------------------------
with st.sidebar:
    st.markdown("### ⚙️ 설정")

    model = st.selectbox(
        "GPT 모델",
        ["gpt-4o-mini", "gpt-4o", "gpt-4.1"],
        index=["gpt-4o-mini", "gpt-4o", "gpt-4.1"].index(st.session_state.model_choice),
    )
    st.session_state.model_choice = model

    # 1. 역할 지침
    with st.expander("1. 역할 지침 (Role Instructions)", expanded=False):
        st.caption("ChatGPT가 어떤 캐릭터 / 전문가 / 화자인지 정의합니다.")
        st.markdown(
            "- 예: `당신은 다큐멘터리 전문 내레이터이다.`\n"
            "- 예: `당신은 사건의 흐름을 촘촘히 짜주는 스토리텔링 편집자다.`\n"
            "- 예: `당신은 유튜브 쇼츠용 대본을 압축해주는 전문가다.`"
        )
        inst_role_edit = st.text_area(
            "역할 지침",
            st.session_state.inst_role,
            height=90,
            key="inst_role_edit",
        )
        if st.button("역할 지침 저장", key="save_role"):
            if inst_role_edit.strip():
                st.session_state.inst_role = inst_role_edit.strip()
                save_config()
            st.success("역할 지침이 저장되었습니다.")

    # 2. 톤 & 스타일
    with st.expander("2. 톤 & 스타일 지침", expanded=False):
        st.caption("어떤 분위기/문체/리듬으로 말할지 정의합니다.")
        st.markdown(
            "- 예: `톤은 진지하고 저널리즘 스타일을 유지한다.`\n"
            "- 예: `첫 문장은 100% 강렬한 훅으로 시작한다.`\n"
            "- 예: `문장은 짧고 간결하며 리듬감 있게 구성한다.`"
        )
        inst_tone_edit = st.text_area(
            "톤 & 스타일 지침",
            st.session_state.inst_tone,
            height=90,
            key="inst_tone_edit",
        )
        if st.button("톤 & 스타일 지침 저장", key="save_tone"):
            if inst_tone_edit.strip():
                st.session_state.inst_tone = inst_tone_edit.strip()
                save_config()
            st.success("톤 & 스타일 지침이 저장되었습니다.")

    # 3. 콘텐츠 구성
    with st.expander("3. 콘텐츠 구성 지침", expanded=False):
        st.caption("초반–중반–후반 또는 장면 흐름을 어떻게 짤지 정의합니다.")
        st.markdown(
            "- 예: `인트로 → 배경 → 사건 → 인물 → 결론 단계로 전개하라.`\n"
            "- 예: `각 문단은 3~4문장으로 제한한다.`\n"
            "- 예: `스토리 전개는 시간순으로 배열한다.`"
        )
        inst_structure_edit = st.text_area(
            "콘텐츠 구성 지침",
            st.session_state.inst_structure,
            height=90,
            key="inst_structure_edit",
        )
        if st.button("콘텐츠 구성 지침 저장", key="save_structure"):
            if inst_structure_edit.strip():
                st.session_state.inst_structure = inst_structure_edit.strip()
                save_config()
            st.success("콘텐츠 구성 지침이 저장되었습니다.")

    # 4. 정보 밀도 & 조사 심도
    with st.expander("4. 정보 밀도 & 조사 심도 지침", expanded=False):
        st.caption("얼마나 깊게, 얼마나 촘촘하게 설명할지 정의합니다.")
        st.markdown(
            "- 예: `사실 기반의 정보 비율을 50% 이상 유지.`\n"
            "- 예: `불필요한 수식어는 최소화.`\n"
            "- 예: `사건의 핵심 원인·결과를 반드시 포함.`"
        )
        inst_depth_edit = st.text_area(
            "정보 밀도 & 조사 심도 지침",
            st.session_state.inst_depth,
            height=90,
            key="inst_depth_edit",
        )
        if st.button("정보 밀도 지침 저장", key="save_depth"):
            if inst_depth_edit.strip():
                st.session_state.inst_depth = inst_depth_edit.strip()
                save_config()
            st.success("정보 밀도 지침이 저장되었습니다.")

    # 5. 금지 지침
    with st.expander("5. 금지 지침 (Forbidden Rules)", expanded=False):
        st.caption("절대 쓰지 말아야 할 표현/스타일/토픽을 정의합니다.")
        st.markdown(
            "- 예: `예시나 비유를 남발하지 마라.`\n"
            "- 예: `독자에게 질문 형태로 말 걸지 말라.`\n"
            "- 예: `선정적 표현은 제외.`"
        )
        inst_forbidden_edit = st.text_area(
            "금지 지침",
            st.session_state.inst_forbidden,
            height=90,
            key="inst_forbidden_edit",
        )
        if st.button("금지 지침 저장", key="save_forbidden"):
            if inst_forbidden_edit.strip():
                st.session_state.inst_forbidden = inst_forbidden_edit.strip()
                save_config()
            st.success("금지 지침이 저장되었습니다.")

    # 6. 출력 형식
    with st.expander("6. 출력 형식 지침 (Output Format)", expanded=False):
        st.caption("길이, 단락, 제목, 마크다운 형식 등을 정의합니다.")
        st.markdown(
            "- 예: `전체 500자 이상.`\n"
            "- 예: `소제목 없이 자연스러운 내레이션만 생성.`\n"
            "- 예: `문단 간 공백 1줄 유지.`"
        )
        inst_format_edit = st.text_area(
            "출력 형식 지침",
            st.session_state.inst_format,
            height=90,
            key="inst_format_edit",
        )
        if st.button("출력 형식 지침 저장", key="save_format"):
            if inst_format_edit.strip():
                st.session_state.inst_format = inst_format_edit.strip()
                save_config()
            st.success("출력 형식 지침이 저장되었습니다.")

    # 7. 사용자 요청 반영
    with st.expander("7. 사용자 요청 반영 지침", expanded=False):
        st.caption("사용자가 준 주제/키워드를 어떻게 스토리 안에 녹일지 정의합니다.")
        st.markdown(
            "- 예: `사용자가 입력한 키워드를 내러티브 중심축으로 사용한다.`\n"
            "- 예: `주제의 배경 정보를 먼저 파악한 뒤 스토리화한다.`"
        )
        inst_user_intent_edit = st.text_area(
            "사용자 요청 반영 지침",
            st.session_state.inst_user_intent,
            height=90,
            key="inst_user_intent_edit",
        )
        if st.button("사용자 요청 지침 저장", key="save_user_intent"):
            if inst_user_intent_edit.strip():
                st.session_state.inst_user_intent = inst_user_intent_edit.strip()
                save_config()
            st.success("사용자 요청 반영 지침이 저장되었습니다.")

    st.markdown("---")

    # 계정 관리 (비밀번호 변경 + 로그아웃)
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


# -------------------------
# 메인 화면 상단 로고/타이틀
# -------------------------
st.markdown(
    """
<div style='text-align:center;'>
    <div style='
        width:80px; height:80px;
        border-radius:50%;
        background:#bfdbfe;
        display:flex; align-items:center; justify-content:center;
        font-size:34px; margin:auto;
        color:#111827; font-weight:bold;
        box-shadow: 0 3px 8px rgba(0,0,0,0.06);
    '>N</div>
    <h1 style='margin-top:20px; margin-bottom:6px;'>대본 마스터</h1>
    <p style='color:#6b7280; font-size:0.9rem; margin-bottom:10px;'>
        한 줄 주제만 입력하면 감성적인 다큐멘터리 내레이션을 생성합니다.
    </p>
</div>
""",
    unsafe_allow_html=True,
)

# -------------------------
# (NEW) 최근 검색어 - 본문에 작게, 세로 리스트
# -------------------------
if st.session_state.history:
    items = st.session_state.history[-5:]  # 오래된 것 위, 최신이 아래
    html_items = ""
    for h in items:
        html_items += f"""
        <div style="
            display:block;
            margin:2px auto 4px auto;
            padding:3px 12px;
            max-width:260px;
            font-size:0.78rem;
            color:#374151;
            background:#f3f4f6;
            border-radius:999px;
            text-align:left;
        ">
            - {h}
        </div>
        """
    st.markdown(
        f"""
        <div style="
            text-align:center;
            margin-top:10px;
            margin-bottom:16px;
        ">
            <div style="font-size:0.75rem; color:#6b7280; margin-bottom:4px;">
                최근 검색어
            </div>
            {html_items}
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
        <div style="
            text-align:center;
            margin-top:10px;
            margin-bottom:16px;
            font-size:0.7rem;
            color:#9ca3af;
        ">
            최근 검색어 없음
        </div>
        """,
        unsafe_allow_html=True,
    )

# -------------------------
# 주제 입력 + 버튼
# -------------------------
st.markdown(
    "<div style='color:#4b5563; font-size:0.9rem; margin-bottom:6px;'>한 문장 또는 짧은 키워드로 주제를 적어주세요.</div>",
    unsafe_allow_html=True,
)

input_col, btn_col = st.columns([4, 1])

with input_col:
    st.text_input(
        label="주제 입력",
        key="current_input",
        placeholder="예: 축구의 경제학, 인공지능이 바꿀 우리의 일상",
        label_visibility="collapsed",
        on_change=run_generation,
        help="한 줄로 간단히 적어주세요.",
    )

with btn_col:
    st.button("대본 생성", use_container_width=True, on_click=run_generation)

st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

# -------------------------
# 결과 출력
# -------------------------
if st.session_state.last_output:
    st.subheader("📄 생성된 내레이션")
    st.write(st.session_state.last_output)
