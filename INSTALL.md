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

---

## What you are installing

Six scripts, three directories, and a starter set of three crystals so the loop is visible on day one.

A fifth script, `crystal_starter.py`, seeds that set and runs the selftest. You run it **from the
clone** and it is not copied into your repo, which is why the tree below shows four.

```
your-repo/
  scripts/       crystal_act.py  crystal_registry.py  crystallize-stop-hook.py  crystal_inject.py  crystal_scratchpad.py  crystal-discriminators.py
  memory/        your crystals live here, as .md files, at any depth
  scratch/       the delivery ledger (backoff + per-session counts)
```

`memory/` and `scratch/` are the only places anything is written. Nothing is written outside your repo.

**Two of those four scripts are optional channels, and neither is wired by this install.** Copy them
now and ignore them until you want them:

- `crystal_inject.py` — the *inject* channel. Re-delivers a small number of standing notes mid-session,
  on a cadence, because a rule drifts over long work. Wire it to a periodic hook when you want it.
- `crystallize-stop-hook.py` — a `Stop` hook that notices a substantial session which banked nothing
  new, and offers a ready-to-fill template once. It never writes anything and never decides what is
  worth keeping.

The act-bound channel described in this document needs only `crystal_act.py` and `crystal_registry.py`.

---

## Install

**1. Make the layout and copy the six scripts.**

```sh
mkdir -p scripts memory scratch
for f in crystal_act.py crystal_registry.py crystallize-stop-hook.py crystal_inject.py \
         crystal_scratchpad.py crystal-discriminators.py; do
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

A crystal is a finished knowing. You do not arrive at one directly — you notice something half-formed
mid-session and by the next session it is gone. The scratchpad is where that lives until it is worth
crystallising.

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
                     "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/crystal_scratchpad.py\" --boot" } ] }
    ]
  }
}
```

It stays **silent** when the scratchpad is empty or was seeded and never written in — a boot channel
that speaks when it has nothing teaches you to skip it. It delivers the newest ~120 lines, says how
many it withheld, and warns you when the file wants folding. Newest goes at the TOP: ours once ran 503
lines against a 500-line budget, and because the convention was to append at the bottom, everything
carefully preserved sat in the one region a truncated reader never reaches.

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
