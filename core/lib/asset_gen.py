"""Sequential local image-generation gate. No provider URLs or keys in the repo.

The operator keeps the real adapter + credentials under $MANJU_HOME.
This module only: queue one asset, n=1, no poll, budget door, identity check.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .asset_prompt import check_text
from .channel import load_channel, manju_home
from .identity import check_asset_binding, characters_from_project, normalize_sex

SECRET_RE = re.compile(r"(sk-|Bearer\s+|3b_sk_)\S+", re.I)


def _scrub(text: str) -> str:
    return SECRET_RE.sub("***", text or "")


def _runs_dir(project_id: str) -> Path:
    d = manju_home() / "runs" / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _queue_path(project_id: str) -> Path:
    return _runs_dir(project_id) / "asset_queue.json"


def load_queue(project_id: str) -> dict[str, Any]:
    p = _queue_path(project_id)
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"project_id": project_id, "spent": 0.0, "items": []}


def save_queue(project_id: str, queue: dict[str, Any]) -> None:
    _queue_path(project_id).write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")


def _kind_of(asset: dict[str, Any]) -> str:
    role = str(asset.get("asset_role") or "")
    kind = str(asset.get("kind") or "")
    if kind in {"character"} or role == "identity":
        return "character"
    if kind in {"weapon", "artifact"} or role == "weapon":
        return "weapon"
    if kind == "scene" or role == "scene":
        return "scene"
    return "character"


def build_queue(project: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for asset in project.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        if asset.get("status") not in {"planned", "candidate"}:
            continue
        items.append(
            {
                "asset_id": asset.get("asset_id"),
                "kind": _kind_of(asset),
                "status": "queued",
                "owner_id": asset.get("owner_id") or asset.get("character_id"),
                "presentation_sex": asset.get("presentation_sex") or asset.get("sex"),
                "prompt": asset.get("prompt") or asset.get("description") or "",
                "aspect": asset.get("aspect_ratio") or "16:9",
            }
        )
    return items


def _infer_sex(text: str, asset: dict[str, Any], characters: dict[str, dict[str, Any]]) -> str | None:
    sex = normalize_sex(asset.get("presentation_sex") or asset.get("sex"))
    if sex:
        return sex
    owner = asset.get("owner_id") or asset.get("character_id")
    if owner and owner in characters:
        return normalize_sex(characters[owner].get("presentation_sex") or characters[owner].get("sex"))
    body = text or ""
    if re.search(r"(女性|女主|女将|女修|female)", body, re.I):
        return "female"
    if re.search(r"(男性|男主|男将|男修|male)", body, re.I):
        return "male"
    return None


def preflight(project: dict[str, Any], asset: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    characters = characters_from_project(project)
    errors.extend(check_asset_binding(asset, characters))
    kind = _kind_of(asset)
    text = str(asset.get("prompt") or asset.get("description") or "")
    sex = _infer_sex(text, asset, characters)
    cid = str(asset.get("owner_id") or asset.get("character_id") or asset.get("asset_id") or "CHAR")
    if kind in {"character", "weapon"}:
        errors.extend(check_text(kind, text, str(asset.get("aspect_ratio") or "16:9"), sex=sex, character_id=cid))
    return errors


def _price(channel: dict[str, Any]) -> float | None:
    img = (channel.get("image_gen") or {}) if isinstance(channel.get("image_gen"), dict) else {}
    raw = img.get("price_per_image")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _call_adapter(channel: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    img = channel.get("image_gen") if isinstance(channel.get("image_gen"), dict) else {}
    adapter = str(img.get("adapter") or "")
    adapter = adapter.replace("$MANJU_HOME", str(manju_home()))
    if not adapter:
        raise RuntimeError("channel.image_gen.adapter missing (local path only)")
    path = Path(adapter)
    if not path.is_file():
        raise RuntimeError(f"adapter not found: {path}")
    env = {k: v for k, v in os.environ.items() if not re.search(r"(KEY|TOKEN|SECRET|PASSWORD)", k, re.I)}
    # Adapter may read secrets itself from the machine; this process does not log them.
    spec = importlib.util.spec_from_file_location("manju_image_adapter", path)
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "generate"):
            result = mod.generate({**payload, "n": 1})
            if not isinstance(result, dict):
                raise RuntimeError("adapter.generate must return a dict")
            return result
    payload_path = manju_home() / "runs" / "_adapter_payload.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(json.dumps({**payload, "n": 1}, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(path), str(payload_path)],
        capture_output=True,
        text=True,
        timeout=float(img.get("timeout_seconds") or 120),
        env={**env, **{k: os.environ[k] for k in (img.get("env_passthrough") or []) if k in os.environ}},
    )
    if proc.returncode != 0:
        raise RuntimeError(_scrub(proc.stderr or proc.stdout or f"adapter exit {proc.returncode}"))
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"adapter stdout is not JSON: {_scrub(proc.stdout[:200])}") from exc


def cmd_queue(project: dict[str, Any]) -> int:
    pid = str(project.get("project_id") or "unknown")
    queue = load_queue(pid)
    if not queue.get("items"):
        queue["items"] = build_queue(project)
        save_queue(pid, queue)
    for item in queue["items"]:
        print(f"{item.get('status'):<16} {item.get('asset_id')} {item.get('kind')} owner={item.get('owner_id')}")
    awaiting = [i for i in queue["items"] if i.get("status") == "awaiting_review"]
    print(f"spent={queue.get('spent')} awaiting_review={len(awaiting)}")
    return 0


def cmd_next(project: dict[str, Any], *, channel_id: str, budget: float, confirm: bool) -> int:
    pid = str(project.get("project_id") or "unknown")
    ch = load_channel(channel_id)
    if not ch:
        print(f"ERROR: channel {channel_id} not in {manju_home() / 'channels'} (local only)", file=sys.stderr)
        return 2
    queue = load_queue(pid)
    if not queue.get("items"):
        queue["items"] = build_queue(project)
    if any(i.get("status") == "awaiting_review" for i in queue["items"]):
        print("ERROR: an asset is awaiting_review; accept/reject before next", file=sys.stderr)
        return 1
    if any(i.get("status") == "unknown" for i in queue["items"]):
        print("ERROR: an asset is unknown; resolve --asset <id> --charged 0|1 before next", file=sys.stderr)
        return 1
    nxt = next((i for i in queue["items"] if i.get("status") == "queued"), None)
    if not nxt:
        print("queue empty")
        save_queue(pid, queue)
        return 0
    assets = {str(a.get("asset_id")): a for a in (project.get("assets") or []) if isinstance(a, dict)}
    asset = assets.get(str(nxt.get("asset_id")), nxt)
    errors = preflight(project, asset)
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    price = _price(ch)
    if price is None:
        print("ERROR: channel.image_gen.price_per_image unknown — refuse", file=sys.stderr)
        return 1
    spent = float(queue.get("spent") or 0)
    if spent + price > budget + 1e-9:
        print(f"ERROR: spent {spent} + {price} exceeds budget {budget}", file=sys.stderr)
        return 1
    preview = {
        "asset_id": nxt.get("asset_id"),
        "kind": nxt.get("kind"),
        "aspect": asset.get("aspect_ratio") or nxt.get("aspect"),
        "owner_id": nxt.get("owner_id"),
        "price": price,
        "spent": spent,
        "remaining": budget - spent,
        "channel_id": channel_id,
    }
    print(json.dumps(preview, ensure_ascii=False, indent=2))
    if not confirm:
        print("dry-run: pass --confirm to call the local adapter once (n=1, no poll)")
        save_queue(pid, queue)
        return 0
    payload = {
        "asset_id": nxt.get("asset_id"),
        "prompt": asset.get("prompt") or "",
        "n": 1,
        "aspect": asset.get("aspect_ratio") or "16:9",
    }
    nxt["charged"] = price
    try:
        result = _call_adapter(ch, payload)
    except subprocess.TimeoutExpired:
        nxt["status"] = "unknown"
        save_queue(pid, queue)
        print("ERROR: adapter timeout — recorded unknown, no retry", file=sys.stderr)
        return 3
    except Exception as exc:
        nxt["status"] = "unknown"
        save_queue(pid, queue)
        print(f"ERROR: {_scrub(str(exc))}", file=sys.stderr)
        return 3
    paths = result.get("paths") or result.get("images") or []
    if isinstance(paths, str):
        paths = [paths]
    anomaly = False
    if isinstance(paths, list) and len(paths) > 1:
        paths = paths[:1]
        anomaly = True
    path = paths[0] if paths else result.get("path")
    nxt["status"] = "awaiting_review"
    nxt["path"] = path
    nxt["anomaly"] = anomaly
    nxt["channel_id"] = channel_id
    nxt["charged"] = price
    nxt["at"] = datetime.now(timezone.utc).isoformat()
    if path and Path(str(path)).is_file():
        nxt["sha256"] = hashlib.sha256(Path(str(path)).read_bytes()).hexdigest()
    queue["spent"] = spent + price
    save_queue(pid, queue)
    print(json.dumps({"status": "awaiting_review", "path": path, "anomaly": anomaly, "channel_id": channel_id}, ensure_ascii=False))
    return 0


def cmd_accept(project: dict[str, Any], asset_id: str, path: str | None) -> int:
    pid = str(project.get("project_id") or "unknown")
    queue = load_queue(pid)
    item = next((i for i in queue["items"] if i.get("asset_id") == asset_id), None)
    if not item:
        print(f"ERROR: {asset_id} not in queue", file=sys.stderr)
        return 2
    if item.get("status") != "awaiting_review":
        print(f"ERROR: {asset_id} status {item.get('status')} is not awaiting_review", file=sys.stderr)
        return 1
    item["status"] = "accepted"
    if path:
        item["path"] = path
    save_queue(pid, queue)
    print(f"accepted {asset_id}")
    return 0


def cmd_resolve(project: dict[str, Any], asset_id: str, charged: int) -> int:
    pid = str(project.get("project_id") or "unknown")
    queue = load_queue(pid)
    item = next((i for i in queue["items"] if i.get("asset_id") == asset_id), None)
    if not item:
        print(f"ERROR: {asset_id} not in queue", file=sys.stderr)
        return 2
    if item.get("status") != "unknown":
        print(f"ERROR: {asset_id} status {item.get('status')} is not unknown", file=sys.stderr)
        return 1
    if charged:
        queue["spent"] = float(queue.get("spent") or 0) + float(item.get("charged") or 0)
    item["status"] = "queued"
    item["resolved_charged"] = bool(charged)
    save_queue(pid, queue)
    print(f"resolved {asset_id} charged={charged}")
    return 0


def cmd_reject(project: dict[str, Any], asset_id: str, reason: str) -> int:
    pid = str(project.get("project_id") or "unknown")
    queue = load_queue(pid)
    item = next((i for i in queue["items"] if i.get("asset_id") == asset_id), None)
    if not item:
        print(f"ERROR: {asset_id} not in queue", file=sys.stderr)
        return 2
    if item.get("status") != "awaiting_review":
        print(f"ERROR: {asset_id} status {item.get('status')} is not awaiting_review", file=sys.stderr)
        return 1
    item["status"] = "queued"
    item["reject_reason"] = reason
    item.pop("path", None)
    save_queue(pid, queue)
    print(f"rejected {asset_id}: {reason}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Sequential local asset generation (n=1, no poll)")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("queue", "next", "accept", "reject", "resolve"):
        sp = sub.add_parser(name)
        sp.add_argument("--project", type=Path, required=True)
        if name == "next":
            sp.add_argument("--channel", required=True)
            sp.add_argument("--budget", type=float, required=True)
            sp.add_argument("--confirm", action="store_true")
        if name == "accept":
            sp.add_argument("--asset", required=True)
            sp.add_argument("--path", default=None)
        if name == "reject":
            sp.add_argument("--asset", required=True)
            sp.add_argument("--reason", required=True)
        if name == "resolve":
            sp.add_argument("--asset", required=True)
            sp.add_argument("--charged", type=int, required=True, choices=[0, 1])
    args = p.parse_args()
    project = json.loads(args.project.read_text(encoding="utf-8"))
    if args.cmd == "queue":
        return cmd_queue(project)
    if args.cmd == "next":
        return cmd_next(project, channel_id=args.channel, budget=args.budget, confirm=args.confirm)
    if args.cmd == "accept":
        return cmd_accept(project, args.asset, args.path)
    if args.cmd == "resolve":
        return cmd_resolve(project, args.asset, args.charged)
    return cmd_reject(project, args.asset, args.reason)


if __name__ == "__main__":
    raise SystemExit(main())
