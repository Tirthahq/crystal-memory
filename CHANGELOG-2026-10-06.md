# Package sync — 2026-10-06

Prepared from public master 6cb8479. Uncommitted review tree; not published.

Changes present since September 23, including improvements already in the baseline:

| Change | What it addresses | How to test |
|---|---|---|
| `--dry` explains no context, no matches, and suppression; regression test retained | Different silences looked identical to a broken install | `python3 scripts/crystal_act.py --selftest` |
| Registry list/doctor print undeliverable state and the two payload markers | A registered note without markers appeared healthy but could never fire | Remove a marker in a throwaway note; run `crystal_registry.py list` and `doctor` (doctor exits 2) |
| Legacy tombstone fallback retained | Upgrades could forget acknowledged broken references | Put an acknowledgement at `memory/librarian-tombstones.txt` with no new tombstone file; run node-health |
| Dual-layout starter lookup and experimental environment scrub | Extracted packages seeded zero; inherited holdback knobs contaminated selftests | `python3 scripts/crystal_starter.py selftest`; repeat with `CRYSTAL_HOLDBACK_PCT=100` |
| Starter included in the packager’s tracked set | A hand-maintained adaptation could be overwritten or left behind | Run the development packager’s `--list` and starter selftest |
| Short-key word boundaries, plus guard/copy/usage/board/bench/reply/price | Keys fired inside unrelated words | Act selftest: `pty` does not match `empty`; long tool/path keys retain substring matching |
| Overlap ordering inside session rotation tiers | Equally unheard candidates were ordered without act relevance | Act selftest; compare default with `CRYSTAL_ORDER=rotation` |
| Opt-in bounded candidate snapshot | Delivery logs could not explain which eligible notes lost the budget race | Set `CRYSTAL_ELIGIBILITY_LOG=1` and `CRYSTAL_DELIVERY_LOG` to a temp file; make a real matched act; inspect `act-candidates` row; dry runs emit none |
| Candidate snapshot never counts as an arrival | Old snapshot rows without a displacement prefix could pollute counts or crash arrival consumers | Call `crystal_registry.is_arrival` with channel `act-candidates` and event `candidate-snapshot`; expect false |
| `CRYSTAL_STORE_ROOT` and `CRYSTAL_DELIVERY_LOG` overrides | Replays needed isolated stores and telemetry instead of the live repository | Point both to temporary fixtures and run a real hook; development `test_crystal_store_override.py` covers both directions |
| Cleaner help and unknown-flag handling | Typos silently ran the dry consolidation path and looked successful | With the optional maintenance scripts installed in a seeded store: `python3 scripts/node-cleaner.py --help` exits 0; `--aply` exits 2 |
| Hygiene excludes `CLAUDE.md` | Auto-loaded instructions were reported as nodes missing metadata | Run hygiene against an instruction file; package does not add development-only exclusions |
| Four catalogue projections re-derived | Source changes had left public lessons stale | Development `check-catalogue-drift.py --catalogue <this-package>/catalogue --sources <development-repo>/memory` |
| Matching/order documentation; unverified accuracy/drop and drift percentages removed | Documentation overstated matching and cited figures absent from the verified ledger | Read README, how-it-works, measured; compare ledger |

The catalogue keeps the generated-document entry’s declared UI false-positive caveat. Source hashes
are hashes of the live essence bytes, not hashes of the public prose.

Release exclusions: no adaptive pack implementation, NodeRAG, study/lab tools, or new candidate
checker scripts. Candidate scripts passed their individual portability scan, but dependency closure
reported findings in the act selftest and unpublished audit/scope helpers; they are held out.
Overlap is a ranking proxy, not semantic matching. This sync does not establish behavioural efficacy
on a foreign corpus. The E1/E2 refusal-channel experiments do not validate match-gated package delivery.

Verification (2026-10-06, `CRYSTAL_*` unset, clean foreign working directory): installer selftest,
installed act selftest, and package starter selftest each exit 0. Local drift: 15 checked / 0 failures;
package drift: 21 checked / 0 failures. The orchestrator still verifies, commits, and publishes.
