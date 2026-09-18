---
last_verified: 2026-09-03
name: crystal-green-tests-do-not-prove-head-builds
description: A test run compiles your working tree, so it stays green while the committed tree is unbuildable. A partial commit that leaves a referenced symbol behind is invisible to every local check. Build HEAD in a detached worktree - that is the only thing that asks the question.
trigger: committing a subset of paths; adding a symbol in one file and using it in another; before pushing a repo someone else will clone or CI will build; "tests pass so it is fine"
crystal:
  deliver: act
  on: bash
  match: git commit, git push, go build, go test, cargo, tsc, compile, worktree
  when: act
  who: all
  mint_from: crystal-green-tests-do-not-prove-head-builds
  minted: 2026-09-03
metadata:
  type: feedback
---

<!-- crystal:essence -->
⛔ **A TEST RUN COMPILES THE WORKING TREE. IT SAYS NOTHING ABOUT WHAT YOU COMMITTED.** Every local
check — the test command, the linter, the app you just ran — reads the files on disk, including the
ones you did not commit. So a partial commit can leave the repository unbuildable **while every
instrument you own stays green**, and the first person to find out is whoever clones it.

**OBSERVED, on a Go repo.** `move.go` was committed using a struct field `Essential`; the field itself
sat uncommitted in `layout.go`. HEAD failed to compile with
`p.Children[i].Essential undefined (type *Node has no field or method Essential)` while
`go test ./internal/layout/` printed **ok**. Green tests, broken repo, no warning anywhere.

🔑 **THE CHECK IS THREE LINES AND READ-ONLY — no stash, nothing in your tree touched:**
```
git worktree add -q --detach /tmp/headcheck HEAD
(cd /tmp/headcheck && go build ./...)     # or cargo build / tsc / your compile step
git worktree remove /tmp/headcheck --force
```
⚠ **Do not pipe that build into `head` or `tail` to keep it readable** — the pipe reports the filter's
exit status, so a failed build prints `EXIT=0`.

⭐ **THE TELL: you added a symbol in one file, used it in another, then committed named paths.**
Committing exact paths is a good habit and this is its cost: it commits what you list and silently
omits what that code needs. The two files that must travel together are usually the two you think of
separately.
⚠ **Cheapest prevention: `git show --stat HEAD`, then ask whether anything the diff REFERENCES is
missing from it** — not whether the files you meant to commit are present.
<!-- /crystal:essence -->

## The wider form

Anything that verifies "the code" against files on disk inherits this. A test suite, a type checker, a
dev server, a notebook. The question they answer is *does my working tree work*. The question that
matters before a push is *does the artifact I just created work*, and only a clean checkout asks it.

This is worth its own habit rather than a footnote because the failure is silent by construction:
there is no error, no warning and no red anywhere in your own environment. The signal only exists in a
checkout you have not made yet.
