#!/usr/bin/env bash
#
# cron 이 매달 부르는 스크립트.
#
#   새로 공시된 달만 받아오기 -> CSV 갱신 -> 커밋 -> push -> 컨테이너 재시작
#
# 과거 전체를 다시 긁지 않는다. 받아올 게 없으면 커밋도 push 도 하지 않는다.
#
# 설정은 ~/.config/hoesik/env 에서 읽는다 (README 참고).
#   GITHUB_TOKEN=ghp_...        push 에 쓸 토큰. 없으면 커밋까지만 한다.
#   GIT_AUTHOR_NAME=...         커밋에 쓸 이름·메일 (없으면 저장소 설정)
#   GIT_AUTHOR_EMAIL=...
#   RESTART_CONTAINER=sunrin-web   갱신 후 재시작할 컨테이너. 비우면 재시작 안 함.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${HOESIK_ENV:-$HOME/.config/hoesik/env}"
LOG_DIR="${HOESIK_LOG_DIR:-$HOME/.local/state/hoesik}"
LOG="$LOG_DIR/update.log"

mkdir -p "$LOG_DIR"
exec >>"$LOG" 2>&1

say() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

say "=== 갱신 시작 ($REPO) ==="

# shellcheck source=/dev/null
[ -r "$CONFIG" ] && . "$CONFIG"

PYTHON="${PYTHON:-python3}"
RESTART_CONTAINER="${RESTART_CONTAINER-sunrin-web}"

cd "$REPO" || { say "저장소로 이동 실패"; exit 1; }

# 로컬에 커밋되지 않은 변경이 있으면 멈춘다. 사람이 손대던 걸 덮지 않는다.
if ! git diff --quiet -- data site/data || ! git diff --cached --quiet -- data site/data; then
	say "data/ 에 커밋되지 않은 변경이 있다. 사람이 정리한 뒤 다시 돌린다."
	exit 1
fi

"$PYTHON" scripts/update.py
status=$?

case "$status" in
	0) say "새 행을 받았다. 커밋한다." ;;
	2) say "새로 공시된 달이 없다. 끝낸다."; exit 0 ;;
	*) say "수집 실패 (exit $status). 커밋하지 않는다."; exit "$status" ;;
esac

if git diff --quiet -- data site/data; then
	say "받아온 행이 기존과 같다. 커밋할 게 없다."
	exit 0
fi

export GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-$(git config user.name)}"
export GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-$(git config user.email)}"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

git add data site/data

# 무엇이 늘었는지 한 줄로 남긴다.
summary="$(git diff --cached --numstat -- data site/data \
	| awk '{ added += $1 } END { printf "%d", added }')"

git commit --quiet -m "chore(data): 공시 자료 갱신 ($(date '+%Y-%m'))" \
	-m "새로 공시된 달만 받아 CSV 에 추가했다. 추가된 줄 ${summary}개." \
	-m "Co-Authored-By: AnA <holy9unjinx@gmail.com>" || {
	say "커밋 실패"; exit 1
}
say "커밋했다: $(git log -1 --format='%h %s')"

if [ -n "${GITHUB_TOKEN:-}" ]; then
	# 토큰을 명령줄에 두지 않는다. ps 에 노출되지 않도록 환경변수에서 읽는다.
	if git -c credential.helper= \
		-c credential.helper='!f() { printf "username=x-access-token\npassword=%s\n" "$GITHUB_TOKEN"; }; f' \
		push --quiet origin HEAD:main; then
		say "push 완료"
	else
		say "push 실패. 커밋은 남아 있으니 다음 실행이나 수동 push 로 올라간다."
	fi
else
	say "GITHUB_TOKEN 이 없다. 커밋만 하고 push 는 건너뛴다."
fi

if [ -n "$RESTART_CONTAINER" ] && command -v docker >/dev/null 2>&1; then
	# API 는 시작할 때 CSV 를 메모리에 올리므로 재시작해야 새 행이 보인다.
	if docker restart "$RESTART_CONTAINER" >/dev/null 2>&1; then
		say "컨테이너 재시작: $RESTART_CONTAINER"
	else
		say "컨테이너 재시작 실패: $RESTART_CONTAINER (실행 중이 아닐 수 있다)"
	fi
fi

say "=== 갱신 끝 ==="
