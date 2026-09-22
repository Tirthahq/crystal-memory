---
name: a-generated-document-is-unverified-until-you-render-it
family: E
symptom: The file validates and the output still looks wrong
source: crystal-a-generated-document-is-unverified-until-you-render-it
source_sha: f6f37a2aea7f30871c97aa9e47734b93bba69cd4acc7a3d8d1178431ec97ba8a
derived: 2026-09-18
measured_on: 2026-08-26
arrival:
  - C: i just opened it and still has spacing issues and looks like nothing was done
  - C: the coverletter seemed to be in a different file format and did not work
  - G: the README examples don't match what I get when I run it
---

## Symptom

You generate a document, every structural assertion passes, and the person looking at it says it is
broken.

## What the instrument said

Valid archive. Well-formed XML. Every styling element present and counted: shading elements 3, border
elements 8, capitalisation runs 5.

## What was actually true

Three defects, none visible to code review or to any of those passing checks.

1. The shaded header band did nothing. The shading element was written, counted, present, and rendered
   plain white. A heavy border rule renders everywhere and was the fix.
2. The font fell back to a serif on a document specified as sans, across all 41 runs.
3. The page ran about a quarter empty, which reads as thin to a human and is only visible as a picture.

## The rival, and the discriminator

**Rival:** the generator is correct and the viewer is unusual.
**Why it is hard to separate:** the file genuinely is valid, so every instrument that reads the *file*
agrees with you. The reader sees the *render*, and nothing in the file tells you the two agree.

**Discriminator:** render it and look. Change one thing, re-render, look again. A property the file
states and the renderer drops is invisible from the source and obvious from the picture.

⚠ **And when the person looking at the real artifact disagrees with your tooling, the tooling is wrong.**
We verified three passes against a preview that exaggerates spacing, so it looked fixed to us and
unchanged to them, twice. Do not spend a third round defending the instrument.

## The one-line check

Produce an image of the output and look at it. On macOS, `qlmanage -t -s 1400 -o /tmp/prev <file>`
renders page one with no dependencies. Treat the render as evidence about layout, balance, whitespace,
hierarchy and page count, and confirm anything it may ignore against the source separately.

## The tell

You are about to describe a document you have never seen. "Clean hierarchy", "nicely balanced", "looks
sharp" are claims about a render.

Three sub-rules worth carrying:

**A font name in a generated file is a claim about somebody else's machine, not a property of the file.**
Check the font is present locally *and* universal on the recipient's platform. A document that falls
back is worse than one that was plain on purpose. The tell is that you chose the font because it looked
modern.

**A property a renderer may drop is not a property you have set.** Document-level defaults were ignored
outright by one viewer, so the spacing paid for there never applied and the document silently spilled to
a second page. State it on each element, where no renderer gets a choice.

**A minimal-but-valid file leaves the renderer guessing.** The rejected versions were a six-part package
with no named styles and no settings; the accepted one was ten parts with real styles. "It validates" is
a claim about the parser. "It looks right" is a claim about the renderer, and the gap between them is
where you lose.
