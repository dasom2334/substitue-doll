#!/usr/bin/env bash
# git push / gh pr create 직후(PostToolUse) 발동.
# 현재 브랜치에 열린 PR이 있으면 §10 자동 리뷰(/review) 실행을 세션에 상기시킨다.
# 로컬 Claude Code 훅 — GitHub/서버와 무관, API 비용 없음. (내가 실행한 명령에만 발동)
set -euo pipefail

# 훅 실행 cwd가 루트가 아닐 수 있으므로 프로젝트 루트로 이동(없으면 현재 위치 유지).
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || true

# settings의 `if` 필터는 런타임에 따라 신뢰성이 떨어질 수 있으므로, 스크립트가
# PostToolUse 입력(stdin JSON)의 실제 명령을 직접 읽어 git push / gh pr create 일 때만 진행한다.
input="$(cat 2>/dev/null || true)"
if ! command -v jq >/dev/null 2>&1; then
  echo "review-reminder: jq 미설치 — 명령 판별 불가, 상기 누락" >&2
  exit 0
fi
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"
case "$cmd" in
  *"git push"*|*"gh pr create"*) : ;;  # 대상 명령 → 진행
  *) exit 0 ;;                          # 그 외 → 조용히 종료
esac

# gh 미설치/미인증은 "PR 없음"과 구분해 진단을 남긴다(§10: 리뷰를 조용히 버리지 않음).
if ! command -v gh >/dev/null 2>&1; then
  echo "review-reminder: gh 미설치 — 자동 리뷰 상기 누락" >&2
  exit 0
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "review-reminder: gh 미인증 — 자동 리뷰 상기 누락" >&2
  exit 0
fi

pr="$(gh pr view --json number -q .number 2>/dev/null || true)"
[ -z "$pr" ] && exit 0  # 열린 PR 없음(정상) → 조용히 종료

printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"방금 PR #%s 브랜치에 푸시/생성했다. CLAUDE.md §10에 따라 /review 스킬을 실행해 자동 리뷰를 PR #%s에 게시하라. 단, 사용자가 방금 다른 작업을 지시했다면 그 지시를 우선하라."}}' "$pr" "$pr"
