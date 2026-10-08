# DataWorX/AGENTS.md

## 역할
Data worX는 Raspberry Pi 5와 PLC 사이의 연동 계층이다.

현재 구조:

```text
Raspberry Pi 5
↔ MQTT QoS 1
↔ Data worX
↔ PLC
```

Data worX/PLC 기능은 프로젝트에서 유지한다.

실린더 전진/후진/Cycle 판단은 Data worX가 아니라 `Sensor/`의 HC-SR04 3개가 담당한다.

PICO별 Web 상세 화면 진입 구조:

```text
Data worX
↓
더보기
↓
PICO 01~06 선택
↓
Render 공개 Web 주소 https://ml-cylinder.onrender.com/
↓
선택한 PICO 상세 화면
```

PICO 상세 화면의 최종 URL Route는 실제 Frontend / Backend 구조를 확인하기 전까지 확정하지 않는다. 하나의 Render 공개 Web 서비스가 PICO를 식별하며 PICO별로 별도 Render Service를 만들지 않는다.

## 담당
- Pi 5와 PLC 사이 데이터 전달
- 설비/PLC 상태 정보 연동
- 필요한 제어 정보 전달
- PICO 01~06 더보기 UI와 공개 Web 상세 화면 진입
- `process_order_bridge.py`에서 Supabase의 미전송 A/B 주문·판단 이벤트를
  로컬 Mosquitto의 `smart-cylinder/process/events`로 QoS 1 Publish

공정 이벤트는 `PROCESS_START`와 `PROCESS_JUDGMENT`를 하나의 Topic에서
`message_type`으로 구분한다. QoS 1 중복 전달에 대비해
`order_id + message_type` 이벤트를 한 번만 설비 명령으로 처리한다.

## 보호 규칙
- Pi 5 ↔ Data worX MQTT QoS 1을 임의 변경하지 않는다.
- Data worX에서 ML 판별을 다시 구현하지 않는다.
- Data worX에서 STFT, RMS, FFT 또는 ML Inference를 계산하지 않는다.
- Cycle 판단을 Data worX에 넣지 않는다.
- Render 공개 URL과 Pi 내부 MQTT Broker 주소를 혼동하지 않는다.
- 향후 통신 방식 변경은 사용자 승인 후 진행한다.
- 새 파일/폴더는 사용자 승인 후 생성

## 커밋 / PR
`<type>(dataworx): <변경 내용>`

Pi 5와 PLC 사이 데이터가 기존 의미 그대로 전달되고 Sensor/ML 역할을 침범하지 않아야 완료다.
