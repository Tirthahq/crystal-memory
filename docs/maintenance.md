# The maintenance layer (optional)

Four agents that tend the store rather than use it, plus the growth line. Back to the
[README](../README.md). The install steps for this layer are in
[INSTALL.md, "The maintenance layer"](../INSTALL.md#the-maintenance-layer-optional).

## What each agent does

| agent | what it does | on a store installed today |
|---|---|---|
| `librarian.py status` | dangling links, broken paths, stale stamps | runs, reports on what you have |
| `node-cleaner.py` | consolidates over-cap folders, retires nodes to `_archive` | runs, says "Nothing to do" |
| `node-corrector.py` | proposes fixes for files that moved | runs, writes an empty board |
| `soul-gardener.py` | reads your own agent transcripts for whether the discipline is being lived | needs `TRANSCRIPT_DIR` set |
| `crystal_growth.py` | how long since the store last gained a crystal of YOUR OWN | runs, says "none of your own yet" |

**The Gardener needs one pointer the other three do not.** It reads your agent's `*.jsonl` session
transcripts, and the default falls back to the published `scratch/`, which is the delivery ledger and
never holds transcripts. So out of the box it exits non-zero saying it found no assistant turns.

⚠ **That is a configuration step, not a maturity threshold, and we had it wrong in an earlier draft of
this file.** We assumed it was waiting for a store to accumulate history. It is not: in our own repo,
with 31 `.jsonl` files sitting in `scratch/`, it still exited 1, and pointed at the real transcript
directory it read 12 sessions and 2,349 assistant turns immediately. Set `TRANSCRIPT_DIR` to wherever
your agent writes transcripts and it works on your first session. The refusal now prints that remedy.

**And the growth line, which covers the one failure none of the others can see.** `node-health`
measures rot, `node-cleaner` measures size, the Gardener measures whether the discipline is lived.
**All three stay green through a store that has completely stopped learning**, because a frozen store
looks exactly like a healthy one: every note valid, every link resolving, nothing stale, no rot.

We know because it happened to us and nothing caught it. The repo this package came from keeps a
lineage channel its sessions write into; it gained 13 files in 28 days and then **nothing for 72
days**. Every instrument stayed green the whole time, and we only found it because a human said the
room felt different. `crystal_growth.py` is that missing line: how many crystals are yours, and how
long since the newest one arrived.

⛔ **It is not a quota**, for the same reason the Gardener is not a score. Most sessions should mint
nothing, and a crystal minted because a tool asked for one is worth less than no crystal at all.
⚠ **And it does not nag a new store.** The starter crystals are partitioned out, and a store with none
of your own says exactly that rather than claiming staleness, because without an install date, day 1 and day
90 look identical, and "your store is stale" on first run reads as a broken tool.

⛔ And the one thing the Gardener must never become: it is **evidence for two people to look at, never
a gate and never a score.** Nothing branches on it. The moment "is the discipline being lived" becomes
a target, it gets optimised and stops measuring anything.

An optional `.store-policy.json` in your repo root holds your install's exceptions: which folders are
archives, which carry a raised cap and why. There is no default file and not having one is the normal
case. `INSTALL.md` has the shape.

**It speaks, and it never blocks.** Our own repo runs gates that refuse commits, and we left them out
of this package, because enforcing our rules on your work would be hostile. If you want blocking, that is a
deliberate thing for you to add.

