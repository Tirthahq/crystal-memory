---
name: a-guard-keyed-on-a-field-nobody-fills-is-a-silent-no-op
family: A
symptom: A guard has never fired and I assume that means things are fine
source: crystal-a-guard-keyed-on-a-field-nobody-fills-is-a-silent-no-op
source_sha: fb33ca317f960eebca5a14e39c12a62bbcde8a0ca9460b94a100fc86bb51dd39
derived: 2026-09-18
measured_on: 2026-08-15
arrival:
  - G: I don't trust this green check
  - G: my agent is being lazy and not checking anything
---

## Symptom

A checker runs on schedule and always reports clean, while a counter beside it is visibly over budget.

## What the instrument said

"Nothing to do", every run, for days.

## What was actually true

The archiver looks at a status block on each item to decide whether it is finished. The folder held
**14 items against a budget of 1**, ten of them genuinely complete. **Zero of the 14 carried the status
block at all.** The guard was never wrong and was never broken. It was never handed the field it reads.

The population split is the whole mechanism. Items created from the template carry the block, so those
were visible. Items hand-written straight into the folder do not, so those were invisible. The guard
covered the population that did not need it and was blind to the one that did, and nothing about that
is visible from its output. Of the already-archived items, 22 of 40 had the field; every current one
lacked it.

## The rival, and the discriminator

**Rival:** there genuinely is nothing to do.
**Why it is hard to separate:** a clean report and an empty population print the same words.

**Discriminator:** measure the coverage, not the verdict. *What fraction of this guard's subjects carry
the field it keys on?* Zero, or falling, means the green line describes an empty set. A real "nothing to
do" has a non-zero denominator behind it.

## The one-line check

Count subjects with the field against subjects without it, and print both. Then make the absence itself
a flag: "N subjects have no field" is the finding, and it is the one thing a field-keyed check cannot
say on its own.

## The tell

A guard that has never fired, sitting next to a counter that is visibly over budget. Two instruments
describing the same thing disagreed for days, and the disagreement *was* the diagnosis. When a count and
a checker disagree, distrust the checker: the count cannot miss what it can see.

Two variants worth carrying. **A check that cannot see something must not call it false.** The same
archiver verified commits in one repository only, so work shipped elsewhere could never verify, and it
was reported as a false completion claim, meaning *you are lying about this*, when the truth was *I
cannot see that repository*. An accusation and an admission are different claims and must print
differently. Unverified is still a refusal; it is just an honest one.

**And a guard keyed on one tool is blind to the same act done through another, and it accuses.** A
reading requirement was implemented by scanning for one file-reading tool. Under a shell-first mode the
work was done with `cat` and `sed`, so a session that had read every required file in order was told it
had skipped them. A field-keyed guard fails silently, because nothing to see reads as clean. A
channel-keyed guard fails loudly and costs its subject's credibility. Enumerate every channel the act
can travel before keying on one.
