# Raspberry Pi 5 공압 실린더 상태변화 수집·분석 시스템

## 1. 프로젝트 개요

이 프로젝트는 모든 공압 실린더의 고장을 확정적으로 진단하거나 각 실린더에 장치를 영구 설치하는 상용 시스템을 목표로 하지 않는다. 반복 동작하는 공압 실린더의 소리와 진동을 수집해 평소와 다른 상태변화를 찾고, 작업자가 점검할 대상을 선별하는 **실험용 보조 시스템**의 가능성과 한계를 검증한다.

Raspberry Pi Pico W가 SPH0645 또는 INMP441 센서의 원시 샘플을 MQTT로 전송하면 Raspberry Pi 5가 이를 수신해 검증, SQLite 저장, FFT 및 특징 추출, 후보 모델 추론을 수행한다. 인터넷 연결과 관계없이 로컬 수집·분석이 계속되는 오프라인 우선 구조이며, 필요할 때만 요약 결과를 Supabase에 업로드한다.

이 시스템이 출력하는 결과는 고장 확정 판정이나 안전 판단이 아니다. 결과는 다음과 같은 점검 권고로 해석한다.

- `normal`: 학습·시험한 정상 범위와 유사
- `check_required`: 기준 상태와 다른 변화가 감지되어 점검 권장
- `unknown`: 학습하지 않은 조건이거나 신뢰도가 부족해 판단 보류
- 원인 후보: 실링 누설, 공급압력 변화, 부하 증가 등 실험에서 검증한 범위 안의 참고 정보

## 2. 현장 피드백을 반영한 적용 범위

생산 현장에는 여러 설비에서 발생하는 소음과 진동이 섞여 있으므로, 멀리 떨어진 센서 하나로 특정 실린더만 구분하거나 소리만으로 고장 원인을 확정하기 어렵다. 실린더마다 센서, 통신 장치 및 분석 유닛을 영구 설치하면 비용과 공간, 배선, 유지보수 지점 및 오경보가 늘어날 수 있다. 또한 실린더 이상은 급격한 파손보다 누설음, 속도 저하, 출력 저하처럼 서서히 나타나는 경우가 많아 모든 실린더를 상시 감시할 경제적 필요가 낮을 수 있다.

따라서 본 프로젝트의 우선 적용 시나리오는 다음과 같이 제한한다.

1. 고장 시 공정 정지 영향이 큰 핵심 실린더의 시험적 감시
2. 작업자가 접근하거나 소리를 구분하기 어려운 위치의 점검 보조
3. 계획보전 시 휴대형 또는 임시 부착형 장치를 이용한 순회 측정
4. 동일 동작을 반복해 정상 기준 파형과 비교하기 쉬운 자동화 설비
5. 교육·연구 환경에서 이상 조건별 신호 변화를 비교하는 실험

적용 여부는 검출 성능뿐 아니라 센서 수, 설치 시간, 총비용, 오경보에 따른 점검 부담까지 포함해 판단한다.

## 3. 연구 질문과 성공 기준

핵심 연구 질문은 다음과 같다.

> 배경 소음과 운전 조건의 변화가 있는 환경에서 소리·진동 신호를 이용해 정상 상태와 다른 변화를 어느 정도 안정적으로 검출할 수 있는가?

추가 센서를 사용할 수 있다면 공급압력과 전진·후진 동작시간을 함께 기록한다. 이는 소리·진동의 변화가 실린더 누설 때문인지, 공급압력 저하나 부하 변화 때문인지 구분하는 데 도움이 된다.

성능 평가는 단순 정확도 대신 다음 항목을 사용한다.

- 이상 검출률과 미검출률
- 정상 상태를 이상으로 판단한 오경보율
- 누설, 압력 저하, 부하 변화 등 원인 후보 간 혼동행렬
- 센서 부착 위치가 달라졌을 때의 성능 변화
- 다른 기계의 소음과 진동이 추가됐을 때의 성능 변화
- 새로운 실린더 또는 다른 운전 속도에서의 일반화 성능
- 설치 시간, 센서당 비용 및 유지관리 부담

상용성을 주장하려면 독립된 실제 설비 데이터에서 사전에 정한 목표 성능을 충족해야 한다. 학교 실험 데이터만으로는 현장 적용성이나 고장 예측 능력을 확정하지 않는다.

## 4. 시스템 구성

Pi 5는 Mosquitto 브로커와 Python subscriber를 실행하는 중앙 처리 장치이고, Pico W는 센서값 발행을 담당한다. 인터넷이나 Supabase가 중단돼도 MQTT 수신, 로컬 저장, FFT 및 후보 모델 추론은 계속된다. 업로드 실패 데이터는 재시도 큐에 남긴다.

```text
마이크/진동 센서 → Pico W → Wi-Fi MQTT(QoS 1) → Raspberry Pi 5
  → 패킷 검증 → SQLite ingest_queue 즉시 저장
  → 원시값 저장 → FFT·특징 추출 → 후보 모델 추론
  → 결과와 신뢰도 저장 → 선택적 Supabase 요약 업로드
```

구독 토픽은 다음과 같다.

```text
smartCylinder/+/sph0645/raw
smartCylinder/+/inmp441/raw
smartCylinder/+/status
```

중복 데이터는 `device_id + sensor_type + sequence` 조합으로 차단하고, sequence 누락과 역순 수신을 로그에 기록한다.

## 5. 프로젝트 구조

```text
├── main.py                       # Pi 5 서비스 진입점
├── config/settings.py            # 환경 설정 및 검증
├── src/
│   ├── mqtt_receiver.py          # MQTT QoS 1 subscriber
│   ├── data_validator.py         # 패킷 검증
│   ├── database.py               # WAL SQLite와 트랜잭션
│   ├── fft_processor.py          # DC 제거, Hann window, rFFT
│   ├── feature_extractor.py      # 시간·주파수 특징
│   ├── ml_predictor.py           # 후보 모델 및 연결시험 fallback
│   ├── pipeline.py               # 전체 처리 흐름
│   ├── supabase_uploader.py      # 선택적 업로드 및 재시도
│   └── export_manager.py         # CSV/Excel 내보내기
├── tools/
│   ├── generate_dummy_data.py    # MQTT 시험 데이터 발행
│   ├── export_data.py            # 보고서 생성
│   └── inspect_database.py       # DB 확인
├── tests/                        # 핵심 단위 테스트
├── deploy/smart-cylinder.service # systemd 예제
├── supabase_schema.sql           # 선택적 원격 테이블 SQL
├── data/backup, data/export      # 백업 및 내보내기
├── logs/                         # 회전 로그
└── models/cylinder_model.pkl     # 선택적 검증 후보 모델
```

기존 데모용 웹·알고리즘 파일은 참고 자산이며 운영 데이터 수집 경로에는 사용하지 않는다.

## 6. 데이터 형식

```json
{
  "device_id": "pico01",
  "sensor_type": "sph0645",
  "sample_rate": 1600,
  "cylinder_state": "forward",
  "sequence": 1,
  "timestamp": 1785830000,
  "samples": [125, 128, 131, 129],
  "test_condition": "normal",
  "test_session_id": "session-001"
}
```

`sensor_type`은 현재 `sph0645` 또는 `inmp441`, `cylinder_state`는 `forward`, `backward`, `idle`을 허용한다. 샘플은 유한한 숫자 2~100,000개여야 한다. `test_condition`과 `test_session_id`는 통제된 실험에서만 사용하는 선택 필드다. 실제 운전 중 정답을 모르는 데이터에 임의의 라벨을 붙이지 않는다.

시스템 시간이 잘못된 Pi에서는 timestamp도 틀어지므로 NTP 동기화 상태를 확인한다.

## 7. 실험 설계

최소 실험 조건은 다음과 같다.

1. 정상 상태
2. 통제된 미세 공기 누설
3. 공급압력 저하 또는 변동
4. 부하 또는 동작 저항 증가
5. 속도조절밸브 설정 변화
6. 센서 체결 또는 부착 위치 변화
7. 다른 설비의 배경 소음·외부 진동 추가

실린더의 안전한 압력 범위와 제조사 조건을 지키고, 누설이나 부하를 인위적으로 만들 때는 감독자의 승인을 받는다. 설비 충돌, 로드 손상 또는 위험한 압력 조작으로 고장을 재현하지 않는다.

각 조건은 서로 다른 날짜와 여러 반복 세션으로 수집한다. 같은 연속 기록을 임의로 잘라 학습용과 시험용에 나누면 거의 동일한 파형이 양쪽에 포함되어 성능이 과대평가될 수 있다. 따라서 세션 또는 날짜 단위로 학습·검증·시험 데이터를 분리한다. 가능하다면 한 실린더를 완전히 제외한 외부 시험도 수행한다.

## 8. 특징 추출과 후보 모델

수집한 신호에는 DC 제거와 Hann window를 적용한 후 rFFT를 계산한다. 현재 특징 후보는 다음과 같다.

```text
mean, standard_deviation, rms, maximum, minimum,
peak, peak_to_peak, crest_factor,
dominant_frequency, dominant_amplitude, spectral_energy
```

`models/cylinder_model.pkl`이 없거나 손상돼도 서비스는 종료되지 않고 연결시험용 임계 판정으로 동작한다. 이 fallback 결과는 모델 성능 평가나 고장 판정으로 사용하지 않는다.

검증 후보 모델은 다음 형태로 저장할 수 있다.

```python
joblib.dump({
    "model": trained_model,
    "feature_names": [
        "mean", "standard_deviation", "rms", "maximum", "minimum",
        "peak", "peak_to_peak", "crest_factor",
        "dominant_frequency", "dominant_amplitude", "spectral_energy"
    ],
    "model_version": "cylinder-candidate-2026-08-04"
}, "models/cylinder_model.pkl")
```

모델의 1차 목적은 `normal`, `check_required`, `unknown`을 구분하는 것이다. 실험 데이터가 충분할 때만 `pressure_change`, `seal_leak_candidate`, `load_change` 같은 원인 후보를 부가적으로 제공한다. `internal_wear`처럼 직접 확인하지 않은 상태를 신호만으로 단정하지 않는다.

## 9. 건강점수와 잔여수명 표현

기존의 건강점수나 “예상 잔여수명 90%, 60%, 45%”는 실제 남은 사용기간을 의미하지 않는다. 고장까지의 전체 수명 이력과 정비 결과가 없는 상태에서는 잔여수명 모델을 검증할 수 없기 때문이다.

따라서 화면과 보고서에서는 다음 원칙을 사용한다.

- 모델 확률은 `후보 모델 신뢰도`로 표시한다.
- 임의 점수는 `실험용 상태 점수`로 표시하고 실제 수명과 동일시하지 않는다.
- 잔여수명이라는 명칭은 고장 시점과 정비 이력이 포함된 장기간 데이터로 검증하기 전까지 사용하지 않는다.
- 분류기 신뢰도를 임의 기준값으로 치환해 수명처럼 표시하지 않는다.

3단계 후보 모델을 유지해 비교할 경우에도 출력은 다음처럼 해석한다.

```text
진동 특징 → 진동 상태변화 후보와 신뢰도
소리 특징 → 소리 상태변화 후보와 신뢰도
두 결과 → 종합 점검 필요도(실험값)
```

과거 3,234개 시험 행에서 얻은 분포는 해당 가공 데이터와 당시 모델에 한정된 개발 기록이다. 실제 현장 성능이나 고장률을 나타내지 않으므로 대표 성능 결과로 제시하지 않는다. 성능 보고에는 독립 시험 세트의 혼동행렬, 오경보율, 검출률과 실험 조건을 함께 기록한다.

## 10. 자동 학습 제한

`health_score_target` 같은 정답 필드는 점검이나 통제 실험으로 상태를 확인한 패킷에만 추가한다. 라벨이 없는 패킷은 수집·저장·추론할 수 있지만 학습에는 포함하지 않는다.

신규 라벨 10개만으로 운영 모델을 자동 교체하는 방식은 과적합과 잘못된 라벨 전파 위험이 크다. 10개 단위 재학습은 기능 시험에만 사용한다. 실제 후보 모델 갱신은 다음 조건을 만족한 뒤 사람이 검토하고 승인한다.

- 조건별·세션별 최소 표본 기준 충족
- 학습 데이터와 분리된 시험 데이터 사용
- 기존 모델보다 오경보율과 검출률이 모두 허용 범위 이내
- 결과 파일과 모델 버전 보존
- 검토 전 운영 모델을 덮어쓰지 않음

PyCaret 비교 역시 데이터가 30건을 넘었다는 이유만으로 신뢰할 수 있는 모델을 보장하지 않는다. 표본 수는 신호 구간 개수뿐 아니라 독립된 운전 세션, 날짜, 실린더 수를 기준으로 판단한다.

## 11. Raspberry Pi OS 설치와 실행

64비트 Raspberry Pi OS와 Python 3.13 환경을 기준으로 한다.

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients python3.13 python3.13-venv libopenblas0
sudo systemctl enable --now mosquitto

cd /opt/smart-cylinder-pi5
python3.13 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python main.py
```

Supabase를 사용할 때만 `.env`에 실제 값을 입력한다. 키는 소스에 넣지 않는다. 외부 MQTT 접속을 허용하려면 인증과 방화벽을 구성하고, 익명 포트 1883을 인터넷에 노출하지 않는다.

부팅 자동 실행은 서비스 파일의 사용자와 경로를 실제 환경에 맞춘 뒤 설정한다.

```bash
sudo cp deploy/smart-cylinder.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now smart-cylinder
sudo journalctl -u smart-cylinder -f
```

## 12. Render 웹 배포 환경변수

Render 대시보드에서 해당 Web Service를 열고 **Environment**에 아래 값을 설정한다. 비밀번호, DB 연결 문자열, Supabase 키는 README나 Git 저장소에 기록하지 않는다.

| 변수 | 용도 | Render 설정 방법 |
| --- | --- | --- |
| `DATABASE_URL` | 구매 시리얼과 관리자 설정을 저장하는 PostgreSQL 연결 문자열 | Render PostgreSQL 서비스의 Internal Database URL을 값으로 등록한다. 값이 없거나 연결에 실패하면 로컬 `data/serials.json`을 대신 사용한다. |
| `ADMIN_PASSWORD` | 최초 관리자 비밀번호를 초기화하는 비밀값 | 강한 비밀번호를 Secret 환경변수로 등록한다. 이미 PostgreSQL에 비밀번호 해시가 저장된 뒤에는 이 값만 바꿔도 기존 비밀번호는 바뀌지 않으며, 관리자 화면에서 변경한다. |
| `ALLOWED_ORIGIN` | API CORS를 허용할 웹 프런트엔드 origin | 실제 웹 주소만 입력한다. 예: `https://kang0840.github.io` (경로·끝 슬래시 제외). |
| `PORT` | 웹 서버 수신 포트 | Render가 자동 주입한다. 대시보드에서 직접 설정하지 않는다. 로컬 실행 시에만 기본값 `8000`을 사용한다. |
| `SENSOR_DATABASE_PATH` | Render 프로세스가 직접 읽을 SQLite 센서 DB 경로 | Persistent Disk 등에 실제 DB 파일을 보관·마운트한 경우에만 절대 경로를 지정한다. 설정하지 않으면 기본 경로 `data/smart_cylinder.db`를 확인하고, 파일이 없으면 Supabase에서 분석 결과를 조회한다. |

이 서비스의 Build Command와 Start Command는 다음과 같다.

```text
Build Command: pip install --upgrade pip && pip install -r requirements.txt
Start Command: gunicorn --bind 0.0.0.0:${PORT} server:app
```

로컬에서 웹 화면을 확인할 때는 다음 명령을 사용하고 `http://localhost:8000/`에 접속한다.

```bash
python server.py --host 127.0.0.1 --port 8000
```

## 13. 종단 시험

터미널 1에서 서비스를 실행하고 터미널 2에서 시험 데이터를 발행한다.

```bash
source venv/bin/activate
python tools/generate_dummy_data.py --condition normal --count 5
python tools/generate_dummy_data.py --condition seal_leak --count 5 --device-id pico02
python tools/inspect_database.py
```

더미 데이터는 통신·저장·화면 연결 확인용이며 최종 모델 선정이나 현장 성능의 근거로 사용하지 않는다.

## 14. 저장, 업로드 및 보고서

원시 센서 배열은 SQLite에 보관하고 Supabase에는 필요한 요약값만 업로드한다. 원격 업로드는 선택 기능이며 실패해도 로컬 처리를 유지한다.

SQLite 주요 테이블은 다음과 같다.

- `measurements`: 측정 메타데이터와 sequence
- `raw_sensor_data`: sample index와 원시값
- `feature_data`: 통계 및 FFT 특징
- `ml_results`: 상태변화 후보, 신뢰도, 모델 버전
- `upload_queue`: 업로드 payload와 재시도 상태

DB는 `data/smart_cylinder.db`에 생성하며 기존 행을 자동 삭제하지 않는다. 원시값이 많아지므로 보존 기간과 저장 용량 정책을 별도로 정한다.

보고서는 요청할 때 생성한다.

```bash
python tools/export_data.py
python tools/export_data.py --date 2026-08-04
python tools/export_data.py --date 2026-08-04 --raw-limit 500000
```

Excel 한 시트의 최대 행 수는 1,048,576행이므로 원시값은 날짜 또는 개수로 제한한다. 보고서에는 모델 결과뿐 아니라 센서 위치, 실험 세션, 공급압력, 부하, 배경소음 조건과 실제 확인 결과를 함께 남긴다.

## 15. 테스트와 현장 적용 전 확인

```bash
python -m pytest -q
python -m compileall -q config src tools main.py
```

현장 적용 가능성을 검토하기 전 다음 사항을 확인한다.

- 동일 실린더의 반복 측정에서 결과가 안정적인가?
- 센서를 다시 부착해도 결과가 유지되는가?
- 배경 소음이 추가됐을 때 오경보가 허용 가능한가?
- 공급압력 저하와 실링 누설을 혼동하지 않는가?
- 정상적인 속도·부하 변경을 고장으로 오인하지 않는가?
- 작업자가 직접 확인한 결과와 모델 알림이 일치하는가?
- 설치 및 점검 비용이 얻는 효과보다 크지 않은가?

## 16. 한계와 결론

소리와 진동은 비접촉 또는 간단한 부착으로 수집할 수 있지만, 주변 설비의 영향과 센서 위치 변화에 민감하다. 동일한 신호 변화가 실린더 실링, 밸브, 배관, 공급압력, 부하 또는 체결 상태 등 여러 원인으로 발생할 수 있으므로 단독 신호만으로 부품 고장을 확정할 수 없다.

본 프로젝트의 결과는 “공압 실린더 고장을 자동으로 예측했다”가 아니라 다음 질문에 답하는 형태로 정리한다.

> 제한된 실험 조건에서 상태변화를 어느 정도 검출했으며, 배경 소음과 운전 조건 변화에서 어떤 한계가 나타났는가? 그리고 어떤 핵심 설비나 점검 상황에서 보조 정보로 사용할 가능성이 있는가?

검출 성능이 부족한 경우에도 그 결과는 의미가 있다. 예를 들어 소리 단독 방식이 배경 소음에 취약하다면 진동, 공급압력 또는 동작시간을 결합해야 한다는 결론을 낼 수 있다. 최종 평가는 기술적 정확도와 함께 설치비용, 오경보 부담 및 현장 작업 방식까지 포함한다.

## 17. AI 및 오픈소스 고지

### AI 활용 고지

본 프로젝트의 코드 검토, 문서화 및 개발 보조 과정에 OpenAI ChatGPT와 Codex를 활용했다. AI가 제안한 결과는 개발자가 검토·수정했으며, 센서 데이터 수집·검증, 모델 학습·평가 및 배포 판단의 책임은 프로젝트 개발자에게 있다.

### 주요 오픈소스 라이브러리

다음은 `requirements.txt`의 직접 의존성과 모델 학습 전용 의존성이다. 각 라이브러리의 상세 저작권 고지와 전체 라이선스 조건은 해당 배포본 및 공식 저장소를 따른다.

| 라이브러리 | 사용 목적 | 라이선스 |
| --- | --- | --- |
| NumPy, SciPy, pandas | 수치 연산, 신호 처리, 데이터 처리 | BSD-3-Clause |
| scikit-learn, joblib | 모델 실행 및 모델 직렬화 | BSD-3-Clause |
| Flask, python-dotenv | 웹 API 및 환경변수 로딩 | BSD-3-Clause |
| openpyxl | Excel 결과 저장·내보내기 | MIT |
| Eclipse Paho MQTT (`paho-mqtt`) | MQTT 센서 메시지 수신 | EPL-2.0 또는 EDL-1.0 |
| supabase-py | Supabase 업로드·조회 | MIT |
| pytest | 자동 테스트 | MIT |
| Gunicorn (`gunicorn`) | Render의 WSGI 웹 서버 실행 | MIT |
| Psycopg (`psycopg[binary]`) | Render PostgreSQL 연결 | LGPL-3.0-or-later |
| PyCaret | 모델 학습·비교 자동화(학습 전용) | MIT |
| imbalanced-learn | 불균형 학습 데이터 처리(학습 전용) | MIT |
| category-encoders | 범주형 데이터 인코딩(학습 전용) | BSD-3-Clause |

배포용 wheel에는 직접 의존성 외의 하위 의존성과 추가 라이선스가 포함될 수 있다. 외부 배포 시에는 실제 배포 환경에서 의존성·라이선스 목록을 다시 생성하고, LGPL-3.0-or-later인 Psycopg의 라이선스 고지와 해당 라이선스 사본을 함께 제공한다.
