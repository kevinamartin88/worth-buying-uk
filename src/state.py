from __future__ import annotations

import json
from pathlib import Path


class JsonState:
    def __init__(self, path: Path, default):
        self.path = path
        self.default = default
        self.data = self._load()

    def _load(self):
        if not self.path.exists():
            return self.default.copy() if hasattr(self.default, "copy") else self.default
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return self.default.copy() if hasattr(self.default, "copy") else self.default

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
