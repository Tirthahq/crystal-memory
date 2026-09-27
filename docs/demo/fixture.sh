#!/bin/sh
# fixture.sh STAGE: build a throwaway world for one recording, then become its shell.
#
# Every tape in docs/demo/ runs this (hidden) as its first line, so the camera only ever sees:
#   HOME      a fresh directory under $DEMO, with a neutral git identity and a plain `$ ` prompt
#   package   a copy of this repo's tracked files at ~/crystal-memory, so no real path is printed
#   temp      CRYSTAL_TASK_ROOTS points the mid-flight job scan at a fixture dir, not the real /tmp
#   env       `env -i`: nothing from the recording machine's environment is inherited
#
# STAGE is one of: install (empty home), fire (package installed in ~/my-project), boot (installed,
# plus an old forgotten file and a session transcript for the mid-flight capture).
#
# DEMO_CONTROL=1 is the control arm used by record.sh: it keeps the REAL home and the real temp
# roots, so the anti-canary planted there has to show up. Never record a published GIF with it.
set -eu

STAGE=${1:?usage: fixture.sh install|fire|boot}
PKG=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
DEMO=${DEMO:-/tmp/crystals-demo}

rm -rf "$DEMO"
mkdir -p "$DEMO/home" "$DEMO/tasks"
H="$DEMO/home"

# The package, as tracked files only (no scratch/, no caches, nothing untracked).
mkdir -p "$H/crystal-memory"
(cd "$PKG" && git ls-files -z | xargs -0 tar -cf -) | (cd "$H/crystal-memory" && tar -xf -)

cat > "$H/.gitconfig" <<'EOF'
[user]
	name = Demo User
	email = demo@example.com
[init]
	defaultBranch = main
[advice]
	detachedHead = false
EOF

cat > "$H/.crystals-demo-rc" <<'EOF'
PS1='$ '
HISTFILE=/dev/null
export BASH_SILENCE_DEPRECATION_WARNING=1
EOF

# From here on the fixture's own git work (the demo project's commits) sees only the fixture home.
REAL_HOME_SEEN=$HOME
export HOME="$H" XDG_CONFIG_HOME="$H/.config" GIT_CONFIG_NOSYSTEM=1
unset GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL GIT_DIR GIT_WORK_TREE

setup_project() {
  mkdir -p "$H/my-project"
  cd "$H/my-project"
  git init -q
  printf '# my project\n' > README.md
  git add README.md
  git commit -qm "first commit"
  sh "$H/crystal-memory/install.sh" >/dev/null 2>&1
  printf 'scratch/\n' > .gitignore
  git add -A
  git commit -qm "add the crystal loop"
}

case "$STAGE" in
  install)
    echo 'cd ~' >> "$H/.crystals-demo-rc"
    ;;
  fire)
    setup_project
    echo 'cd ~/my-project' >> "$H/.crystals-demo-rc"
    ;;
  boot)
    setup_project
    # A note written two days ago and never committed or mentioned: the shape of lost work.
    mkdir -p notes
    printf 'Retry logic for the upload job: back off 2s, 4s, 8s, then give up and alert.\n' > notes/retry-plan.md
    touch -t "$(date -v-2d +%Y%m%d%H%M 2>/dev/null || date -d '2 days ago' +%Y%m%d%H%M)" notes/retry-plan.md
    # A session transcript, in the harness's jsonl shape, for the PreCompact capture to read.
    cat > "$DEMO/session.jsonl" <<'EOF'
{"type":"user","timestamp":"2026-09-26T14:02:11Z","message":{"content":"Add retries to the upload job."}}
{"type":"user","timestamp":"2026-09-26T14:20:40Z","message":{"content":"Keep the old endpoint working until Friday, the mobile app still calls it."}}
{"type":"attachment","timestamp":"2026-09-26T14:31:05Z","attachment":{"type":"queued_command","prompt":"Wait, do not delete the v1 route, just mark it deprecated."}}
EOF
    printf '{"transcript_path": "%s/session.jsonl"}\n' "$DEMO" > "$H/payload.json"
    # A background job still writing, in the harness's task-output layout.
    mkdir -p "$DEMO/tasks/claude-demo/my-project/session-1/tasks"
    printf 'running migration 3 of 7...\n' > "$DEMO/tasks/claude-demo/my-project/session-1/tasks/migrate.output"
    echo 'cd ~/my-project' >> "$H/.crystals-demo-rc"
    ;;
  *) echo "fixture.sh: unknown stage $STAGE" >&2; exit 2 ;;
esac
echo 'clear' >> "$H/.crystals-demo-rc"

# The shell reads its startup file from $HOME/.crystals-demo-rc, so WHICH home it gets decides what
# it reads. That is the seam the anti-canary in record.sh sits behind.
PY_DIR=$(dirname "$(command -v python3)")
if [ "${DEMO_CONTROL:-0}" = 1 ]; then
  RH=${REAL_HOME:-$REAL_HOME_SEEN}
  exec env -i HOME="$RH" PATH="$PY_DIR:/usr/bin:/bin" TERM=xterm-256color LANG=en_US.UTF-8 \
    DEMO="$DEMO" bash --rcfile "$RH/.crystals-demo-rc" -i
fi
exec env -i HOME="$H" PATH="$PY_DIR:/usr/bin:/bin" TERM=xterm-256color LANG=en_US.UTF-8 \
  CRYSTAL_TASK_ROOTS="$DEMO/tasks" DEMO="$DEMO" bash --rcfile "$H/.crystals-demo-rc" -i
