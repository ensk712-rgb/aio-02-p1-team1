"""브라우저 Web Speech API 기반 한국어 STT/TTS 화면."""

import streamlit as st
import streamlit.components.v1 as components

from frontend.components.layout import render_sidebar

render_sidebar("voice")
st.title("음성 안내", icon=":material/mic:")
st.caption("마이크로 질문을 받아 글자로 바꾸고, 입력한 안내문을 한국어 음성으로 들을 수 있습니다.")

components.html(
    """
    <style>
      body{font-family:Pretendard,'Malgun Gothic',sans-serif;color:#0e2a21;margin:0}
      .voice-card{border:1px solid #c9d6ce;border-radius:14px;padding:22px;background:#fff}
      textarea{box-sizing:border-box;width:100%;min-height:125px;padding:14px;border:1px solid #aebfb5;border-radius:9px;font:16px inherit;resize:vertical}
      .buttons{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
      button{border:0;border-radius:8px;padding:11px 18px;font-weight:700;cursor:pointer;background:#0b5c43;color:#fff}
      button.secondary{background:#e6f2ec;color:#07452f;border:1px solid #9fc4ae}
      #status{font-size:13px;color:#4a5f57;margin:10px 0 0}
    </style>
    <div class="voice-card">
      <label for="speechText"><strong>음성 또는 안내 문장</strong></label>
      <textarea id="speechText" placeholder="마이크 버튼을 누르고 말씀하거나, 들을 문장을 입력하세요."></textarea>
      <div class="buttons">
        <button id="listen">🎙️ 음성 인식 시작</button>
        <button id="speak">🔊 한국어로 듣기</button>
        <button class="secondary" id="stop">정지</button>
        <button class="secondary" id="clear">내용 지우기</button>
      </div>
      <p id="status">마이크 권한 요청이 표시되면 허용해 주세요.</p>
    </div>
    <script>
      const text = document.getElementById('speechText');
      const status = document.getElementById('status');
      const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      document.getElementById('listen').onclick = () => {
        if (!Recognition) { status.textContent = '이 브라우저는 음성 인식을 지원하지 않습니다. Chrome 또는 Edge를 이용해 주세요.'; return; }
        const recognition = new Recognition();
        recognition.lang = 'ko-KR'; recognition.interimResults = true; recognition.continuous = false;
        recognition.onstart = () => status.textContent = '듣고 있습니다…';
        recognition.onresult = e => { text.value = Array.from(e.results).map(r => r[0].transcript).join(''); };
        recognition.onerror = e => status.textContent = '음성 인식 오류: ' + e.error;
        recognition.onend = () => { if (!status.textContent.startsWith('음성 인식 오류')) status.textContent = '음성 인식이 완료되었습니다.'; };
        recognition.start();
      };
      document.getElementById('speak').onclick = () => {
        if (!text.value.trim()) { status.textContent = '먼저 문장을 입력해 주세요.'; return; }
        speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(text.value);
        utterance.lang = 'ko-KR'; utterance.rate = 1; speechSynthesis.speak(utterance);
        status.textContent = '음성 안내를 재생하고 있습니다.';
      };
      document.getElementById('stop').onclick = () => { speechSynthesis.cancel(); status.textContent = '재생을 정지했습니다.'; };
      document.getElementById('clear').onclick = () => { text.value = ''; speechSynthesis.cancel(); status.textContent = '내용을 지웠습니다.'; };
    </script>
    """,
    height=290,
)

st.info("음성 데이터는 이 화면의 브라우저 기능으로 처리됩니다. 공용 기기에서는 민감한 개인정보를 말하지 마세요.")

