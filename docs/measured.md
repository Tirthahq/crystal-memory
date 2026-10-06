# What we have measured, and what we have not

Back to the [README](../README.md).

⚠ **Every measurement we have comes from one repo, one team and one corpus.** That is the limit we
most want help with, and it is why this is published at all.

## Why you would want it: things we learned

Every team has a set of knowings that live in someone's head, a stale wiki, or a 40-page rules file
nobody re-reads. In almost every case the rule WAS written down. It was written down somewhere the reader is not, at a
moment they are not thinking about it.

We ran this on our own repo for four months and measured it. ⚠ **These observations are ours, from
our own corpus, and you cannot reproduce them from this repo**: they are here because they are the
reasons the design looks the way it does, not as claims about your codebase. The full write-ups, with
method and caveats, are linked at the bottom.

Things we learned that are worth your time before you decide:

- **A knowing can be delivered on the exact call it was written for and change nothing.** Ours fired on
  the precise command it was written to prevent, and the mistake happened anyway, because the channel
  we used speaks *after* the command runs. Speaking and blocking are different tools and picking wrong
  is invisible.
- **Irrelevant notes and stale notes are risks the design limits.** Narrow bindings and a small
  delivery budget reduce unwanted interruptions; freshness checks flag source drift. The earlier
  accuracy-drop and drift-percentage figures are omitted because they are not recorded in the
  verified claims ledger.

If those sound like problems you have, this is a 5 minute install with no service and no account.
If your rules are already enforced by CI and linters, you probably do not need it.

## What we have measured, and what we have not

- Measured on one repo, by one team. We have now run the behavioural holdout on three model
  families. **One scenario separated cleanly on all three** (crystal arm perfect, placebo and
  dropped arms at zero). The others did not replicate, and the reason is visible in the data rather
  than mysterious: the dropped arm already scored high, meaning that model already knew the thing.
  **A crystal cannot help where the model is not going to make the mistake**, so which notes earn
  their slot depends on the model you run. The corpus is still ours either way, which is exactly
  what we would like a second pair of hands to fix.
- Selection is literal matching. A `match:` list that is too broad fires on everything and costs you
  accuracy; too narrow and it never fires. There is no tuning loop yet, only your judgement.
- The freshness check detects **drift** and stops there. It knows the source moved; whether the note is
  now wrong stays beyond it.
- The maintenance layer is **new here and has been run against a day-0 store, not a large one.** We
  measured it on a clean install: three of four agents run, one refuses for a stated reason, and a full
  retire works end to end. What we have *not* measured is what it does to a store with years in it and
  a shape unlike ours, which is the report we would most like back.
- `.store-policy.json` refuses a file it cannot trust rather than reading it as empty, including on an
  unknown key. A typo silently disabling an exclusion is the failure we chose to make loud, and the
  cost is that a malformed policy stops the agents until you fix it.

## The write-ups

The three write-ups below carry the method and the caveats behind the historical observations, including
the ones that went against us:

1. [Crystal memory: notes that arrive when you act, not when you go looking](https://dev.to/tom_jones_230c4659491adcd/crystal-memory-notes-that-arrive-when-you-act-not-when-you-go-looking-83): the delivery mechanism, and a placebo-controlled test of whether it changes behaviour at all.
2. [Whole notes, not fragments](https://dev.to/tom_jones_230c4659491adcd/whole-notes-not-fragments-the-retrieval-half-58ni): the retrieval half, and why the number that flatters us is the one you cannot re-run.
3. [Your hooks are a fence. They could be a body.](https://dev.to/tom_jones_230c4659491adcd/your-hooks-are-a-fence-they-could-be-a-body-966): what it is like to work inside it, and the evening the agent went numb to its own alerts.
