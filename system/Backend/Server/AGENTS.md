# Server/AGENTS.md

## 역할
기존 Flask 애플리케이션 시작, Gunicorn 실행과 Render 배포 환경 자산을 담당한다.

```text
현재 Render 배포 구조

Render
→ Gunicorn
→ Flask
→ API
```

현재 개발 방향에서 주요 Backend 처리와 Sensor / Cycle, STFT, RMS / FFT, Feature Extraction, ML Inference는 Raspberry Pi 5에서 실행한다. Render는 `https://ml-cylinder.onrender.com/` 공개 Web 진입점을 유지한다.

기존 Render Flask / Gunicorn 서버가 향후 Gateway 또는 Frontend / API 일부 역할을 담당할지는 실제 구현 단계에서 결정한다. 모든 Backend를 Render에서 실행한다고 강제하지 않으며 Render Backend를 폐기한다고도 확정하지 않는다. Render ↔ Pi의 정확한 연결·중계 방식은 미확정이다.

`sensor_runtime.py`는 MQTT wire 메시지를 제한된 Queue에 넣고 단일 순서 보장 Worker에서 기존 Parser·저장 Service·실시간 Buffer·Canonical STFT 계산을 호출한다. Queue/payload/세션 Dedup/센서별 Buffer 크기와 만료·종료 시간은 외부 `RealtimeConfig`를 필수로 받는다. 누락·세션 변경·입력 손실은 연속 Buffer를 끊고, 초과·만료·분석 오류는 로그와 카운터로 보고한다. 센서 timestamp와 STFT 상대 시간축을 구분하고 최근 장치별 계산 결과만 Memory에 유지한다. Reference가 없으면 REFERENCE_REQUIRED이며 동작 구간·Prediction을 생성하지 않는다. 실제 Pi 성능·배포·기준 Pattern·Threshold·Web 연결 완료를 의미하지 않는다.

## 검증
0.1.7 OPERATION은 STFT·Model 설정이 없어도 Raw 저장 후 ML 공통 함수로 패킷별 평균 제거 RMS·Peak를 계산하여 `runtime.packet_metrics`에 기록한다. MQTT 원본과 학습·Cycle 특징은 수정하지 않는다. 계산·저장 오류는 로그로 보고한다. Pi Adapter의 `--operation`은 기존 외부 설정을 읽고 TRAINING 라벨을 제거하며 학습 모드와 동시에 선택할 수 없다.

0.1.6 Runtime은 원본 Raw 저장 경로를 유지하고 STFT 분석 Buffer의 복사본만 공통 평균 제거 함수로 전처리한다. Cycle 특징도 같은 ML 전처리 함수를 사용하며 Saved Model의 전처리 계약이 없으면 MODEL_REQUIRED로 처리한다. 실제 Pi 배포와 Web 표시 검증은 설치·자동 테스트와 구분한다.

0.1.5 Pi 바탕화면 실행기는 `pi_sensor_runtime.py --interactive`를 호출하는 `.sh`와 `.desktop`을 사용한다. Linux에서 `.bat`를 실행하지 않는다. 외부 `.env`에서 기존 서버 Secret을 읽되 출력·파일 복사하지 않는다. 한 실행기만 잠금으로 실행하고 장치/실험/라벨 확인 후 Subscribe 대기 상태에서 Pico를 새 부팅한다. 실험 전환은 종료와 새 실행·새 Pico 세션을 필요로 한다. 바탕화면 파일 교체와 Wheel 설치 완료는 실제 MQTT/Raw 저장 검증 완료를 의미하지 않는다.

STFT가 없는 Raw-only 수집은 분석 Buffer를 만들지 않으며 외부 자원 제한으로 수신 Queue를 제한한다. 분석용 Queue 만료로 수락한 Raw를 폐기하지 않고 종료 시 제한 시간 내 수락한 Raw 처리를 시도한다. Queue 초과·저장 오류·종료 시간 초과는 영구 저장 보장이 아니며 손실 가능성을 보고한다. STFT 설정 누락은 `CONFIG_REQUIRED`로 표시하고 실제 저장·센서·라벨 검증 전 READY를 선언하지 않는다.

Pi 수신 시각은 Queue 진입 시 기록하고, Sensor 원본과 구분된 `raw_payload.runtime`에 처리 상태를 연결한다. Web Preview는 외부 크기·생성/저장 간격·보관 개수 설정이 있을 때만 축약하며 분석·학습 입력으로 사용하지 않는다. 저장 오류는 별도 로그로 보고하고 MQTT 수신을 종료하지 않는다.

```powershell
cd "C:\Smart Cylinder Case\system\Backend\Server"
python -m black --check .
python -m compileall .
```

실제 실행 파일/모듈 이름이 확정되기 전에는 임의의 실행 명령을 만들지 않는다.

## 보호 규칙
- 기존 Flask/Gunicorn/Render 구조를 확인 없이 삭제하거나 임의 변경하지 않는다.
- Worker/Timeout/Thread 값은 실제 환경 확인 전 임의 확정하지 않는다.
- `.env`, `config.py`, `secrets.py`, `app.py`, `wsgi.py` 등을 사용자 승인 없이 만들지 않는다.
- 서버 Secret은 Frontend/API 응답/로그에 노출하지 않는다.
- Pi 내부 Flask 개발 서버 포트나 `192.168.137.xxx` 주소를 인터넷에 직접 공개하지 않는다.

## 커밋 / PR
`<type>(server): <변경 내용>`

사용 중인 Render 또는 Pi 서버 역할이 실제 구현과 일치하고 API가 연결되며 민감정보가 노출되지 않아야 완료다. 미확정 연결 방식은 완료된 구조로 보고하지 않는다.
