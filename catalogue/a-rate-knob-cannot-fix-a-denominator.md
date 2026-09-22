---
name: a-rate-knob-cannot-fix-a-denominator
family: C
symptom: I turned the sampling rate all the way up and almost nothing was sampled
source: crystal-a-rate-knob-cannot-fix-a-denominator
source_sha: 9142c1152831e1cd6c72dd120f17f17eab7936774545c8390eb603c322326a47
derived: 2026-09-18
measured_on: 2026-08-02
arrival:
  - G: this coverage number can't be right
---

## Symptom

An audit log is nearly empty. You raise the sampling rate by a large factor and it stays nearly empty.

## What the instrument said

Healthy. The sampler ran, the writer ran, and the startup line confirmed the new rate was in effect.

## What was actually true

The rate went from 0.02 to 1.0, a fiftyfold raise, and produced **one row in about ninety minutes**
against a projection of roughly 3.4 per hour. Nothing was broken. The denominator was the constraint:
only one narrow request shape was eligible, and almost nothing in the live traffic had that shape. The
instrument was healthy and starving.

**The projection was the real error, and it is the reusable part.** The estimate came from dividing an
old row count by elapsed days and by the old rate. That arithmetic silently assumes the traffic *mix* is
stationary, and it was not.

## The rival, and the discriminator

**Rival:** the sampler or the writer is broken.
**Why it is hard to separate:** an empty log is exactly what a broken writer produces, and every health
signal you have says the component is fine, which reads as a contradiction worth debugging.

**Discriminator:** count the **eligible** events directly over a recent window. Not the total, the ones
that can actually be sampled. If eligible is near zero, the component is correct and the population is
the problem, and no rate will fix it.

## The one-line check

Before turning a rate up, count eligible events over the last window. `eligible ≈ 0` means the fix is to
generate the shape or widen what qualifies, never a bigger multiplier. A rate multiplies eligible
events; 100% of nothing is nothing.

## The tell

You are reasoning about a rate back-derived from an old row count. That is a claim about a population
you have not re-checked.

⚠ Two cautions on the way out. Seeding the missing shape fixes the denominator and **creates a selection
bias in the same act**: our seed cases were written to be answerable, which makes the sampled set easy by
construction, so any rate computed from it is the flattering one. Name that in the same sentence as the
result. And an empty log is not evidence of a dead feature until you have waited longer than the slowest
step in it: a related auditor took about 20 seconds per row and was nearly written off after a 12-second
look.
