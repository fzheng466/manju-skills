"""Post-production deliverables: audio plan, SRT, CMX3600 EDL. Fail open."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _lines(project: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for job in project.get("jobs") or []:
        if not isinstance(job, dict):
            continue
        offset = float(job.get("episode_start_seconds") or 0)
        track = job.get("track_id") or ("P" if job.get("aspect_ratio") == "9:16" else "L")
        for shot in job.get("shots") or []:
            if not isinstance(shot, dict):
                continue
            for line in shot.get("dialogue") or []:
                if not isinstance(line, dict):
                    continue
                start = float(line.get("start_seconds") or shot.get("start_seconds") or 0)
                end = float(line.get("end_seconds") or shot.get("end_seconds") or start)
                out.append(
                    {
                        "utterance_id": line.get("utterance_id"),
                        "speaker_id": line.get("speaker_id"),
                        "name": line.get("speaker_name") or line.get("name") or line.get("speaker_id"),
                        "voice_profile_id": line.get("voice_profile_id") or job.get("voice_profile_id"),
                        "track": track,
                        "global_start": offset + start,
                        "global_end": offset + end,
                        "text": line.get("text") or "",
                        "kind": line.get("kind") or "dialogue",
                        "delivery": line.get("delivery") or line.get("tone"),
                        "job_id": job.get("id"),
                        "job_status": job.get("status"),
                    }
                )
    out.sort(key=lambda x: (x["global_start"], x["global_end"]))
    return out


def audio_plan(project: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "audio_post_plan.1", "items": _lines(project)}


def _ts(seconds: float, srt: bool = True) -> str:
    ms = int(round(max(0.0, seconds) * 1000))
    h, rem = divmod(ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    sep = "," if srt else ":"
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{milli:03d}"


def srt_text(project: dict[str, Any], track: str | None = None) -> str:
    blocks = []
    n = 1
    for item in _lines(project):
        if track and item.get("track") != track:
            continue
        text = item["text"]
        if item.get("kind") in {"OS", "VO"}:
            text = f"[{item['kind']}] {text}"
        blocks.append(f"{n}\n{_ts(item['global_start'])} --> {_ts(item['global_end'])}\n{text}\n")
        n += 1
    return "\n".join(blocks)


def edl_text(project: dict[str, Any], track: str | None = None) -> tuple[str, list[str]]:
    warns: list[str] = []
    lines = ["TITLE: manju", "FCM: NON-DROP FRAME", ""]
    rec = 1
    prev_end = 0.0
    for job in project.get("jobs") or []:
        if not isinstance(job, dict):
            continue
        job_track = job.get("track_id") or ("P" if job.get("aspect_ratio") == "9:16" else "L")
        if track and job_track != track:
            continue
        if job.get("status") != "reviewed":
            warns.append(f"skip job {job.get('id')} status={job.get('status')}")
            continue
        start = float(job.get("episode_start_seconds") or 0)
        dur = float(job.get("duration_seconds") or 0)
        if start > prev_end + 0.05:
            warns.append(f"gap before job {job.get('id')}: {prev_end:.3f}->{start:.3f}")
        src = "AX"
        path = ""
        for asset in project.get("assets") or []:
            if isinstance(asset, dict) and asset.get("generated_by_job_id") == job.get("id"):
                path = str(asset.get("path") or "")
                break
        rec_in = _ts(start, srt=False).replace(",", ":")
        rec_out = _ts(start + dur, srt=False).replace(",", ":")
        src_in = _ts(0, srt=False).replace(",", ":")
        src_out = _ts(dur, srt=False).replace(",", ":")
        lines.append(f"{rec:03d}  {src:<8} V     C        {src_in} {src_out} {rec_in} {rec_out}")
        if path:
            lines.append(f"* FROM CLIP NAME: {path}")
        rec += 1
        prev_end = start + dur
    return "\n".join(lines) + "\n", warns


def main() -> int:
    p = argparse.ArgumentParser(description="Write audio plan / SRT / EDL (fail open)")
    p.add_argument("cmd", choices=["audio-plan", "srt", "edl"])
    p.add_argument("--project", type=Path, required=True)
    p.add_argument("--track", default=None)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    project = json.loads(args.project.read_text(encoding="utf-8"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.cmd == "audio-plan":
        args.out.write_text(json.dumps(audio_plan(project), ensure_ascii=False, indent=2), encoding="utf-8")
    elif args.cmd == "srt":
        args.out.write_text(srt_text(project, args.track), encoding="utf-8")
    else:
        text, warns = edl_text(project, args.track)
        args.out.write_text(text, encoding="utf-8")
        for w in warns:
            print(f"WARN: {w}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
