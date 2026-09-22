---
name: a-single-run-ranking-is-noise-even-at-temp-zero
family: C
symptom: My benchmark ranking flipped between two identical runs
source: crystal-a-single-run-ranking-is-noise-even-at-temp-zero
source_sha: 0c96b3fadfbdfef674d90f2acbcef636c1b9185d1ea5cfacdb13abbf8ace906b
derived: 2026-09-18
measured_on: 2026-08-05
arrival:
  - G: same prompt as last time and now it fails
  - G: it works in one chat and fails in the other with the same prompt
  - G: it works on the first try and fails when I rerun it
  - G: I don't believe these benchmark numbers
---

## Symptom

You rank candidates on a benchmark, deterministic settings, and a re-run puts them in a different
order.

## What the instrument said

A clean leaderboard with a 1.3 point gap between first and third. Deterministic sampling, same harness,
same items.

## What was actually true

Three candidates, 164 items, temperature zero, two identical runs an hour apart: **first and last
swapped.** One candidate moved up by 2.5 points across the two runs and went from third to first; the
incumbent moved down and went from first to third. The candidate beat the incumbent by 1.4 on the
second run having lost by 1.3 on the first.

**The run moved more than the gap.** Deterministic settings did not prevent it.

## The rival, and the discriminator

**Rival:** the ranking is real and one run is anomalous.
**Why it is hard to separate:** both runs look clean, both are internally consistent, and each on its
own supports a confident ordering.

**Discriminator:** measure the run-to-run movement on *that* set, then compare it to the gap you are
about to report. Here the observed movement was 2.5 points against gaps of 1.3 to 1.4. A gap smaller
than the movement is not a finding.

⚠ Do not import a movement figure from another benchmark. On a different set the totals were nearly
still while items flipped underneath, because flips cancel in an aggregate. Movement is a property of
the set, measured on the set.

## The one-line check

Run it twice and report the floor. If the gap you want to publish is smaller than the distance the same
system travelled between two identical runs, you have measured the run and not the system.

## The tell

You are about to quote a small ranking gap from one run, and the run that agrees with your prior is the
one you did not re-run.

**What survives is the partition, and it is the more useful statistic.** Across both runs, the same 130
items were answered correctly by everything and the same 2 were failed by everything; the contested set
moved only slightly, 17.5% to 14.8%. *Which* items the candidates split on is a property of the
candidates. *Who tops the total* is a property of the run. Report the partition. The fragile statistic
is the one everybody quotes and the robust one is the one nobody computes.

⚠ And defend the partition on the items contested in **both** runs with no flips by anybody. Difficulty
alone makes everything wobble together; only a genuine candidate-by-item interaction makes one reliably
right and another reliably wrong, twice.
