---
name: a-benchmark-arm-is-its-candidate-pool
family: C
symptom: Two configurations are being compared and I cannot say what is different between them
source: crystal-a-benchmark-arm-is-its-candidate-pool
source_sha: 7ddb8deff48fd3f7d7b3e43a0fc79b96d91371f39daffe4cae80d4b3f087ca12
derived: 2026-10-06
measured_on: 2026-09-22

---

## Symptom

You have two arms of a benchmark and a clean-looking gap between them. Every number is correctly
computed. You are about to attribute the gap to the one thing the arms are named after.

## What the instrument said

Two retrieval arms, one score each, presented as a single-variable comparison: whole documents versus
chunks. One arm clearly ahead. Both numbers reproducible.

A related arm reported a **+14.3 point** win for adding a reranking step, and that figure sat in the
code as a docstring for months, cited as precedent.

## What was actually true

The arms did not differ in the way their names said.

**One ranked over 3,038 documents. The other ranked over 7** — and those 7 were the files holding the
answers, because an implementation convenience had built that arm's index from the task list itself:

```python
files = sorted({t["node"] for t in TASKS})   # the candidate pool, built from the answer set
```

The reranking arm inherited the same pool. Its "+14.3 points" was measured with the answering document
**guaranteed to be in the candidate set**, among roughly fourteen files. That is a different problem
from picking one document out of three thousand, and the number licenses nothing about the second.

Both arms reported a hit rate. **Neither carried its candidate set anywhere in its output.** Every
figure was accurate and the comparison meant nothing.

The return unit is a separate axis from the candidate pool. In a later 14-task unit ablation,
the chunk ranker’s top hit resolved to the answering document 0 of 14 times. Serving that hit’s
whole document therefore tests an inflated chunk winner, not a document ranker. The no-retrieval
reader varied between runs; once allowed to abstain it scored 0 of 42. Do not claim the whole-document
arm is below no retrieval without naming that answer policy.

## The rival, and the discriminator

**Rival:** the arms differ as labelled, and the gap measures the thing under test.

**Why it is hard to separate:** nothing in the output is wrong. There is no failed assertion, no
anomalous value, no disagreement between instruments. The pool is established once, far from the
scoring code, usually by a line written for convenience rather than as a design decision — and it is
the one property the report does not carry.

**Discriminator:** make each arm state, in its own output, **what it ranked over** — the size of the
candidate set and where it came from. The moment `(of 3,038 documents)` prints next to `(of 7
documents)`, the comparison explains itself and no analysis is needed.

## The one-line check

```python
print(f"[{arm}] picked {best}  (of {len(candidates)} candidates from {source})")
```

Before comparing any two arms, read that line for both. If they differ, you are not measuring what the
arm names say you are measuring.

## The tell

You can describe what the two arms *do* differently, but you have not said out loud where each one's
candidates come from. Ask it as a sentence — "arm A chooses from ___, arm B chooses from ___" — and
if either blank is filled by something derived from the task list, the answer set is inside the
experiment.

This generalises past retrieval. Any evaluation that selects before it scores has a pool, and the pool
is part of the arm whether or not anyone wrote it down.
