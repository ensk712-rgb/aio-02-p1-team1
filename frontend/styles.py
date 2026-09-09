"""시안(docs/design/zoo_guide_mockup_v3.html)에서 확정한 v3 디자인 토큰과 전역 스타일.

색상은 에버랜드·서울대공원 라이브 화면과 대조해 WCAG AA(4.5:1) 대비 기준으로 재조정했다.
가장 큰 변경은 기본 강조색이다: 이전 --leaf(#7da94a) 위 흰 글자는 대비 2.75:1로 기준 미달이었고,
로그인·질문하기·확인 버튼 전체에 적용됐다. 새 --forest(#0b5c43) 위 흰 글자는 8.0:1이다.
"""

import streamlit as st


def apply_theme() -> None:
    st.html("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');
    :root {
        --forest:#0b5c43; --forest-2:#0f6a4e; --forest-deep:#07452f;
        --leaf:#2f9e5f; --leaf-dark:#1f7a46; --leaf-bright:#9fd7b4;
        --moss:#cfe6d8; --moss-soft:#e6f2ec;
        --ivory:#f3f7f4; --paper:#ffffff; --sand:#e1e9e4; --sand-2:#c9d6ce;
        --ink:#0e2a21; --ink-2:#4a5f57; --muted:#64786f;
        --ok:#167a40; --warn:#7a4b05; --danger:#b02a1e;
        --sans:"Pretendard Variable",Pretendard,-apple-system,BlinkMacSystemFont,
            "Noto Sans KR","Malgun Gothic",sans-serif;
    }
    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
    [data-testid="stHeader"], .block-container { font-family: var(--sans); }
    [data-testid="stAppViewContainer"] { background:var(--ivory); }
    [data-testid="stHeader"] { background:transparent; }
    [data-testid="stSidebar"] { background:var(--forest); min-width:250px; max-width:250px; }
    [data-testid="stSidebar"] * { color:var(--moss-soft); }
    [data-testid="stSidebar"] button { border-color:rgba(255,255,255,.24); background:rgba(255,255,255,.07); }
    .block-container { padding-top:1.2rem; max-width:1540px; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--sand); }
    .zoo-brand { color:#ffffff; font-weight:800; font-size:1.45rem; line-height:1.18; }
    .zoo-kicker { color:var(--forest); font-size:.72rem; font-weight:800; letter-spacing:.16em; }
    .zoo-hero { position:relative; min-height:330px; overflow:hidden; border-radius:14px; padding:46px 50px; color:white; border:1px solid rgba(255,255,255,.35); background-position:center 42%; background-size:cover; box-shadow:0 22px 55px rgba(14,42,33,.24); }
    .zoo-hero:before { content:''; position:absolute; inset:0; background:linear-gradient(90deg,rgba(7,69,47,.94) 0%,rgba(11,92,67,.74) 44%,rgba(11,92,67,.08) 78%); }
    .zoo-hero>* { position:relative; z-index:1; }
    .zoo-hero h1 { max-width:540px; margin:.6rem 0 1rem; font-size:clamp(2.1rem,4vw,4rem); line-height:1.02; letter-spacing:-.04em; }
    .zoo-hero p { max-width:500px; color:#e3f0e9; font-weight:600; }
    .zoo-page-hero { border-radius:14px; padding:34px 38px; color:white; min-height:180px; background-position:center; background-size:cover; box-shadow:0 18px 45px rgba(14,42,33,.20); position:relative; overflow:hidden; }
    .zoo-page-hero:before { content:''; position:absolute; inset:0; background:linear-gradient(90deg,rgba(7,69,47,.93),rgba(7,69,47,.25)); }
    .zoo-page-hero>* { position:relative; z-index:1; max-width:620px; }
    .zoo-page-hero h1 { margin:.2rem 0; font-size:2.4rem; }
    .zoo-glass { background:linear-gradient(145deg,rgba(255,255,255,.92),rgba(230,242,236,.85)); border:1px solid rgba(255,255,255,.8); border-radius:14px; padding:18px; box-shadow:0 12px 35px rgba(14,42,33,.10); }
    [data-testid="stImage"] img { border-radius:14px; box-shadow:0 14px 35px rgba(14,42,33,.16); }
    [data-testid="stPageLink"] a { border-radius:8px; padding:.48rem .65rem; }
    [data-testid="stPageLink"] a:hover { background:rgba(255,255,255,.13); }
    .zoo-route { background:linear-gradient(145deg,var(--moss-soft),var(--moss)); border-radius:14px; padding:22px; text-align:center; font-size:1.05rem; line-height:2.8; color:var(--ink); }
    .zoo-status-dot { display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--ok); margin-right:6px; }
    @media (max-width:800px) { [data-testid="stSidebar"]{min-width:auto;max-width:none}.block-container{padding:.8rem 1rem 2rem}.zoo-hero{min-height:240px;padding:28px 24px}.zoo-page-hero{padding:26px 24px} }
    @media (prefers-reduced-motion:reduce) { *{scroll-behavior:auto!important;transition:none!important} }
    </style>
    """)
