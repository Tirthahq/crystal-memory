---
name: a-surviving-mutant-can-mean-the-code-is-dead
family: A
symptom: I deleted the code on purpose and the test still passed
source: crystal-a-surviving-mutant-can-mean-the-code-is-dead
source_sha: 287018ea59a7bcf85269676d04cf8b48f33a60b5c58afc825a6c2c8c9029f5cb
derived: 2026-09-18
measured_on: 2026-08-15

---

## Symptom

You add a guard, write a test for it, then delete the guard on purpose to prove the test would catch
it. The test passes anyway. Every instinct says the test is too weak.

## What the instrument said

Test green with the guard present. Test green with the guard deleted. A surviving mutant, which the
literature and your own reflex both read as one thing: go write a stronger assertion.

## What was actually true

A surviving mutant has three causes and the third is the one nobody checks.

1. The test is weak. This is the assumed one.
2. The behaviour is over-determined, so removing one producer changes nothing observable. The code is
   correct and the mutant is harmless.
3. **The mutated code is never reached.** You cannot change the behaviour of a branch that has no
   behaviour.

Ours was the third. In a Go terminal UI, a key handler was guarded so that only Enter, and not Space,
jumped back to the shell. Before strengthening anything we measured what the runtime actually produces:

```
keyMsg(" ").String()      == "space"
keyMsg("space").String()  == "space"
```

The case read `msg.String() == " "`. That branch could never match, and had never matched for the
entire life of the file. It was not a regression anybody introduced. It was a dead binding that a
refactor had faithfully preserved. One literal fixed it, and the same mutant then died.

## The rival, and the discriminator

**Rival:** the test is weak and needs a stronger assertion.
**Why it is hard to separate:** absence-of-effect is what the mutant and the original both produce, so
no assertion over outcomes can tell them apart. Every "write a better test" instinct is aimed at the
wrong thing, and it will keep being aimed there for as long as you keep writing tests.

**Discriminator:** prove the path runs before you blame the test. Print or assert that the branch is
entered. A weak test reaches the branch and fails to notice; a dead branch is never reached at all.
That is one line of instrumentation and it separates them completely.

## The one-line check

Put a counter, a log line or a fatal assertion inside the branch under test and run the suite once. If
it never fires, you have found a dead path, which is a better finding than a weak test and is invisible
to every other instrument you own.

## The tell

The surviving mutant sits on a path you are *sure* is live, and the test you wrote for it passed on its
very first run, before you changed anything. Both halves of that sentence are the signal.

The sharpest instances are literals in a condition: a key name, an enum string, a flag value, an
environment variable, a header. `" "` against `"space"`. `parent_id` against `parentId`. The compiler
cannot object, review reads it as obviously right, and behavioural tests are structurally incapable of
seeing it. Compare against the value the runtime actually produces, measured, rather than the value the
name suggests.
