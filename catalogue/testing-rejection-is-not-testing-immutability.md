---
name: testing-rejection-is-not-testing-immutability
family: B
symptom: My immutability test passes and the operation still edits the caller's copy
source: crystal-testing-rejection-is-not-testing-immutability
source_sha: 57987ba7280ce7dfad14a4181a869c7f6efd8cc4d3c8e5ef6008b8a8bcb921d5
derived: 2026-09-18
measured_on: 2026-08-12

---

## Symptom

You have a test named for the property you care about, it passes, and the property does not hold.

## What the instrument said

A suite containing a test called, in as many words, "a failed operation leaves the original untouched".
Green.

## What was actually true

Every case in it used an invalid identifier. A rejected operation returns at the guard clause, before
it touches anything, so the assertion passed on code with no copying in it at all.

Replacing the defensive clone with a direct assignment on a **successful** path passed the entire
suite. The gap was found by mutation, never by reading.

## The rival, and the discriminator

**Rival:** the copying works, which is why the test passes.
**Why it is hard to separate:** the test is named for the property, exercises the real API, and goes
green on correct code too.

**Discriminator:** look at the *inputs*, not the assertions. If every case in the test is a not-found,
bad-argument or refused case, it is a test of your guard clauses wearing an immutability name. Run one
case that succeeds and the two come apart immediately.

## The one-line check

Capture the input's full observable state, run an operation that returns **no error**, then compare.
Assert on the value, not the shape: a swap that reorders in place leaves the same count, the same ids
and the same types.

## The tell

Your immutability test's inputs are all invalid.

The untested half is the dangerous one. Nobody is harmed by a rejected call leaving state alone. The
harm is a call that succeeds and quietly edits the caller's copy, because the caller is usually holding
that value as the previous state, which is what an undo restores, what a diff compares against, and what
a retry re-sends.
