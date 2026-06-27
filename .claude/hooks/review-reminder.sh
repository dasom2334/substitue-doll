#!/usr/bin/env bash
# git push / gh pr create 직후(PostToolUse) 발동.
# 현재 브랜치에 열린 PR이 있으면 §10 자동 리뷰(/review) 실행을 세션에 상기시킨다.
# 로컬 Claude Code 훅 — GitHub/서버와 무관, API 비용 없음. (내가 실행한 명령에만 발동)
set -euo pipefail

pr="$(gh pr view --json number -q .number 2>/dev/null || true)"
[ -z "$pr" ] && exit 0  # 열린 PR 없으면 조용히 종료

printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"방금 PR #%s 브랜치에 푸시/생성했다. CLAUDE.md §10에 따라 /review 스킬을 실행해 자동 리뷰를 PR #%s에 게시하라. 단, 사용자가 방금 다른 작업을 지시했다면 그 지시를 우선하라."}}' "$pr" "$pr"
