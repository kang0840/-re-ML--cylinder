# Message/AGENTS.md

## 1. 폴더 개요

`pico/Message/`는 Pico W가 Raspberry Pi 5의 MQTT Broker로 보낼 센서 메시지(Payload)를 구성하고 검증하는 코드만 담당한다.

센서 측정, Wi-Fi 연결, MQTT 연결·Publish, QoS 처리, Topic 결정, 재연결은 이 폴더에서 구현하지 않는다.

---

## 2. 메시지 규칙

메시지에는 최소한 다음 정보가 포함되어야 한다.

```text
cylinder_id
session_id
sequence_id
timestamp
SPH0645 데이터
INMP441 데이터
```

실제 필드명과 자료형은 프로젝트에서 확정된 규격을 따른다.

현재 `sph0645`와 `inmp441`은 다음 compact sensor chunk object다.

```text
sample_rate
sample_format = s32le
sample_count
encoding = base64
data
```

SPH0645 sample_rate는 4000 Hz, INMP441 sample_rate는 16000 Hz다. PCM은 JSON integer array가 아닌 signed 32-bit little-endian binary를 Base64로 인코딩한다.

`Message/`의 역할은 다음으로 제한한다.

- 전달받은 센서값으로 Payload 생성
- 필수 필드 누락 확인
- 자료형 및 값 형식 확인
- MQTT 전송 가능한 형태로 변환
- 잘못된 메시지 생성 방지

다음 기능은 다른 폴더의 책임이다.

```text
sensor/       → SPH0645·INMP441 데이터 측정
sequence_id/  → sequence_id 생성·증가
timestamp/    → timestamp 생성
Topic/        → MQTT Topic 결정
QoS/          → QoS 1 규칙
MQTT/         → 실제 MQTT 연결·Publish
```

timestamp는 `timestamp/`의 NTP 동기화가 완료된 뒤 전달된 ISO 8601 `+09:00` 문자열만 허용한다. Message는 동기화 자체를 수행하지 않으며, 정상 timestamp가 없으면 Payload 생성에 실패해야 한다.

---

## 3. 실행·검증 명령

PowerShell에서 실행한다.

```powershell
cd "C:\Smart Cylinder Case\pico\Message"
```

Black 적용:

```powershell
python -m black .
```

Black 검사:

```powershell
python -m black --check .
```

Python 문법 검사:

```powershell
python -m compileall .
```

이 폴더에는 아직 독립 실행용 진입 파일이 확정되지 않았으므로 임의의 `main.py`나 테스트 실행 파일을 만들지 않는다.

실행 진입점이 확정되면 이 AGENTS.md에 실제 명령을 추가한다.

---

## 4. 코드 스타일

포매터는 **Black**을 사용한다.

네이밍:

- 변수·함수: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`

예:

```python
def build_payload():
    pass


def validate_payload():
    pass


REQUIRED_FIELDS = ()
```

함수는 역할을 분리한다.

```text
Payload 생성
Payload 검증
직렬화
```

를 하나의 거대한 함수에 모두 넣지 않는다.

---

## 5. 금지 사항

사용자 승인 없이 다음 행동을 하지 않는다.

- 새 Python 파일 생성
- 새 하위 폴더 생성
- 기존 파일 삭제·이동·이름 변경
- MQTT Topic 결정 로직 추가
- QoS 설정 추가
- Wi-Fi 연결 코드 추가
- MQTT Broker/Client 연결 코드 추가
- 센서 직접 읽기
- `sequence_id` 생성 규칙 변경
- `timestamp` 생성 규칙 변경
- RMS·FFT 계산
- NORMAL/ABNORMAL 판별
- DB 저장
- Payload 필드 임의 추가·삭제·이름 변경
- Secret Key, 비밀번호, Token 하드코딩

새 파일이 필요하면 먼저 다음 내용을 사용자에게 확인한다.

```text
새 파일:
필요한 이유:
기존 파일로 해결할 수 없는 이유:
영향받는 메시지 규격:
```

---

## 6. 커밋·PR 규칙

커밋 메시지 형식:

```text
<type>(message): <변경 내용>
```

허용 type:

```text
feat
fix
refactor
test
docs
chore
```

예:

```text
feat(message): build pico sensor payload
fix(message): reject payload with missing sequence id
docs(message): update payload rules
```

PR 전 확인:

- [ ] `python -m black --check .` 통과
- [ ] `python -m compileall .` 통과
- [ ] 필수 메시지 필드 유지
- [ ] 기존 Payload 규격과 호환
- [ ] Topic/QoS/MQTT 연결 로직이 섞이지 않음
- [ ] 사용자 승인 없는 새 파일·폴더 생성 없음
- [ ] 민감정보가 Payload 또는 로그에 포함되지 않음
- [ ] 메시지 규격이 바뀌었다면 관련 AGENTS.md도 같은 PR에서 수정

---

## 7. 완료 기준

## 세션 Payload 규칙

Payload 필수값에 `session_id`를 포함한다. 필수 식별값은 `cylinder_id`, `session_id`, `sequence_id`, `timestamp`다. `cycle_id`는 Pico Payload에 포함하지 않는다.

다음 조건을 모두 만족해야 작업 완료로 판단한다.

1. `python -m black --check .` 성공
2. `python -m compileall .` 성공
3. 정상 입력에서 필수 필드가 포함된 Payload 생성
4. 필수 필드가 누락된 입력을 정상 메시지로 처리하지 않음
5. 기존 메시지 필드명과 구조를 임의로 변경하지 않음
6. Message 폴더 밖의 역할이 코드에 섞이지 않음
7. 사용자 승인 없는 새 파일·폴더 생성 없음
8. 실행하지 않은 검증은 `미검증`으로 명시

작업 완료 보고 형식:

```text
수정한 파일:
변경 내용:
실행한 검증:
검증 결과:
미검증 항목:
남아 있는 문제:
```
