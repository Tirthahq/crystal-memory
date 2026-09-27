#!/bin/sh
# record.sh: render every docs/demo/*.tape to a GIF, then prove the recordings carry nothing private.
#
#   sh docs/demo/record.sh          record all three, run the privacy checks, keep the GIFs only if clean
#
# Needs vhs (https://github.com/charmbracelet/vhs). Run from anywhere; it works from the repo root.
#
# WHY THE CHECKS ARE PART OF THE RECORDER. A demo of your own tool records your own machine, and the
# first take of a sister project's demo held the founder's real headlines and personal config while
# looking perfect. A GIF cannot be read for that by eye. So every take is checked from vhs's text
# output, the same frames the GIF shows:
#
#   1. ANTI-CANARY. A unique string is planted in the two real places the fixture overrides: a startup
#      file in the real $HOME, and a job-output file under the real /tmp where the mid-flight scan
#      looks. The published takes must NOT contain it.
#   2. CONTROL ARM. boot.tape is recorded once more with the overrides switched off (DEMO_CONTROL=1).
#      That take MUST contain the canary, or check 1 proves nothing: an absence test that has never
#      been seen to fire passes on an empty frame too.
#   3. PRIVATE STRINGS. This machine's user name, home path, host name and git email, plus key and
#      home-directory shapes, must not appear in any published take.
#
# The canary files are removed on exit. The control take is written to a temp dir and never kept.
set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT" || exit 2
CANARY=CANARY-REAL-HOME-7731          # behind $HOME: the shell startup file
TCANARY=CANARY-REAL-TMP-7731          # behind the real /tmp: the mid-flight job scan
RC_CANARY="$HOME/.crystals-demo-rc"
TMP_CANARY_DIR=/tmp/claude-canary-7731
CTRL=$(mktemp -d 2>/dev/null || mktemp -d -t crystals-ctrl)
fails=0

if [ -e "$RC_CANARY" ]; then
  echo "record: $RC_CANARY already exists; refusing to overwrite it. Move it aside and re-run." >&2
  exit 2
fi
cleanup() { rm -f "$RC_CANARY"; rm -rf "$TMP_CANARY_DIR" "$CTRL"; }
trap cleanup EXIT INT TERM

printf 'echo %s\n' "$CANARY" > "$RC_CANARY"
mkdir -p "$TMP_CANARY_DIR/p/s/tasks"
printf '%s\n' "$TCANARY" > "$TMP_CANARY_DIR/p/s/tasks/$TCANARY.output"

mkdir -p docs/demo/out
for t in install fire boot; do
  DEMO_CONTROL=0 vhs -q "docs/demo/$t.tape"
  rc=$?
  if [ "$rc" -ne 0 ]; then echo "  [FAIL] vhs exited $rc on $t.tape"; fails=$((fails + 1)); fi
done

echo "privacy checks"
for c in "$CANARY" "$TCANARY"; do
  if grep -l "$c" docs/demo/out/*.txt >/dev/null 2>&1; then
    echo "  [FAIL] $c reached a published take:"; grep -l "$c" docs/demo/out/*.txt
    fails=$((fails + 1))
  else
    echo "  [ok] $c ABSENT from every published take"
  fi
done

pats="$HOME|$(id -un)|/Users/|(^|[^A-Za-z0-9_-])/home/|(^|[^A-Za-z])sk-[A-Za-z0-9]{8,}"
h=$(hostname -s 2>/dev/null || true); [ -n "$h" ] && pats="$pats|$h"
e=$(git config --global user.email 2>/dev/null || true); [ -n "$e" ] && pats="$pats|$e"
sed -e "s|\"docs/demo/boot.gif\"|\"$CTRL/boot.gif\"|" -e "s|\"docs/demo/out/boot.txt\"|\"$CTRL/boot.txt\"|" \
  docs/demo/boot.tape > "$CTRL/boot.tape"
DEMO_CONTROL=1 REAL_HOME="$HOME" DEMO=/tmp/crystals-demo-ctrl vhs -q "$CTRL/boot.tape"
rc=$?
if [ "$rc" -ne 0 ]; then echo "  [FAIL] vhs exited $rc on the control take"; fails=$((fails + 1)); fi
for c in "$CANARY" "$TCANARY"; do
  n=$(grep -c "$c" "$CTRL/boot.txt" 2>/dev/null || true)
  if [ "${n:-0}" -gt 0 ]; then
    echo "  [ok] control arm (overrides off): $c APPEARS on $n line(s), so its absence check can fire"
    grep -m 1 -o "[^ ]*$c[^ ]*" "$CTRL/boot.txt" | sed 's/^/         e.g. /'
  else
    echo "  [FAIL] control arm did not show $c; its absence check is unproven"
    fails=$((fails + 1))
  fi
done
pc=$(grep -E -c "$pats" "$CTRL/boot.txt" 2>/dev/null || true)
if [ "${pc:-0}" -gt 0 ]; then
  echo "  [ok] and the private-string check fires on the control take: $pc line(s)"
else
  echo "  [FAIL] the private-string check found nothing even in the control take"; fails=$((fails + 1))
fi
rm -rf /tmp/crystals-demo-ctrl

hits=$(grep -E -c "$pats" docs/demo/out/*.txt 2>/dev/null | awk -F: '{s+=$2} END {print s+0}')
if [ "$hits" -eq 0 ]; then
  echo "  [ok] zero private-string hits in the published takes"
else
  echo "  [FAIL] $hits private-string hit(s):"; grep -n -E "$pats" docs/demo/out/*.txt | head
  fails=$((fails + 1))
fi

for g in docs/demo/*.gif; do
  sz=$(wc -c < "$g" | tr -d ' ')
  if [ "$sz" -gt 2200000 ]; then echo "  [FAIL] $g is $sz bytes (over ~2 MB)"; fails=$((fails + 1));
  else echo "  [ok] $g  $sz bytes"; fi
done

rm -rf /tmp/crystals-demo
if [ "$fails" -eq 0 ]; then echo "RECORD PASS"; exit 0; fi
echo "RECORD FAILED ($fails). Do not publish these GIFs."; exit 1
