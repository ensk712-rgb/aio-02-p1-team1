"""시안에서 추출한 최소 디자인 토큰과 전역 스타일."""

import streamlit as st


def apply_theme() -> None:
    st.html("""
    <style>
    :root { --forest:#07503b; --leaf:#7da94a; --moss:#dcebbf; --ivory:#f8f5ec; --sand:#e7dfcf; --ink:#173b30; }
    [data-testid="stAppViewContainer"] { background:var(--ivory); }
    [data-testid="stHeader"] { background:transparent; }
    [data-testid="stSidebar"] { background:var(--forest); min-width:250px; max-width:250px; }
    [data-testid="stSidebar"] * { color:#f8f5ec; }
    [data-testid="stSidebar"] button { border-color:rgba(255,255,255,.24); background:rgba(255,255,255,.07); }
    .block-container { padding-top:1.2rem; max-width:1540px; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--sand); }
    .zoo-brand { color:#f4f4c8; font-weight:800; font-size:1.45rem; line-height:1.18; }
    .zoo-kicker { color:#40725e; font-size:.72rem; font-weight:800; letter-spacing:.16em; }
    .zoo-hero { position:relative; min-height:330px; overflow:hidden; border-radius:28px; padding:46px 50px; color:white; border:1px solid rgba(255,255,255,.35); background-position:center 42%; background-size:cover; box-shadow:0 22px 55px rgba(16,65,47,.22); }
    .zoo-hero:before { content:''; position:absolute; inset:0; background:linear-gradient(90deg,rgba(1,47,35,.93) 0%,rgba(4,71,50,.72) 44%,rgba(7,80,59,.08) 78%); }
    .zoo-hero>* { position:relative; z-index:1; }
    .zoo-hero h1 { max-width:540px; margin:.6rem 0 1rem; font-size:clamp(2.1rem,4vw,4rem); line-height:1.02; letter-spacing:-.05em; }
    .zoo-hero p { max-width:500px; color:#ecf6df; font-weight:600; }
    .zoo-page-hero { border-radius:24px; padding:34px 38px; color:white; min-height:180px; background-position:center; background-size:cover; box-shadow:0 18px 45px rgba(18,64,46,.18); position:relative; overflow:hidden; }
    .zoo-page-hero:before { content:''; position:absolute; inset:0; background:linear-gradient(90deg,rgba(3,51,38,.92),rgba(3,51,38,.25)); }
    .zoo-page-hero>* { position:relative; z-index:1; max-width:620px; }
    .zoo-page-hero h1 { margin:.2rem 0; font-size:2.4rem; }
    .zoo-glass { background:linear-gradient(145deg,rgba(255,255,255,.92),rgba(238,246,225,.82)); border:1px solid rgba(255,255,255,.8); border-radius:18px; padding:18px; box-shadow:0 12px 35px rgba(27,75,55,.10); }
    [data-testid="stImage"] img { border-radius:20px; box-shadow:0 14px 35px rgba(25,65,50,.14); }
    [data-testid="stPageLink"] a { border-radius:10px; padding:.48rem .65rem; }
    [data-testid="stPageLink"] a:hover { background:rgba(255,255,255,.13); }
    .zoo-route { background:linear-gradient(145deg,#e6f2c8,#d0e5b4); border-radius:16px; padding:22px; text-align:center; font-size:1.05rem; line-height:2.8; }
    .zoo-status-dot { display:inline-block; width:8px; height:8px; border-radius:50%; background:#57a867; margin-right:6px; }
    @media (max-width:800px) { [data-testid="stSidebar"]{min-width:auto;max-width:none}.block-container{padding:.8rem 1rem 2rem}.zoo-hero{min-height:240px;padding:28px 24px}.zoo-page-hero{padding:26px 24px} }
    @media (prefers-reduced-motion:reduce) { *{scroll-behavior:auto!important;transition:none!important} }
    </style>
    """)
