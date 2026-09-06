"""우리동물원 AI 가이드 Streamlit 화면."""

from __future__ import annotations

import streamlit as st

from frontend.clients.agent_client import AgentClient, AgentClientError

st.set_page_config(page_title="우리동물원 AI 가이드", page_icon="🌿", layout="wide")

APP_CSS = """
<style>
.stApp{background:#f7f4e9;color:#183d2c}[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebar"]{background:#075239}[data-testid="stSidebar"] *{color:#f7fbef}
.block-container{max-width:1440px;padding-top:1.5rem;padding-bottom:2rem}.zoo-brand{font-size:1.55rem;font-weight:800;letter-spacing:-.04em}
.zoo-muted{color:#718076;margin:.25rem 0 1.4rem}.zoo-hero{min-height:260px;padding:2.5rem;border-radius:24px;background:radial-gradient(circle at 82% 62%,#8ba76f 0 8%,transparent 8.4%),radial-gradient(circle at 73% 77%,#bfd3a4 0 15%,transparent 15.4%),linear-gradient(125deg,rgba(255,255,255,.93),rgba(224,239,218,.78)),linear-gradient(135deg,#dfe8d1,#9bb88b);border:1px solid #c7d2b6;box-shadow:0 16px 38px rgba(42,73,49,.10)}
.zoo-kicker{color:#237257;font-size:.75rem;font-weight:800;letter-spacing:.18em}.zoo-hero h1{color:#064b35;font-size:clamp(2rem,4vw,3.35rem);line-height:1.05;margin:1rem 0}
.zoo-card{background:#fffdf7;border:1px solid #e6e0d1;border-radius:20px;padding:1.25rem;min-height:150px;box-shadow:0 9px 28px rgba(42,55,38,.06)}.zoo-card h3{margin:0 0 .85rem;color:#183d2c;font-size:1.05rem}
.zoo-pill{display:inline-block;border-radius:999px;padding:.36rem .7rem;margin:.2rem .15rem;background:#eaf2df;color:#315c3b;font-size:.82rem}.login-wrap{max-width:480px;margin:6vh auto 1.25rem;text-align:center}.login-mark{width:74px;height:74px;margin:auto;display:grid;place-items:center;border-radius:22px;background:#eaf0c7;font-size:2rem}
div[data-testid="stForm"]{background:#fffdf8;border:1px solid #e3dece;border-radius:22px;padding:1.25rem 1.35rem;box-shadow:0 16px 42px rgba(30,60,40,.10)}.stButton>button,.stFormSubmitButton>button{border-radius:12px;border-color:#17694d}.stFormSubmitButton>button{background:#0a5b40;color:white}.stChatMessage{background:rgba(255,255,255,.58);border-radius:16px}
@media(max-width:768px){.block-container{padding:1rem}.zoo-hero{min-height:220px;padding:1.5rem}}
</style>
"""


def _init_state() -> None:
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("user_id", None)
    st.session_state.setdefault("session_id", None)
    st.session_state.setdefault("messages", [])


def _login_succeeded(payload: dict) -> bool:
    """로그인 API 계약의 명시적인 성공 값만 허용합니다."""
    return payload.get("authenticated") is True


def _source_caption(source: dict) -> str:
    score = source.get("score")
    score_text = f" · 관련도 {float(score):.2f}" if score is not None else ""
    page = f" · p.{source['page']}" if source.get("page") is not None else ""
    return f"{source.get('title', '출처')}{page}{score_text}"


def render_response(message: dict) -> None:
    status = message.get("status", "error")
    if status == "error":
        st.error(message.get("final_answer", "요청 처리에 실패했습니다."))
    elif status in {"rejected", "stopped", "needs_clarification"}:
        st.warning(message.get("final_answer", "요청을 계속할 수 없습니다."))
    else:
        st.write(message.get("final_answer", ""))
    sources = message.get("sources") or []
    if sources:
        with st.expander("확인한 출처", expanded=True):
            for source in sources:
                st.caption(_source_caption(source))
    tool_calls = message.get("tool_calls") or ([message["tool_call"]] if message.get("tool_call") else [])
    for call in tool_calls:
        name = call.get("name") or call.get("tool", "알 수 없는 Tool")
        with st.expander(f"조회 Tool · {name}", expanded=True):
            st.caption("MCP를 통한 교육용 Mock 운영 데이터 조회")
            st.json(call.get("result") or {})


def render_login(client: AgentClient) -> None:
    st.markdown('<div class="login-wrap"><div class="login-mark">🐾</div><h1>우리동물원 AI 가이드</h1><p class="zoo-muted">동물과 자연이 함께하는 특별한 하루를 시작해 보세요.</p></div>', unsafe_allow_html=True)
    _, center, _ = st.columns([1, 1.15, 1])
    with center:
        with st.form("login_form", clear_on_submit=False):
            st.subheader("로그인")
            st.caption("등록된 사용자 계정으로 서비스를 이용할 수 있습니다.")
            user_id = st.text_input("아이디", placeholder="아이디를 입력하세요", autocomplete="username")
            password = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요", autocomplete="current-password")
            submitted = st.form_submit_button("로그인", use_container_width=True)
        if submitted:
            if not user_id.strip() or not password:
                st.warning("아이디와 비밀번호를 모두 입력해 주세요.")
                return
            try:
                payload = client.login(user_id.strip(), password)
            except (AgentClientError, AttributeError):
                st.error("로그인할 수 없습니다. 서버 상태를 확인해 주세요.")
                return
            if not _login_succeeded(payload):
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
                return
            st.session_state.authenticated = True
            st.session_state.user_id = payload.get("user_id") or payload.get("id") or user_id.strip()
            st.rerun()


def _render_sidebar(client: AgentClient) -> None:
    with st.sidebar:
        st.markdown('<div class="zoo-brand">🐾 우리동물원<br>AI 가이드</div>', unsafe_allow_html=True)
        st.write("")
        st.radio("메뉴", ["🏠 홈", "🐾 동물 정보", "🗺️ 지도", "🗓️ 먹이주기 일정", "📍 관람 동선 추천"], label_visibility="collapsed")
        st.divider()
        st.markdown("#### 🌿 오늘의 한마디")
        st.caption("동물에게 조용한 응원과 따뜻한 시선을 보내주세요.")
        st.markdown("#### 🌤️ 26°C")
        st.caption("구름 조금 · 시연 정보")
        if st.button("로그아웃", use_container_width=True):
            for key, value in {"authenticated": False, "user_id": None, "session_id": None, "messages": []}.items():
                st.session_state[key] = value
            st.rerun()
        with st.expander("서비스 연결 상태"):
            if st.button("상태 새로고침", use_container_width=True):
                try:
                    health = client.get_health()
                    st.success("Backend · MCP 연결 정상") if health.get("status") == "ok" else st.warning("일부 조회 기능을 사용할 수 없습니다.")
                except AgentClientError as error:
                    st.error(str(error))


def _render_dashboard_cards() -> None:
    st.markdown("### 오늘의 동물원")
    schedule, route, animal = st.columns(3)
    with schedule:
        st.markdown('<div class="zoo-card"><h3>🗓️ 먹이주기 일정</h3><span class="zoo-pill">10:30 기린</span><span class="zoo-pill">11:00 펭귄</span><br><span class="zoo-pill">13:30 코끼리</span><span class="zoo-pill">15:30 호랑이</span></div>', unsafe_allow_html=True)
    with route:
        st.markdown('<div class="zoo-card"><h3>📍 추천 관람 동선</h3><p>입구 → 사바나 → 판다월드 → 펭귄빌리지</p><span class="zoo-pill">약 2시간 30분</span><span class="zoo-pill">약 3.2km</span></div>', unsafe_allow_html=True)
    with animal:
        st.markdown('<div class="zoo-card"><h3>🐼 오늘의 동물</h3><p><b>자이언트 판다</b></p><p>대나무를 주식으로 하는 중국의 국보급 동물이에요.</p></div>', unsafe_allow_html=True)


def render_home(client: AgentClient) -> None:
    _ = _render_sidebar(client)
    st.markdown('<div class="zoo-brand">우리동물원 AI 가이드 🌿</div><p class="zoo-muted">자연과 동물이 함께하는 특별한 하루 되세요!</p>', unsafe_allow_html=True)
    st.markdown('<section class="zoo-hero"><div class="zoo-kicker">WELCOME TO OUR ZOO</div><h1>오늘 어떤 동물을<br>만나볼까요?</h1><p>궁금한 동물과 관람 정보를 AI 가이드에게 물어보세요.</p></section>', unsafe_allow_html=True)
    st.caption("운영 일정과 날씨는 시연용 Mock 정보입니다. 실제 방문 전 공식 공지를 확인해 주세요.")
    prompt = st.chat_input("AI에게 물어보기 · 예: 판다는 어디에 있어?")
    suggestions = st.columns(3)
    suggestions[0].button("🐾 인기 동물은?", use_container_width=True)
    suggestions[1].button("🗓️ 오늘의 먹이주기?", use_container_width=True)
    suggestions[2].button("📍 추천 관람 동선", use_container_width=True)
    _ = _render_dashboard_cards()
    if st.session_state.messages:
        st.markdown("### AI 가이드 챗봇")
    for item in st.session_state.messages:
        with st.chat_message(item["role"]):
            if item["role"] == "assistant":
                render_response(item["payload"])
            else:
                st.write(item["content"])
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        try:
            result = client.ask(prompt, st.session_state.session_id)
            if result.get("session_id"):
                st.session_state.session_id = result["session_id"]
        except AgentClientError as error:
            result = {"status": "error", "final_answer": str(error), "sources": [], "tool_calls": []}
        st.session_state.messages.append({"role": "assistant", "payload": result})
        st.rerun()


def main() -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)
    _ = _init_state()
    client = AgentClient()
    _ = render_home(client) if st.session_state.authenticated else render_login(client)


_ = main()
