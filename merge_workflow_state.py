from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def merge_record(remote: dict, local: dict) -> dict:
    merged = dict(remote)
    merged.update(local)

    # Never regress a record that another workflow has already advanced.
    if remote.get("status") == "published" or local.get("status") == "published":
        merged["status"] = "published"
    if (
        remote.get("delivery_status") == "published"
        or local.get("delivery_status") == "published"
    ):
        merged["delivery_status"] = "published"

    # Keep useful identifiers/URLs already written by another workflow when
    # this snapshot does not yet know about them.
    for key in (
        "url",
        "post_id",
        "buffer_post_id",
        "buffer_channel_id",
        "buffer_sent_at",
        "image_url",
    ):
        if remote.get(key) and not local.get(key):
            merged[key] = remote[key]

    if remote.get("sent") or local.get("sent"):
        merged["sent"] = True

    if "send_attempts" in remote or "send_attempts" in local:
        try:
            merged["send_attempts"] = max(
                int(remote.get("send_attempts", 0) or 0),
                int(local.get("send_attempts", 0) or 0),
            )
        except (TypeError, ValueError):
            pass

    remote_sent = str(remote.get("last_sent_at", ""))
    local_sent = str(local.get("last_sent_at", ""))
    if remote_sent and remote_sent > local_sent:
        merged["last_sent_at"] = remote_sent

    return merged


def merge_maps(remote: dict, local: dict) -> dict:
    merged = dict(remote)
    for key, local_value in local.items():
        remote_value = remote.get(key)
        if isinstance(remote_value, dict) and isinstance(local_value, dict):
            merged[key] = merge_record(remote_value, local_value)
        else:
            merged[key] = local_value
    return merged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", required=True)
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    snapshot_dir = Path(args.snapshot_dir)

    for relative in args.files:
        target = root / relative
        snapshot = snapshot_dir / relative
        if not snapshot.exists():
            continue

        remote = load_json(target)
        local = load_json(snapshot)
        merged = merge_maps(remote, local)

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(merged, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"[merged-state] {relative}: remote={len(remote)} local={len(local)} merged={len(merged)}")


if __name__ == "__main__":
    main()
