"""Write and load effective-capability.lock.json (per deliverable track)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .channel import file_hash, load_channel, merge_effective, project_tracks


def compute_lock(
    *,
    channel_id: str,
    model_profile: str,
    baseline: dict[str, Any],
    channel_model: dict[str, Any],
    project: dict[str, Any] | None = None,
    baseline_path: Path | None = None,
    channel_path: Path | None = None,
    project_path: Path | None = None,
) -> dict[str, Any]:
    tracks = {}
    for tr in project_tracks(project):
        tracks[tr["track_id"]] = merge_effective(baseline, channel_model, project, tr)
    # backward compat: first track as effective
    first = next(iter(tracks.values()), {})
    return {
        "channel_id": channel_id,
        "model_profile": model_profile,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "tracks": tracks,
        "effective": first,
        "sources": {
            "baseline_hash": file_hash(baseline_path) if baseline_path and baseline_path.is_file() else None,
            "channel_hash": file_hash(channel_path) if channel_path and channel_path.is_file() else None,
            "project_hash": file_hash(project_path) if project_path and project_path.is_file() else None,
        },
    }


def write_lock(path: Path, lock: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_lock(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    p = argparse.ArgumentParser(description="Write effective-capability.lock.json")
    p.add_argument("--project", type=Path, required=True)
    p.add_argument("--channel", required=True, help="channel_id under $MANJU_HOME/channels")
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("effective-capability.lock.json"))
    p.add_argument("--model-key", default=None, help="key inside channel.models (default: first / baseline profile)")
    args = p.parse_args()
    project = json.loads(args.project.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    from .channel import channels_dir

    ch = load_channel(args.channel)
    channel_path = channels_dir() / f"{args.channel}.json"
    if not ch:
        print(f"ERROR: channel {args.channel} not found in {channels_dir()}", file=sys.stderr)
        return 2
    models = ch.get("models") or {}
    mk = args.model_key or baseline.get("model_profile")
    if mk and mk in models:
        channel_model = models[mk]
        baseline_profile = str(baseline.get("model_profile") or "")
        if args.model_key and baseline_profile and args.model_key != baseline_profile:
            print(
                f"ERROR: --model-key {args.model_key!r} does not match baseline model_profile {baseline_profile!r}",
                file=sys.stderr,
            )
            return 2
    else:
        print(
            f"ERROR: channel {args.channel} has no model key {mk!r}; "
            f"available={list(models.keys())}. Pass --model-key explicitly.",
            file=sys.stderr,
        )
        return 2
    lock = compute_lock(
        channel_id=args.channel,
        model_profile=str(baseline.get("model_profile") or mk),
        baseline=baseline,
        channel_model=channel_model,
        project=project,
        baseline_path=args.baseline,
        channel_path=channel_path,
        project_path=args.project,
    )
    write_lock(args.out, lock)
    print(f"wrote {args.out} tracks={list((lock.get('tracks') or {}).keys())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
