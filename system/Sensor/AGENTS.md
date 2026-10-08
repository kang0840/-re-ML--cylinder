# Sensor/AGENTS.md

## 역할
Raspberry Pi 5에 연결된 **HC-SR04 3개**로 실린더 동작 상태와 Cycle 경계를 판단한다.

```text
HC-SR04 × 3
→ 거리 측정
→ 정지 / 전진 / 후진
→ Cycle 시작 / 종료
```

한 Cycle:

```text
전진 + 후진 = 1 Cycle
```

PLC 신호는 현재 Cycle 판별의 주 신호가 아니다.

Pico의 SPH0645 / INMP441 수집과 역할을 섞지 않는다.

## 검증
```powershell
cd "C:\Smart Cylinder Case\system\Sensor"
python -m black --check .
python -m compileall .
```

실제 센서 검증은 Raspberry Pi 5 + HC-SR04 3개에서 수행한다.

## 보호 규칙
- HC-SR04 3개 구조 유지
- GPIO 번호는 BCM 기준으로 다음과 같이 확정한다.

  ```text
  HC_SR04_1: TRIGGER=17, ECHO=27
  HC_SR04_2: TRIGGER=22, ECHO=23
  HC_SR04_3: TRIGGER=24, ECHO=25
  ```

- 센서 1/2/3의 물리적 역할·설치 위치, 거리 임계값, 허용 오차, Debounce, Polling 주기, timeout, 필터링 방식 및 Cycle 판단 기준은 실제 측정 전 확정하지 않는다.
- `front`, `rear`, `forward`, `backward`, `start`, `end` 같은 역할명은 사용하지 않고 `HC_SR04_1`~`HC_SR04_3`만 사용한다.
- 거리 측정 timeout, state resolver, debounce confirmation, 최대 Cycle 길이는 constructor 인자로 주입한다. `STOP`/`FORWARD`/`RETURN`은 sensor 이름이 아닌 external resolver가 반환하는 motion state다.
- HC-SR04 ECHO 출력은 Pi GPIO에 직접 연결하지 않는다. 실제 배선 시 전압 분배 또는 적절한 Level Shifter를 거쳐 Pi GPIO 입력 전압 수준에 맞춘다.
- RMS/FFT/NORMAL/ABNORMAL 판별 금지
- PLC/Data worX 로직을 Sensor에 중복 구현하지 않는다.
- 새 파일/폴더는 사용자 승인 후 생성

## 커밋 / PR
`<type>(sensor): <변경 내용>`

세 센서로 상태와 Cycle 시작/종료를 안정적으로 구분할 수 있어야 완료다.
