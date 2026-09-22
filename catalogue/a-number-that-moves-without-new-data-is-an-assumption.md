---
name: a-number-that-moves-without-new-data-is-an-assumption
family: D
symptom: A figure is correct and its premise is dead
source: crystal-a-number-that-moves-without-new-data-is-an-assumption
source_sha: db920bebc86076ae3e284fbc8c4a0aa813efd34605fb06c0f2e3f00c41ace7e0
derived: 2026-09-18
measured_on: 2026-07-30
arrival:
  - G: these numbers jumped overnight and I don't buy it
  - G: this pass rate looks too good to be true
  - G: these timings look way too perfect
---

## Symptom

A published figure gets revised, then revised again, and no new measurement happened in between.

## What the instrument said

Three successive values for the same quantity, each derived carefully, each defended in argument. All
three looked like results.

## What was actually true

**Zero additional measurements were taken between the three.** Decomposed, it was obvious: the measured
half, the token counts, was frozen in the run artifacts the entire time and never moved once. The
supplied half, a per-unit rate, was assumed, and it moved three times. All three "results" were one
dataset priced three different ways.

Two days went into arguing the rate. The decomposition also surfaced what the argument had buried: one
path consumed **1.71× the input tokens** of the other for identical cases, measured all along, and that
was the real driver nobody was looking at.

## The rival, and the discriminator

**Rival:** the number improved because the analysis improved.
**Why it is hard to separate:** each revision genuinely came with better reasoning, and revision is what
careful work looks like.

**Discriminator:** split the number into what was **measured** and what was **supplied**, and check
whether any measurement changed between versions. If none did, you are watching an assumption move, not
a result. The measured side is rarely the culprit.

## The one-line check

For every number in the sentence you are about to publish, can you say whether it was measured or
supplied, and where each supplied one came from *today*, read from its source rather than from a note?

## The tell

The number moved and nothing was re-run.

⚠ **The silent default is the nastiest variant.** A rate lookup that falls back to a default when the key
is missing looks exactly like a lookup that answered. Ours fell back to a retired tier for days without
erroring. **An unfetchable rate must be an error, never a zero and never a default.**
