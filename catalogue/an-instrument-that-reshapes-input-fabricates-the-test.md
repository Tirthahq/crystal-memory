---
name: an-instrument-that-reshapes-input-fabricates-the-test
family: E
symptom: My test harness reports bugs that do not reproduce by hand
source: crystal-an-instrument-that-reshapes-input-fabricates-the-test
source_sha: 19f3ffe77e8cbc4f53635953884358e3cb01fa9edc7b4f32ec52ae1acb317ed5
derived: 2026-09-18
measured_on: 2026-08-10
arrival:
  - G: it works on my machine but CI is red
  - G: it works for me and not for my teammate
---

## Symptom

An automated capture harness produces confident, specific bug reports about features that work fine
when a human drives them.

## What the instrument said

Three findings, all reproducible on demand: the command palette ignores its arrow keys, Enter runs
nothing, the list never scrolls.

## What was actually true

All three were false. The harness slept between **bytes**, and an arrow key is three bytes. So the
escape sequence arrived as three separate keypresses, the first of which was a bare Escape, and Escape
closes the overlay. Driving the component directly with real key events passed every case. With the
harness fixed so an escape sequence leaves as one write, the same sequence scrolled the list correctly
with the cursor where it belonged.

## The rival, and the discriminator

**Rival:** the product really is broken in the way the harness describes.
**Why it is hard to separate:** the harness is reproducible, specific, and points at a plausible
component. A harness bug is worse than a product bug precisely because it aims the search at working
code, and it survives because green captures are never re-examined.

**Discriminator:** when a harness and a direct unit test disagree, believe neither and find which one is
lying about the **input**. Drive the component synchronously with constructed events to establish what
the code does, then fix the harness until it reproduces that.

**And the corruption has a shape you can read before forming any theory.** The palette came back with an
*empty query*. That is Escape's signature, not a dead arrow key. A garbled result is the instrument's
own reading; read its shape first.

## The one-line check

Log the exact byte sequence, and the number of write calls, that your harness delivers for one logical
keystroke. One event must leave as one write.

## The tell

Your harness has a per-character or per-byte delay knob, and you tuned it to make things reliable.

The rule is that the harness must preserve the **atomicity of one input event**. A keystroke, a click, a
paste is one event. Anything that splits it changes the event the program receives, and it cuts both
ways: too slow splits a sequence into pieces, too fast merges two presses into one string that matches
no binding. Both produce a real-looking failure of working code.

⚠ The sibling: a test helper that *constructs* input can encode a shape the world never produces. A
helper built the string `"down"` as four runes, whose rendered form is also `"down"`, so bindings matched
and the test read as though it had exercised the arrow key. It never had. Build real event types, not
strings that stringify the same.
