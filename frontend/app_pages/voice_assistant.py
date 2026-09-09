"""브라우저 Web Speech API와 Agent API를 연결한 음성 안내 화면."""

from __future__ import annotations

import json
import os

import streamlit as st
import streamlit.components.v1 as components

from frontend.components.layout import render_sidebar


render_sidebar("voice")
st.title("음성 안내", icon=":material/mic:")
st.caption("말한 질문을 글자로 바꾼 뒤 AI 가이드의 답변을 화면과 음성으로 확인합니다.")

backend_url = os.getenv("BACKEND_URL", "http://192.100.200.198:8000/").rstrip("/")
voice_html = """
<style>
  body{font-family:Pretendard,'Malgun Gothic',sans-serif;color:#0e2a21;margin:0}
  .voice-card{border:1px solid #c9d6ce;border-radius:14px;padding:22px;background:#fff}
  label{display:block;margin:0 0 7px}
  textarea{box-sizing:border-box;width:100%;min-height:105px;padding:14px;border:1px solid #aebfb5;border-radius:9px;font:16px inherit;resize:vertical}
  #answerText{background:#f3f8f5;min-height:120px}
  .buttons{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}
  button{border:0;border-radius:8px;padding:11px 18px;font-weight:700;cursor:pointer;background:#0b5c43;color:#fff}
  button.secondary{background:#e6f2ec;color:#07452f;border:1px solid #9fc4ae}
  button:disabled{opacity:.55;cursor:not-allowed}
  #status{font-size:13px;color:#4a5f57;margin:10px 0 0}
</style>
<div class="voice-card">
  <label for="speechText"><strong>음성으로 입력한 질문</strong></label>
  <textarea id="speechText" placeholder="음성 인식 시작을 누르고 질문을 말하거나, 직접 입력하세요."></textarea>
  <div class="buttons">
    <button id="listen">🎙 음성 인식 시작</button>
    <button id="ask">AI에게 질문하기</button>
    <button class="secondary" id="clear">내용 지우기</button>
  </div>
  <label for="answerText"><strong>AI 안내 답변</strong></label>
  <textarea id="answerText" readonly placeholder="질문을 보내면 AI 가이드 답변이 여기에 표시됩니다."></textarea>
  <div class="buttons">
    <button id="speak" disabled>🔊 답변 듣기</button>
    <button class="secondary" id="stop">정지</button>
  </div>
  <p id="status">마이크 권한 요청이 표시되면 허용해 주세요.</p>
</div>
<script>
  const backendUrl = __BACKEND_URL__;
  const text = document.getElementById('speechText');
  const answer = document.getElementById('answerText');
  const status = document.getElementById('status');
  const listen = document.getElementById('listen');
  const ask = document.getElementById('ask');
  const speak = document.getElementById('speak');
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const sessionStorageKey = 'zoo_voice_agent_session_id';

  function setStatus(message) { status.textContent = message; }
  function setAnswer(value) {
    answer.value = value || '';
    speak.disabled = !answer.value.trim();
  }

  listen.onclick = () => {
    if (!Recognition) {
      setStatus('이 브라우저는 음성 인식을 지원하지 않습니다. Chrome 또는 Edge를 이용해 주세요.');
      return;
    }
    const recognition = new Recognition();
    recognition.lang = 'ko-KR';
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onstart = () => setStatus('듣고 있습니다…');
    recognition.onresult = event => { text.value = Array.from(event.results).map(result => result[0].transcript).join(''); };
    recognition.onerror = event => setStatus('음성 인식 오류: ' + event.error);
    recognition.onend = () => {
      if (!status.textContent.startsWith('음성 인식 오류')) setStatus('음성 인식이 완료되었습니다. AI에게 질문하기를 눌러 주세요.');
    };
    recognition.start();
  };

  ask.onclick = async () => {
    const question = text.value.trim();
    if (!question) { setStatus('먼저 질문을 말하거나 입력해 주세요.'); return; }
    ask.disabled = true;
    setAnswer('');
    setStatus('AI 가이드가 답변을 확인 중입니다…');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 95000);
    try {
      const savedSessionId = localStorage.getItem(sessionStorageKey);
      const payload = {message: question};
      if (savedSessionId) payload.session_id = savedSessionId;
      const response = await fetch(backendUrl + '/api/agent/ask', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || '안내 서버가 요청을 처리하지 못했습니다.');
      if (!body.final_answer || !String(body.final_answer).trim()) throw new Error('AI 답변 형식이 올바르지 않습니다.');
      if (body.session_id) localStorage.setItem(sessionStorageKey, body.session_id);
      setAnswer(String(body.final_answer));
      setStatus('AI 안내 답변을 받았습니다. 답변 듣기를 눌러 음성으로 들을 수 있습니다.');
    } catch (error) {
      const message = error && error.name === 'AbortError'
        ? '응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.'
        : (error.message || '안내 서버에 연결하지 못했습니다.');
      setAnswer('');
      setStatus('답변 오류: ' + message);
    } finally {
      clearTimeout(timeout);
      ask.disabled = false;
    }
  };

  speak.onclick = () => {
    if (!answer.value.trim()) return;
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(answer.value);
    utterance.lang = 'ko-KR';
    utterance.rate = 1;
    speechSynthesis.speak(utterance);
    setStatus('AI 안내 답변을 재생하고 있습니다.');
  };
  stop.onclick = () => { speechSynthesis.cancel(); setStatus('재생을 정지했습니다.'); };
  clear.onclick = () => {
    text.value = '';
    setAnswer('');
    speechSynthesis.cancel();
    setStatus('질문과 답변을 지웠습니다.');
  };
</script>
""".replace("__BACKEND_URL__", json.dumps(backend_url))

components.html(voice_html, height=440)

st.info("음성 데이터는 이 화면의 브라우저 기능으로 처리됩니다. 공용 기기에서는 민감한 개인정보를 말하지 마세요.")
