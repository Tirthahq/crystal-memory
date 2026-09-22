#!/bin/sh
# install.sh — put the crystal loop into the repo you are standing in.
#
# POSIX sh on purpose, and verified under dash: the install is the part most likely to break for
# somebody else, so it does not get to depend on bash.
#
# Usage, from inside YOUR repo:
#   sh /path/to/crystal-memory/install.sh
#   CRYSTALS=/path/to/crystal-memory sh -c 'sh "$CRYSTALS/install.sh"'
#
# It creates scripts/, memory/ and scratch/, copies the loop, seeds three starter crystals, and then
# PRINTS the hook wiring rather than editing your settings for you.
#
# ⛔ IT DOES NOT TOUCH YOUR HOOK CONFIG. Writing into a stranger's .claude/settings.json is the kind of
# helpfulness that silently breaks somebody's setup, and an installer that edits config you have not
# read is exactly the class of thing this package exists to warn about. You paste the hooks.
#
# ⛔ AND IT REFUSES TO OVERWRITE. A second run reports what it skipped. If you want the new version of
# a script, delete yours first, deliberately.

set -eu

SRC=${CRYSTALS:-$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)}
DEST=$(pwd)

if [ ! -d "$SRC/scripts" ]; then
  echo "install: cannot find the package scripts at $SRC/scripts" >&2
  echo "         run this from inside your own repo, pointing at the crystal-memory checkout." >&2
  exit 2
fi

if [ "$SRC" = "$DEST" ]; then
  echo "install: you are standing in the package itself." >&2
  echo "         cd into YOUR repo first, then run: sh $SRC/install.sh" >&2
  exit 2
fi

echo "installing the crystal loop"
echo "  from : $SRC"
echo "  into : $DEST"
echo

mkdir -p scripts memory scratch

copied=0
skipped=0
for f in crystal_act.py crystal_registry.py crystallize-stop-hook.py crystal_inject.py \
         crystal_starter.py crystal_scratchpad.py crystal-discriminators.py redact.py; do
  if [ ! -f "$SRC/scripts/$f" ]; then
    echo "  MISSING in package: $f" >&2
    exit 2
  fi
  if [ -f "scripts/$f" ]; then
    echo "  skip  scripts/$f  (already there — delete it first to take the new one)"
    skipped=$((skipped + 1))
  else
    cp "$SRC/scripts/$f" "scripts/$f"
    echo "  copy  scripts/$f"
    copied=$((copied + 1))
  fi
done

seeded=0
mkdir -p memory/crystals
for f in "$SRC"/starter/*.md; do
  [ -e "$f" ] || continue
  base=$(basename "$f")
  if [ -f "memory/crystals/$base" ]; then
    skipped=$((skipped + 1))
  else
    cp "$f" "memory/crystals/$base"
    seeded=$((seeded + 1))
  fi
done
echo "  seed  memory/crystals/  ($seeded starter crystal(s))"

echo
echo "  $copied script(s) copied, $seeded crystal(s) seeded, $skipped left alone"
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

cat <<'NEXT'

NOW WIRE IT. Nothing above changed your settings, and until you paste these the loop
is installed and silent.

In .claude/settings.json:

  {
    "hooks": {
      "PreToolUse":   [ { "hooks": [ { "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/crystal_act.py\" --hook" } ] } ],
      "SessionStart": [ { "hooks": [ { "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/crystal_scratchpad.py\" --boot" } ] } ],
      "Stop":         [ { "hooks": [ { "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/crystallize-stop-hook.py\"" } ] } ]
    }
  }

PreToolUse is the loop: a note arrives in the second before the action it belongs to.
SessionStart is the scratchpad: what you were in the middle of, handed back at boot.
Stop is the capture reminder: it offers a template when a session banked nothing.

See one fire again any time, without waiting for a real mistake:

  python3 scripts/crystal_act.py --act bash --ctx "go test ./... | tail" --dry

Full detail, including the optional maintenance layer and .store-policy.json:  INSTALL.md
NEXT
