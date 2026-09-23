---
name: one-calibration-pair-is-a-smoke-test-not-a-validation
family: B
symptom: I checked the judge on an example and it was fine, so the null must be real
source: crystal-one-calibration-pair-is-a-smoke-test-not-a-validation
source_sha: e6d89989073deda13da4c43bd93ea2c8c4c7ad6c854e47e470d23eea5dc51395
derived: 2026-09-23
measured_on: 2026-09-23

---

## Symptom

You use a model to score something — relevance, quality, whether an answer is correct. Being careful,
you check it first on an example you know the answer to. It gets that example right. You run the
experiment. It comes back flat, and you write up the null.

## What the instrument said

A 0-9 relevance scorer, temperature 0, checked before the run against a passage that states the
answer and a passage that does not:

```
calibration  positive=5  unrelated=0   ✅ the prompt discriminates
```

Then, over a full run: no improvement anywhere. The obvious conclusion is that the technique under
test does not work on this data.

## What was actually true

**Three separate versions of that control passed while the scorer was unusable**, each fix leaving
the next failure reachable.

**1 — The phrasing decided everything, and no control was in place to see it.** Two natural
formulations ("Does this document contain the answer?" and "could someone answer the question from
this passage?") returned **NO for a passage that explicitly states the answer, and NO for an unrelated
one**. Identical output; zero discrimination.

Changing only the ORDER of the two blocks, with the same model, scale, temperature and text:

| prompt shape | answer-bearing passage | unrelated passage |
|---|---|---|
| question first, passage second | **0** | 0 |
| **passage first, question second** | **9** | 0 |

**2 — The control was hand-written, so it validated prose nobody would ever score.** The synthetic
positive scored 5. The **real** stored passage carrying the same fact — markdown bold, backticks, a
table, an em-dash — scored **0**, and still 0 when cut down to the answer sentence alone. The
calibration gate went green and a 26-minute run produced a clean null that was entirely the scorer.

**3 — Then one real pair passed and the judge was still unreliable.** With the working prompt order
and a control drawn from the store (positive 9, unrelated 0), the re-run scored the known-correct
passage **0 on four of the six items where it was present**, and 9 on two. Rank improved exactly where
it scored 9 and degraded where it scored 0. The aggregate moved not at all.

The result is therefore **not** "the technique does not help here". It is "this judge is too
unreliable to answer the question" — and those two conclusions are indistinguishable from the summary
table.

## The rival, and the discriminator

**Rival:** the technique genuinely does nothing, which is exactly what a flat aggregate looks like.

**Why it is hard to separate:** a null is the cheapest result to believe. It requires no follow-up, it
closes a line of work, and a passing calibration line at the top of the log reads as due diligence
already done.

**Discriminator:** validate the judge **per item**, not once. If you have known-correct answers — and
if you are measuring retrieval or ranking, you do — score each item's known-correct passage before
scoring that item's candidates, and report the hit rate beside the result. A judge that recognises two
of six correct passages cannot rank the other four, and no single aggregate control can show you that.

## The one-line check

```python
# before trusting any per-item score, score the thing you already know is right
recognised = sum(1 for item in items if judge(item.question, item.known_good) >= threshold)
print(f"judge recognised {recognised}/{len(items)} known-good passages")
```

If that number is not close to all of them, you are measuring the judge.

## The tell

You are reporting a null from a model-scored experiment, and your control is a single pair — or a pair
you wrote yourself. Both were true here, in that order, hours apart. A control must travel the exact
path the measurement travels: same source, same formatting, same shape of text.
