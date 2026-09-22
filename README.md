# Crystals

**Your coding agent keeps making the same mistake. You already wrote the rule down. It is in a file the agent does not read at the moment it matters.**

The note is not missing. Reaching it requires someone to decide to go looking, and **you cannot look up the mistake you do not know you are about to make**: forming the query means already suspecting the answer.

Crystals is a small memory layer for [Claude Code](https://claude.com/claude-code), in two halves. Neither half waits to be searched.

| | holds | arrives |
|---|---|---|
| **The scratchpad** | what you were in the middle of: the open threads, the hunch not yet proven, the thing deliberately left undone and the reason it was left | at session start, before the first question |
| **Crystals** | one finished knowing each: what was learned, and what it cost to learn it | in the second before the action it applies to |

**The scratchpad carries your reasoning across a context reset. A crystal arrives before the mistake.**

Nobody searches. Nobody has to remember either of them exists. That is the whole design, and it works.

They are called crystals because each one is a single knowing, compressed until it fits in the small space you get at the moment of an action, and then left alone.

We run this on our own repository every day. It catches things we would otherwise ship, and it has changed what our agent does in a placebo-controlled test rather than in our impression of it. This is the first time it has been packaged for anybody else, so the install is the young part, not the engine. If it breaks for you we want the details, and the rest of this page tells you exactly what we have measured and what we have not.

## What it actually is

Three ways to get knowledge to a coding agent. The third one is this project.

**1. Put it in a rules file.** `CLAUDE.md`, a contributing guide, a long standards document. It is always loaded, so it competes for room with everything else, and it grows until nobody re-reads it. The agent sees all of it on every single turn, which sounds thorough and means it is background noise by the second page. Worst of all, the specific line that would have saved you is sitting in paragraph forty of a file about something else.

**2. Put it in a search index.** RAG, embeddings, a wiki, a vector store. This works, and we run one too. But a search only happens if somebody decides to search. That decision is exactly what you skip when you are about to do something you believe is fine. **You cannot look up the mistake you do not know you are about to make**, because forming the query means already suspecting it.

**3. Attach it to the action.** This project. A note declares which action it belongs to, and some words that have to appear in that action. Claude Code lets a hook run just before it takes an action, so at that instant we look at what it is about to do, find the notes that match, and put them in front of it. The agent did not ask. It did not know the note existed.

So the difference is not smarter search. It is that **nobody has to decide to go looking.** A rules file is always there and therefore ignored. A search index is precise and only reaches people already close to the answer. This is neither: it is quiet almost all of the time, and it speaks in the one second where the note is the only thing that matters.

The cost, and it is real: someone has to write the notes, one at a time, and mean them. There is no pipeline that generates these from your codebase. We tried that and it invented a statistic that appeared nowhere in the source. A note that arrives unasked, in the voice of settled fact, is dangerous in a way a search result is not, so a human writes every one.

## A note that asserts live state needs a shelf life

The README above says a note arriving unasked, in the voice of settled fact, is dangerous in a way a
search result is not. That cuts both ways: **when such a note goes out of date, nothing tells you.** A
stale document is dated and you can see it. A stale note is simply believed.

We measured this hurting us twice — one said a feature was unbuilt when it had shipped a week earlier,
and cost a decision that had already been made.

So a note may carry two more keys:

```yaml
crystal:
  stale_after: 2026-12-01
  discriminator: test "$(the command that answers it)" != "the answer that would falsify this"
```

Past that date the text is **withheld** and you get a short stub naming the command instead. Never the
old text. It is not dropped, because silence loses the pointer and you would repeat the claim from
memory.

**`discriminator` is the half that matters**, and it is worth saying why. A date is a prediction of an
unscheduled event — if you could name the day the thing changes, you did not need the note. So
`scripts/crystal-discriminators.py --run` executes those commands **offline, on whatever cadence you
like**, and a claim its own check refuses is expired immediately, whatever its date says.

⛔ **The contract: exit 0 while the claim HOLDS, non-zero when it is FALSIFIED.** This is not automatic
and the first one we wrote got it wrong — a cloud CLI call printed one answer when our server was down
and a different answer when it came back, and exited 0 both times. It would have read "still true"
forever, including on the day it stopped being. Wrap the answer in a `test` so it can refuse.

A passing check records evidence and **extends nothing**. Pushing the date forward automatically would
let the store re-assert a claim no human looked at again, which is the whole problem one level up.

## One note, one resource

`match:` is an OR-list, so a note about one server fires on acts about any other. If a note is about a
specific thing, name it:

```yaml
  depends_on: i-0123456789abcdef0, vol-0fedcba9876543210
```

The act must name that resource. It gates only when the act names a **competing** resource of the same
shape — an act that names no resource at all still gets the note, because that is often exactly when a
warning matters most.

## Show me

Here is a real note from the starter set. The top half is bookkeeping. The `match:` line is the whole trick, and the text between the markers is the only part that ever gets delivered.

```yaml
---
name: crystal-exit-code-through-a-pipe
trigger: piping a build/test command into head, tail or grep; about to claim build-green from piped output
crystal:
  deliver: act              # push it, do not wait to be asked
  on: bash                  # the action it belongs to
  match: "| tail, |tail, | head, |head, | grep, |grep, ssh , ssm"
  who: all                  # audience tag; `all` reaches every reader
---

<!-- crystal:essence -->
⛔ **`cmd | tail` REPORTS TAIL'S EXIT CODE, NOT `cmd`'s** — a failing build reads as PASS.
And the bash escape hatch **`${PIPESTATUS[0]}` is silently EMPTY in zsh**: it prints `EXIT=`
with no error at all, which looks like success to a hurried eye. zsh's array is lowercase and
1-indexed, **`${pipestatus[1]}`**. Safest: run it clean —
`cmd > /dev/null 2>&1; echo "EXIT=$?"`.
<!-- /crystal:essence -->
```

Now the agent goes to run `npm run build 2>&1 | tail -20`. Before the command executes, this lands in its context:

```
✦ CRYSTAL — you are about to bash. This knowing is bound to that act, not matched by topic:
✦ ⛔ **`cmd | tail` REPORTS TAIL'S EXIT CODE, NOT `cmd`'s** — a failing build reads as PASS.
  And the bash escape hatch **`${PIPESTATUS[0]}` is silently EMPTY in zsh** …
```

Run `ls -la` instead and **nothing arrives**. Selection is literal: the note binds to an action *and* to the text of that specific action, so a store of two hundred notes stays quiet until one of them is about the thing you are actually doing.

That is the entire idea. The rest of this page is what we learned running it.

## What you need

- **Claude Code**, because delivery uses its hooks. The notes themselves are plain markdown and portable; the push mechanism is Claude Code specific today.
- **Python 3**, standard library only. No packages to install, no service, no account, no network calls.
- **A git repo** to put it in. The install adds `scripts/`, `memory/` and `scratch/`; only `memory/` and `scratch/` are ever written to after that, and nothing outside your repo is touched.

## Try it without installing anything

```sh
git clone https://github.com/tjonesit/crystal-memory
cd crystal-memory
python3 scripts/crystal_starter.py selftest
```

That builds a throwaway repo in a temp directory, seeds three crystals and proves the whole loop end to end: an empty store refuses, each note fires on its own trigger, the store stays silent on an unrelated command, re-seeding never overwrites your edits, and a note stripped of its markers turns the doctor red. Fifteen checks. Nothing is written outside the temp directory.

Then **[INSTALL.md](INSTALL.md)** puts it in your own repo in about five minutes.

---

## Why you would want it

Every team has a set of knowings that live in someone's head, a stale wiki, or a 40-page rules file
nobody re-reads. In almost every case the rule WAS written down. It was written down somewhere the reader is not, at a
moment they are not thinking about it.

We ran this on our own repo for four months and measured it. ⚠ **These three numbers are ours, from
our own corpus, and you cannot reproduce them from this repo** — they are here because they are the
reasons the design looks the way it does, not as claims about your codebase. The full write-ups, with
method and caveats, are linked at the bottom.

Three things we learned that are worth your time before you decide:

- **A knowing can be delivered on the exact call it was written for and change nothing.** Ours fired on
  the precise command it was written to prevent, and the mistake happened anyway, because the channel
  we used speaks *after* the command runs. Speaking and blocking are different tools and picking wrong
  is invisible.
- **Noise can cost accuracy, on some models.** An irrelevant note took a task our cheap tier already
  did perfectly from 100% to 35%. We re-ran that on two other model families in September and the
  harm did **not** reproduce on either: the irrelevant note scored about the same as delivering
  nothing at all. So the narrow matching and the small budget are cheap insurance against a cost we
  have measured once and failed to reproduce twice, not a law.
- **A note rots while looking exactly as confident as the day you wrote it.** 9% of ours had drifted
  from their sources when we last measured, so the store checks for that and says so.

If those sound like problems you have, this is a 5 minute install with no service and no account.
If your rules are already enforced by CI and linters, you probably do not need it.

---

## What is in the box

| | |
|---|---|
| `starter/` | three portable crystals, which the seeder copies into your repo as `memory/crystals/*.md` |
| `INSTALL.md` | the install, every command in it run verbatim under `dash` before shipping |
| the loop | `crystal_act.py`, `crystal_registry.py`, `crystallize-stop-hook.py`, `crystal_inject.py`, `crystal_starter.py`, `crystal_scratchpad.py`, `crystal_handoff.py`, `crystal-discriminators.py` |
| the maintenance layer, optional | four agents that tend the store rather than use it, plus the helpers they load. See below, and §"The maintenance layer" in `INSTALL.md`. |

**The delivery path is stdlib Python with no process launching.** Importing it pulls two modules,
neither outside the standard library, and none of `subprocess`, `socket`, `ssl`, `urllib`, `http` or
`asyncio`. It writes to two directories inside your repo and nowhere else.

⚠ **Two parts of the package do launch processes, and you should know which.** `crystal-discriminators.py`
runs the command a note names, because settling a claim against the world is its entire job. The
**maintenance layer needs `git`** and shells out to it: the Librarian reads `git diff --cached`, the
Corrector reads `git ls-files`, and **`node-cleaner.py --apply` uses `git mv`** to relocate files. All
of those are reads except the `git mv`, and every `--apply` defaults to a plan that changes nothing.
Nothing in the package reaches the network.

### The capture reminder

`crystallize-stop-hook.py` is the other end of the loop from everything above. Delivery is worthless if
nothing ever gets banked, and the moment a knowing is cheapest to write down is the moment it is about
to evaporate. At the end of a substantial session that banked nothing, it offers a template once.

⚠ It deliberately avoids asking whether you learned anything. That question is answered "no" forever,
because nothing feels new at the end of a session where you did the work. It surfaces **specific
candidates from the session itself** — what you re-derived, what failed before it worked — so you are
judging a concrete thing rather than searching your memory. It writes nothing and decides nothing.

⛔ It needs a `Stop` hook to fire. Unwired it is an inert file, and `INSTALL.md` has the snippet.

### The scratchpad, which is the memory between sessions

`crystal_scratchpad.py` ships with a `SessionStart` hook and is easy to mistake for a scratch file. It
is the part of this package that carries **continuity**, and it answers a different question from the
crystals.

A crystal is one finished knowing, pushed back at the moment of the act. The scratchpad holds the live
working state of an agent mid-problem: the open threads, the hunch it has not proven, the thing it
deliberately left alone and why, what it would start next. **Most of that never becomes a crystal and
should not.** It is not truth, nothing governs it, and it is cheap to write into.

What it prevents is specific: without it, a context reset leaves the next session to reconstruct your
situation from commits and files. It recovers the facts and loses the reasoning — and the cost lands on
you, as re-explaining your own project to your own agent. **That re-explanation is the defect**, and a
pad that is read at boot is the direct fix for it.

⛔ Which is why it ships **with** the hook. A scratchpad nobody reads at boot is a diary.

### The maintenance layer

| agent | what it does | on a store installed today |
|---|---|---|
| `librarian.py status` | dangling links, broken paths, stale stamps | runs, reports on what you have |
| `node-cleaner.py` | consolidates over-cap folders, retires nodes to `_archive` | runs, says "Nothing to do" |
| `node-corrector.py` | proposes fixes for files that moved | runs, writes an empty board |
| `soul-gardener.py` | reads your own agent transcripts for whether the discipline is being lived | needs `TRANSCRIPT_DIR` set |

**The Gardener needs one pointer the other three do not.** It reads your agent's `*.jsonl` session
transcripts, and the default falls back to the published `scratch/`, which is the delivery ledger and
never holds transcripts. So out of the box it exits non-zero saying it found no assistant turns.

⚠ **That is a configuration step, not a maturity threshold, and we had it wrong in an earlier draft of
this file.** We assumed it was waiting for a store to accumulate history. It is not: in our own repo,
with 31 `.jsonl` files sitting in `scratch/`, it still exited 1 — and pointed at the real transcript
directory it read 12 sessions and 2,349 assistant turns immediately. Set `TRANSCRIPT_DIR` to wherever
your agent writes transcripts and it works on your first session. The refusal now prints that remedy.

⛔ And the one thing the Gardener must never become: it is **evidence for two people to look at, never
a gate and never a score.** Nothing branches on it. The moment "is the discipline being lived" becomes
a target, it gets optimised and stops measuring anything.

An optional `.store-policy.json` in your repo root holds your install's exceptions — which folders are
archives, which carry a raised cap and why. There is no default file and not having one is the normal
case. `INSTALL.md` has the shape.

**It speaks, and it never blocks.** Our own repo runs gates that refuse commits, and we left them out
of this package, because enforcing our rules on your work would be hostile. If you want blocking, that is a
deliberate thing for you to add.

---

## Install

From inside your repo, pointing at a clone of this one:

```sh
sh "$CRYSTALS/install.sh"
```

It ends by firing a real crystal at you, so "it installed and nothing happened" is answered before you
can ask it. Hooks are printed for you to paste rather than written into your settings. `INSTALL.md` has
the by-hand version and the optional maintenance layer.

## What we have measured, and what we have not

- Measured on one repo, by one team. We have now run the behavioural holdout on three model
  families. **One scenario separated cleanly on all three** (crystal arm perfect, placebo and
  dropped arms at zero). The others did not replicate, and the reason is visible in the data rather
  than mysterious: the dropped arm already scored high, meaning that model already knew the thing.
  **A crystal cannot help where the model is not going to make the mistake**, so which notes earn
  their slot depends on the model you run. The corpus is still ours either way, which is exactly
  what we would like a second pair of hands to fix.
- Selection is literal matching. A `match:` list that is too broad fires on everything and costs you
  accuracy; too narrow and it never fires. There is no tuning loop yet, only your judgement.
- The freshness check detects **drift** and stops there. It knows the source moved; whether the note is
  now wrong stays beyond it.
- The maintenance layer is **new here and has been run against a day-0 store, not a large one.** We
  measured it on a clean install: three of four agents run, one refuses for a stated reason, and a full
  retire works end to end. What we have *not* measured is what it does to a store with years in it and
  a shape unlike ours, which is the report we would most like back.
- `.store-policy.json` refuses a file it cannot trust rather than reading it as empty, including on an
  unknown key. A typo silently disabling an exclusion is the failure we chose to make loud, and the
  cost is that a malformed policy stops the agents until you fix it.

---

## If you are testing this for us

The most useful thing you can report is the moment you thought *"I installed it and
nothing happened."* That sentence is the failure mode this whole package is built to avoid, and if you
say it, we want to know exactly which screen you were looking at.

Second most useful: a crystal of yours that fired when it should not have. Third: one that should have
fired and did not.

---

## Where this came from, and the numbers

Built and run by [Spanda Works](https://github.com/tjonesit), a one-person shop, inside a working
product repo. It exists because we kept making the same three or four classes of mistake and wanted
something that interrupted the fourth time rather than the fortieth.

The three write-ups below carry the method and the caveats behind every number on this page, including
the ones that went against us:

1. [Crystal memory: notes that arrive when you act, not when you go looking](https://dev.to/tom_jones_230c4659491adcd/crystal-memory-notes-that-arrive-when-you-act-not-when-you-go-looking-83) — the delivery mechanism, and a placebo-controlled test of whether it changes behaviour at all.
2. [Whole notes, not fragments](https://dev.to/tom_jones_230c4659491adcd/whole-notes-not-fragments-the-retrieval-half-58ni) — the retrieval half, and why the number that flatters us is the one you cannot re-run.
3. [Your hooks are a fence. They could be a body.](https://dev.to/tom_jones_230c4659491adcd/your-hooks-are-a-fence-they-could-be-a-body-966) — what it is like to work inside it, and the evening the agent went numb to its own alerts.

⚠ **Every measurement we have comes from one repo, one team and one corpus.** That is the limit we
most want help with, and it is why this is published at all.

---

## License

Apache License 2.0. The full text is in `LICENSE`, and the copyright and attribution notice is in
`NOTICE`. You may use, modify and redistribute this, including commercially, provided you keep the
notice and state your changes.

Two things worth knowing, because they are the reason this license and not a shorter one:

- **It grants you a patent licence, explicitly.** If any of this is covered by a patent we hold, you
  have a licence to it for this work. That grant ends only if you sue somebody over patents in it.
- **It does not grant trademark rights.** Spanda Works, Tirtha and Ra stay ours. Build on the code,
  fork it, ship it. Just do not call yours by our names.

The three crystals under `starter/` are documentation rather than code. They record things we observed
while building our own systems, and they carry the same licence as the code.
