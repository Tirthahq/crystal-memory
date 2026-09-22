#!/usr/bin/env python3
"""
crystal_act.py — the ACT dispatcher. Delivers crystals because you are DOING THE THING.

WHY THIS EXISTS (measured 2026-07-20). The store had two failure modes that were one bug:
  · 66 of 82 crystals sat on `deliver: rag`, which ranks by TOKEN OVERLAP and keeps ONE winner
    per prompt → a few broad-topic crystals won every time and 50 had NEVER been delivered.
  · rag is PULL-shaped, and topic-retrieval-cannot-deliver-the-unthought measured what that
    costs: 13 deliveries to the session that already knew, 0 to the session that needed it.
Meanwhile everything that actually CAUGHT something that day — the discriminator gate, the
Librarian, the duplicate-node catch — was BOUND TO AN ACT and never touched the ranking at all.
Each was a bespoke hook, hand-written per knowing.

This generalises that. A crystal declares the act it belongs to in its own frontmatter:

    crystal:
      deliver: act
      on: bash            # or: on: commit,write

and fires when that act happens. It NEVER enters the topic ranking, so it cannot be crowded out.

THE ACTS map 1:1 to hook events that already fire — nothing new to schedule:
    bash    PreToolUse/Bash        you are about to run a shell command
    write   PreToolUse/Write|Edit  you are about to write or edit a file
    commit  pre-commit             you are about to commit
    prompt  UserPromptSubmit       you are starting a turn
    boot    SessionStart           the session is beginning

BOUNDED, because "fires every time you do the thing" would be its own spam:
per-session delivery cap with the same backoff crystal_inject uses. A new session starts fresh —
it genuinely has forgotten.

USAGE (hook or CLI):
    CRYSTAL_ACT=bash python3 scripts/crystal_act.py         # emit hook JSON, or nothing
    python3 scripts/crystal_act.py --act commit --dry       # show what WOULD fire
    python3 scripts/crystal_act.py --act bash --text --max 2   # at most 2 crystals, plain text
    python3 scripts/crystal_act.py --selftest

`--max N` caps delivery INSIDE selection (see due_for step 5). A caller that trims the output itself
gets a telemetry row and a spent session-budget for crystals nobody read; `--max` does not.
CRYSTAL_HOLDBACK_PCT opts into deterministic session/crystal/act suppression (0-100).
Unset or 0 leaves delivery unchanged. Never enabled by settings here.
Delivery failures exit 0; invalid CLI flags exit non-zero.
"""
import argparse, hashlib, json, os, re, select, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
LEDGER = REPO / "scratch" / ".act-ledger.json"
MAX_PER_SESSION = 3
TIER0_MAX = 6                 # cascade tier 0: how many starved crystals announce a tell
TIER0_CHARS = 150            # per-tell cap; the whole tier costs ~1k against a 4000 budget          # then silence for this session
BACKOFF_BASE = 2.0           # nth repeat needs BASE_MIN * BACKOFF_BASE**n minutes
BASE_MIN = 3.0               # an act-bound crystal may re-fire this often at first
CHARS_BUDGET = 4000          # bounded like the rag path; packed at whole-crystal granularity
FAT_ESSENCE = 1500           # HOWTO-mint-a-crystal §6: keep an essence ≲ this. Not enforced (a hard
                             # cap would silence an oversized crystal entirely, which is worse than
                             # a slow one) — reported by crystal_delivery_audit.py --budget instead.

CLAIM_BINDING_PATH = "builtin/claim-shaped-write-binding"
CLAIM_BINDING_ESSENCE = (
    "CLAIM-SHAPED WRITE: pause before this strategy/positioning claim hardens. "
    "Ask: (1) What would FALSIFY this? "
    "(2) Does an existing vision/positioning node already claim something DIFFERENT? "
    "Check [[VISION-what-we-are-building]]: the extender is the DOOR, not the destination. "
    "(3) Have you briefed this leg to an adversary, or only the legs you like? "
    "Name the legs you did NOT brief."
)
_CLAIM_PATH_RE = re.compile(
    r"(^|/)(memory/(business/strategy|design/aris|claude/feedback)/|.*(?:strategy|positioning|vision).*)",
    re.I,
)
_CLAIM_FINDING_RE = re.compile(r"(^|/)FINDING-[^/]+\.md$", re.I)
_MOAT_RE = re.compile(
    r"\b(defensible|moat|structural|they cannot|nobody else can|can't be copied|cannot copy|"
    r"unfair advantage|durable advantage|only we can)\b",
    re.I,
)
# A claim is made in PROSE. `ctx` is command + file_path + new_string + content, so without this the
# binding fired on any module whose comments happened to say "moat"/"structural"/"strategy".
_PROSE_TARGET_RE = re.compile(r"\.md\b", re.I)
_FALSIFIER_SECTION_RE = re.compile(
    r"(?m)^\s{0,3}#{1,6}\s+(?:what would falsify|falsifier|falsifiers|falsification)\b",
    re.I,
)


def is_claim_shaped_write(ctx, target=""):
    """Return True when a Write/Edit is the nearest act to a strategic claim forming.

    Strategy/positioning/vision/FINDING writes are claim-shaped by path, but stay quiet when
    the draft already includes an explicit falsifier section. Moat-shaped language is stronger:
    it fires even with a falsifier section because the 2026-07-27 miss was not "no falsifier";
    it was "the unbriefed leg was never sent to an adversary."
    """
    text = ctx or ""
    # A CLAIM IS MADE IN PROSE (2026-07-27 narrowing). `ctx` carries the file CONTENT, so before this
    # guard 51 of 429 scripts/*.py (11.9%) fired when written — triggered by `moat` ×23, `structural`
    # ×16, `strategy` ×11 appearing in comments and docstrings. A module that MENTIONS the moat is not
    # MAKING a strategic claim; that is the same mention-vs-doing defect the guards had.
    # ⚠ Matching ".md" anywhere in ctx was NOT enough (only 11.9% → 6.0%): 26 modules NAME a markdown
    # file they generate (arxiv-sync.py → digest.md). Only the write TARGET settles it, so callers
    # pass it explicitly; the blob fallback stays for the --ctx CLI, which is a test path.
    if target:
        if not target.lower().endswith((".md", ".markdown")):
            return False
    elif not _PROSE_TARGET_RE.search(text):
        return False
    pathish = bool(_CLAIM_PATH_RE.search(text) or _CLAIM_FINDING_RE.search(text))
    moatish = bool(_MOAT_RE.search(text))
    if not (pathish or moatish):
        return False
    if pathish and not moatish and _FALSIFIER_SECTION_RE.search(text):
        return False
    return True


def _claim_shaped_binding(ctx, target=""):
    if os.environ.get("CLAIM_SHAPED_BINDING_DISABLE") == "1":
        return []
    if not is_claim_shaped_write(ctx, target):
        return []
    return [{
        "path": CLAIM_BINDING_PATH,
        "deliver": "act",
        "on": "write",
        "match": "strategy, positioning, vision, finding, moat, defensible, structural",
        "essence": CLAIM_BINDING_ESSENCE,
        "who": "all",
        "builtin": "claim-shaped-write",
    }]


def _load():
    try:
        return json.loads(LEDGER.read_text())
    except Exception:
        return {}


def _save(d):
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(d))
    except Exception:
        pass


def _session_id(payload=None):
    """Same stdin contract session-vitals.py uses. An absent id degrades to a shared bucket —
    weaker dedupe, never silence."""
    try:
        if isinstance(payload, dict) and payload.get("session_id"):
            return str(payload["session_id"])[:40]
    except Exception:
        pass
    return os.environ.get("CLAUDE_SESSION_ID", "nosession")[:40]


def held_back(crystal, act, session=None):
    """Stable assignment using the full telemetry identity, never the dedupe fallback/id.

    Unknown is one shared unknown bucket, NOT a fabricated session. Invalid percentages
    fail open like the delivery hook. No env setting means no hashing or suppression.
    """
    try:
        pct = float(os.environ.get("CRYSTAL_HOLDBACK_PCT", "0"))
    except ValueError:
        return False
    if not 0 < pct <= 100:
        return False
    identity = [session or os.environ.get("CLAUDE_SESSION_ID") or "unknown",
                os.path.basename(crystal.get("path") or "?"), act]
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=True).encode()).digest()
    return int.from_bytes(digest, "big") < (pct / 100) * (1 << 256)


def _infer_act(payload):
    """Derive the act from the hook payload when CRYSTAL_ACT is not set explicitly."""
    if os.environ.get("CRYSTAL_ACT"):
        return os.environ["CRYSTAL_ACT"].strip().lower()
    if not isinstance(payload, dict):
        return ""
    ev = str(payload.get("hook_event_name") or "").lower()
    tool = str(payload.get("tool_name") or "").lower()
    if ev == "sessionstart":
        return "boot"
    if ev == "userpromptsubmit":
        return "prompt"
    if ev == "pretooluse":
        if tool == "bash":
            return "bash"
        if tool in ("write", "edit", "notebookedit"):
            return "write"
        # 2026-08-02: briefing a subagent is its own act, and it was invisible to every guard we owned.
        # Both names are matched because the harness has used each: `Task` historically, `Agent` now.
        if tool in ("task", "agent"):
            return "delegate"
    return ""


# ⛔ RELEVANCE FELL AS THE WRITE GOT LONGER, WHICH IS EXACTLY BACKWARDS. MEASURED 2026-09-17 on a
# 7,638-char handoff: matching the FILE PATH admitted 2 crystals, matching the DOCUMENT TEXT admitted
# 39. `match:` is a substring test, so every extra paragraph buys more accidental keyword hits, the
# 4000-char budget then delivers two of them and starves thirty-seven. Writing prose that evening
# surfaced two long crystals about pty panes and `glow` staying on screen, ranked top of thirty-five.
# The more careful the work, the noisier the channel got.
#
# THE RULE: a key hit deep in a long body is a coincidence; a key hit in the SUBJECT is relevance.
# The subject of a write is its path plus its opening (title, frontmatter, lede). Below LONG_CTX the
# whole payload IS the subject, so short acts, every bash command among them, keep today's behaviour
# byte for byte and the existing bindings cannot regress.
HEAD_CHARS = 600         # path + title + frontmatter + lede: what the write is ABOUT
LONG_CTX = 2000          # above this, body-only keyword hits stop predicting relevance


def match_scope(ctx, target="", long_ctx=None, head=None):
    """The text a `match:` key must appear in for this act. See the note above."""
    long_ctx = LONG_CTX if long_ctx is None else long_ctx
    head = HEAD_CHARS if head is None else head
    ctx = ctx or ""
    subject = ctx if len(ctx) <= long_ctx else ctx[:head]
    return (subject + " " + (target or "")).lower()


def matches_ctx(c, ctx_l):
    """Does this crystal's `match:` comma-list admit this act's text? No `match:` ⇒ always.

    `ctx_l` is the SCOPE from match_scope(), not the raw payload. An unconditional binding (no
    `match:` list) is deliberate and still always admitted; narrowing applies to keyword bindings.
    """
    # ⭐ DEPENDENCY GATING (deliverable 2 of the invalidation ticket, 2026-09-22). `match:` is a broad
    # OR-list, so a crystal about ONE resource fires on acts about any other. Measured: the vimsara
    # crystal fired identically for `start-instances --instance-ids i-0537b62e3a76cc5aa` and for a
    # DIFFERENT instance id, because `vimsara` and `start-instances` are also in its match list.
    # `depends_on:` is an AND on top: the act must actually NAME this crystal's resource.
    # Deterministic — a literal id the act already carries, never an embedding, and it can only ever
    # NARROW delivery, so a crystal without the key behaves exactly as before.
    dep = (c.get("depends_on") or "").strip().lower()
    if dep:
        ids = [d.strip() for d in dep.split(",") if d.strip()]
        if ids and not any(d in ctx_l for d in ids):
            # ⚠ ONLY gate when the act names a COMPETING resource of the same shape. A blunt
            # "deps must appear" also silenced a generic `vimsara` mention, and this crystal's whole
            # job is to stop you PLANNING a run — losing that is a worse failure than the noise it
            # fixes. So: the act names some `i-…`/`vol-…` that is not ours ⇒ it is about a different
            # resource, withhold. The act names no such id at all ⇒ fall through to `match:` as before.
            # Recall is preserved; only the wrong-resource case is removed.
            prefixes = {d.split("-", 1)[0] + "-" for d in ids if "-" in d}
            competing = any(re.search(r"\b" + re.escape(p) + r"[0-9a-z]{6,}", ctx_l)
                            for p in prefixes)
            if competing:
                return False
    mp = (c.get("match") or "").strip().lower()
    if not mp:
        return True
    keys = [k.strip() for k in mp.split(",") if k.strip()]
    return (not keys) or any(k in ctx_l for k in keys)


def candidates(act, ctx="", target="", who=None, repo=None, crystals=None):
    """Everything act-bound + who-admitted + essence-bearing + `match`-satisfied for this act.

    The set that SHOULD be considered, before any budget is applied. Split out of due_for so the
    audit can replay it without touching the ledger (crystal-selftest-green-is-not-correct — the
    instrument must ask the delivery path, not model it; that divergence is exactly what let three
    crystals read as healthy while being unroutable, 2026-08-02).
    """
    import crystal_registry as cr
    who = who or os.environ.get("CRYSTAL_WHO", "frontier")
    cands = cr.for_act(crystals if crystals is not None else cr.load_crystals(str(repo or REPO)),
                       act, who=who)
    if act == "write":
        cands = _claim_shaped_binding(ctx, target) + cands
    ctx_l = match_scope(ctx, target)
    live = [c for c in cands if (c.get("essence") or "").strip() and matches_ctx(c, ctx_l)]
    # ⛔ ACT-CHANNEL STALENESS, applied HERE so the audit replay and the real hook cannot diverge —
    # the same reason `candidates` was split out of `due_for` in the first place. An expired crystal
    # keeps its slot but delivers a stub instead of its essence: it must never assert live state it
    # can no longer vouch for, and it must not vanish either, or a session repeats it from memory.
    return cr.apply_staleness(live)


def order(cands, act, session, led=None, now=None):
    """THE PRIORITY RULE — rotation first, packing second. Returns a NEW ordered list.

    ⛔ WHY (measured 2026-08-02, real corpus of 158 crystals / 34 act-bound). The old key was
    `0 if c['match'] else 1` — match-bearing crystals ahead of generic ones, from the 2026-07-23
    crowd-out fix. **ALL 34 act crystals now carry `match:`**, so that key is a total no-op and the
    real order was `os.walk` + `sorted(filenames)`, i.e. ALPHABETICAL PATH. Delivery priority was
    being decided by a crystal's filename. Kept as the tiebreak it still is, but it can no longer be
    the whole rule.

    THE RULE: **least-served first (rotation), then longest-unheard, then shortest as a packing
    tiebreak, then path for determinism.**
      1. `seen` — times this crystal already fired THIS SESSION for THIS act (the existing ledger
         counter; no new state). A crystal that has not been heard yet outranks one that has.
      2. `last` — when it last fired for this act (the existing throttle timestamp). Longest-unheard
         first among equals.
      3. essence length ASC — **a packing heuristic, NOT a priority.** ⚠ "Shortest first" on its own
         is the obvious-and-wrong rule: it optimises for COUNT and permanently starves the fat
         crystals, which here are load-bearing (check-the-store 3396, superseded-essence 3080).
         It is only safe UNDER rotation: being starved does not increment `seen`, so a crystal that
         loses this act outranks every winner on the next one. Rotation is what turns starvation
         from permanent into a one-act delay.
      4. path — deterministic, so two runs agree.

    SIGNALS DELIBERATELY NOT USED, with the evidence (checked, not assumed, 2026-08-02):
      · `tier:` — populated on **1 of 34** act crystals (53/158 corpus-wide, but almost all on rag).
        Ordering by a field 97% of the population lacks is ordering by its absence.
      · `minted:` recency — **18 of 34**. Half the set lands in an "unknown" bucket, and mint date is
        not evidence of importance anyway (an old crystal is often the load-bearing one).
      · all-time delivery counts from `crystal-deliveries.jsonl` — populated (33/34) but it mixes
        boot/rag/act channels and rewards crystals whose `match:` happens to be common. It measures
        MATCH FREQUENCY, not need. The per-session ledger counter above is the same idea scoped to
        the thing we actually control: airtime within one session.
    """
    led = _load() if led is None else led
    now = time.time() if now is None else now

    def key(c):
        base = os.path.basename(c.get("path", ""))
        return (led.get(f"act-session:{session}:{act}:{base}", 0),
                led.get(f"act:{act}:{base}", 0.0),
                len(c.get("essence") or ""),
                base)
    return sorted(cands, key=key)


class Due(list):
    """The delivered crystals, carrying what they displaced.

    ⛔ A LIST SUBCLASS ON PURPOSE. `due_for` had EIGHT call sites treating its result as a plain list;
    returning a tuple would have rewritten every one of them to learn a fact only `main` uses. This
    keeps len()/iteration/comprehension identical and hangs the starvation data off the side.
    """
    starved = 0
    starved_names = ()
    starved_pairs = ()



def _redacted(text):
    """Strip credential-shaped strings before this leaves for a model's context.

    ⛔ THE COMMIT GATE CANNOT COVER THIS CHANNEL. Our secret scan reads the staged diff and tracked-file
    content; a delivery carries whatever is in the store right now, including a file edited but not yet
    committed. And in a shipped install the store is a stranger's. Fails OPEN on any error: a redactor
    that can crash the delivery would silence the channel it exists to protect, which is the worse
    failure. Verified not to alter any of our 95 shipped essences or the scratchpad.
    """
    try:
        import redact
        return redact.redact(text)
    except Exception:
        return text

def pack(cands, budget=None):
    """Greedy fit at whole-crystal granularity. Returns (delivered, starved) as [(c, piece)].

    ⛔ THE DEFECT THIS FIXES (re-derived 2026-08-02 against the real corpus). This loop used to
    `break` at the first crystal that would not fit, so ONE fat crystal ended delivery for every
    crystal behind it. Measured on a realistic write (benchmark + superseded number + pricing claim
    + matcher + selftest): 8 matched, 11,559 chars — break delivered **3**, using only **1807 of the
    4000-char budget**. It was not merely unfair, it left 55% of the budget unspent. Skipping instead
    of breaking delivers 5 for 3568 chars, and the 3 it still cannot fit come back first next act
    (see `order`). The budget stays 4000 on purpose: it is the wallpaper guard
    (crystal-inject-budget-discipline), and a fix that delivered all 8 every time would be the
    regression, not the win.
    """
    budget = CHARS_BUDGET if budget is None else budget
    got, starved, used = [], [], 0
    for c in cands:
        piece = f"✦ {(c.get('essence') or '').strip()}"
        if used and used + len(piece) > budget:
            starved.append((c, piece))
            continue            # SKIP, never break — a fat crystal must not silence the queue
        got.append((c, piece))
        used += len(piece)
    return got, starved


def plan(act, ctx="", target="", who=None, repo=None, crystals=None, session="plan",
         led=None, budget=None, now=None):
    """Pure what-would-happen for one act: matched / delivered / starved. Reads NO ledger unless one
    is handed in, and writes none — the audit replays with this."""
    cands = candidates(act, ctx=ctx, target=target, who=who, repo=repo, crystals=crystals)
    ordered = order(cands, act, session, led=led if led is not None else {}, now=now)
    got, starved = pack(ordered, budget)
    return {"matched": cands, "ordered": ordered, "delivered": got, "starved": starved}


def due_for(act, session, now=None, repo=None, dry=False, ctx="", target="", max_n=None):
    """The crystals that should fire for this act right now. Pure enough to test.

    `ctx` is the act's text (a bash COMMAND, a write's FILE PATH + the CONTENT being written) so a
    crystal can bind to a SPECIFIC act, not just the act TYPE: a `match:` in the binding fires the
    crystal only when it is relevant to THIS act. `match` is a COMMA-LIST of substrings — the crystal
    fires if ANY is in ctx (R2, 2026-07-24) — so a topic-specific crystal lists its topic words
    (`match: cost, pricing, subscription`) and fires only when the act is about that topic, instead of
    on every write/bash (the "topic-blind wallpaper" failure). A crystal with NO `match` fires on any
    occurrence of the act, as before (reserve that for genuinely universal disciplines).
    This was declared in the convention but originally NEVER IMPLEMENTED — for_act ignored `match`, so it
    was decorative and crystals over-fired on EVERY act.

    `dry=True` INSPECTS without consuming: no ledger write, no counter bump, no backoff started.
    Load-bearing — verified 2026-07-21 that the old `--dry` path bumped the ledger like a real
    delivery, so checking a new crystal three times burned its whole 3-per-session budget and it
    then reported as not-firing. A verification tool that mutates the state it reports on will make
    correct work look broken. (crystal-selftest-green-is-not-correct — verify the instrument.)
    """
    now = time.time() if now is None else now
    led = _load()

    # 1. WHAT MATCHES — act + who + essence + `match:` (comma-list; any key in ctx). A topic crystal
    #    fires only when the act is about its topic, not on every write/bash (the wallpaper fix).
    cands = candidates(act, ctx=ctx, target=target, repo=repo)

    # 2. WHAT IS ELIGIBLE RIGHT NOW — the per-session cap and the backoff. Done BEFORE ordering so an
    #    exhausted crystal cannot influence the order of the ones that can still speak.
    eligible = []
    for c in cands:
        base = os.path.basename(c.get("path", ""))
        seen = led.get(f"act-session:{session}:{act}:{base}", 0)
        if seen >= MAX_PER_SESSION:
            continue
        # ⛔ AN EXPIRED CRYSTAL IS ANNOUNCED ONCE PER SESSION, THEN GOES QUIET. Raised by Grok in the
        # 2026-09-22 review of this mechanism and re-derived here: a stub still bumps the session
        # counter at the bottom of this function, so it rotates like any live crystal and keeps taking
        # a slot and ~675 chars of a 4000-char shared budget — for a payload that carries no knowing,
        # only a pointer. Enough expired crystals and the withhold notices ARE the channel.
        # Once is what the pointer is worth; after that, silence costs the reader nothing.
        if c.get("expired") and seen >= 1:
            continue
        if now - led.get(f"act:{act}:{base}", 0) < BASE_MIN * (BACKOFF_BASE ** seen) * 60:
            continue
        # Remove before packing AND the tier-0 hints: a held-back knowing must not leak
        # through the short-form starvation footer or consume delivery/backoff budget.
        if held_back(c, act, session):
            if not dry:
                import crystal_registry as cr
                # ⛔ TWO SENTINELS: _session_id() returns "nosession", the ledger documents "unknown".
                # Passing the sentinel through would put BOTH in the file and a join on
                # "unknown" would silently miss those rows. Normalise to one here.
                cr.record_delivery("act", c.get("path"), event="suppressed-holdback", act=act,
                                   session=(session if session and session != "nosession" else None))
            continue
        eligible.append(c)

    # 3. ORDER — least-served first, so a starved crystal comes back ahead of one just heard.
    # 4. PACK — SKIP the ones that will not fit; never `break` (see `pack`).
    # ⛔ THE STARVED LIST USED TO BE DISCARDED INTO `_starved` RIGHT HERE, AND THAT WAS THE WHOLE
    # DEFECT. pack() has always computed exactly what the budget displaced; nothing ever told the
    # reader. MEASURED 2026-08-11 across 85 replayed acts: 729 crystals matched, 200 delivered (27%),
    # 52 acts starved at least one, and the worst act delivered 5 of 46. A reader saw five knowings
    # and had no way to know forty-one others had matched. Silent truncation is indistinguishable
    # from "there was nothing else to say".
    out, _starved = pack(order(eligible, act, session, led=led, now=now))
    out = Due(out)
    out.starved = len(_starved)
    out.starved_names = tuple(os.path.basename(c.get("path", "")) for c, _p in _starved)
    out.starved_pairs = tuple(_starved)          # cascade tier 0 needs the crystal, not just its name

    # 5. CAP — `max_n` is applied HERE, inside selection, and that placement is the whole point.
    #    A caller that trimmed the returned list downstream still left this function believing it had
    #    delivered every crystal: the ledger below was bumped and `record_delivery` wrote a telemetry
    #    row for crystals the reader never saw. Delivery counts read high and the per-session budget of
    #    a never-heard crystal was silently spent. Capping before the ledger write keeps "recorded as
    #    delivered" and "actually handed over" the same set. Crystals cut here are NOT consumed — they
    #    keep seen=0 and so lead the next act by the rotation rule in `order`.
    if max_n is not None:
        try:
            n = int(max_n)
        except (TypeError, ValueError):
            n = None
        if n is not None:
            # ⚠ A PLAIN SLICE OF A Due RETURNS A PLAIN list AND DROPS THE STARVATION COUNT — which
            # would make the announcement vanish for exactly the callers that cap hardest.
            cut = out[max(0, n):]
            kept = Due(out[:max(0, n)])
            kept.starved = out.starved + len(cut)
            kept.starved_names = out.starved_names + tuple(
                os.path.basename(c.get("path", "")) for c, _p in cut)
            kept.starved_pairs = getattr(out, "starved_pairs", ()) + tuple(cut)
            out = kept

    if not dry:
        for c, _piece in out:
            base = os.path.basename(c.get("path", ""))
            led[f"act:{act}:{base}"] = now
            led[f"act-session:{session}:{act}:{base}"] = led.get(
                f"act-session:{session}:{act}:{base}", 0) + 1
    if out and not dry:
        # prune timestamps only; session counters are COUNTS, not times
        led = {k: v for k, v in led.items()
               if k.startswith("act-session:") or now - v < 86400}
        _save(led)
    return out


def _read_payload(argv):
    """Read the hook payload from stdin WITHOUT ever blocking forever.

    ⛔ 2026-07-28: `crystal_act.py --act ... --dry` hung indefinitely, and four orphaned processes
    (Sun, Mon, and twice on 07-28) had been accumulating unnoticed. The `isatty()` guard below is not
    enough: under the Claude Code bash harness stdin is a PIPE, not a tty, and nothing ever closes the
    write end — so `sys.stdin.read()` waits for an EOF that never comes. It read as "the crystal
    system is wedged" and cost a session's confidence in every delivery claim; it was only ever the CLI
    blocking on an empty pipe.

    Two independent stops: the hooks call this script with NO argv (act inferred from the payload), so
    an explicit `--act` means a human/CLI invocation that never needs stdin; and a select() timeout
    backstops every other path.
    """
    if any(arg == "--act" or arg.startswith("--act=") for arg in argv):
        return {}
    try:
        if sys.stdin.isatty():
            return {}
        if not select.select([sys.stdin], [], [], 2.0)[0]:
            return {}                   # nothing piped within 2s — treat as no payload, never block
        return json.loads(sys.stdin.read() or "{}") or {}
    except Exception:
        return {}


def main():
    parser = argparse.ArgumentParser(description="Deliver act-bound crystals", allow_abbrev=False)
    for flag in ("act", "ctx", "target", "max"):
        parser.add_argument("--" + flag)
    for flag in ("dry", "text", "selftest"):
        parser.add_argument("--" + flag, action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    payload = _read_payload(sys.argv[1:])

    act = args.act.strip().lower() if args.act is not None else _infer_act(payload)
    if not act:
        return 0

    # the act's text, so a crystal's `match:` can bind to a SPECIFIC act, not just the act type.
    # Include the CONTENT being written (new_string/content), not just the path — a topic-specific
    # write crystal (cost, superseded-number, acknowledgment…) is relevant to WHAT you are writing,
    # which lives in the content, not the filename. This is what makes match topic-relevant instead of
    # path-only. (R2, 2026-07-24: the topic crystals were firing on every write regardless of content.)
    ti = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    ctx = " ".join(str(ti.get(k) or "") for k in ("command", "file_path", "new_string", "content"))[:8000]
    # The write TARGET, kept separate from the blob: ctx cannot distinguish the file being written
    # from a filename merely NAMED inside it, and that ambiguity was the claim-binding's whole false
    # positive rate (2026-07-27).
    target = str(ti.get("file_path") or "")
    if args.ctx is not None:             # test/CLI override
        ctx = args.ctx
    if args.target is not None:
        target = args.target
    max_n = None
    if args.max is not None:
        try:
            max_n = int(args.max)
        except ValueError:
            max_n = None                # a malformed --max means "no cap", never "deliver nothing"

    try:
        session = _session_id(payload)
        due = due_for(act, session, dry=args.dry, ctx=ctx, target=target,
                      max_n=max_n)
    except Exception:
        return 0                        # delivery must never break a turn

    if not due:
        return 0
    header = (f"✦ CRYSTAL — you are about to {act}. "
              f"{'This knowing is' if len(due) == 1 else 'These knowings are'} bound to that act, "
              f"not matched by topic:")
    body = "\n\n".join(p for _c, p in due)
    # ⭐ ANNOUNCE WHAT THE BUDGET DISPLACED, AT THE POINT OF DELIVERY. The whole class of failure this
    # closes is "written successfully, silently never delivered": every check we had asked whether a
    # crystal COULD fire, and none asked whether the reader got the whole set. A truncated delivery is
    # indistinguishable from a short one unless it says so.
    # ⚠ Deferred, not lost — being starved does not bump `seen`, so these lead the next act by the
    # rotation rule in `order`. That is real mitigation ACROSS acts and none at all FOR THIS ONE, which
    # is the act the knowing was bound to. Say "did not fit", never "lost".
    # ⚠ This footer is appended AFTER packing, so it costs ~1 line beyond CHARS_BUDGET rather than
    # displacing a crystal to describe the displacement.
    if getattr(due, "starved", 0):
        # ⭐ CASCADE TIER 0 (2026-08-31): announce each starved crystal by its TELL,
        # not its FILENAME. A filename carries no knowledge, so the old footer spent
        # its characters naming things the reader still could not act on. A tell is
        # ~100 chars against a 1496-char essence median, so the cheap tier buys most
        # of the value for ~7% of the budget. Tier 1 remains the full essence next act.
        tells = []
        for c, _piece in getattr(due, "starved_pairs", ())[:TIER0_MAX]:
            name = os.path.basename(c.get("path", "")) or "crystal"
            try:
                import crystal_registry
                t = (crystal_registry.tell(c, TIER0_CHARS) or "").strip()
            except Exception:
                t = ""
            # ⚠ A BLANK TIER 0 IS WORSE THAN A FILENAME. Found by mutation 2026-08-31:
            # guarding only the empty LIST still emitted "  · " bullets when an individual
            # tell came back empty. Fall back PER CRYSTAL, not just for the whole set.
            tells.append(f"  · {t or name}")
        if not tells:                       # never emit an empty tier 0
            tells = [f"  · {n}" for n in due.starved_names[:TIER0_MAX]]
        more = f"\n  · +{due.starved - len(tells)} more" if due.starved > len(tells) else ""
        body += (f"\n\n⚠ {due.starved} further knowing(s) matched this act and did not fit the "
                 f"{CHARS_BUDGET}-char budget. The short form of each:\n"
                 + "\n".join(tells) + more
                 + f"\nThey rank first on your next act; in full: python3 scripts/crystal_act.py --act {act} --dry")
    if args.dry:
        print(f"[dry] act={act} would fire {len(due)}:")
        for c, _p in due:
            print("   ", os.path.basename(c.get("path", "")))
        return 0
    ev = payload.get("hook_event_name") or os.environ.get("CRYSTAL_ACT_EVENT", "PreToolUse")
    if args.text:
        # For callers that are NOT the Claude Code hook harness — a git hook, a shell wrapper. The JSON
        # envelope only means something to the harness; anywhere else it is noise a human never reads.
        # This is what let the `commit` act stay dead: it was a documented act with a bound crystal and
        # NOTHING that could render it. Still records telemetry, so a commit delivery is measurable.
        sys.stderr.write("\n" + header + "\n" + body + "\n\n")
        try:
            import crystal_registry as cr
            for c, _p in due:
                cr.record_delivery("act", c.get("path"), event=ev, act=act,
                                   session=(session if session and session != "nosession" else None))
        except Exception:
            pass
        return 0
    print(json.dumps({"hookSpecificOutput": {"hookEventName": ev,
                                             "additionalContext": _redacted(header + "\n" + body)}}))
    try:
        import crystal_registry as cr
        for c, _p in due:
            cr.record_delivery("act", c.get("path"), event=ev, act=act,
                               session=(session if session and session != "nosession" else None))
    except Exception:
        pass                        # telemetry must never cost a delivery
    return 0


def selftest():
    import crystal_registry as cr
    global LEDGER
    ok = True
    def check(c, label):
        nonlocal ok
        print(("  [PASS] " if c else "  [FAIL] ") + label)
        ok = ok and bool(c)

    cs = [{"path": "/x/a.md", "on": "bash", "essence": "E1", "who": "all"},
          {"path": "/x/b.md", "on": "commit,write", "essence": "E2", "who": "all"},
          {"path": "/x/c.md", "essence": "E3", "who": "all"},              # no act
          {"path": "/x/d.md", "on": "bash", "essence": "E4", "who": "resident"}]
    check([c["path"] for c in cr.for_act(cs, "bash", who="frontier")] == ["/x/a.md"],
          "act match, and `who` still filters (resident crystal excluded)")
    check([c["path"] for c in cr.for_act(cs, "commit", who="frontier")] == ["/x/b.md"],
          "comma list matches on either act")
    check(cr.for_act(cs, "write", who="frontier")[0]["path"] == "/x/b.md",
          "…and on the second act in the list")
    check(cr.for_act(cs, "typo-act", who="frontier") == [],
          "an UNKNOWN act fires nothing (a typo must go quiet, never spam)")
    check(cr.for_act(cs, "", who="frontier") == [],
          "empty act fires nothing")
    check(all(c.get("on") for c in cr.for_act(cs, "bash", who=None)),
          "a crystal with no `on:` is never act-delivered")

    # --- SUBJECT SCOPE: relevance must not fall as the payload grows ------------------------------
    # Regression this closes, MEASURED 2026-09-17: `match:` was tested against the WHOLE payload, so a
    # 7,638-char handoff admitted 39 crystals where its path admitted 2, and the two actually
    # delivered were about pty panes while the act was writing prose. Longer work, worse delivery.
    _far = {"path": "/x/far.md", "on": "write", "essence": "E", "who": "all", "match": "widget"}
    _short = "a note about a widget"
    _long = ("filler. " * 400) + "and here we mention a widget once, deep in the body"
    check(matches_ctx(_far, match_scope(_short)),
          "SCOPE: a key in a SHORT payload still admits (short acts unchanged)")
    check(not matches_ctx(_far, match_scope(_long)),
          "SCOPE: the same key, buried in a LONG body, no longer admits (the 39-crystal defect)")
    check(matches_ctx(_far, match_scope(_long, target="docs/widget-design.md")),
          "SCOPE: …but a key in the TARGET PATH admits even in a long body (subject beats length)")
    check(matches_ctx(_far, match_scope("a widget appears early. " + ("filler. " * 400))),
          "SCOPE: …and a key in the OPENING admits (title/frontmatter/lede is the subject)")
    check(matches_ctx({"path": "/x/blanket.md", "on": "write", "essence": "E", "who": "all"},
                      match_scope(_long)),
          "SCOPE: an unconditional binding (no `match:`) is deliberate and still always admitted")

    # --- `match`: a crystal binds to a SPECIFIC command/file, not just the act type -----------------
    # Regression this closes: `match` was in the convention (reply-lane crystal) but UNIMPLEMENTED, so
    # it was decorative — the crystal over-fired on every bash and author-specific dev-crystals could
    # not be wired. Test with a synthetic store + isolated ledger + far-future `now` (no backoff skip).
    import tempfile as _tf, pathlib as _pl
    _sv = LEDGER
    try:
        LEDGER = _pl.Path(_tf.mkdtemp()) / ".act-ledger.json"
        synth = [{"path": "/x/generic.md", "deliver": "act", "on": "bash", "essence": "GEN", "who": "all"},
                 {"path": "/x/reply.md", "deliver": "act", "on": "bash", "match": "reply-lane",
                  "essence": "REPLY", "who": "all"}]
        _orig = cr.load_crystals
        cr.load_crystals = lambda *a, **k: synth
        try:
            hit = [os.path.basename(c["path"]) for c, _ in
                   due_for("bash", "m1", now=9e12, dry=True, ctx="node reply-lane.mjs 42")]
            miss = [os.path.basename(c["path"]) for c, _ in
                    due_for("bash", "m2", now=9e12, dry=True, ctx="ls -la")]
        finally:
            cr.load_crystals = _orig
        check("reply.md" in hit and "generic.md" in hit,
              "match crystal FIRES when ctx contains its substring; a no-match crystal still fires")
        check("reply.md" not in miss and "generic.md" in miss,
              "match crystal is SILENT when ctx lacks its substring; no-match crystal unaffected")
    finally:
        LEDGER = _sv

    # --- R2: `match` is a COMMA-LIST (any key), and ctx is content-aware (topic-relevance, not path-only) --
    _sv2 = LEDGER
    try:
        LEDGER = _pl.Path(_tf.mkdtemp()) / ".act-ledger.json"
        synth2 = [{"path": "/x/cost.md", "deliver": "act", "on": "write", "essence": "COST",
                   "match": "cost, pricing, subscription", "who": "all"}]
        _orig = cr.load_crystals
        cr.load_crystals = lambda *a, **k: synth2
        try:
            # a write whose CONTENT mentions a topic word fires, even if the FILE PATH does not
            on_topic = [os.path.basename(c["path"]) for c, _ in
                        due_for("write", "c1", now=9e12, dry=True,
                                ctx="scratchpad.md we route work to a cheaper subscription tier")]
            # second keyword in the list also fires
            second = [os.path.basename(c["path"]) for c, _ in
                      due_for("write", "c2", now=9e12, dry=True, ctx="notes.md our pricing model")]
            # off-topic write stays silent (this is the wallpaper fix)
            off = [os.path.basename(c["path"]) for c, _ in
                   due_for("write", "c3", now=9e12, dry=True, ctx="notes.md a note about cats")]
        finally:
            cr.load_crystals = _orig
        check("cost.md" in on_topic, "comma-list match fires on the 3rd keyword found in CONTENT (not path)")
        check("cost.md" in second, "comma-list match fires on a different keyword in the list")
        check("cost.md" not in off, "topic crystal is SILENT on an off-topic write (the wallpaper fix)")
    finally:
        LEDGER = _sv2
    # act inference from real hook payload shapes
    for payload, want in ((({"hook_event_name": "PreToolUse", "tool_name": "Bash"}), "bash"),
                          (({"hook_event_name": "PreToolUse", "tool_name": "Edit"}), "write"),
                          (({"hook_event_name": "UserPromptSubmit"}), "prompt"),
                          (({"hook_event_name": "SessionStart"}), "boot"),
                          (({"hook_event_name": "PreToolUse", "tool_name": "Read"}), "")):
        os.environ.pop("CRYSTAL_ACT", None)
        check(_infer_act(payload) == want,
              f"infer {payload.get('tool_name') or payload.get('hook_event_name')} -> {want or '(none)'}")
    # --dry must INSPECT, never CONSUME. Regression: the dry path used to bump the ledger like a real
    # delivery, so verifying a new crystal 3x burned its session budget and it read as not-firing.
    import tempfile, pathlib
    _saved = LEDGER
    try:
        LEDGER = pathlib.Path(tempfile.mkdtemp()) / ".act-ledger.json"
        _orig = cr.load_crystals
        cr.load_crystals = lambda *a, **k: [
            {"path": "/x/ledger.md", "deliver": "act", "on": "bash", "essence": "LEDGER", "who": "all"}
        ]
        try:
            first = due_for("bash", "s1", dry=True)
            again = due_for("bash", "s1", dry=True)
            check(bool(first) and len(first) == len(again),
                  "--dry is repeatable — inspecting does not consume the budget it reports on")
            check(not LEDGER.exists(),
                  "--dry writes no ledger at all")
            real = due_for("bash", "s2", dry=False)
            check(bool(real) and LEDGER.exists(),
                  "a REAL delivery still records (the fix did not disable the ledger)")
        finally:
            cr.load_crystals = _orig
    finally:
        LEDGER = _saved
    # --- BUDGET: SKIP, NEVER BREAK + rotation (2026-08-02) ------------------------------------------
    # ⚠ These restate intent, which is exactly what a hand-written selftest is worst at. The load-bearing
    # measurement is the REAL-CORPUS replay: `python3 scripts/crystal_delivery_audit.py --budget`.
    # ⚠ Names chosen so ALPHABETICAL order (the pre-fix de-facto rule) disagrees with rotation order at
    # every step — otherwise the old behaviour passes these and the guard proves nothing.
    # Verified by removing the fix: pack=break → 3 FAIL, order=walk → 4 FAIL.
    fat = {"path": "/x/z-fat.md", "deliver": "act", "on": "bash", "essence": "F" * 3000, "who": "all"}
    mid = {"path": "/x/a-mid.md", "deliver": "act", "on": "bash", "essence": "M" * 1500, "who": "all"}
    thin = {"path": "/x/m-thin.md", "deliver": "act", "on": "bash", "essence": "T" * 200, "who": "all"}
    got, starved = pack([fat, mid, thin], budget=4000)
    names = [os.path.basename(c["path"]) for c, _ in got]
    check(names == ["z-fat.md", "m-thin.md"],
          "pack SKIPS the crystal that will not fit and keeps going (mid starved, thin still fires)")
    check([os.path.basename(c["path"]) for c, _ in starved] == ["a-mid.md"],
          "pack REPORTS what it starved (the guard reads this)")

    # ⛔ AND THE REPORT MUST SURVIVE THE TRIP TO THE READER. pack() always computed `starved`;
    # due_for threw it away into `_starved`, so a reader got five knowings with no way to know
    # forty-one more had matched. Silent truncation reads exactly like "nothing else to say".
    # ⚠ THE FIRST VERSION OF THIS TEST WAS A NO-OP — it guarded on a `crystals` kwarg due_for does
    # not have, so it never ran and passed anyway. A test that silently does not test is the same
    # defect as a channel that silently does not deliver.
    d1 = due_for("bash", "starve1", now=9e12, dry=True, ctx="ls -la")
    check(isinstance(d1, Due) and isinstance(d1.starved, int),
          "due_for RETURNS a Due carrying the starvation count (not a bare list)")
    d2 = due_for("bash", "starve2", now=9e12, dry=True, ctx="ls -la", max_n=1)
    check(isinstance(d2, Due) and isinstance(d2.starved, int) and len(d2) <= 1,
          "the max_n cap PRESERVES the count (a plain slice would silently drop it)")
    check(d2.starved >= d1.starved,
          "capping to 1 starves at least as many as the budget alone")
    check(sum(len(p) for _c, p in got) <= 4000, "pack never exceeds the budget")
    # the pre-fix behaviour, stated so the regression is legible: break would have stopped at mid.
    _brk, _u = [], 0
    for _c in [fat, mid, thin]:
        _p = f"✦ {_c['essence']}"
        if _u and _u + len(_p) > 4000:
            break
        _brk.append(_c); _u += len(_p)
    check([os.path.basename(c["path"]) for c in _brk] == ["z-fat.md"] and len(got) > len(_brk),
          "…and the old `break` delivered strictly fewer (1 vs 2) on the same input")

    # ROTATION: a crystal starved on act N outranks the winners on act N+1, because being starved
    # does not increment the session counter. This is what keeps "shortest first" from being the
    # permanent bias it would otherwise be.
    _led = {}
    check([os.path.basename(c["path"]) for c in order([mid, thin, fat], "bash", "r1", led=_led)]
          == ["m-thin.md", "a-mid.md", "z-fat.md"],
          "cold order is shortest-first (packing tiebreak, all seen=0) — NOT alphabetical")
    _led["act-session:r1:bash:m-thin.md"] = 1
    _led["act-session:r1:bash:a-mid.md"] = 1
    check(order([mid, thin, fat], "bash", "r1", led=_led)[0]["path"] == "/x/z-fat.md",
          "ROTATION: the un-served fat crystal leads once its neighbours have been heard")
    _led["act-session:r1:bash:z-fat.md"] = 1
    _led["act:bash:a-mid.md"] = 500.0        # mid was heard LATER than thin
    _led["act:bash:m-thin.md"] = 100.0
    check(order([mid, thin], "bash", "r1", led=_led)[0]["path"] == "/x/m-thin.md",
          "…equally-served crystals break the tie on LONGEST-UNHEARD, not on filename")

    # --- `--max N`: cap INSIDE selection, so a capped-out crystal is not recorded as delivered -------
    # The API gap this closes: capping downstream still bumped the ledger and wrote a telemetry row for
    # crystals the reader never saw. The load-bearing assertion is the SECOND one — not "the list is
    # shorter" (trivially true either way) but "the crystal we cut is still unspent."
    _sv3 = LEDGER
    try:
        LEDGER = _pl.Path(_tf.mkdtemp()) / ".act-ledger.json"
        synth3 = [{"path": "/x/one.md", "deliver": "act", "on": "bash", "essence": "ONE", "who": "all"},
                  {"path": "/x/two.md", "deliver": "act", "on": "bash", "essence": "TWO-LONGER", "who": "all"}]
        _orig = cr.load_crystals
        cr.load_crystals = lambda *a, **k: synth3
        try:
            uncapped = due_for("bash", "x0", now=9e12, dry=True)
            capped = due_for("bash", "x1", now=9e12, dry=False, max_n=1)
            # the one we did NOT deliver must be untouched: a fresh session sees it first (seen=0),
            # and the delivering session's ledger holds a counter for the delivered crystal only.
            _led_after = _load()
            cut = "two.md"
            kept = os.path.basename(capped[0][0]["path"])
        finally:
            cr.load_crystals = _orig
        check(len(uncapped) == 2 and len(capped) == 1, "--max N truncates the delivered set")
        check(_led_after.get(f"act-session:x1:bash:{kept}") == 1,
              "the crystal that WAS delivered is recorded")
        check(_led_after.get(f"act-session:x1:bash:{cut}") is None
              and f"act:bash:{cut}" not in _led_after,
              "a crystal cut by --max is NOT consumed (no ledger bump, no spent session budget)")
        check(due_for("bash", "x2", now=9e12, dry=True, max_n=0) == [],
              "--max 0 delivers nothing rather than erroring")
    finally:
        LEDGER = _sv3

    print("SELFTEST: " + ("ALL PASS" if ok else "FAILURES ABOVE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
