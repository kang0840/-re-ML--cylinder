# timestamp/AGENTS.md

## 1. 폴더 개요

`pico/timestamp/`는 Pico W가 MQTT 메시지에 넣을 **측정 시간 정보(timestamp)를 생성·관리하는 코드**만 담당한다.

Pico W는 인터넷에서 시간 정보를 동기화한 뒤 센서 데이터가 측정된 시간을 메시지에 포함한다. MQTT 연결, Topic, QoS, Payload 전체 구성, 센서 수집, `sequence_id` 생성은 다른 폴더에서 처리한다.

---

## 2. timestamp 규칙

기본 역할:

```text
인터넷 시간 동기화
↓
현재 시간 확인
↓
센서 데이터에 사용할 timestamp 생성
↓
Message/로 전달
```

timestamp는 다음 용도로 사용한다.

- 센서 데이터의 측정 시점 기록
- 시간 순서 확인
- 같은 실린더 데이터의 시간 변화 분석
- DB 저장 시 측정 시간 기록
- 이후 RMS·FFT·수명 분석 데이터와 시간 기준 연결

`sequence_id`는 전송 순서를 구분하고, `timestamp`는 실제 측정 시간을 기록한다.

두 값의 역할을 섞지 않는다.

### 확정 정책

- timestamp는 ISO 8601 `+09:00` 문자열이다. 예: `2026-09-27T10:15:30+09:00`.
- Pico는 Wi-Fi 연결 뒤 NTP 동기화를 시도하고, 성공 후에만 정상 센서 Payload를 Publish한다.
- NTP 실패 시 1970년, 기본 RTC, 임의 시간을 정상 timestamp로 Publish하지 않는다.
- Wi-Fi/MQTT 재연결은 이미 동기화된 시간 상태를 초기화하지 않는다.
- offline drift 보정과 동기화 주기 세부값은 현재 구현하지 않으며 실제 Pico W 검증 항목이다.

---

## 3. 실행·검증 명령

PowerShell 기준:

```powershell
cd "C:\Smart Cylinder Case\pico\timestamp"
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

사용자 승인 없이 `main.py`, `timestamp.py` 같은 파일을 새로 만들거나 존재하지 않는 실행 명령을 추가하지 않는다.

실제 실행 파일이 확정되면 이 문서에 복사 실행 가능한 검증 명령을 추가한다.

구현 모듈은 `timestamp.py`다. `TimestampProvider`는 부팅 시 `time_synced=False`로 시작하고 `ntptime.settime()` 성공 후에만 `time_synced=True`로 바꾼다. `get_timestamp()`는 동기화 전 예외를 내며, 동기화 후 UTC RTC를 `+09:00` ISO 8601 문자열로 변환한다. Wi-Fi/MQTT 재연결은 이 상태를 초기화하지 않는다.

---

## 4. 코드 스타일

포매터는 **Black**을 사용한다.

네이밍:

- 변수·함수: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`

예:

```python
def sync_time():
    pass


def get_timestamp():
    pass
```

패턴 규칙:

- 시간 동기화와 timestamp 생성 역할을 구분한다.
- 센서 측정 함수 안에서 시간 동기화 전체 로직을 중복 구현하지 않는다.
- MQTT Publish 함수 안에서 timestamp 생성 규칙을 중복 구현하지 않는다.
- 동기화 실패를 무조건 숨기지 않고 확인 가능한 상태로 처리한다.
- 잘못된 시간값을 정상 timestamp처럼 전달하지 않는다.

---

## 5. 금지 사항

사용자 승인 없이 다음 행동을 하지 않는다.

- 새 Python 파일 생성
- 새 하위 폴더 생성
- 기존 파일·폴더 삭제·이동·이름 변경
- timestamp 형식 임의 변경
- 타임존 규칙 임의 변경
- 동기화 주기 임의 확정
- 오프라인 시간 보정 방식 임의 추가
- `sequence_id` 생성 규칙 변경
- Topic 규칙 변경
- QoS 1 변경
- MQTT Broker/Client 연결 코드 추가
- Payload 전체 구조 변경
- 센서 수집 코드 추가
- RMS·FFT 계산
- NORMAL/ABNORMAL 판별
- DB 저장
- Secret Key, 비밀번호, Token 하드코딩

timestamp 정책 변경이 필요하면 먼저 다음 내용을 사용자에게 확인한다.

```text
변경하려는 규칙:
현재 동작:
변경하려는 동작:
필요한 이유:
Message/ 및 Pi 5에 미치는 영향:
```

---

## 6. 커밋·PR 규칙

커밋 메시지 형식:

```text
<type>(timestamp): <변경 내용>
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
feat(timestamp): add internet time sync
fix(timestamp): reject invalid time value
docs(timestamp): update timestamp rules
```

PR 전 확인:

- [ ] `python -m black --check .` 통과
- [ ] `python -m compileall .` 통과
- [ ] 인터넷 시간 동기화 결과 확인
- [ ] 생성된 timestamp가 측정 시점과 연결됨
- [ ] `sequence_id` 역할과 섞이지 않음
- [ ] 미확정 timestamp 형식·타임존 정책을 임의 확정하지 않음
- [ ] 사용자 승인 없는 새 파일·폴더 생성 없음
- [ ] timestamp 규칙 변경 시 관련 AGENTS.md도 같은 PR에서 수정

---

## 7. 완료 기준

다음 조건을 모두 만족해야 완료로 판단한다.

1. `python -m black --check .` 성공
2. `python -m compileall .` 성공
3. Pico W가 인터넷 시간 정보를 정상적으로 동기화
4. 센서 데이터에 사용할 timestamp 생성 가능
5. 연속 측정 데이터의 시간 순서를 확인할 수 있음
6. 잘못된 시간값을 정상 timestamp로 사용하지 않음
7. `sequence_id`, MQTT, 센서 수집 등 다른 역할이 이 폴더에 섞이지 않음
8. 사용자 승인 없는 새 파일·폴더 생성 없음
9. 실제 Pico W 검증을 하지 못한 항목은 `미검증`으로 보고

작업 완료 보고:

```text
수정한 파일:
변경 내용:
실행한 검증:
검증 결과:
미검증 항목:
남아 있는 문제:
```
