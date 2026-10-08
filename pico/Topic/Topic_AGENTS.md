# Topic/AGENTS.md

## 1. 폴더 개요

`pico/Topic/`는 Pico W가 MQTT 메시지를 발행할 때 사용할 **MQTT Topic 규칙**만 담당한다.

Topic은 어느 실린더의 어떤 데이터인지 구분하기 위한 주소 역할을 한다. MQTT 연결, Broker 정보, QoS, Payload 생성, 센서 수집은 다른 폴더에서 처리한다.

---

## 2. Topic 규칙

Topic은 Pico W와 Raspberry Pi 5가 같은 규칙을 사용해야 한다.

기본 목적:

```text
Pico W
↓
Topic 선택
↓
MQTT Publish
↓
Raspberry Pi 5가 같은 Topic 규칙으로 수신
```

Topic에는 최소한 다음 정보를 구분할 수 있어야 한다.

```text
실린더 식별
데이터 종류
```

최종 Sensor Topic 형식:

```text
smart-cylinder/{cylinder_id}/sensor
```

예: `pico01` → `cylinder_01` → `smart-cylinder/cylinder_01/sensor`.

Topic의 cylinder_id는 Payload cylinder_id와 일치해야 한다. Pi Subscriber는 `smart-cylinder/+/sensor`로 여섯 sensor Topic을 구독할 수 있다.

---

## 3. 실행·검증 명령

PowerShell 기준:

```powershell
cd "C:\Smart Cylinder Case\pico\Topic"
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

현재 독립 실행 파일은 확정되지 않았다.

사용자 승인 없이 `main.py`, `topic.py` 같은 파일을 새로 만들거나 존재하지 않는 실행 명령을 추가하지 않는다.

실제 Topic 구현 파일이 확정되면 이 문서에 복사 실행 가능한 검증 명령을 추가한다.

---

## 4. 코드 스타일

포매터는 **Black**을 사용한다.

네이밍:

- 변수·함수: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`

예:

```python
def build_topic():
    pass


SENSOR_TOPIC_PREFIX = "cylinder"
```

패턴 규칙:

- Topic 생성은 한 곳에서 관리한다.
- 같은 Topic 문자열을 여러 파일에 하드코딩하지 않는다.
- `cylinder_id`를 임의로 변형하지 않는다.
- Topic 생성 함수 안에서 MQTT Publish를 직접 실행하지 않는다.
- Topic 규칙과 Payload 구조를 혼합하지 않는다.

---

## 5. 금지 사항

사용자 승인 없이 다음 행동을 하지 않는다.

- 새 Python 파일 생성
- 새 하위 폴더 생성
- 기존 파일·폴더 삭제·이동·이름 변경
- 최종 Topic 문자열 임의 확정
- 기존 Topic 구조 임의 변경
- `cylinder_id` 규칙 변경
- QoS 1 변경
- Payload 구조 변경
- Broker Host / Port 변경
- MQTT Client 연결 코드 추가
- `sequence_id` 규칙 변경
- `timestamp` 규칙 변경
- 센서 수집 코드 추가
- RMS·FFT 계산
- NORMAL/ABNORMAL 판별
- DB 저장

Topic 변경이 필요하면 먼저 다음 내용을 사용자에게 확인한다.

```text
현재 Topic:
변경하려는 Topic:
변경 이유:
Pico W에 미치는 영향:
Pi 5 수신 코드에 미치는 영향:
```

---

## 6. 커밋·PR 규칙

커밋 메시지 형식:

```text
<type>(topic): <변경 내용>
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
feat(topic): add cylinder sensor topic builder
fix(topic): keep cylinder id in topic
docs(topic): update topic rules
```

PR 전 확인:

- [ ] `python -m black --check .` 통과
- [ ] `python -m compileall .` 통과
- [ ] Pico W와 Pi 5가 같은 Topic 규칙 사용
- [ ] `cylinder_id`가 올바르게 Topic에 반영됨
- [ ] Topic 문자열이 여러 파일에 중복 하드코딩되지 않음
- [ ] QoS·Payload·Broker 역할이 이 폴더에 섞이지 않음
- [ ] 사용자 승인 없는 새 파일·폴더 생성 없음
- [ ] Topic 규칙 변경 시 관련 AGENTS.md도 같은 PR에서 수정

---

## 7. 완료 기준

다음 조건을 모두 만족해야 완료로 판단한다.

1. `python -m black --check .` 성공
2. `python -m compileall .` 성공
3. 동일한 `cylinder_id`에 대해 예상한 Topic 생성
4. Pico W가 해당 Topic으로 Publish 가능
5. Raspberry Pi 5가 같은 Topic을 구독해 메시지 수신 가능
6. Topic 규칙이 한 곳에서 관리됨
7. Topic 외 다른 기능이 이 폴더에 섞이지 않음
8. 사용자 승인 없는 새 파일·폴더 생성 없음
9. 실제 MQTT 통신 검증을 하지 못한 항목은 `미검증`으로 보고

작업 완료 보고:

```text
수정한 파일:
변경 내용:
실행한 검증:
검증 결과:
미검증 항목:
남아 있는 문제:
```
