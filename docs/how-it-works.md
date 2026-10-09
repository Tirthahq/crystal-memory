# How crystals work

The long form of the [README](../README.md). Watch [the firing demo](demo/fire.gif) first; this page
explains what you saw.

![A crystal firing before a piped build command](demo/fire.gif)

## Three ways to get knowledge to a coding agent

There are three ways to do it. The third one is this project.

**1. Put it in a rules file.** `CLAUDE.md`, a contributing guide, a long standards document. It is always loaded, so it competes for room with everything else, and it grows until nobody re-reads it. The agent sees all of it on every single turn, which sounds thorough and means it is background noise by the second page. Worst of all, the specific line that would have saved you is sitting in paragraph forty of a file about something else.

**2. Put it in a search index.** RAG, embeddings, a wiki, a vector store. This works, and we run one too. But a search only happens if somebody decides to search. That decision is exactly what you skip when you are about to do something you believe is fine. **You cannot look up the mistake you do not know you are about to make**, because forming the query means already suspecting it.

**3. Attach it to the action.** This project. A note declares which action it belongs to, and some words that have to appear in that action. Claude Code lets a hook run as it takes an action, so at that instant we look at what it is doing, find the notes that match, and attach them to that action. The agent reads them together with the action's result, so today they shape its next step rather than this one; a mode that holds the action until the note has been read is in testing. The agent did not ask. It did not know the note existed.

So the difference is not smarter search. It is that **nobody has to decide to go looking.** A rules file is always there and therefore ignored. A search index is precise and only reaches people already close to the answer. This is neither: it is quiet almost all of the time, and it speaks at the one moment the note is about.

The cost, and it is real: someone has to write the notes, one at a time, and mean them. There is no pipeline that generates these from your codebase. We tried that and it invented a statistic that appeared nowhere in the source. A note that arrives unasked, in the voice of settled fact, is dangerous in a way a search result is not, so a human writes every one.

## A note that asserts live state needs a shelf life

The README says a note arriving unasked, in the voice of settled fact, is dangerous in a way a
search result is not. That cuts both ways: **when such a note goes out of date, nothing tells you.** A
stale document is dated and you can see it. A stale note is simply believed.

We measured this hurting us twice. One said a feature was unbuilt when it had shipped a week earlier,
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
unscheduled event: if you could name the day the thing changes, you did not need the note. So
`scripts/crystal-discriminators.py --run` executes those commands **offline, on whatever cadence you
like**, and a claim its own check refuses is expired immediately, whatever its date says.

⛔ **The contract: exit 0 while the claim HOLDS, non-zero when it is FALSIFIED.** This is not automatic
and the first one we wrote got it wrong. A cloud CLI call printed one answer when our server was down
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
shape. An act that names no resource at all still gets the note, because that is often exactly when a
warning matters most.

## What runs, and what launches processes

**The delivery path is stdlib Python with no process launching.** Importing it pulls two modules,
neither outside the standard library, and none of `subprocess`, `socket`, `ssl`, `urllib`, `http` or
`asyncio`. It writes to two directories inside your repo and nowhere else.

⚠ **Two parts of the package do launch processes, and you should know which.** `crystal-discriminators.py`
runs the command a note names, because settling a claim against the world is its entire job. The
**maintenance layer needs `git`** and shells out to it: the Librarian reads `git diff --cached`, the
Corrector reads `git ls-files`, and **`node-cleaner.py --apply` uses `git mv`** to relocate files. All
of those are reads except the `git mv`, and every `--apply` defaults to a plan that changes nothing.
Nothing in the package reaches the network.

## The capture reminder and the scratchpad

### The capture reminder

`crystallize-stop-hook.py` is the other end of the loop from everything above. Delivery is worthless if
nothing ever gets banked, and the moment a knowing is cheapest to write down is the moment it is about
to evaporate. At the end of a substantial session that banked nothing, it offers a template once.

⚠ It deliberately avoids asking whether you learned anything. That question is answered "no" forever,
because nothing feels new at the end of a session where you did the work. It surfaces **specific
candidates from the session itself** (what you re-derived, what failed before it worked), so you are
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
situation from commits and files. It recovers the facts and loses the reasoning, and the cost lands on
you, as re-explaining your own project to your own agent. **That re-explanation is the defect**, and a
pad that is read at boot is the direct fix for it.

⛔ Which is why it ships **with** the hook. A scratchpad nobody reads at boot is a diary.


## Match semantics and delivery order

Matching uses a comma-separated OR-list, case-insensitively. Keys normally match substrings,
including longer tool names and path prefixes. Keys shorter than five characters, plus
`guard`, `copy`, `usage`, `board`, `bench`, `reply`, and `price`, require word boundaries
(no adjacent letters, digits, or underscore): `guard` matches “run guard” but not “guardrails”.
A missing or empty list admits every context that reaches matching; dependency and act bindings
still apply. Long writes match their subject and target path rather than their whole body.

Delivery orders eligible notes by how often they have spoken in the current session first.
Within each rotation tier, the default ranks word overlap with the act ahead of last-delivery
time, payload length, and filename. Overlap is Jaccard similarity of lowercase word tokens
at least three characters long, using the first 1,500 essence characters. `CRYSTAL_ORDER=rotation`
restores the previous ordering. Backoff, session caps, and the character budget still apply;
overlap ranks already-matched candidates and does not admit new ones. Adaptive packing is not
included in this release.
