---
name: an-instrument-that-answers-a-different-question-can-be-wrong-two-ways
family: C
symptom: Two tools share the same rule and give me different answers
source: crystal-an-instrument-that-answers-is-anyone-waiting-can-be-wrong-two-ways
source_sha: f9246b836f5f59c77e53376adfe1d12a95d3cae4591ddd5f1651297a15194f3e
derived: 2026-09-18
measured_on: 2026-09-01
arrival:
  - G: the PR page says passing and the job log says failed
  - G: the UI shows success and the terminal shows an error
  - G: CI is green and production is down
---

## Symptom

Two checkers implement the same threshold. One says everything is within limits, the other lists
violations. Both have been running for weeks.

## What the instrument said

`all folders within cap` — true on every run, for months.

## What was actually true

Both tools used the identical constant, `FOLDER_CAP = 45`, and one of them carried a comment saying it
must match the other. **The comment was correct. The rule was identical. The populations were not.**

| tool | how it enumerated | what it saw | verdict |
|---|---|---|---|
| the cleaner | three named directories, non-recursive listing | 37, 20, 25 | within cap, true |
| the hygiene reporter | recursive walk of the whole tree | 60, 83, 49 | three over cap, true |

Every over-cap folder sat outside the first tool's population by construction. Its green tick had never
once been the thing that told anyone a folder was over.

**And the accurate comment is what hid it.** A cross-reference that checks out reads as a
cross-reference that *was* checked, so it stopped the next reader looking. A bare assertion would have
invited the question.

## The rival, and the discriminator

**Rival:** one of the two is simply buggy or stale.
**Why it is hard to separate:** a shared rule makes the disagreement look impossible, so the instinct is
to assume one implementation drifted, and to go diffing the logic. The logic was identical.

**Discriminator:** compare the **populations**, not the rules. Feed the recursive enumerator's list to
the non-recursive one, and the nested folders answer immediately: one producer reports violations where
the other has no verdict to give. That is cheaper than any amount of reading, and it is decisive.

## The one-line check

When two instruments disagree, print what each one *counted* before you compare what each one
*concluded*. Ask what it enumerated, not what rule it applied.

## The tell

Two tools that are supposed to agree, agreeing on the constant and disagreeing on the answer. The
disagreement *is* the diagnosis, and it is available for free the moment you put the two outputs side by
side.

⚠ **A second instance, measured 2026-09-18, four hours after the first was fixed — and it landed inside
the shared module written to fix it.** Consolidating the two tools behind one owner, the shared
enumerator was written as a non-recursive glob. A link checker bound to that owner had its universe cut
from **2,375 items to 16**, so it reported every reference in a new file as dangling while the same
checker run standalone resolved all 2,755 names. The static contract checker could not see it, because a
plain glob contains no hardcoded path: it was clean by the rule and wrong by the population, which is
the same sentence as the original defect.

The repair keeps both properties rather than picking one. A **mutator** takes an exact allowlist, never
a walk, because a recursive sweep of somebody else's directory can move files they care about. A
**reader** takes the recursive population, because a reader that cannot see the tree reports on a set
nobody chose. The bug was writing one enumerator for both.
