# Crystals

**A note you write once, that arrives in your coding agent's context at the moment it is about to make
the mistake the note prevents.**

Selection is literal. A crystal binds to an **act** (running a command, writing a file, making a commit) and to the text of
that specific act. When you are about to type `npm run build 2>&1 | tail -20`, the one about pipes
eating exit codes arrives. When you are about to type `ls`, nothing does.

---

## Why you might want it

Every team has a set of knowings that live in someone's head, a stale wiki, or a 40-page rules file
nobody re-reads. In almost every case the rule WAS written down. It was written down somewhere the reader is not, at a
moment they are not thinking about it.

We ran this on our own repo for four months and measured it. Three things we learned that are worth
your time before you decide:

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

## Try it

```sh
python3 scripts/crystal_starter.py selftest
```

That builds a throwaway repo in a temp directory, seeds three crystals, and proves the whole loop:
the empty store refuses, each crystal registers and fires on its own trigger, the store stays silent on
an unrelated command, re-seeding never overwrites, and a crystal stripped of its essence marker turns
the doctor red. Nothing is written outside the temp directory.

Then **[INSTALL.md](INSTALL.md)** puts it in your repo in five minutes.

---

## What is in the box

| | |
|---|---|
| `starter/` | three portable crystals, so your store is not empty on day one |
| `INSTALL.md` | the install, every command in it run verbatim under `dash` before shipping |
| five scripts | `crystal_act.py`, `crystal_registry.py`, `crystallize-stop-hook.py`, `crystal_inject.py`, `crystal_starter.py` |

**Stdlib Python only.** Importing the delivery path pulls two modules, neither outside the standard
library, and none of `subprocess`, `socket`, `ssl`, `urllib`, `http` or `asyncio`. It writes to two
directories inside your repo and nowhere else.

**It speaks, and it never blocks.** Our own repo runs gates that refuse commits, and we left them out
of this package, because enforcing our rules on your work would be hostile. If you want blocking, that is a
deliberate thing for you to add.

---

## Honest limits

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

---

## If you are testing this for us

The most useful thing you can report is the moment you thought *"I installed it and
nothing happened."* That sentence is the failure mode this whole package is built to avoid, and if you
say it, we want to know exactly which screen you were looking at.

Second most useful: a crystal of yours that fired when it should not have. Third: one that should have
fired and did not.

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
