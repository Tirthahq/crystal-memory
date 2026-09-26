---
name: a-status-field-is-a-claim-about-the-world-not-an-observation
family: D
symptom: The record says it has not happened yet and it already has
source: crystal-a-status-field-is-the-weakest-witness-you-have
source_sha: 64ae5f8195a1a0191f969552753809fed2dfc6902ea06e8ab16815db654d2d67
derived: 2026-09-26
measured_on: 2026-09-25

---

## Symptom

A queue of outgoing messages is drained by a script. Each row carries a `status` field, and the drain
skips anything already marked `posted`. A duplicate goes out anyway, or a message is re-queued that is
already live.

## What the instrument said

The same outbox, on three separate occasions:

| the row said | alongside it |
|---|---|
| `pending` | a 24-hour staleness warning, silent because the row was under an hour old |
| `held`, with a note saying it was never posted | nothing; the note was written from a check and trusted from then on |
| (no row at all for the duplicate) | the drain reported success |

Every instrument that looked at the queue was green.

## What was actually true

**All three messages were already live on the public thread.** One had been live for three days while
its row said `held`.

The `status` field is written by the process, about something that happens outside the process. It
records what the process intended or last believed. The staleness warning was innocent too: it was
asking whether the row was old, and the row was young. The `held` note was worse than a wrong reading,
because it became a durable record, and later reasoning used the record as evidence.

## The rival, and the discriminator

**RIVAL:** the bookkeeping is fine and something else posted the duplicate: a second process, a manual
post, a retry from somewhere upstream.

**DISCRIMINATOR:** read the world, not the field. Fetch the target thread and look for your own account
carrying the draft's text. In every one of the three cases the text was there and the field disagreed,
so the field, not a second poster, was the thing out of step. The drain now does exactly this before it
posts, and aborts when it finds the text.

## The one-line check

Before a brake acts on a status field that records an EXTERNAL effect, **check the external thing
itself**, and make the check fail closed: if the world cannot be read, refuse. "Could not look" must
never read as "nothing there".

```
# the field answers "what did I intend?"; only the target answers "what is true out there?"
```

Keep writing the field. It is still useful bookkeeping; it just cannot be the brake.

## The tell

**Your safety check reads a column your own code wrote.** Any brake built on that is a brake on your
bookkeeping, not on the world. The receipt from the post itself is no better: its verdict has been
wrong in both directions (a probe bug said not posted; a rejected duplicate matched earlier text and
said posted). Believe a receipt's numbers, never its verdict, and never blind-retry on it.
