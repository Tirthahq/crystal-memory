#!/usr/bin/env python3
"""
crystal_inject.py — the INJECT channel of from-within crystal deployment.

Boot delivers crystals at session start; INJECT delivers them MID-RUN via the nervous system (SPEAK), because a
rule drifts over long work and the refresh is what catches it (the drift-map's "refresh caught me over the 18h
session"). Reads `deliver: inject` crystals from crystal_registry and speaks the DUE ones as ONE SPEAK injection,
sharing inject.py's budget ledger (scratch/.inject-ledger.json) so cadence is UNIFIED with the rest of the nervous
system — never spam. Binding fields it honors (frontmatter `crystal:` block):
  deliver: inject   who: frontier|7b|resident|all   tier: critical|steering|ambient   ttl: <minutes>
  when: always  -> cadence refresh (v1, implemented — the TTL is the cadence)
  when: drift   -> fire only on a drift signal (GROW-PATH: needs a detector; falls back to cadence for now)

The 2×2 guard lives in the binding: `who` is the capacity axis (don't inject into a capacity-starved tier), the
TTL is the "don't re-supply a still-present rule" throttle. Always exits 0, never raises — SPEAK must not break a turn.

USAGE (standalone / from a hook, default-OFF behind CRYSTAL_INJECT=1):
  python3 scripts/crystal_inject.py            # emit due inject-crystals as one hook JSON (or nothing)
  CRYSTAL_WHO=frontier CRYSTAL_INJECT_EVENT=PreToolUse python3 scripts/crystal_inject.py
"""
import json, os, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
LEDGER = REPO / "scratch" / ".inject-ledger.json"          # SHARED with inject.py — one unified budget
# ⚠ critical was 0.0, and the check is `now - last >= ttl*60` — which for 0.0 is ALWAYS TRUE.
# That is not a cadence, it is "re-fire on every single prompt". Floored to 2 minutes: a rule you
# must not drift from still should not be re-sent between one tool call and the next.
TIER_TTL_MIN = {"critical": 2.0, "steering": 5.0, "ambient": 30.0}  # default cadence if a binding omits ttl
# FIRE-ONCE-PER-SESSION + BACKOFF (2026-07-20). A fixed cadence has no notion of "they already read
# this and have not forgotten". MEASURED on a 9h session: the same ~1,500-token block was injected
# 6-7 times = ~9,000 tokens spent re-telling a reader something they had just been told. The intent
# (a rule drifts over long work; the refresh catches it) is real, so this does not fire-once and
# stop — it makes each REPEAT cost exponentially more elapsed time, and caps the total per session.
MAX_PER_SESSION = 3          # after this, silence for the rest of the session
BACKOFF_BASE = 2.0           # nth repeat needs ttl * BACKOFF_BASE**n minutes

def _session_id():
    """Hook mode: Claude Code sends {"session_id": ...} on stdin (same contract session-vitals.py
    uses). Falls back to a per-boot marker so dedupe still works if the payload is absent — a wrong
    session id degrades to the OLD cadence behaviour, never to silence."""
    try:
        if not sys.stdin.isatty():
            sid = (json.loads(sys.stdin.read() or "{}") or {}).get("session_id")
            if sid:
                return str(sid)[:40]
    except Exception:
        pass
    try:                       # fallback: boot time, stable within a session, changes across reboots
        return "boot-" + str(int(os.path.getmtime("/dev/console")))
    except Exception:
        return "nosession"


def _load():
    try: return json.loads(LEDGER.read_text())
    except Exception: return {}

def _save(d):
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True); LEDGER.write_text(json.dumps(d))
    except Exception: pass  # best-effort; never fail the turn

def main():
    try:
        # ⛔ A REAL OFF SWITCH, HONOURED INSIDE THE SCRIPT (2026-08-12).
        # The hook line is gated on `$CRYSTAL_INJECT = 1`, but that variable is SET IN
        # .claude/settings.json, and the project `env` block WINS over both a shell export and an
        # override supplied via `--settings`. MEASURED: with CRYSTAL_INJECT=0 in the shell AND in a
        # --settings file, the refresh still fired. So there was NO way to disable delivery from
        # outside the project settings file — not for us running an A/B, and not for a customer.
        # `CRYSTAL_OFF` is deliberately NOT set in settings.json, so nothing overrides it: only a
        # variable the settings file does not mention can be controlled from outside.
        if os.environ.get("CRYSTAL_OFF", "").strip().lower() in ("1", "true", "yes"):
            return 0
        import crystal_registry as cr
        who = os.environ.get("CRYSTAL_WHO", "frontier")
        inj = cr.for_channel(cr.load_crystals(str(REPO)), "inject", who=who)
        if not inj:
            return 0
        now = time.time(); led = _load(); due = []
        sid = _session_id()
        for c in inj:
            if not c.get("essence"):
                continue
            # GUARD (2026-07-25): the injector historically ignored `when`, so crystals authored
            # `when: topic` leaked onto the always-on cadence channel as wallpaper (3 of them, the
            # inject-set shrink). Only `always`/`drift` belong on this mid-run cadence; a topic/boot
            # crystal must not fire here. Default a missing `when` to "always" (the channel's own
            # documented cadence meaning) so a legitimately-unlabelled inject crystal still fires.
            if str(c.get("when") or "always").strip().lower() not in ("always", "drift"):
                continue
            base = os.path.basename(c["path"])
            # ⛔ THE CADENCE TIMER IS PER-SESSION, NOT GLOBAL (fixed 2026-08-12).
            # It used to be keyed `crystal-inject:<base>` — one timestamp shared by EVERY session on
            # the machine. So a brand-new session inherited an unrelated session's recency and was
            # silently starved of its refresh. MEASURED: a fresh session fired nothing because the
            # live interactive session had fired these two crystals 22 and 32 min earlier, against
            # 40/45-min TTLs. The reader who most needs the re-pointing — one just starting — was the
            # one guaranteed not to get it, and nothing reported the suppression.
            # The per-session COUNT (`skey`) was already session-scoped; only the clock was not.
            # MAX_PER_SESSION still bounds the total, so this cannot become spam.
            key = f"crystal-inject:{sid}:{base}"
            skey = f"crystal-inject-session:{sid}:{base}"     # per-session delivery count
            tier = c.get("tier", "ambient")
            ttl_min = float(c["ttl"]) if c.get("ttl") else TIER_TTL_MIN.get(tier, 30.0)
            seen = led.get(skey, 0)
            if seen >= MAX_PER_SESSION:                       # said it enough; stop paying for it
                continue
            wait = ttl_min * (BACKOFF_BASE ** seen) * 60      # each repeat costs exponentially more time
            if now - led.get(key, 0) >= wait:
                due.append((key, c)); led[key] = now; led[skey] = seen + 1
        if not due:
            return 0
        parts = ["✦ CRYSTAL REFRESH (from within) — a rule re-supplied mid-run because it drifts over long work "
                 "(not new info; a re-pointing. If it's already fresh in mind, this costs you a glance):"]
        for _, c in due:
            parts.append(c["essence"])
        # prune timestamps only — session counters are COUNTS, not times, and wiping them mid-session
        # would silently restore the spam this change exists to stop.
        led = {k: t for k, t in led.items()
               if k.startswith("crystal-inject-session:") or now - t < 86400}
        _save(led)
        event = os.environ.get("CRYSTAL_INJECT_EVENT", "PreToolUse")
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": "\n".join(parts)}}))
        return 0
    except Exception:
        return 0  # SPEAK must never break the turn

if __name__ == "__main__":
    sys.exit(main())
