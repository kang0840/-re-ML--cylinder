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

## 담당
- Pi 5와 PLC 사이 데이터 전달
- 설비/PLC 상태 정보 연동
- 필요한 제어 정보 전달

## 보호 규칙
- Pi 5 ↔ Data worX MQTT QoS 1을 임의 변경하지 않는다.
- Data worX에서 ML 판별을 다시 구현하지 않는다.
- Cycle 판단을 Data worX에 넣지 않는다.
- 향후 통신 방식 변경은 사용자 승인 후 진행한다.
- 새 파일/폴더는 사용자 승인 후 생성

## 커밋 / PR
`<type>(dataworx): <변경 내용>`

Pi 5와 PLC 사이 데이터가 기존 의미 그대로 전달되고 Sensor/ML 역할을 침범하지 않아야 완료다.
