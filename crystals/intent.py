"""Durable intent journal, inspired by facebookresearch/logact (MIT).

Independent implementation: append intent before acting, append a terminal record
only after success/failure. Pending means outcome UNKNOWN: never auto-replay.
Run ``python -m crystals.intent --help`` for the explicit lifecycle CLI.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from os import open as open_fd
from pathlib import Path
import sys
import uuid

# Windows CRT text descriptors translate LF; the journal is UTF-8 bytes.
BINARY = getattr(os, "O_BINARY", 0)


class IntentLog:
    """One local append-only journal; advisory OS locks serialize cooperating writers.

    ``recovery`` reports unresolved intents at startup. A killed process releases
    its lock. A torn final line is retained and reported, never truncated/replayed.
    fsync completes before begin() returns, so failure prevents the caller's act.
    """
    def __init__(self, store):
        self.path = Path(store).resolve() / "scratch" / "intent-log.jsonl"
        self.lock_path = self.path.with_suffix(".lock")
        self.recovery = self.pending()

    @contextmanager
    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = open_fd(self.lock_path, os.O_CREAT | os.O_RDWR | BINARY, 0o600)
        try:
            if not os.fstat(fd).st_size:
                os.write(fd, b"0")
            os.lseek(fd, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                os.lseek(fd, 0, os.SEEK_SET)
                if os.name == "nt":
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def _read(self):
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            raw = b""
        pending, terminal, damaged = {}, {}, []
        for i, line in enumerate(raw.splitlines(), 1):
            try:
                row = json.loads(line)
                if not isinstance(row, dict) or not {"id", "status", "ts"} <= row.keys():
                    raise ValueError("invalid intent record")
                ident, status = row["id"], row["status"]
                if status == "intended":
                    if ident in pending or ident in terminal:
                        raise ValueError("duplicate intent id")
                    if any(not isinstance(row.get(k), str) for k in ("act", "text", "session")):
                        raise ValueError("invalid intent fields")
                    pending[ident] = row
                elif status in ("committed", "aborted"):
                    if ident not in pending or ident in terminal:
                        raise ValueError("terminal record without pending intent")
                    pending.pop(ident)
                    terminal[ident] = status
                else:
                    raise ValueError("unknown intent status")
            except (ValueError, TypeError, KeyError, UnicodeError):
                # Only the unterminated last line can be a crash-torn write.
                if i != len(raw.splitlines()) or raw.endswith(b"\n"):
                    raise ValueError(f"corrupt intent journal at line {i}") from None
                damaged.append(i)
        return pending, terminal, damaged, raw

    def _append(self, row, raw):
        data = ((b"\n" if raw and not raw.endswith(b"\n") else b"") +
                (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8"))
        fd = open_fd(self.path, os.O_CREAT | os.O_WRONLY | os.O_APPEND | BINARY, 0o600)
        try:
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                if not written:
                    raise OSError("intent journal write made no progress")
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)

    def pending(self):
        with self._locked():
            pending, _, damaged, _ = self._read()
        return {"pending": list(pending.values()), "torn_lines": damaged}

    def begin(self, act, text, session):
        from . import ACTS
        if act not in ACTS or not all(isinstance(v, str) for v in (act, text, session)) or not session:
            raise ValueError("known act, string text and nonempty session required")
        row = dict(id=uuid.uuid4().hex, status="intended", act=act, text=text,
                   session=session, ts=datetime.now(timezone.utc).isoformat())
        with self._locked():
            _, _, damaged, raw = self._read()
            if damaged:
                raise ValueError("torn journal tail: inspect and preserve it before resuming")
            self._append(row, raw)
        return row["id"]

    def finish(self, ident, status):
        if not isinstance(ident, str) or status not in ("committed", "aborted"):
            raise ValueError("intent id and committed/aborted status required")
        with self._locked():
            pending, terminal, damaged, raw = self._read()
            if damaged:
                raise ValueError("torn journal tail: inspect and preserve it before resuming")
            if ident in terminal:
                if terminal[ident] == status:
                    return  # a duplicate post-hook is idempotent
                raise ValueError("conflicting terminal state")
            if ident not in pending:
                raise ValueError("unknown intent id")
            self._append(dict(id=ident, status=status,
                              ts=datetime.now(timezone.utc).isoformat()), raw)

    @contextmanager
    def action(self, act, text, session):
        """Wrap the caller's act; logging errors propagate, and nothing is executed here."""
        ident = self.begin(act, text, session)
        try:
            yield ident
        except BaseException:
            self.finish(ident, "aborted")
            raise
        else:
            self.finish(ident, "committed")


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--store", required=True)
    sub = parser.add_subparsers(dest="operation", required=True)
    begin = sub.add_parser("begin")
    begin.add_argument("--act", required=True)
    begin.add_argument("--text", default="")
    begin.add_argument("--session", required=True)
    for status in ("committed", "aborted"):
        finish = sub.add_parser(status)
        finish.add_argument("id")
    sub.add_parser("recover")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    try:
        journal = IntentLog(args.store)
        if args.operation == "begin":
            result = dict(intent_id=journal.begin(args.act, args.text, args.session),
                          recovery=journal.recovery)
        elif args.operation == "recover":
            result = journal.recovery
        else:
            journal.finish(args.id, args.operation)
            result = dict(id=args.id, status=args.operation)
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"crystals intent: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
