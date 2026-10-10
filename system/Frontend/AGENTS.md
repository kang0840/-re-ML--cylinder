# Frontend/AGENTS.md

## 역할
HTML/CSS/JavaScript 기반 웹 대시보드다. 기존 Render Frontend 자산을 유지하며 `https://ml-cylinder.onrender.com/`을 Data worX와 외부 PC·노트북·휴대폰이 사용하는 공개 Web 진입점으로 제공하는 것을 목표로 한다. Frontend 전체 실행 위치를 Pi 또는 Render 중 하나로 임의 확정하지 않는다.

현재 구현 데이터 흐름:

```text
Supabase Realtime
→ Frontend 직접 실시간 갱신

Supabase SELECT
→ Frontend 직접 과거 데이터 조회
```

Backend API는 필요한 서버 기능에 사용할 수 있지만, 실시간 DB 변경 전달의 주 경로는 Supabase Realtime이다.

`order-system.html`의 A/B 공정 주문과 `YOLO TEST / MANUAL TEST` 입력은
같은 Render 서비스의 Backend API만 호출한다. Frontend는 Supabase
Service Role Key 또는 MQTT 계정으로 직접 연결하지 않는다.

하나의 공개 Web 서비스에서 `pico01`~`pico06` 상세 화면, 실린더 상태, STFT 동작음 검출 결과, RMS / FFT 특징, ML Prediction과 센서 그래프를 표시할 수 있어야 한다. 각 상세 화면은 `pico01 → cylinder_01`부터 `pico06 → cylinder_06`까지의 고정 매핑에 따라 선택한 cylinder 데이터만 조회한다.

Data worX의 더보기 UI와 외부 Browser는 동일한 공개 Web 시스템에서 서로 다른 PICO 상세 화면에 동시에 접근할 수 있어야 한다. PICO 상세 Route와 WebSocket / SSE / Supabase Realtime 중 최종 실시간 방식은 실제 Frontend / Backend 구현을 확인한 뒤 결정한다.

## 보안
2026-10-11: STFT 시간 눈금(초)과 ‘구간 내 경과 시간(초)’ 제목은 그래프 내부 하단의 반투명 어두운 띠 위에 표시한다. 띠는 저주파 셀을 삭제하거나 필터링하지 않는 시각적 오버레이이며 실제 상대 시간 좌표를 0초로 재설정하지 않는다. 측정 시각(KST)은 그래프 위 상태 줄에서 별도로 구분한다.

2026-10-10: STFT Preview는 실제 상대 시간·주파수 좌표에 맞춘 선형 축과 중간 눈금, 단위·축 제목, viridis 근사 색상 막대를 표시한다. 색은 센서별 축약 Preview의 최대 진폭 대비 20 log10 상대 dB이며 표시 범위는 −60~0 dB다. 표시 범위는 필터·검출 임계값이 아니고 절대 음압·에너지 비율도 아니다. 진폭 모두 0은 상대 기준 없음으로 표시하고 과거 측정 STALE는 센서 갱신 중지임을 명시한다. 원본·STFT 계산 설정·API/DB·학습 입력은 변경하지 않는다.

2026-10-09: 모니터링의 별도 평가 영역에는 정확도·이상 검출률·오경보율 항목만 표시한다. 현재 연산 미구현·독립 평가 데이터 부족 상태를 명시하고, 숫자·0%·실시간 모델 신뢰도를 평가 성능으로 대체하지 않는다. 기존 핵심 상태 5개와 그래프·조회 경로는 유지하며 평가 API/DB 연결은 별도 승인 전 추가하지 않는다.

2026-10-08: Canonical 웹 조회는 한 번에 하나만 실행하며 완료 후 다음 조회를 예약한다. 요청은 15초 제한, 실패는 최대 30초 backoff, HTTP 429는 최소 60초 대기를 사용한다. 조회 실패는 마지막 정상 그래프를 보존하되 LIVE가 아닌 조회 실패 상태로 표시한다. 이 Frontend 변경은 Wheel 재생성 없이 별도 Web 배포가 필요하며 실제 서버 지연 해소와 구분한다.

0.1.7 웹은 OPERATION Packet RMS·Peak와 Cycle 결과를 별도로 표시한다. 현재 세션의 패킷 순서 그래프는 누락 지점을 연결하거나 0으로 채우지 않으며 균일한 연속 음향 시간으로 해석하지 않는다. 모델·실제 수명 근거가 없으면 대기/데이터 부족을 유지한다.

모니터링 요약 카드는 실린더 동작, 종합 판정, 잔여수명, 두 센서 패킷 RMS, Pi 마지막 수신의 5가지로 표시하며 기존 그래프와 분석·저장 계약은 유지한다.

`monitoring.html`은 기존 2초 Polling API를 확장한 Canonical 조회를 사용한다. 등록된 serial의 Cylinder 매핑은 서버 외부 설정으로 관리하며, 매핑 누락 시 다른 장치를 표시하지 않는다. STFT Preview는 상대 시간·주파수·Magnitude를 표시하는 Web 전용 축약 결과이며 미수신·STALE·기준/모델 부족을 정상 판정과 구분한다.

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
- PICO마다 Render Service를 별도로 만들지 않는다.
- 상세 Route를 확인 없이 `/pico/01` 또는 `/pico?id=pico01` 등으로 확정하지 않는다.
- `192.168.137.xxx` 내부 주소를 공개 Web 주소로 사용하지 않는다.
- 새 파일/폴더는 사용자 승인 후 생성

## 커밋 / PR
`<type>(frontend): <변경 내용>`

Realtime과 과거 조회가 정상 동작하고 민감정보가 노출되지 않아야 완료다.
