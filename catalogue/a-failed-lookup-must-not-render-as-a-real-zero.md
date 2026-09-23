---
name: a-failed-lookup-must-not-render-as-a-real-zero
family: C
symptom: I got a clean zero and it is telling me to abandon the work
source: crystal-a-failed-lookup-must-not-render-as-a-real-zero
source_sha: 361725a4416923019e486875bc38ead1c9e13168f6aed7e4967c189a3d1a29b0
derived: 2026-09-23
measured_on: 2026-09-23

---

## Symptom

A measurement script reports zero across the board, and the zero is interesting. It confirms
something you suspected, or it justifies abandoning a piece of work. The script exited cleanly.

## What the instrument said

A recall table reading **0 out of 14 at every depth**, followed by a verdict in the tool's own words:

```
⇒ VERDICT: FIRST STAGE
  gold doc missing from the top 100 for 14/14 tasks. Reranking is the WRONG PROJECT.
```

Exit code 0.

## What was actually true

Not one of the fourteen lookups had succeeded. The search subprocess died immediately with **exit 2**
(`Failed to initialize cache at ~/.cache/uv`) in a sandbox that could not reach its own package cache.
The script read only `.stdout` and discarded the return code and stderr, so every failed call became
an empty result, every empty result became a legitimate miss, and fourteen misses became a recall
curve.

Three ordinary lines, each survivable on its own:

1. `subprocess.run(...).stdout` — the return code never examined.
2. `except Exception:` → `ranked = []` in the task loop.
3. `main()` printing the table and the verdict regardless, and returning 0.

The same tool, once it raised on a failed lookup instead, reproduced the real ranks exactly. So the
underlying result survived. What did not survive was the claim that the output had measured anything.

## The rival, and the discriminator

**Rival:** the retriever genuinely finds nothing, which is what a table of zeros looks like.

**Why it is hard to separate:** a broken lookup and a real zero are the same table. There is no
visual difference, no warning line, and no non-zero exit. Worse, this failure mode is not neutral
about which way it points — it fabricates the *strongest available* version of whatever you were
investigating. An instrument whose failure manufactures your headline gets believed on the day you
most want to believe it.

**Discriminator:** assert that the lookups succeeded before reading the aggregate. The return code
answers it in one line, and the parse answers the other half: a call that exits 0 and yields nothing
parseable is a changed output format, not a recall of zero.

## The one-line check

```python
if proc.returncode != 0:
    raise SearchFailed(f"exit {proc.returncode}: {proc.stderr.strip()[:300]}")
```

And, at the aggregate: if any lookup failed, print **no** results table at all and exit non-zero. A
partial table invites the reader to use it.

## The tell

You wrapped a lookup in `except Exception` and returned `[]`, `{}`, `0` or `""`. That keystroke
converts "I could not tell" into "the answer is none", and only one of those is a finding. The same
shape appears as `x / (len(items) or 1)`, where an empty denominator silently relabels a total as a
rate.

Related: an agent's environment failure arrives in the same format as a real finding. The agent in
this case behaved correctly and reported that it could not reproduce the measurement. The laundering
happened in the instrument, not in the report.
