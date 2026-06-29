# substitue-doll

> 과거 대화로 **말투를 학습**하고 사용자를 능동적으로 인도하는 **AI 에이전트**. 두 가지 쓰임을 목표로 한다:
> - **모드1** — 내 말투로 **대신 답해주는** 감정쓰레기통/친밀도/공감 도우미 (대답하기 곤란한 상황에서 추천 답변을 생성·어드바이징)
> - **모드2** — 떠나보낸 대상(전 연인·반려동물·고인 등)의 **대리자**와 대화하며 이별·상실의 마음을 정리

[![CI](https://github.com/dasom2334/substitue-doll/actions/workflows/ci.yml/badge.svg)](https://github.com/dasom2334/substitue-doll/actions/workflows/ci.yml)

> ⚠️ **초기 개발 중**(early WIP). 로드맵은 [PLAN.md](PLAN.md), 개발 규칙은 [CLAUDE.md](CLAUDE.md) 참고.

## 무엇인가

단순한 말투 재현 도구가 아니라, 사용자를 **능동적으로 인도하는** 에이전트다. 핵심은 말투가 아니라 **하네스**(능동적 인도 행동)이고, 말투 재현은 그 그릇일 뿐이다.

- 두 모드 공통: **과거 대화로 말투를 학습(RAG)** 해 그 말투로 **답변을 "생성"만** 한다. 자동 발송/실행은 하지 않는다.
- **(모드2)** 하네스의 목적을 **"이별·상실 마음 정리를 돕는"** 것으로 고정한다 — 고찰을 돕고, 나쁜 방향의 생각을 잡아주고, 객관적으로 보게 하며, 힘든 과정을 건강하게 이겨내도록 함께하는 **동반자**.
- **(모드2) 과몰입 방지:** 대리자는 처음부터 "나는 그 대상의 대리자"임을 고지하고 대화 내내 분명히 한다. 사용자가 대리자를 진짜 그 대상처럼 여겨 빠져들지 않도록 흐름 자체에 방지를 둔다.

## 모드 구조

| 모드 | 내용 | 상태 |
|---|---|---|
| **모드1** | 감정쓰레기통/공감 — 내 말투를 학습해 대답하기 곤란한 상황에서 추천 답변을 생성·어드바이징("대리 출동") | 개발 중 |
| **모드2** | 상실·이별 정리 대리자 (프로덕션 지향, 하네스의 본진) | 설계 |
| **모드3** | 다채널/실시간 (필요 시) | 보류 |

## 동작 방식

- **RAG**: 과거 대화를 정제해 저장하고, 새 상황에 대해 관련 과거 대화를 검색(top-k)해 근거로 답변 초안을 생성한다. (모델 파인튜닝이 아니다.)
- **자유 형식 입력**: 평문이든 대화 로그든 무엇이든 받는다. 한 입력에 평문과 여러 포맷의 대화 기록이 섞여 와도, 구조를 **추론**해(특정 메신저에 묶지 않음) 추출한다.

## 아키텍처

엔진과 껍데기(인터페이스)를 분리한다.

```
core/        ← 순수 도메인. UI/API/입출력을 모른다. "입력 → 결과" 함수·모델.
  ↑ 얇게 호출만 하는 껍데기들 (공존 가능)
cli.py        (MVP / 엔진 검증)
streamlit 앱   (모드1 데모)
fastapi 앱     (모드2 프로덕션)
```

- **저장**: 1단계는 **SQLite**(파일 티어). 2단계 벡터 검색은 sqlite-vec. 모드2 프로덕션에서 Postgres+pgvector로 승격(저장소는 인터페이스 뒤라 어댑터 교체만으로).

## 데이터·윤리 원칙

- **정제 먼저.** 사적·민감 정보는 제거하고, 원본 raw는 영구 저장하지 않는다. (직업·MBTI 등 품질에 필요한 특정 정보는 보존.)
- 정제 구현 전(스텁 단계)에는 **합성/더미 데이터로만** 테스트한다.
- 회복 지표 등은 임상 진단이 아니라 **휴리스틱 신호**다.

## 프로젝트 구조

```
substitue_doll/
  core/                 # 순수 도메인 (CLAUDE.md §8)
    record.py           #   RefinedRecord (정제물 모델)
    repository.py       #   Repository 포트(Protocol)
  refine/               # 정제 — 현재 스텁(no-op)
    stub.py
  store/                # 어댑터
    sqlite_repository.py #   SQLite 구현
tests/                  # 합성 더미 기반 테스트
.claude/                # 리뷰어 에이전트 · 자동 리뷰 훅 · /review 스킬
PLAN.md                 # 로드맵
CLAUDE.md               # 개발 실행 규칙
```

## 개발

요구: Python 3.10+

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

품질 게이트 (커밋 전 전부 통과 필수, pre-commit이 강제):

```bash
ruff check . && ruff format --check .
mypy substitue_doll tests
pytest
```

## 워크플로우

- `main`에 직접 커밋하지 않는다. 모든 작업은 feature 브랜치 → **PR**.
- PR 푸시 후 **자동 리뷰**가 로컬 서브에이전트로 돈다: `reviewer-correctness`(정확성·안전 게이트) → 통과 시 `reviewer-design`(설계·가독성 권고) → 결과를 PR 코멘트로 게시.
- 머지는 사람이 한다. CI(GitHub Actions)가 ruff/mypy/pytest를 required check로 검증.

## 진행 상황

- ✅ 0단계: 개발 게이트(ruff/mypy/pytest + pre-commit), CI, 브랜치 보호, 정제 스텁
- 🚧 1단계(모드1 인입): 1A 정제물 스키마 + SQLite 저장소 — 진행 중

---

자세한 단계별 계획·미정 사항은 [PLAN.md](PLAN.md), 매 작업에 적용되는 규칙은 [CLAUDE.md](CLAUDE.md)에 있다.
