#!/usr/bin/env python3
"""Compatibility entry point; implementation lives in the crystals package."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crystals import registry as implementation
# Preserve script-relative hook stores and imports that patch module globals.
implementation.REPO = str(Path(__file__).resolve().parents[1])
implementation.DELIVERY_LOG = implementation.os.environ.get("CRYSTAL_DELIVERY_LOG") or str(Path(implementation.REPO) / "memory" / "corpus" / "crystal-deliveries.jsonl")
if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.exit(implementation.main())
else:
    sys.modules[__name__] = implementation
