# 2026-10-12 — local handback, uncommitted

- Add optional append-only intent logging before acts, committed/aborted outcome
  markers after acts, and startup recovery reporting. Matching stays read-only.
- Add crash, concurrent-writer, durability-failure, lifecycle and CLI acceptance
  tests, picked up by the existing Windows/macOS/Ubuntu Python CI matrix.
- Credit Meta's LogAct (MIT), https://github.com/facebookresearch/logact and
  arXiv 2604.07988. Independent implementation; see LOGACT-NOTICE.
- Local tests only. Windows CI has not been executed in this handback.
