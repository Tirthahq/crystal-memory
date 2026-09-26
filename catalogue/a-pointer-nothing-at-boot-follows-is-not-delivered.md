---
name: a-pointer-nothing-at-boot-follows-is-not-delivered
family: A
symptom: The detail is in the handoff and the next session never read it
source: crystal-a-pointer-nothing-at-boot-follows-is-not-delivered
source_sha: bcd45ead3d132e9d6815b543ff89ae44df943e6a3550b4e24deb7ea846d5df94
derived: 2026-09-26
measured_on: 2026-09-26

---

## Symptom

An agent keeps a short scratchpad that is delivered at the start of every session, with a size cap.
To stay under the cap, the detail goes into a handoff document or a note, and the scratchpad keeps a
one-line pointer: "see the handoff". The next session starts, and asks the human for something the
handoff already said.

## What the instrument said

The boot output, at the start of the next session:

| the boot line | what it carried |
|---|---|
| the current handoff | its file NAME, resolved correctly |
| the scratchpad | every line up to the cap, including the pointer, as plain text |

Both lines were present and correct. The session looked oriented.

## What was actually true

**No part of the boot path opened the file the pointer named.** The handoff's name arrived and its
content did not; the pointer in the scratchpad arrived as bare text. Every "see the handoff" written to
keep the pad short had moved the detail somewhere no reader at boot goes. It read as tidy linking the
whole time, and the human had already been asked once whether the handoff had been read. It had not.

The same shape turned up a second time the same day, one level down: the hook that runs just before a
context compaction wrote its notes into the scratchpad, trimming the pad to fit, so its capture
reached the next context only through the file it was cutting.

## The rival, and the discriminator

**RIVAL:** the delivery is fine and the session simply did not act on what it was given.

**DISCRIMINATOR:** read what boot actually emitted, not what it names. Search the boot output for a
sentence from the BODY of the linked file. It was absent in every case. Then change the boot hook to
deliver the handoff's opening and each pointer's one-line description, and ask the same question cold:
the session answers from the delivered text without asking.

## The one-line check

For every pointer you leave for a later reader, **name the code that opens its target at the moment
that reader starts.** If you cannot, the pointer is a name, not a delivery.

```
# does any boot hook read the target, or only print its name?
grep -n "handoff" your-boot-hooks/*   # a match that only formats a path is not a read
```

## The tell

**You are about to write "see X" or "details in X" for the next session, or trim a file to fit a
cap.** Cramming loses content visibly. An unfollowed link loses it just as surely, and looks tidier.
