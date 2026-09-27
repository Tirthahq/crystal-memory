# fire.tape: a crystal arrives in the second before the command it is about.
# Record with docs/demo/record.sh (it checks the output for private data). Never run bare.
Output "docs/demo/fire.gif"
Output "docs/demo/out/fire.txt"
Source "docs/demo/common.tape"
Set Height 760

Hide
Type "exec sh docs/demo/fixture.sh fire" Enter
Sleep 5s
Show

Type "# a crystal names the act it belongs to, and words that must appear in it" Enter
Sleep 400ms
Type "grep -A4 '^crystal:' memory/crystals/crystal-exit-code-through-a-pipe.md" Enter
Sleep 4s
Type "# the agent is about to run: npm run build 2>&1 | tail -20" Enter
Sleep 400ms
Type "# this is what the PreToolUse hook hands it, before the command runs:" Enter
Sleep 400ms
Type `python3 scripts/crystal_act.py --act bash --ctx "npm run build 2>&1 | tail -20" --text` Enter
Sleep 9s
Type "clear" Enter
Sleep 300ms
Type "# an unrelated command gets nothing at all" Enter
Sleep 400ms
Type `python3 scripts/crystal_act.py --act bash --ctx "ls -la" --dry` Enter
Sleep 4s
