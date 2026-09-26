#!/bin/sh
# install.sh — put the crystal loop into the repo you are standing in.
#
# POSIX sh on purpose, and verified under dash: the install is the part most likely to break for
# somebody else, so it does not get to depend on bash.
#
# Usage, from inside YOUR repo:
#   sh /path/to/crystal-memory/install.sh              first install; never overwrites anything
#   sh /path/to/crystal-memory/install.sh --upgrade    replace the package's own scripts, after a backup
#   sh /path/to/crystal-memory/install.sh --selftest   prove install + upgrade on a throwaway repo
#   CRYSTALS=/path/to/crystal-memory sh -c 'sh "$CRYSTALS/install.sh"'
#
# It creates scripts/, memory/ and scratch/, copies the loop, seeds three starter crystals, and then
# PRINTS the hook wiring rather than editing your settings for you.
#
# ⛔ IT DOES NOT TOUCH YOUR HOOK CONFIG. Writing into a stranger's .claude/settings.json is the kind of
# helpfulness that silently breaks somebody's setup, and an installer that edits config you have not
# read is exactly the class of thing this package exists to warn about. You paste the hooks.
#
# ⛔ A PLAIN RUN REFUSES TO OVERWRITE. A second run reports what it skipped.
#
# ⚠ WHICH IS WHY --upgrade EXISTS. Refusing to overwrite is right for a first install and wrong for
# every install after it: a fix to a package script could never land, and the skip line was the only
# sign. An installed copy just stayed at whatever version it first got, and looked current.
# --upgrade replaces ONLY the package's own scripts (the list below), and only when they differ.
# Every replaced file is copied first to scratch/crystal-upgrade-backup/<stamp>/, so a local edit is
# recoverable and the upgrade can be rolled back by copying the directory back. Your crystals, your
# scratchpad, your handoffs and the starter crystals you may have edited are NEVER touched.

set -eu

SRC=${CRYSTALS:-$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)}
DEST=$(pwd)

# The package-owned scripts. Upgrade replaces these and nothing else.
SCRIPTS="crystal_act.py crystal_registry.py crystallize-stop-hook.py crystal_inject.py
         crystal_starter.py crystal_scratchpad.py crystal_handoff.py crystal_growth.py
         crystal_midflight.py crystal_uncommitted.py crystal-discriminators.py redact.py"

MODE=install
case "${1:-}" in
  "")          ;;
  --upgrade)   MODE=upgrade ;;
  --selftest)  MODE=selftest ;;
  -h|--help)   sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *)           echo "install: unknown option: $1 (try --help)" >&2; exit 2 ;;
esac

if [ ! -d "$SRC/scripts" ]; then
  echo "install: cannot find the package scripts at $SRC/scripts" >&2
  echo "         run this from inside your own repo, pointing at the crystal-memory checkout." >&2
  exit 2
fi

# ── --selftest: install, re-install, and upgrade a throwaway repo, and assert each outcome ──────────
# ⛔ It checks OUTCOMES on disk, not the installer's own report: a skip line that lies and a copy that
# never happened would both pass a check that reads stdout.
if [ "$MODE" = selftest ]; then
  T=$(mktemp -d 2>/dev/null || mktemp -d -t crystals)
  LOG="$T/.log"
  fails=0
  pass() { echo "  [ok] $1"; }
  fail() { echo "  [FAIL] $1"; fails=$((fails + 1)); }
  run()  { (cd "$T/repo" && CRYSTALS="$SRC" sh "$SRC/install.sh" "$@") >"$LOG" 2>&1; }
  mkdir -p "$T/repo"

  run || true
  missing=0
  for f in $SCRIPTS; do cmp -s "$SRC/scripts/$f" "$T/repo/scripts/$f" || missing=$((missing + 1)); done
  [ "$missing" -eq 0 ] && pass "a first install copies every package script, byte-identical" \
                       || fail "a first install left $missing script(s) missing or different"
  grep -q "loop fires     : yes" "$LOG" && pass "and the install proves the loop fires" \
                                        || fail "the install did not prove the loop fires"

  # ⛔ THE WIRING IT PRINTS MUST RUN. The block used to say `crystal_act.py --hook`, a flag the script
  # has never accepted: argparse exits 2 on every tool call and the loop is silent after a clean
  # install. Run each printed hook command, as printed, against the installed tree.
  bad=0
  for cmd in $(sed -n 's/.*"command": "python3 \\"\$CLAUDE_PROJECT_DIR\/\(scripts\/[^\\]*\)\\"\([^"]*\)".*/\1\2/p' "$LOG" | tr ' ' '#'); do
    c=$(echo "$cmd" | tr '#' ' ')
    (cd "$T/repo" && echo '{}' | CLAUDE_PROJECT_DIR="$T/repo" python3 $c >/dev/null 2>&1) || { bad=$((bad + 1)); echo "      printed hook fails: $c"; }
  done
  nprinted=$(grep -c '"command": "python3' "$LOG" || true)
  [ "$nprinted" -ge 5 ] && [ "$bad" -eq 0 ] && pass "every hook command it prints ($nprinted) runs and exits 0" \
                                            || fail "$bad of $nprinted printed hook command(s) fail"

  echo "# a local edit" >> "$T/repo/scripts/crystal_act.py"
  echo "my edit to a starter crystal" >> "$T/repo/memory/crystals/crystal-exit-code-through-a-pipe.md"
  run || true
  grep -q "# a local edit" "$T/repo/scripts/crystal_act.py" \
    && pass "a plain re-run does NOT overwrite a changed script" \
    || fail "a plain re-run overwrote a changed script"
  grep -q "skip  scripts/crystal_act.py" "$LOG" && grep -q -- "--upgrade" "$LOG" \
    && pass "and it says so, pointing at --upgrade" || fail "a plain re-run did not report the skip"

  run --upgrade || true
  cmp -s "$SRC/scripts/crystal_act.py" "$T/repo/scripts/crystal_act.py" \
    && pass "--upgrade REPLACES a package script that differs" \
    || fail "--upgrade left the old script in place"
  bk=$(ls -d "$T/repo/scratch/crystal-upgrade-backup/"* 2>/dev/null | head -1)
  if [ -n "$bk" ] && grep -q "# a local edit" "$bk/scripts/crystal_act.py" 2>/dev/null; then
    pass "and the replaced copy, local edit included, is in the backup"
  else
    fail "the replaced script was not backed up"
  fi
  if [ -n "$bk" ] && [ ! -f "$bk/scripts/crystal_registry.py" ]; then
    pass "an identical script is left alone, not backed up"
  else
    fail "an identical script was backed up or replaced"
  fi
  grep -q "my edit to a starter crystal" "$T/repo/memory/crystals/crystal-exit-code-through-a-pipe.md" \
    && pass "--upgrade never touches crystals, even the seeded starters" \
    || fail "--upgrade overwrote a crystal"

  n_before=$(ls "$T/repo/scratch/crystal-upgrade-backup" | wc -l)
  run --upgrade || true
  n_after=$(ls "$T/repo/scratch/crystal-upgrade-backup" | wc -l)
  [ "$n_before" -eq "$n_after" ] && pass "an upgrade with nothing to change makes no backup" \
                                 || fail "a no-op upgrade still made a backup directory"

  rm "$T/repo/scripts/crystal_midflight.py"
  run --upgrade || true
  [ -f "$T/repo/scripts/crystal_midflight.py" ] && pass "--upgrade also installs a script that is new" \
                                                || fail "--upgrade did not install a missing script"

  # MUTATION: make the upgrade branch skip like a plain install, and the REPLACES row goes red.
  rm -rf "$T"
  if [ "$fails" -eq 0 ]; then echo "SELFTEST PASS"; exit 0; fi
  echo "SELFTEST FAILED ($fails)"; exit 1
fi

if [ "$SRC" = "$DEST" ]; then
  echo "install: you are standing in the package itself." >&2
  echo "         cd into YOUR repo first, then run: sh $SRC/install.sh" >&2
  exit 2
fi

if [ "$MODE" = upgrade ]; then
  echo "upgrading the crystal loop (package scripts only; your crystals are not touched)"
else
  echo "installing the crystal loop"
fi
echo "  from : $SRC"
echo "  into : $DEST"
echo

mkdir -p scripts memory scratch

copied=0
replaced=0
same=0
skipped=0
BACKUP=""
for f in $SCRIPTS; do
  if [ ! -f "$SRC/scripts/$f" ]; then
    echo "  MISSING in package: $f" >&2
    exit 2
  fi
  if [ ! -f "scripts/$f" ]; then
    cp "$SRC/scripts/$f" "scripts/$f"
    echo "  copy  scripts/$f"
    copied=$((copied + 1))
  elif cmp -s "$SRC/scripts/$f" "scripts/$f"; then
    same=$((same + 1))
  elif [ "$MODE" = upgrade ]; then
    if [ -z "$BACKUP" ]; then
      BACKUP="scratch/crystal-upgrade-backup/$(date +%Y%m%d-%H%M%S)-$$"
      mkdir -p "$BACKUP/scripts"
    fi
    cp "scripts/$f" "$BACKUP/scripts/$f"
    cp "$SRC/scripts/$f" "scripts/$f"
    echo "  new   scripts/$f  (old copy in $BACKUP/)"
    replaced=$((replaced + 1))
  else
    echo "  skip  scripts/$f  (yours differs from the package; --upgrade replaces it after a backup)"
    skipped=$((skipped + 1))
  fi
done

seeded=0
mkdir -p memory/crystals
for f in "$SRC"/starter/*.md; do
  [ -e "$f" ] || continue
  base=$(basename "$f")
  if [ -f "memory/crystals/$base" ]; then
    :                                   # a starter you have may carry your edits: never replaced
  else
    cp "$f" "memory/crystals/$base"
    seeded=$((seeded + 1))
  fi
done
echo "  seed  memory/crystals/  ($seeded starter crystal(s))"

echo
echo "  $copied copied, $replaced replaced, $same already current, $skipped differ and were left alone," \
     "$seeded crystal(s) seeded"
if [ -n "$BACKUP" ]; then
  echo "  roll back with: cp $BACKUP/scripts/* scripts/"
fi
if [ "$skipped" -gt 0 ]; then
  echo "  ⚠ $skipped script(s) are NOT the package version. To take it: sh \"$SRC/install.sh\" --upgrade"
fi
echo

# ⛔ PROVE THE LOOP FIRES. NOT THAT THE FILES ARE PRESENT.
# An installer that copies files and says "done" is the exact shape of "I installed it and nothing
# happened" — the failure this package is most afraid of. The first draft of this script printed a
# suggested command for the user to try, and that command matched none of the starter crystals, so it
# would have printed nothing on a correct install. Run a context that MUST match, here, and say so.
if ! python3 scripts/crystal_registry.py list >/dev/null 2>&1; then
  echo "  ⚠ the registry did not load. python3 is required; nothing else is." >&2
else
  n=$(python3 scripts/crystal_registry.py list 2>/dev/null | grep -c . || true)
  echo "  registry loads : $n crystal(s)"
  probe=$(CLAUDE_PROJECT_DIR="$DEST" python3 scripts/crystal_act.py \
            --act bash --ctx "go test ./... | tail" --dry 2>/dev/null || true)
  if [ -n "$probe" ]; then
    echo "  loop fires     : yes"
    echo "$probe" | sed 's/^/                   /'
  else
    echo "  ⚠ loop did NOT fire on a context that should match a starter crystal." >&2
    echo "    The files are installed and the delivery is not working. Please report this," >&2
    echo "    saying which step you were on — it is the most useful bug we can receive." >&2
  fi
fi

if [ "$MODE" = upgrade ]; then
  echo
  echo "Upgrade done. Your hook config was not touched. If this version added a hook, the block a"
  echo "plain install prints shows it: run  sh \"$SRC/install.sh\"  in an empty directory to see it."
  exit 0
fi

# ⛔ THE HOOK COMMANDS BELOW ARE RUN BY --selftest EXACTLY AS PRINTED. The PreToolUse line used to pass
# `--hook`, which crystal_act.py has never accepted: every tool call exited 2 and the loop was silent
# on a clean install, while the "loop fires" probe above (which passes --act) stayed green.
cat <<'NEXT'

NOW WIRE IT. Nothing above changed your settings, and until you paste these the loop
is installed and silent.

In .claude/settings.json:

  {
    "hooks": {
      "PreToolUse":   [ { "hooks": [ { "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/crystal_act.py\"" } ] } ],
      "SessionStart": [ { "hooks": [ { "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/crystal_scratchpad.py\" --boot" },
                                     { "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/crystal_handoff.py\" --boot" },
                                     { "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/crystal_midflight.py\" --boot" },
                                     { "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/crystal_uncommitted.py\" --boot" } ] } ],
      "PreCompact":   [ { "hooks": [ { "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/crystal_midflight.py\" --capture" } ] } ],
      "Stop":         [ { "hooks": [ { "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/crystallize-stop-hook.py\"" } ] } ]
    }
  }

PreToolUse is the loop: a note arrives in the second before the action it belongs to.
SessionStart is the scratchpad: what you were in the middle of, handed back at boot.
It also delivers the last handoff's next action, and stays silent until one is written.
PreCompact saves what a compaction summary loses (your latest words verbatim, jobs in
flight, open loops); the midflight SessionStart line hands it to the next context.
The uncommitted line flags old, hand-written files nothing names: possibly lost work.
Stop is the capture reminder: it offers a template when a session banked nothing.

See one fire again any time, without waiting for a real mistake:

  python3 scripts/crystal_act.py --act bash --ctx "go test ./... | tail" --dry

Later, to take a newer version of the package scripts:  sh "$CRYSTALS/install.sh" --upgrade
Full detail, including the optional maintenance layer and .store-policy.json:  INSTALL.md
NEXT
