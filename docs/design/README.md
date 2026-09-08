# 디자인 시안

## zoo_guide_mockup_v3.html

관람객 화면(홈, 체험 예약, 동물 정보, 관람 동선 추천, 지도, 먹이주기 일정, 나의 관람 기록, 환경 상태)과
관리자 승인 화면의 정적 HTML 시안이다. 브라우저에서 파일을 직접 열면 동작한다(별도 서버 불필요).

- 데이터는 전부 화면 안 상수(Mock)이며 실제 백엔드 API와 연결되어 있지 않다.
- 팔레트는 에버랜드(everland.com)와 서울대공원(grandpark.seoul.go.kr) 라이브 CSS/화면을 대조해
  WCAG AA(4.5:1) 대비 기준을 통과하도록 재조정했다.
- 동물 실루엣은 [PhyloPic](https://www.phylopic.org/) CC0, 사진은
  [Wikimedia Commons](https://commons.wikimedia.org/)의 CC0/퍼블릭 도메인 이미지를 base64로 내장했다.
  출처는 파일 하단 "관리자 승인" 화면의 크레딧 블록에 명시되어 있다.
- 참고한 UI 레퍼런스: Airbnb 예약 4단계 체크아웃, Google Maps 폴드라인, Ticketmaster 카운트다운,
  SeoulMetro 노선도, 에버랜드 앱(Red Dot Design Award 2024)의 실시간 대기·스마트 예약·관람 기록.

Streamlit 프론트엔드(`frontend/`)에 그대로 이식된 상태는 아니며, 색상·타이포·컴포넌트 방향성을
검토하기 위한 참고용 시안이다.
