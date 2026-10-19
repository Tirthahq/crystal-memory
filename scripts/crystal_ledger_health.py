#!/usr/bin/env python3
"""crystal_ledger_health.py: warn before the act ledger grows large enough to slow every hook.

Why: `due_for` cost is linear in ledger entries (measured by Mikhail, crystals#1, ~2.7 us/entry on
Windows), and every hook is a fresh process, so the in-process parse cache never helps. Session keys
are pruned on idle; `act:*` global backoff clocks are never pruned, so they are the part that grows.

    python3 scripts/crystal_ledger_health.py                # one line; exit 1 when over a limit
    python3 scripts/crystal_ledger_health.py --ledger PATH  # check another ledger file
    python3 scripts/crystal_ledger_health.py --selftest     # includes a planted oversized ledger that must go red

Limits (env): CRYSTAL_LEDGER_MAX_ENTRIES (default 10000), CRYSTAL_LEDGER_MAX_BYTES (default 1048576).
A missing ledger is fine (nothing has fired yet). An unreadable one exits 2.
"""
import argparse, json, os, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = REPO / "scratch" / ".act-ledger.json"


def limits():
    return (int(os.environ.get("CRYSTAL_LEDGER_MAX_ENTRIES", "10000")),
            int(os.environ.get("CRYSTAL_LEDGER_MAX_BYTES", str(1024 * 1024))))


def health(path):
    """Return (status, line). status: 'ok' | 'over' | 'absent' | 'unreadable'."""
    path = Path(path)
    if not path.exists():
        return "absent", f"act-ledger: absent at {path} (nothing has fired yet)"
    size = path.stat().st_size
    try:
        led = json.loads(path.read_text())
        assert isinstance(led, dict)
    except Exception as exc:
        return "unreadable", f"act-ledger: UNREADABLE at {path} ({type(exc).__name__})"
    entries = len(led)
    globals_ = sum(1 for k in led if str(k).startswith("act:"))
    max_entries, max_bytes = limits()
    over = entries > max_entries or size > max_bytes
    line = (f"act-ledger: {entries} entries ({globals_} never-pruned act:* clocks), {size / 1024:.0f} KB; "
            f"limits {max_entries} entries / {max_bytes // 1024} KB")
    if over:
        return "over", "⚠ " + line + " -> OVER: every hook parses this file; prune act:* clocks or raise the limit on purpose"
    return "ok", line


def selftest():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        small = tmp / "small.json"
        small.write_text(json.dumps({"act:edit:x": 1.0, "s1:crystal-a": 2.0}))
        assert health(small)[0] == "ok", health(small)
        assert health(tmp / "missing.json")[0] == "absent"
        bad = tmp / "bad.json"
        bad.write_text("{not json")
        assert health(bad)[0] == "unreadable"
        # NEGATIVE CONTROL: a planted ledger past the entry limit must go red.
        big = tmp / "big.json"
        big.write_text(json.dumps({f"act:edit:{i}": float(i) for i in range(limits()[0] + 1)}))
        status, line = health(big)
        assert status == "over" and "OVER" in line, line
        # And past the byte limit with few entries.
        fat = tmp / "fat.json"
        fat.write_text(json.dumps({"act:x": "y" * (limits()[1] + 10)}))
        assert health(fat)[0] == "over"
    print("PASS crystal_ledger_health selftest (ok, absent, unreadable, over-by-entries, over-by-bytes)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    status, line = health(args.ledger)
    print(line)
    return {"ok": 0, "absent": 0, "over": 1, "unreadable": 2}[status]


if __name__ == "__main__":
    sys.exit(main())
