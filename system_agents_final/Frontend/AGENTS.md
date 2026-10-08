# Frontend/AGENTS.md

## 역할
HTML/CSS/JavaScript 기반 웹 대시보드이며 Render Static Site에 배포한다.

확정 데이터 흐름:

```text
Supabase Realtime
→ Frontend 직접 실시간 갱신

Supabase SELECT
→ Frontend 직접 과거 데이터 조회
```

Backend API는 필요한 서버 기능에 사용할 수 있지만, 실시간 DB 변경 전달의 주 경로는 Supabase Realtime이다.

## 보안
- Frontend에는 Supabase Secret / Service Role Key를 넣지 않는다.
- 공개 가능한 Key + RLS만 사용한다.
- Secret/비밀번호/관리자 Token을 HTML/JS/로그에 남기지 않는다.

## 스타일
JavaScript는 기존 코드 스타일을 우선하고 블록은 Allman 스타일을 유지한다.

```javascript
function updateCylinderStatus(data)
{
    // ...
}
```

새 Formatter/Framework를 임의 도입하지 않는다.

## 보호 규칙
- React/Vue/Next.js 등으로 임의 전환 금지
- ML/MQTT/Sensor/DB 스키마 기능을 Frontend에 구현 금지
- 실시간 갱신 방식을 임의로 Backend Push로 변경 금지
- 새 파일/폴더는 사용자 승인 후 생성

## 커밋 / PR
`<type>(frontend): <변경 내용>`

Realtime과 과거 조회가 정상 동작하고 민감정보가 노출되지 않아야 완료다.
