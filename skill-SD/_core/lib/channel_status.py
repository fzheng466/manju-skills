"""Record local channel capability outcomes into $MANJU_HOME/channels."""
from __future__ import annotations

import argparse
import json

from .channel import record_capability


def main() -> int:
    p = argparse.ArgumentParser(description="Write capability probe results to local channel archive")
    p.add_argument("cmd", choices=["record"])
    p.add_argument("--channel", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--cap", required=True)
    p.add_argument("--result", choices=["ok", "fail"], required=True)
    p.add_argument("--observed", default=None, help="JSON object of observed limits")
    args = p.parse_args()
    observed = json.loads(args.observed) if args.observed else None
    path = record_capability(args.channel, args.model, args.cap, args.result, observed)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
