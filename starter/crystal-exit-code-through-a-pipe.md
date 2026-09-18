---
last_verified: 2026-09-03
name: crystal-exit-code-through-a-pipe
description: An exit code read after a pipe belongs to the LAST command, not the one you care about, so a failed build reads as PASS. The bash escape hatch $PIPESTATUS is silently empty in zsh. Worse across a machine boundary - a pipe inside a shipped ssh or SSM script makes a failed remote run report Success.
trigger: piping a build/test command into head, tail or grep; reading $? or PIPESTATUS after a pipe; writing a script to run on another machine; about to claim build-green from piped output
crystal:
  deliver: act
  on: bash
  match: | tail, |tail, | head, |head, | grep, |grep, ssh , ssm, <<'EOF', <<EOF
  when: act
  who: all
  mint_from: crystal-exit-code-through-a-pipe
  minted: 2026-09-03
metadata:
  type: feedback
---

<!-- crystal:essence -->
⛔ **`cmd | tail` REPORTS TAIL'S EXIT CODE, NOT `cmd`'s** — a failing build reads as PASS.
And the bash escape hatch **`${PIPESTATUS[0]}` is silently EMPTY in zsh**: it prints `EXIT=` with no
error at all, which looks like success to a hurried eye. zsh's array is lowercase and 1-indexed,
**`${pipestatus[1]}`**. Safest: run it clean — `cmd > /dev/null 2>&1; echo "EXIT=$?"`.
🔑 **An empty `EXIT=` is a RED result, not a green one. Blank means the check did not run.**

⭐ **THE VARIANT THAT CROSSES A MACHINE BOUNDARY IS THE DANGEROUS ONE.** A script shipped to another
box ending `python3 - <<'EOF' … EOF 2>&1 | grep -v Deprecation` exits with **grep's** status. `set -e`
does not trip, the remote shell exits 0, the runner records Success, and a fleet summary prints OK for
every host. One swallowed database auth error can become a health verdict about production hardware,
and it looks **more** authoritative at every hop.
🔑 **`set -euo pipefail` on the first line of every script you ship somewhere else** — `set -e` alone
is blind to a pipe. Then verify by the work's own artifact, never the runner's status: did the query
print its result line, did the file change, did the row appear.
⚠ **THE TELL:** you filtered the output to keep it readable. That readability filter is the thing that
ate the error.
<!-- /crystal:essence -->

## Where this came from

Observed on a real build, then a second time on a real fleet. A `npm run build 2>&1 | tail -20` was
checked with `${PIPESTATUS[0]}` and returned `BUILD EXIT=` — blank, sitting next to a `built in 359ms`
line that made the blank look fine. Had the build failed, the visible twenty lines would have been
asset listings and the exit check would still have been blank.

The remote form showed up later. A query script shipped to two servers died on a database password
failure. Because its last stage was a `grep -v` filter that existed only to hide a deprecation warning,
both shells exited 0, and the run printed OK for both boxes. The runner was not lying. It faithfully
reported an exit code that was itself a lie.

**How to apply.** Verifying a build or a test: redirect to a file and echo `$?`, or `set -o pipefail`
first. Shipping a script to another machine: `set -euo pipefail`, have it print a sentinel line, and
assert on the sentinel rather than on the runner saying Success.
