# Windows re-test fixes — 2026-10-13

Two findings from Mikhail (@ManSio) re-testing the any-agent package on Windows 11 / Python 3.14.4 (crystals#1).
Each was reproduced with a test that fails on the commit before the fix and passes after it.

| Change | What it addresses | How to test |
|---|---|---|
| Crystal files are read as `utf-8-sig` (`d557917`) | A UTF-8 BOM (Notepad, PowerShell 5.1 `Out-File`) broke frontmatter detection, so the crystal was silently skipped: `[]`, rc 0, empty stderr | `test_utf8_bom_crystal_is_still_delivered`: BOM and BOM+CRLF deliver the same match as the plain file |
| A symlinked crystal must resolve inside the store root (`1a65c22`) | A `*.md` link to a crystal-shaped file elsewhere delivered rules from outside the store. Bounded to rule injection: non-crystal targets (`.env`, keys) were never delivered | `test_symlink_out_of_store_is_not_delivered`: an outside crystal linked in returns `[]`; an in-store crystal and an in-store alias still deliver |

Re-tested by Mikhail at `1a65c22` against nine bypass attempts, including a chain of links and `CRYSTAL_STORE_ROOT`:
all blocked except NTFS hardlinks (out of scope, need volume access).

Not addressed here, and named so it stays visible:
- Content checks on crystals arriving from outside the store (supply chain). This includes the default-Windows
  case where `core.symlinks=false` turns a link into a regular file whose text the repo author chooses.
- **The symlink guard is walk-only** (`load_crystals`). Any future entry point that reads a crystal by name must
  apply the same resolve-inside-the-store check, or carry its own test.
- The budget packer's preference for small pieces, and a backoff clock keyed by act type.
