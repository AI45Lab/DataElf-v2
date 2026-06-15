from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class RawCache:
    def __init__(self, raw_dir: Path):
        self.raw_dir = raw_dir
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def write_json(self, payload: dict[str, Any]) -> tuple[str, Path]:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        path = self.raw_dir / f"{digest}.json"
        if not path.exists():
            path.write_text(body, encoding="utf-8")
        return digest, path

    def read_json(self, content_uri: str) -> dict[str, Any]:
        return json.loads(Path(content_uri).read_text(encoding="utf-8"))
