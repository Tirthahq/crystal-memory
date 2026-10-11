# Key matching fix — 2026-10-10

Two input-validation holes found by Mikhail (@ManSio) in an independent audit of fe4e465, reproduced here by calling
`matches_ctx` itself before any change.

| Change | What it addresses | How to test |
|---|---|---|
| Keys of five characters now need word boundaries too (was: under five) | `cargo` fired inside "escargot", `\|tail` inside "log\|tailspin", `<<eof` inside "<<EOFILE" | Act selftest: each audited string no longer fires, the real command still does |
| A boundary is required only on a side of the key that ends in a letter or digit | A key ending in a symbol, like `post-`, is a prefix key and must still match `POST-notes.md` | Act selftest: `post-` matches `POST-linkedin.md`, not `repost-like` |
| Act text and keys are normalized before matching: NFKC, zero-width characters removed, Unicode spaces to a plain space, common Cyrillic and Greek lookalikes folded to Latin | A zero-width space inside `ssh`, a Cyrillic `ѕ`, a thin space inside `git status`, or fullwidth `ｓｓｈ` slipped past their keys | Act selftest: each audited string now fires its key |

Not addressed here, and named so it stays visible: content checks on crystals arriving from outside the store, the
budget packer's preference for small pieces, and a backoff clock keyed by act type. Those are design questions.
