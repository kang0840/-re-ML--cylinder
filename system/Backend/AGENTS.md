# Backend/AGENTS.md

## 역할
Raspberry Pi 5 중심의 Edge Backend와 기존 Render Web Service용 Backend 자산을 담당하는 영역이다.

```text
Backend/
├─ API/
├─ Service/
└─ Server/
```

목표 구조에서 Raspberry Pi 5 Backend는 센서·분석 결과 처리, Supabase 연동과 필요 시 Local API / Web 실행을 담당한다. STFT, RMS, FFT, Feature Extraction, ML Inference와 Cycle 처리는 Pi 영역이며 Render에서 다시 계산하지 않는다.

기존 Render Backend / Gateway는 공개 Web 진입에 필요한 경우 사용할 수 있다. 현재 Flask / API 자산은 삭제하지 않으며, Render Gateway 사용 여부와 Render ↔ Pi의 정확한 연결·중계 방식은 구현 단계 전까지 확정하지 않는다.

현재 구현의 Frontend 실시간 갱신은 Backend Push가 아니라 **Supabase Realtime 직접 연결**을 사용한다. 최종 실시간 Web 방식은 WebSocket / SSE / Supabase Realtime 중 아직 확정하지 않는다.

기존 서버 구조인 `Python + Flask + Gunicorn + Render`는 참고·이전 자산으로 유지하며 모든 Backend가 반드시 Render에서 실행된다고 규정하지 않는다.

현재 A/B 공정 주문 테스트 API는 기존 `ml-cylinder` Render Flask 서비스에
통합한다. Render Backend는 주문과 MANUAL 판정을 Supabase에 기록하고,
내부 MQTT Publish는 Raspberry Pi 5의 Data worX bridge가 담당한다.

MANUAL 및 YOLO 입력은 동일한 A/B 비교·판정 저장 로직을 사용한다.
YOLO 수신은 주문 ID를 명시하고 기존 카메라 서버 인증을 사용하며,
미검출·불명확한 검출을 즉시 NG로 저장하거나 새 Timeout 정책을 만들지 않는다.

## 검증
```powershell
cd "C:\Smart Cylinder Case\system\Backend"
python -m black --check .
python -m compileall .
```

## 보호 규칙
- Flask를 다른 프레임워크로 임의 교체하지 않는다.
- 기존 API 경로/응답을 임의 변경하지 않는다.
- Supabase Secret / Service Role Key는 Backend에서만 사용한다.
- ML, MQTT, Sensor 로직을 Backend에 중복 구현하지 않는다.
- Render에서 Pi의 STFT, RMS, FFT, Feature Extraction 또는 ML Inference를 중복 수행하지 않는다.
- Render가 `192.168.137.xxx` 내부 주소에 직접 접속한다고 가정하지 않는다.
- 새 파일/폴더는 사용자 승인 후 생성한다.

## 커밋 / PR
`<type>(backend): <변경 내용>`

API/Service/Server 역할 분리가 유지되고 기존 Backend 기능이 깨지지 않아야 완료다.
