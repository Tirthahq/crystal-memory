---
name: a-check-written-with-the-code-inherits-its-assumptions
family: B
symptom: My check fails and I am sure the fix is wrong
source: crystal-evidence-must-not-share-the-thing-under-test
source_sha: 6854d974767e8efa24f3528bbe56f820cdc11577c041df84029b1e27df84524f
derived: 2026-10-06
measured_on: 2026-09-23

---

## Symptom

You write a fix, then write a check for it. The check fails. Your first thought is that the fix is
wrong, so you go back and adjust the code. Or the check passes immediately, and you move on.

## What the instrument said

Four checks in one session, each reporting confidently on the code it was written for:

| the check | what it reported |
|---|---|
| a leakage gate over generated text | `0.0` on every item — a clean corpus |
| an assertion on cost-per-marginal-answer | the metric was absent, so the arm "bought nothing" |
| a false-positive check over a store | "no false positives" |
| a regex-matching check | the pattern did not match, so the fix was broken |

## What was actually true

**Every one of the four checks was the broken thing, not the code.**

- The leakage gate compared six-word sequences between a *question* and a *document*. Questions are
  phrased as questions and documents as statements, so six consecutive shared words essentially never
  occur. It read `0.0` on items deliberately written to leak. **It could not fire.**
- The cost assertion ran against a fixture that was the same rows with one field changed, so there was
  no marginal answer to price. It was asserting on a quantity the fixture could not produce.
- The false-positive check ran over a store holding **one** item, and that item was the broken one. It
  proved nothing, and said so in the voice of coverage.
- The regex check hand-rewrote the pattern into a literal to test it, and mangled the escaping while
  doing so. It fed `error TSd` to a pattern that requires a digit.

Three of the four times, the first reaction was *"the fix is wrong."*

## The rival, and the discriminator

**RIVAL:** the obvious explanation is rushing, or the well-known one — *the same author wrote both, so
the check shares the author's blind spot.*

**DISCRIMINATOR:** in the same session, the same author wrote an analysis script **before its data
existed**, and validated it against a previously published result, which it reproduced exactly. Same
author, same day, same hurry. **What differed was the ORDER.** A check written first cannot encode how
you solved the problem, because you have not solved it yet.

⚠ Four failures against one counter-example. Worth following because it costs nothing; not established.

## The one-line check

Before trusting a check that reports a clean result, **construct the input that would make it fail**:

```
# for a threshold: what value trips it?  for a matcher: what string matches?
# if you cannot name one, the check is documentation with a number on it
```

For a measurement, run the instrument on a case it **must** detect. Twenty words lifted verbatim from a
document scored 100% on the same function that scored every real question 0.0 — which is how the dead
gate was found. **Measure the measurer before believing its zero.**

A control can also arrive as a specification: a six-gram leakage gate was implemented exactly
as specified, yet could not fire. Construct an input that makes the gate reject before treating
its clean output as evidence. Writing the check before the implementation or data exists is a
cheap precaution; the timing explanation remains a hypothesis, not a proven cause.

## The tell

**You just finished the thing, and the check comes easily.** That ease is the implementation still
being in your head, not the check being obvious.

⭐ **And the expensive variant: a check can leave your hands as a SPECIFICATION.** The leakage gate
above was written into a task and handed to another agent, which implemented it exactly, reported the
zero honestly, and even warned that a zero overlap does not rule out the bias. The defect was in the
requirement, and it shipped.
