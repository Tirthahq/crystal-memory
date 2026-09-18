---
last_verified: 2026-09-03
name: crystal-a-positive-control-cannot-detect-a-yes-machine
description: A positive control - feed the gold answers through your scorer and expect roughly 100 percent - is passed perfectly by a scorer that returns valid unconditionally. Pair it with a negative control where silence and sabotage must score zero, before any number from that instrument means anything.
trigger: writing or running any eval, scorer, checker or judge; about to quote a benchmark number; validating a test harness; "the gold control passed"
crystal:
  deliver: act
  on: bash
  match: --selftest, selftest, gold control, benchmark, eval, scorer, checker
  when: act
  who: all
  mint_from: crystal-a-positive-control-cannot-detect-a-yes-machine
  minted: 2026-09-03
metadata:
  type: feedback
---

<!-- crystal:essence -->
⛔ **A POSITIVE CONTROL CANNOT DETECT A YES-MACHINE.** Feeding the gold answers through your scorer and
seeing roughly 100% is passed *perfectly* by a scorer that returns "valid" unconditionally. It proves
the happy path is wired. It proves nothing about whether the instrument can say NO.

🔑 **ALWAYS PAIR IT WITH A NEGATIVE CONTROL: silence and sabotage must score ZERO.**

**OBSERVED on an agentic tool-use benchmark**, using the benchmark authors' own checker:
`positive 199/199 · negative (silent and sabotaged transcripts) 0/199 accepted`. Only then was a score
printed. Those controls earned their cost three times over in one run: a double-wrapped tool schema
that raised `KeyError('name')`, caught before a single request went out; an upstream data defect where
one case had five user turns against six ground-truth turns, which crashed the authors' own checker;
and a leak-check that banned the token `"path"`, a real parameter name, so it fired on the model's own
tool catalogue.

⭐ **AND MAKE THE HARNESS REFUSE TO PRINT A SCORE WHEN A CONTROL FAILS.** Not warn — refuse. A number
from an unvalidated instrument is worse than no number, because it gets quoted, and the quote outlives
the caveat.
⚠ **THE TELL:** you are about to say *"the gold control passed."* Ask: *what did I feed it that SHOULD
have failed, and did it?*
<!-- /crystal:essence -->

## Why the negative control is the one that gets skipped

The positive control is the pleasant one. It confirms the thing you built does what you hoped, and it
is the natural first thing to run. The negative control asks the unpleasant question, costs a second
fixture, and its reward is that nothing happens. That asymmetry is why harnesses ship with only half
the pair, and it is why the same failure keeps arriving as a confident number rather than as a crash.

A useful generalisation: this applies to any check, not only to scorers. Before trusting a guard, a
linter rule or a test, break the thing it is supposed to catch and watch it go red. A check that has
never failed has not been shown to be capable of failing.
