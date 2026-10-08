# WeibullAFT/AGENTS.md

## 역할
실린더 수명 예측 모델은 **Weibull-AFT로 확정**한다.

기본 입력 계획:

```text
RMS
+ FFT 특징값
+ 누적 가동시간
+ 고장 여부
→ Weibull-AFT
→ 예상 수명
```

모델 선택은 확정되어 있다.

현재 부족한 것은 실제 고장 시점, 누적 가동시간, censored 관측 등을 포함한 **수명 학습·검증 데이터**이다.

## 검증
```powershell
cd "C:\Smart Cylinder Case\system\ML\WeibullAFT"
python -m black --check .
python -m compileall .
```

## 보호 규칙
- Weibull-AFT를 다른 모델로 임의 교체하지 않는다.
- 실제 수명 데이터 없이 학습 성능/오차범위/예상 수명을 만들어내지 않는다.
- 최종 Feature 조합, 모델 파라미터, 오차범위는 실제 데이터 검증 후 확정한다.
- 새 파일/폴더는 사용자 승인 후 생성한다.

## 커밋 / PR
`<type>(weibull-aft): <변경 내용>`

수명 데이터가 부족한 상태를 숨기지 않고 모델 입력/출력 구조를 유지해야 완료다.
