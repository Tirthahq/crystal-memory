# Crystals: a 5 minute install

A crystal is a short knowing bound to an **act** rather than to a topic. When your coding agent is
about to run a command, write a file or make a commit, the ones that match arrive in its context at
that moment. No retrieval query, no chat, no service.

**This installs into a repo you already have, and delivery is wired through [Claude Code](https://claude.com/claude-code) hooks.** The notes themselves are plain markdown and portable;
the push mechanism is Claude Code specific today. Everything here is standard-library Python 3. It
talks to nothing on the network, and it never blocks anything you do.

New here? Read the [README](README.md) first for what this is and a worked example.

**Requirements:** Python 3.8 or newer, standard library only. macOS or Linux; the commands below are
POSIX shell and are verified under `dash`. Windows is untested and the shell loops here will need
translating.

## First, get a copy

Every command below assumes you have cloned this repo somewhere. Adjust `~/src` to taste.

```sh
git clone https://github.com/tjonesit/crystal-memory ~/src/crystal-memory
export CRYSTALS=~/src/crystal-memory      # used by the commands below
```

Then `cd` into **your own repo**, the one you want the crystals in.

## One command

From inside your own repo:

```sh
sh "$CRYSTALS/install.sh"
```

It creates the three directories, copies the loop, seeds the starter crystals, and then **runs a
context that must match one of them** so you see the loop fire before you believe it. It does not touch
your hook config; it prints the hooks for you to paste. A second run overwrites nothing and says what
it skipped.

The rest of this page is the same install done by hand, plus everything the one command does not do.

---

## What you are installing

Six scripts, three directories, and a starter set of three crystals so the loop is visible on day one.

A fifth script, `crystal_starter.py`, seeds that set and runs the selftest. You run it **from the
clone** and it is not copied into your repo, which is why the tree below shows four.

```
your-repo/
  scripts/       crystal_act.py  crystal_registry.py  crystallize-stop-hook.py  crystal_inject.py  crystal_scratchpad.py  crystal_handoff.py  crystal-discriminators.py  librarian.py node-cleaner.py soul-gardener.py node-corrector.py store_contract.py build-node-index.py memory-hygiene.py store_caps.py node-health.py store_policy.py install_layout.py  redact.py
  memory/        your crystals live here, as .md files, at any depth
  scratch/       the delivery ledger (backoff + per-session counts)
```

`memory/` and `scratch/` are the only places anything is written. Nothing is written outside your repo.

**Two of those four scripts are optional channels, and neither is wired by this install.** Copy them
now and ignore them until you want them:

- `crystal_inject.py` — the *inject* channel. Re-delivers a small number of standing notes mid-session,
  on a cadence, because a rule drifts over long work. Wire it to a periodic hook when you want it.
- `crystallize-stop-hook.py` — the capture end of the loop, and the one most worth wiring. See below.

### The capture reminder

Everything above is about *delivering* a knowing. This is the other end: noticing you have one while
you still have it. At the end of a substantial session that banked nothing new, it surfaces what the
session actually did and offers a ready-to-fill template, once.

⚠ **It is not a generic "did you learn anything?"** That prompt gets answered "no" forever, because at
the end of a session nothing feels new. It surfaces **specific candidates drawn from the work itself**
— the thing you had to re-derive, the command that failed before it worked — so the question is about
something concrete rather than about your memory. It never writes anything and never decides what is
worth keeping. Those are both yours.

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [ { "type": "command",
                     "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/crystallize-stop-hook.py\"" } ] }
    ]
  }
}
```

⛔ **Unwired, this file does nothing at all.** The same argument the scratchpad section makes applies
here: a reminder that never fires is not a reminder, and it is worse than absent because the file
sitting in `scripts/` feels like the capability. Earlier versions of this page copied it and left it
cold, which is the defect being named rather than a recommendation.

The act-bound channel described in this document needs only `crystal_act.py` and `crystal_registry.py`.

---

## Install

**1. Make the layout and copy the scripts.**

```sh
mkdir -p scripts memory scratch
for f in crystal_act.py crystal_registry.py crystallize-stop-hook.py crystal_inject.py \
         crystal_scratchpad.py crystal_handoff.py crystal-discriminators.py; do
  cp "$CRYSTALS/scripts/$f" scripts/
done
```

**2. Check the empty store, and expect it to fail.**

```sh
python3 scripts/crystal_registry.py doctor
```

An empty store is **unhealthy on purpose** and exits `2`:

```
crystals found: 0
per-crystal essence:
  BLOCKED: no crystals found; no delivery can be proven
```

If that came back green you would have no way to tell a working install from an empty one, so the
first thing this tool does is refuse.

**3. Seed the scratchpad, and wire it so it is actually read.**

**The scratchpad is the memory between your sessions, and it is not a waiting room for crystals.**
That distinction matters more than it sounds. A crystal is one finished knowing, delivered back to you
at the moment you are about to need it. The scratchpad is the other thing entirely: the live working
state of an agent mid-problem — which threads are open, what it half-suspects and has not proven, what
it would pick up next, why something is deliberately left undone.

Most of what belongs in it will never become a crystal, and should not. It is not truth and it is not
governed; it is the texture of in-progress thought, which is precisely what a context reset destroys.
Without it the next session reconstructs your situation from the artifacts and gets the facts while
losing the reasoning, and you end up re-explaining your own project to your own agent. With it, the
session boots knowing what it was in the middle of.

Crystallising is a separate act that sometimes happens later. Treating the pad as a staging area for
that is the way to end up with an empty one.

```sh
python3 "$CRYSTALS/scripts/crystal_scratchpad.py" --seed
```

⛔ **A scratchpad nobody reads at boot is a diary, not a memory.** Wire the `SessionStart` hook or skip
this step entirely — a file written and never delivered is worse than nothing, because it feels like
you have the capability.

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command",
                     "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/crystal_scratchpad.py\" --boot" },
                   { "type": "command",
                     "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/crystal_handoff.py\" --boot" },
                   { "type": "command",
                     "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/crystal_growth.py\" --boot" } ] }
    ]
  }
}
```

It stays **silent** when the scratchpad is empty or was seeded and never written in — a boot channel
that speaks when it has nothing teaches you to skip it. It delivers the newest ~120 lines, says how
many it withheld, and warns you when the file wants folding. Newest goes at the TOP: ours once ran 503
lines against a 500-line budget, and because the convention was to append at the bottom, everything
carefully preserved sat in the one region a truncated reader never reaches.

**3a-ii. The growth line — the one failure nothing else in this package can see.**

`crystal_growth.py --boot` prints one line: how many crystals are yours, and how long since the newest
one arrived. It is there because **a store that has stopped growing looks exactly like a healthy one.**
Every note still valid, every link resolving, every cap respected, no rot — `node-health`,
`memory-hygiene` and the Gardener all stay green through a total freeze. We measured this in the repo
this package came from: its lineage channel gained 13 files in 28 days and then nothing for 72 days,
and not one instrument could have told us.

⛔ **It is not a quota.** Most sessions should mint nothing, and a crystal minted to satisfy a tool is
worth less than no crystal at all. It reports a number; nothing branches on it.
⚠ **It will not nag a new install.** The three starter crystals are partitioned out, and a store with
none of your own reports that plainly instead of claiming staleness — without an install date, day 1
and day 90 are indistinguishable, and "your store is stale" on first run reads as a broken tool.
Run it by hand any time: `python3 scripts/crystal_growth.py` (exit 2 means quiet, and is a finding,
never a block — under `--boot` it always exits 0, as the hook contract requires).

**3b. The handoff, which is what survives a context reset.**

The scratchpad above and the loop cover two spans. This covers the third, and the three are worth
seeing side by side, because each one fails in a way the others cannot catch:

| span | file | what it carries |
|---|---|---|
| the act | `crystal_act.py` | a knowing, at the second of the command it belongs to |
| the session | `crystal_scratchpad.py` | live working memory, so a boot is not a cold start |
| the reset | `crystal_handoff.py` | what the session **was**, written once at the end |

A scratchpad is open and unfinished by design. A handoff is closed: what shipped, what was decided,
what did not work, what is next. Without one the next session rebuilds your situation from commits
and files, recovers the facts, loses the reasoning, and the cost lands on **you** as re-explaining
your own project to your own agent.

```sh
python3 "$CRYSTALS/scripts/crystal_handoff.py" --new
```

⛔ **The machine fills only what it can prove.** The "what shipped" table is generated from `git log`,
with real hashes, so it cannot contain a claim with no commit behind it — which is the most common
lie in a handoff and the most expensive, because the next session believes it. Everything requiring
judgement (why it matters, what did not work, what is blocked and on whom) is left as a visible
prompt and stays unanswered until somebody answers it.

⚠ **An unanswered skeleton is SILENT at boot.** A document whose every section is still a prompt must
not announce itself, or you learn to skip the channel. And the boot delivery is deliberately narrow —
the pointer, the next action, what is blocked — never the whole document, because the scratchpad
already speaks on that channel and a second one that dumps a page starves the first.

**4. Seed the starter set.**

```sh
python3 "$CRYSTALS/scripts/crystal_starter.py" seed --into .
```

```
seeded  memory/crystals/crystal-exit-code-through-a-pipe.md
seeded  memory/crystals/crystal-green-tests-do-not-prove-head-builds.md
seeded  memory/crystals/crystal-a-positive-control-cannot-detect-a-yes-machine.md
3 seeded, 0 left alone, into memory/crystals
```

Seeding never overwrites. Run it again and it writes nothing, so if you edit a starter crystal your
edit survives a re-seed.

**5. Check again.**

```sh
python3 scripts/crystal_registry.py doctor
```

Now `crystals found: 3`, every essence `OK`, exit `0`.

⚠ The last block will say **`no --ctx given, so nothing CAN match`**. That is expected and it is not a
broken install. Act-bound crystals are selected by the **text of the command you are about to run**,
so a probe with no command cannot match anything. Give it one:

```sh
python3 scripts/crystal_registry.py doctor --act bash --ctx 'npm run build 2>&1 | tail -20'
```

```
would fire for act='bash' who='frontier':
  FIRE: memory/crystals/crystal-exit-code-through-a-pipe.md
```

That is the install proven end to end.

---

## See it fire

```sh
python3 scripts/crystal_act.py --act bash --ctx 'npm run build 2>&1 | tail -20'
```

You get a JSON object shaped for a `PreToolUse` hook, carrying the knowing about `cmd | tail` reporting
the wrong exit code:

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "\u2726 CRYSTAL \u2014 you are about to bash. This knowing is bound to that act, not matched by topic:\n\u26d4 **`cmd | tail` REPORTS TAIL'S EXIT CODE, NOT `cmd`'s** \u2014 a failing build reads as PASS. ..."}}
```

`additionalContext` is the whole payload: it is what your agent reads, and it is the only field that
matters to you. Then try something unrelated:

```sh
python3 scripts/crystal_act.py --act bash --ctx 'ls -la /tmp'
```

**Zero characters.** Silence on an unrelated command is the property that makes the channel worth
having, and it is the one to check first if you ever suspect the matching is too loose.

---

## Wire it to your agent

The output of `crystal_act.py` is `PreToolUse` hook JSON. In Claude Code, add this to your project's
`.claude/settings.json`. If you already have hooks there, merge this entry into `PreToolUse`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Write|Edit|NotebookEdit|Task",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/crystal_act.py\""
          }
        ]
      }
    ]
  }
}
```

If `.claude/settings.json` does not exist yet, create it with exactly the block above; the directory
is `.claude/` at the root of your repo. The matcher list is what decides which acts can reach you:
drop `NotebookEdit` and notebook edits stop delivering, drop `Task` and the `delegate` act never fires.

The hook invokes the script with **no arguments**. Claude Code sends the tool call as JSON on stdin,
and the script reads the act and context from that payload. The project path is quoted so spaces in
your repo's path work too. See the [Claude Code hooks reference](https://code.claude.com/docs/en/hooks).

⚠ **Passing an explicit `--act` skips the stdin read entirely.** That is deliberate, it is the CLI
escape hatch. The `--act bash --ctx '...'` form above works for a manual probe. The no-argument form
works for a hook. Both forms work, but a hook must not pass `--act`.

⛔ **This ships SPEAK-only. It never blocks a tool call, and there is no gate in this package.** Our own
repo runs gates that refuse commits, and shipping those to you would mean enforcing our rules on your
work. If you want blocking behaviour, that is yours to add deliberately.

---

## Write your own

A crystal is a markdown file anywhere under `memory/` with two things: a `crystal:` block in the
frontmatter, and an essence between two markers.

```markdown
---
name: crystal-what-you-learned
description: One line, so a human scanning the directory knows what this is.
crystal:
  deliver: act
  on: bash, write
  match: docker compose, container, up -d
  who: all
---

<!-- crystal:essence -->
The knowing itself. Short. Written to be read in the second before an act, by someone
who is about to make the mistake it prevents.
<!-- /crystal:essence -->
```

- **`on:`** is the acts it binds to. **These are the only acts a Claude Code hook can produce**, so
  binding to anything else gives you a crystal that can never fire:

  | `on:` | fires when |
  |---|---|
  | `bash` | the agent runs a shell command (`git commit ...` is a **bash** act, not a `commit` act) |
  | `write` | the agent writes or edits a file (`Write`, `Edit`, `NotebookEdit`) |
  | `delegate` | the agent briefs a subagent (`Task`/`Agent`) |
  | `boot` | session start |
  | `prompt` | you submit a prompt |
- **`match:`** is a comma-separated list; any one matching the context selects the crystal.
- **On a long write, `match:` is tested against the SUBJECT, not the whole body.** Under 2,000
  characters the whole payload is the subject. Above that, only the file path plus the first 600
  characters (title, frontmatter, lede) are searched. This exists because substring matching over a
  long document accumulates accidental hits: on a 7,638-character file we measured 2 crystals
  matching by path against 39 by body text, so relevance fell as the writing got more substantial.
  Short acts, every shell command among them, are unaffected.
- **`who:`** is the audience tag. `who: all` reaches every reader and is what you want unless you are
  routing notes to different model tiers. A reader identifies itself with `CRYSTAL_WHO` (default
  `frontier`), which is why `doctor` prints `who='frontier'`. A crystal whose `who:` matches neither
  `all` nor the reader's tag is silently skipped.
- The **essence markers are load-bearing.** A crystal with a `crystal:` block and no markers loads,
  lists, and delivers nothing. `doctor` reports it as `MISSING MARKERS` and exits `2`.

Three properties worth knowing before you write many:

- **The channel has a budget** (4,000 characters per act, shared). A crystal longer than the whole
  budget arrives truncated and evicts its neighbours, and truncated is indistinguishable from short.
  Keep an essence under ~1,500 characters.
- **Delivery backs off.** The same crystal will not fire on every act forever; the ledger in
  `scratch/` holds a global-per-repo backoff and a per-session count, and `doctor` prints both.
- **Noise is not free.** An irrelevant crystal is not a wasted slot, it costs accuracy on tasks the
  model already did correctly. Narrow your `match:` rather than widening it.

---

## Troubleshooting

| what you see | what it means |
|---|---|
| `doctor` exits 2, `crystals found: 0` | The store is empty, or `memory/` is not where you think. Doctor prints the root it resolved. |
| `doctor` exits 2, `MISSING MARKERS` | A crystal has the frontmatter block but no `crystal:essence` pair. It can never deliver. |
| `crystals found: N` but `no --ctx given` | Expected. Pass `--ctx` with a real command. |
| Fires on everything | Your `match:` list is too broad. Narrow to the distinctive tokens of the act. |
| Fires on nothing, with `--ctx` | Check `on:` includes the act you are passing, and that a `match:` token really appears in your context string. |
| `__pycache__/` appears in `scripts/` | Normal Python behaviour. Add it to your `.gitignore`. |

---

## Prove the whole thing on a throwaway repo

```sh
python3 "$CRYSTALS/scripts/crystal_starter.py" selftest
```

It builds a clean foreign repo in a temp directory, seeds the set, and asserts the arms that matter:
the empty store is unhealthy, each crystal registers, the store stays silent on an unrelated command,
each starter crystal fires on its own trigger, re-seeding is non-destructive, and a crystal stripped of
its essence marker turns doctor red. That last one is the control: it proves the checks can fail.

---

## Uninstall

Remove the hook entry from `.claude/settings.json`, and delivery stops immediately. Nothing else runs.

```sh
rm scripts/crystal_act.py scripts/crystal_registry.py \
   scripts/crystallize-stop-hook.py scripts/crystal_inject.py
rm -rf scratch/.act-ledger.json scratch/.inject-ledger.json
```

Your crystals are your own markdown under `memory/`. Deleting the scripts leaves them untouched, and
nothing outside your repo was ever written.

---

## What this package is not

- **Not a retrieval system.** There is no index, no embedding, no similarity. Selection is a literal
  match against the act and the command text.
- **Not a memory for your agent's conversation.** It carries knowings you wrote, to the moment they
  apply.
- **Not networked.** Importing `crystal_act` pulls two modules, neither of them outside the standard
  library, and none of `subprocess`, `socket`, `ssl`, `urllib`, `http` or `asyncio`.

---

## The maintenance layer (optional)

Four agents that tend the store rather than use it. They are **optional**: the crystal loop works
without them, and nothing above depends on them.

| agent | what it does | on a brand-new store |
|---|---|---|
| `librarian.py status` | reports dangling links, broken paths, stale stamps | runs; reports on what you have |
| `node-cleaner.py` | consolidates over-cap folders (`--apply` to act; default is a plan) | runs; says "Nothing to do" |
| `node-corrector.py` | proposes fixes for moved files (`--apply` for the confident ones) | runs; writes an empty board |
| `soul-gardener.py` | reads your agent transcripts for whether the discipline is being lived | needs `TRANSCRIPT_DIR` |

**The Gardener takes one pointer the other three do not.** It reads `*.jsonl` session transcripts, and
its default falls back to the published `scratch/` — the delivery ledger, which never holds
transcripts. Out of the box it therefore exits non-zero reporting no assistant turns, and prints the
remedy. Set it to wherever your agent writes transcripts:

```sh
TRANSCRIPT_DIR=~/path/to/agent/transcripts python3 scripts/soul-gardener.py
# or: python3 scripts/soul-gardener.py --transcripts-dir <dir>
```

⚠ This is a configuration step, **not** a threshold you have to grow into: with the variable set it
reports on your very first session. ⛔ It is evidence for a human to read, never a gate and never a
score — nothing may branch on it.

⚠ `node-cleaner.py --apply` and `node-corrector.py --apply` MOVE AND REWRITE FILES. Both default to a
plan that changes nothing. Read the plan first. Both are bounded by the directories declared above and
never by a recursive walk of your repo.

### `.store-policy.json` (optional, in your repo root)

Your install's exceptions. **There is no default file and not having one is the normal case** — with no
policy nothing is excluded, no folder has a raised cap, and nothing is retention-managed.

```json
{
  "excluded_dirs":     ["_archive"],
  "archived_dirs":     ["_archive"],
  "cap_raised":        {"memory/notes": {"cap": 80, "since": "2026-01-01",
                                         "review_by": "2026-04-01", "reason": "why, in your words"}},
  "retention_managed": {"memory/logs": "scripts/your-retention-tool.py"}
}
```

`excluded_dirs` are path fragments the scanners skip. `archived_dirs` are not scanned but still count as
existing link targets. A raised cap must carry a date and a reason and it expires at `review_by`, so a
silently raised cap is not reachable. `retention_managed` names the script that bounds a folder instead
of a count.

A **missing** file is fine. A **malformed** one is refused rather than read as empty, because a policy
that silently reads as empty would drop an exclusion or a cap raise with nothing to show for it. Unknown
keys are refused too (a typo must not read as empty); `version`, `comment` and `_comment` are ignored so
you can annotate it.

`STORE_POLICY_FILE` points at one elsewhere. If you set it and the file is absent, that IS an error —
you asked for a specific file.
