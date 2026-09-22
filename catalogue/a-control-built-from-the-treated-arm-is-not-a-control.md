---
name: a-control-built-from-the-treated-arm-is-not-a-control
family: B
symptom: My before and after look identical, so the change did nothing
source: crystal-a-control-built-from-the-treated-arm-is-not-a-control
source_sha: 176dde4aa86fd5de6391f9ed5a4b64eaf394b8265b66b460b819986682dac6d5
derived: 2026-09-18
measured_on: 2026-08-03

---

## Symptom

You measure a fix against a baseline and see no difference. The obvious conclusion is that the fix is
worthless and should be reverted.

## What the instrument said

Marker present in the new build. Marker present in the old build too. Apparent verdict: the change
makes no difference.

## What was actually true

The control was contaminated by one line. The baseline fixture had been copied **from the directory the
treated arm had just written to**, so the "before" file already contained the marker before the run
started.

Re-seeded from the original source, both arms fresh, the discrimination was total:

| build | mechanism | marker on screen after 2.2s |
|---|---|---|
| pre-fix | 25s heartbeat | **0** (the line was in the file) |
| fixed | 400ms polling gated on file change | **1** |

## The rival, and the discriminator

**Rival:** the change genuinely has no effect.
**Why it is hard to separate:** a null result is exactly what a worthless change produces, and it is
also what a contaminated control produces. This failure mode points in the direction that costs you
most, because a null reads as an argument for reverting code that actually works.

**Discriminator:** assert the control's starting state before you believe the null. One check on the
seed file would have shown the marker sitting there before anything ran.

## The one-line check

Before trusting a no-difference result, grep the control's fixture for the thing you are about to look
for. If it is already present, you have measured nothing.

## The tell

You built one arm's fixture from a directory the other arm had touched, usually with a recursive copy,
usually because it was convenient and already there.

The rule: both arms get fresh fixtures from the original source, never from each other. A copy is only
safe if you can name the moment it was taken and prove nothing has written to it since.

And the reusable half: **a control that shows no difference is a claim about the control until you have
checked the control.** A rollback executed on an unverified null is itself an unverified change.
