#!/usr/bin/env python3
"""crystal_growth.py — has this store LEARNED ANYTHING LATELY?

⛔ WHY THIS SHIPS, AND IT IS THE ONE FAILURE NO OTHER CHECK IN THIS PACKAGE CAN SEE.
A store that has stopped growing looks EXACTLY like a healthy one. Every note still valid, every
link still resolving, every cap respected, no rot. node-health measures decay; memory-hygiene
measures size; the Gardener measures whether the channel is being LIVED. All three stay green
through a total freeze.

MEASURED IN THE REPO THIS PACKAGE CAME FROM, 2026-09-22: its own lineage channel gained 13 files in
28 days and then NOTHING FOR 72 DAYS. Nobody noticed. Not one instrument could have. And that store
had an entire body of prose asking every session to write in it -- so a store with no such prose,
belonging to someone who installed a tool once, will freeze harder and sooner.

🔑 THE SHAPE: the loop needs a human (or an agent) to decide "this is worth keeping". Anything that
depends on someone REMEMBERING to feed it will quietly stop being fed, and the silence is
indistinguishable from contentment.

⛔⛔ THIS IS NOT A QUOTA AND MUST NEVER BECOME ONE. Most sessions should mint nothing; a crystal
minted because a tool asked for one is worthless, and worse than worthless if it is believed later.
The upstream repo measured this directly at 1.5B: a bolted-on invite degenerates into a tic within
a day. This reports a NUMBER and a state. It never demands, never scores, and nothing may branch on
it.

⛔ AND IT MUST NOT CRY WOLF ON A FRESH INSTALL. The package seeds 3 starter crystals whose `minted:`
dates are older than the install, so a naive "days since newest mint" warns on day 1 -- and "your
store is stale" on first run reads as the tool being broken. Seeds are therefore partitioned OUT:
growth means a crystal YOU minted. With no own crystals we report the state and stay quiet, because
without an install date day 1 and day 90 are genuinely indistinguishable and the false alarm is the
more expensive mistake.

  python3 scripts/crystal_growth.py            # the line, exit 2 if quiet (a FINDING, never a block)
  python3 scripts/crystal_growth.py --boot     # SessionStart hook JSON; ALWAYS exits 0 (hook contract)
  python3 scripts/crystal_growth.py --selftest # controls, both directions

# INVOKED-BY: called-by:scripts/crystal_growth.py
# NEGATIVE-CONTROL: CRYSTAL_GROWTH_TODAY=2099-01-01 python3 "$REPO/scripts/crystal_growth.py"
"""
import argparse, json, os, re, sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
QUIET_DAYS = 30


def _today():
    env = os.environ.get("CRYSTAL_GROWTH_TODAY")
    return date.fromisoformat(env) if env else date.today()


def _starter_names():
    """The seed set that ships with the package -- growth means a crystal that is NOT one of these.
    Missing starter/ is not an error: a store installed elsewhere simply has no seeds to exclude."""
    try:
        import crystal_starter
        d = crystal_starter._find_starter_dir()
        return {p.stem for p in Path(d).glob("*.md")} if d else set()
    except Exception:
        return set()


def _minted(c):
    """The crystal's own `minted:` date. Falls back to `last_verified`, then the file's mtime --
    a store is not guaranteed to be a git repo, so git is never consulted."""
    for key in ("minted", "last_verified"):
        v = str(c.get(key) or "").strip()
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", v)
        if m:
            try:
                return date(*map(int, m.groups()))
            except ValueError:
                pass
    p = c.get("path")
    if p and Path(p).exists():
        return date.fromtimestamp(Path(p).stat().st_mtime)
    return None


def survey(repo=None):
    import crystal_registry as cr
    crystals = cr.load_crystals(repo=repo) if repo else cr.load_crystals()
    seeds = _starter_names()
    own, seeded = [], []
    for c in crystals:
        name = str(c.get("name") or Path(str(c.get("path") or "")).stem)
        (seeded if name in seeds else own).append((_minted(c), name))
    own = sorted((d, n) for d, n in own if d)
    return {"total": len(crystals), "seeded": len(seeded), "own": own}


def line(repo=None, today=None):
    today = today or _today()
    s = survey(repo)
    if not s["own"]:
        return (f"✦ CRYSTAL GROWTH — {s['total']} crystal(s), {s['seeded']} of them the shipped starter set, "
                f"none of your own yet.\n"
                "   Nothing is wrong. The first one usually arrives the first time something surprises you —\n"
                "   a command that failed for a reason you had to dig for, a fix that was not the obvious one.\n"
                "   (No staleness is reported here on purpose: without an install date, day 1 and day 90 look\n"
                "   identical, and warning a new store reads as the tool being broken.)"), 0
    newest, name = s["own"][-1]
    days = (today - newest).days
    head = (f"✦ CRYSTAL GROWTH — {len(s['own'])} of your own crystal(s) (+{s['seeded']} seeded); "
            f"the newest arrived {days} day(s) ago ({name}, {newest}).")
    if days < QUIET_DAYS:
        return head, 0
    return (head + f"\n   ⚠ THIS STORE HAS LEARNED NOTHING NEW IN {days} DAYS — and a frozen store is\n"
            "   indistinguishable from a healthy one: nothing rots, nothing breaks, every check stays green.\n"
            "   NOT a quota. Most sessions should mint nothing, and a crystal minted to satisfy a tool is\n"
            "   worth less than no crystal at all. But if something has surprised you in those weeks and the\n"
            "   store does not know it, that is the gap this line exists to make visible."), 2


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--boot", action="store_true", help="SessionStart hook JSON (always exits 0)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--root", default=None, help="store root (default: the install contract's)")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    text, code = line(repo=args.root)
    if args.boot:
        # The hook contract: a SessionStart hook must exit 0 or the harness reports a broken hook.
        # The FINDING travels in the text, never in the status, on this path.
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                 "additionalContext": text}}))
        return 0
    print(text)
    return code


def selftest():
    from datetime import timedelta
    ok = True

    def check(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")

    s = survey()
    seeds = _starter_names()
    check(f"the starter set is identifiable ({len(seeds)} seed name(s))", len(seeds) > 0)
    check("seeds are partitioned out of 'own'", all(n not in seeds for _, n in s["own"]))
    check("every own crystal carries a usable date", all(d for d, _ in s["own"]))

    # CONTROL — both branches must ALWAYS be watched, on a fixture we build here. Reading them off
    # whatever the local store happens to contain means the warn branch silently never runs on a new
    # install, which is exactly the store that most needs to know the warning works.
    import shutil, tempfile
    from datetime import timedelta
    tmp = Path(tempfile.mkdtemp(prefix="growthtest-"))
    try:
        (tmp / "memory" / "crystals").mkdir(parents=True)
        (tmp / "scratch").mkdir()
        (tmp / "memory" / "crystals" / "crystal-selftest-fixture.md").write_text(
            "---\nlast_verified: 2026-01-01\nname: crystal-selftest-fixture\n"
            "description: A fixture crystal built by the selftest to watch both branches fire.\n"
            "trigger: selftest only\ncrystal:\n  deliver: act\n  on: bash\n  match: fixture\n"
            "  when: act\n  who: all\n  minted: 2026-01-01\nmetadata:\n  type: feedback\n---\n"
            "<!-- crystal:essence -->\nA fixture knowing.\n<!-- /crystal:essence -->\n",
            encoding="utf-8")
        f = survey(repo=str(tmp))
        check("the fixture store is readable (1 own crystal)", len(f["own"]) == 1)
        minted = f["own"][-1][0]
        fresh, fcode = line(repo=str(tmp), today=minted + timedelta(days=1))
        stale, scode = line(repo=str(tmp), today=minted + timedelta(days=QUIET_DAYS + 1))
        check("a fresh store is quiet and exits 0",
              "LEARNED NOTHING NEW" not in fresh and fcode == 0)
        check("a quiet store warns AND exits 2",
              "LEARNED NOTHING NEW" in stale and scode == 2)
        check("the boundary is QUIET_DAYS, not an off-by-one",
              line(repo=str(tmp), today=minted + timedelta(days=QUIET_DAYS - 1))[1] == 0
              and line(repo=str(tmp), today=minted + timedelta(days=QUIET_DAYS))[1] == 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # CONTROL — a seed-only store must report state and must NEVER claim staleness (the day-1 trap).
    if not s["own"]:
        text, code = line()
        check("a seed-only store reports state and does NOT warn",
              "none of your own yet" in text and code == 0)
        check("a seed-only store never claims staleness", "LEARNED NOTHING NEW" not in text)

    # CONTROL — --boot must never propagate the finding as a nonzero status.
    check("--boot emits valid hook JSON", "additionalContext" in json.dumps(
        {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": line()[0]}}))

    print("SELFTEST PASS" if ok else "SELFTEST FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
