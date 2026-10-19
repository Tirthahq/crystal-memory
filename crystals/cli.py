"""Portable CLI: each match is read-only and repeatable."""
import argparse
import json
import sys
from . import ACTS, match


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--store", required=True, help="project directory containing memory/")
    parser.add_argument("--act", required=True, choices=ACTS)
    parser.add_argument("--text", default="", help="act text, e.g. the command about to run")
    parser.add_argument("--target", default="", help="write target path")
    parser.add_argument("--who", default="all", choices=("all", "frontier", "7b", "resident"))
    parser.add_argument("--intent-log", action="store_true", help="durably log this proposed act")
    parser.add_argument("--session", help="required with --intent-log")
    args = parser.parse_args()
    if args.intent_log and not args.session:
        parser.error("--intent-log requires --session")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    try:
        knowings = match(args.act, args.text, store=args.store,
                         target=args.target, who=args.who)
        result = knowings
        if args.intent_log:
            from .intent import IntentLog
            journal = IntentLog(args.store)
            result = dict(knowings=knowings,
                          intent_id=journal.begin(args.act, args.text, args.session),
                          recovery=journal.recovery)
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"crystals: {error}\n")
    return 0
