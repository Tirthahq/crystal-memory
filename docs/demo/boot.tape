# boot.tape: the two boot-time guards. Lost work is flagged; a compaction loses nothing.
# Record with docs/demo/record.sh (it checks the output for private data). Never run bare.
Output "docs/demo/boot.gif"
Output "docs/demo/out/boot.txt"
Source "docs/demo/common.tape"
Set Height 680

Hide
Type "exec sh docs/demo/fixture.sh boot" Enter
Sleep 5s
Show

Type "# a note written two days ago, never committed, never mentioned anywhere" Enter
Sleep 400ms
Type "git status --short" Enter
Sleep 1500ms
Type "# at session start, the uncommitted guard says so:" Enter
Sleep 400ms
Type "python3 scripts/crystal_uncommitted.py --show" Enter
Sleep 6s
Type "clear" Enter
Sleep 300ms
Type "# the context is about to be compacted. The PreCompact hook runs:" Enter
Sleep 400ms
Type "python3 scripts/crystal_midflight.py --capture < ../payload.json" Enter
Sleep 2s
Type "# the next context starts. SessionStart hands this back, verbatim:" Enter
Sleep 400ms
Type "python3 scripts/crystal_midflight.py --show" Enter
Sleep 9s
