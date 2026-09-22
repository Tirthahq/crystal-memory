---
name: a-component-that-needs-starting-passes-every-behaviour-test
family: A
symptom: The whole suite is green and the shipped binary draws an empty box
source: crystal-a-component-that-needs-starting-passes-every-behaviour-test
source_sha: f9dbe14a60c9daddfd2dd2777d28cd14154e0c9a7bf6037fc8ba5e6f6245874f
derived: 2026-09-18
measured_on: 2026-08-30
arrival:
  - G: my agent won't use the tools I set up
  - G: all the checks are green and the screen is blank
  - G: it said the tests passed and the app is still broken
  - G: build succeeded and the thing won't even start
  - G: the suite is all passing and I can still reproduce the crash
  - G: the first call works and every call after that does nothing
---

## Symptom

Every test on a UI component passes. You run the actual binary and the component renders nothing.

## What the instrument said

Six green tests, and not trivial ones. The full key sequence typed a body and read it back. The three
exit paths were distinguishable. The update loop never returned a quit command. The view fitted its
height. Fields survived being copied.

## What was actually true

The component was never started. Its initialisation call had been omitted, so it held state, accepted
input and answered every question correctly, and drew nothing.

Measured directly, the same component rendered at the same size:

```
un-initialised:  1539 chars, no field titles present
initialised:     2185 chars, field titles present
```

## The rival, and the discriminator

**Rival:** the tests are too shallow and need more cases.
**Why it is hard to separate:** the tests already looked deep. They drove real key sequences and
asserted real state.

**Discriminator:** ask what the omission changes *on the outside*. Behaviour is fully available from an
unstarted component, because focus is state and values are state. The missing start changes only what
the thing **draws**. So no assertion over behaviour can reach it, and adding behaviour tests never will,
however many you add. An assertion about the rendered picture separates them on the first run.

## The one-line check

Assert that the rendered view contains text a human is supposed to see, by name:

```
if !strings.Contains(view, "Target") { t.Fatal("the component was not started") }
```

Name real drawn text, a title or a label. Never a length, and never a substring so generic that the
surrounding chrome satisfies it.

## The tell

Your suite is green and you have not yet looked at the thing running.

This generalises well past UI. Any lifecycle step you can omit while the object still answers questions
is invisible to tests that only ask questions: Init, Start, Mount, Open, Connect, Subscribe, Attach. The
object is not broken, it is *unstarted*, and unstarted looks exactly like working from the inside.

Two siblings from the same hour, both also green while broken. A value-receiver model handed out a
pointer to its own field and returned itself by value, so the form wrote into an escaped local and the
returned copy stayed empty forever, while an accessor happened to read the right object and everything
passed. And a leak test asserted that no key *closed* an overlay, which is equally true when the keys
reach nothing at all, so it passed with the routing disabled. Assert the positive thing arrived, never
the absence of harm.
