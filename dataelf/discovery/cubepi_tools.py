from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import time
from html import unescape
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from dataelf.discovery.base import DiscoveryContext
from dataelf.domains.ai_index.client import AIIndexClient


ALLOWED_WRITE_ROOTS = {"scripts", "notes", "deep_dives", "insights", "raw", "tables", "logs"}
INSIGHT_REQUIRED_FIELDS = {"insight_id", "title", "thesis", "why_now", "analysis_artifacts", "counterarguments", "confidence"}


class CubePiWorkspaceTools:
    """Workspace-bound tools for the experimental CubePi insights explorer."""

    def __init__(self, workspace_path: Path, context: DiscoveryContext):
        self.workspace_path = workspace_path.resolve()
        self.context = context
        self.logs_dir = self.workspace_path / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def search_papers(self, **kwargs: Any) -> dict[str, Any]:
        return self._ai_index_search("search_papers", kwargs)

    def search_institutions(self, **kwargs: Any) -> dict[str, Any]:
        return self._ai_index_search("search_institutions", kwargs)

    def search_scholars(self, **kwargs: Any) -> dict[str, Any]:
        return self._ai_index_search("search_scholars", kwargs)

    def fetch_institution_funding(self, institution_id: str) -> dict[str, Any]:
        started = time.time()
        try:
            response = AIIndexClient.from_env(workspace_path=self.workspace_path).fetch_institution_funding(institution_id)
            summary = _response_summary(response)
            result = {"ok": True, "summary": summary}
            self._log_event("fetch_institution_funding", {"institution_id": institution_id}, True, summary, started)
            return result
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
            self._log_event("fetch_institution_funding", {"institution_id": institution_id}, False, str(exc), started)
            return result

    def list_workspace_files(self, relative_dir: str = ".", pattern: str = "*", max_files: int = 200) -> dict[str, Any]:
        started = time.time()
        try:
            root = self._resolve_path(relative_dir, must_be_write_root=False)
            files = []
            for path in sorted(root.glob(pattern)):
                if path.is_file():
                    files.append(str(path.relative_to(self.workspace_path)))
                if len(files) >= max_files:
                    break
            result = {"ok": True, "files": files, "truncated": len(files) >= max_files}
            self._log_event("list_workspace_files", {"relative_dir": relative_dir, "pattern": pattern}, True, f"{len(files)} files", started)
            return result
        except Exception as exc:
            self._log_event("list_workspace_files", {"relative_dir": relative_dir, "pattern": pattern}, False, str(exc), started)
            return {"ok": False, "error": str(exc)}

    def read_workspace_file(self, relative_path: str, max_chars: int = 12000) -> dict[str, Any]:
        started = time.time()
        try:
            path = self._resolve_path(relative_path, must_be_write_root=False)
            if not path.is_file():
                raise FileNotFoundError(relative_path)
            text = path.read_text(encoding="utf-8", errors="replace")
            result = {
                "ok": True,
                "path": str(path.relative_to(self.workspace_path)),
                "content": text[:max_chars],
                "truncated": len(text) > max_chars,
            }
            self._log_event("read_workspace_file", {"relative_path": relative_path}, True, f"{len(text)} chars", started)
            return result
        except Exception as exc:
            self._log_event("read_workspace_file", {"relative_path": relative_path}, False, str(exc), started)
            return {"ok": False, "error": str(exc)}

    def write_workspace_file(self, relative_path: str, content: str, append: bool = False) -> dict[str, Any]:
        started = time.time()
        try:
            path = self._resolve_path(relative_path, must_be_write_root=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            if append:
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(content)
            else:
                path.write_text(content, encoding="utf-8")
            result = {"ok": True, "path": str(path.relative_to(self.workspace_path)), "bytes": len(content.encode("utf-8"))}
            self._log_event("write_workspace_file", {"relative_path": relative_path, "append": append}, True, result["path"], started)
            return result
        except Exception as exc:
            self._log_event("write_workspace_file", {"relative_path": relative_path}, False, str(exc), started)
            return {"ok": False, "error": str(exc)}

    def execute_python(
        self,
        code: str | None = None,
        script_path: str | None = None,
        timeout_seconds: int = 120,
    ) -> dict[str, Any]:
        started = time.time()
        try:
            if script_path:
                script = self._resolve_path(script_path, must_be_write_root=False)
            elif code is not None:
                digest = hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]
                script = self.workspace_path / "scripts" / f"cubepi_inline_{digest}.py"
                script.parent.mkdir(parents=True, exist_ok=True)
                script.write_text(code, encoding="utf-8")
            else:
                raise ValueError("execute_python requires code or script_path.")

            repo_root = Path(__file__).resolve().parents[2]
            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = str(repo_root) if not existing_pythonpath else f"{repo_root}{os.pathsep}{existing_pythonpath}"
            completed = subprocess.run(
                [env.get("PYTHON", "python3"), str(script)],
                cwd=self.workspace_path,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            log_path = self.logs_dir / f"cubepi_python_{script.stem}.json"
            log_path.write_text(
                json.dumps(
                    {
                        "script": str(script.relative_to(self.workspace_path)),
                        "returncode": completed.returncode,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            summary = {
                "ok": completed.returncode == 0,
                "script": str(script.relative_to(self.workspace_path)),
                "returncode": completed.returncode,
                "stdout_excerpt": (completed.stdout or "")[:3000],
                "stderr_excerpt": (completed.stderr or "")[:3000],
                "log_path": str(log_path.relative_to(self.workspace_path)),
            }
            self._log_event("execute_python", {"script": summary["script"]}, completed.returncode == 0, f"returncode={completed.returncode}", started)
            return summary
        except subprocess.TimeoutExpired as exc:
            self._log_event("execute_python", {"script_path": script_path}, False, f"timeout after {timeout_seconds}s", started)
            return {"ok": False, "error": f"Python execution timed out after {timeout_seconds}s", "stdout_excerpt": exc.stdout or "", "stderr_excerpt": exc.stderr or ""}
        except Exception as exc:
            self._log_event("execute_python", {"script_path": script_path}, False, str(exc), started)
            return {"ok": False, "error": str(exc)}

    def web_search(self, query: str, max_results: int = 5) -> dict[str, Any]:
        started = time.time()
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            result = {"ok": False, "error": "web_search unavailable: set TAVILY_API_KEY or configure a web search provider"}
            self._log_event("web_search", {"query": query}, False, result["error"], started)
            return result
        try:
            payload = json.dumps({"api_key": api_key, "query": query, "max_results": max_results}, ensure_ascii=False).encode("utf-8")
            req = request.Request(
                "https://api.tavily.com/search",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            results = [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": (item.get("content") or "")[:1000],
                    "score": item.get("score"),
                }
                for item in data.get("results", [])[:max_results]
                if isinstance(item, dict)
            ]
            raw_path = self.workspace_path / "raw" / "web" / f"tavily_{_safe_slug(query)[:80]}.json"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self._append_source_observations(results, source_type="web_search")
            result = {"ok": True, "query": query, "results": results, "raw_path": str(raw_path.relative_to(self.workspace_path))}
            self._log_event("web_search", {"query": query}, True, f"{len(results)} results", started)
            return result
        except Exception as exc:
            self._log_event("web_search", {"query": query}, False, str(exc), started)
            return {"ok": False, "error": str(exc)}

    def fetch_url(self, url: str, max_chars: int = 5000) -> dict[str, Any]:
        started = time.time()
        try:
            req = request.Request(url, headers={"User-Agent": "DataElf-CubePi-Spike/0.1"})
            with request.urlopen(req, timeout=30) as response:
                body = response.read()
                status = response.status
                final_url = response.geturl()
            text = body.decode("utf-8", errors="replace")
            title = _extract_title(text)
            readable = _html_to_text(text)
            raw_path = self.workspace_path / "raw" / "web" / f"fetch_{_safe_slug(final_url)[:80]}.txt"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(readable, encoding="utf-8")
            result = {
                "ok": True,
                "url": final_url,
                "status_code": status,
                "title": title,
                "excerpt": readable[:max_chars],
                "raw_path": str(raw_path.relative_to(self.workspace_path)),
            }
            self._log_event("fetch_url", {"url": url}, True, f"status={status}", started)
            return result
        except Exception as exc:
            self._log_event("fetch_url", {"url": url}, False, str(exc), started)
            return {"ok": False, "error": str(exc)}

    def write_candidate_signal(self, signal: dict[str, Any]) -> dict[str, Any]:
        return self._append_json_item("insights/candidate_signals.json", "candidate_signals", signal, ["signal_id", "signal_type", "summary", "why_might_matter"])

    def write_insight_candidate(self, insight: dict[str, Any]) -> dict[str, Any]:
        return self._append_json_item("insights/insight_candidates.json", "insight_candidates", insight, sorted(INSIGHT_REQUIRED_FIELDS))

    def write_final_brief(self, markdown: str) -> dict[str, Any]:
        return self.write_workspace_file("insights/final_brief.md", markdown, append=False)

    def _ai_index_search(self, method_name: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        started = time.time()
        try:
            kwargs = _normalize_ai_index_kwargs(method_name, kwargs)
            client = AIIndexClient.from_env(workspace_path=self.workspace_path)
            response = getattr(client, method_name)(**kwargs)
            summary = _response_summary(response)
            self._log_event(method_name, kwargs, True, summary, started)
            return {"ok": True, "summary": summary, "request": response.get("request", {})}
        except Exception as exc:
            self._log_event(method_name, kwargs, False, str(exc), started)
            return {"ok": False, "error": str(exc)}

    def _append_json_item(self, relative_path: str, array_key: str, item: dict[str, Any], required_fields: list[str]) -> dict[str, Any]:
        started = time.time()
        missing = [field for field in required_fields if item.get(field) in (None, "", [])]
        if missing:
            result = {"ok": False, "error": f"Missing required fields: {', '.join(missing)}"}
            self._log_event(f"write_{array_key}", {"path": relative_path}, False, result["error"], started)
            return result
        path = self._resolve_path(relative_path, must_be_write_root=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {array_key: []}
        else:
            payload = {array_key: []}
        values = payload.get(array_key, [])
        if not isinstance(values, list):
            values = []
        item_id = item.get("insight_id") or item.get("signal_id") or item.get("id")
        updated = False
        if item_id:
            id_keys = ["insight_id", "signal_id", "id"]
            for idx, existing in enumerate(values):
                if isinstance(existing, dict) and any(existing.get(key) == item_id for key in id_keys):
                    values[idx] = item
                    updated = True
                    break
        if not updated:
            values.append(item)
        payload[array_key] = values
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._log_event(f"write_{array_key}", {"path": relative_path}, True, f"{len(values)} items", started)
        return {"ok": True, "path": relative_path, "count": len(values)}

    def _resolve_path(self, relative_path: str, must_be_write_root: bool) -> Path:
        raw = Path(relative_path)
        if raw.is_absolute():
            raise ValueError("Absolute paths are not allowed.")
        normalized = Path(os.path.normpath(str(raw)))
        if any(part == ".." for part in normalized.parts):
            raise ValueError("Path traversal is not allowed.")
        if must_be_write_root and normalized.parts and normalized.parts[0] not in ALLOWED_WRITE_ROOTS:
            raise ValueError(f"Writes are only allowed under: {', '.join(sorted(ALLOWED_WRITE_ROOTS))}.")
        path = (self.workspace_path / normalized).resolve()
        if self.workspace_path not in path.parents and path != self.workspace_path:
            raise ValueError("Resolved path escapes workspace.")
        return path

    def _append_source_observations(self, results: list[dict[str, Any]], source_type: str) -> None:
        observations_path = self.workspace_path / "tables" / "source_observations.csv"
        findings_path = self.workspace_path / "tables" / "external_findings.csv"
        observations_path.parent.mkdir(parents=True, exist_ok=True)
        observations_exists = observations_path.exists()
        findings_exists = findings_path.exists()
        with observations_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["source_id", "source_type", "title", "url", "observed_at", "summary", "related_entities", "source_raw"])
            if not observations_exists:
                writer.writeheader()
            ts = _now()
            for idx, item in enumerate(results, start=1):
                source_id = f"web_{hashlib.sha1((item.get('url','') + str(idx)).encode('utf-8')).hexdigest()[:10]}"
                writer.writerow(
                    {
                        "source_id": source_id,
                        "source_type": source_type,
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "observed_at": ts,
                        "summary": item.get("content", ""),
                        "related_entities": "",
                        "source_raw": "",
                    }
                )
        with findings_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["finding_id", "source_id", "finding_type", "summary", "supports", "challenges", "confidence", "url", "source_raw"])
            if not findings_exists:
                writer.writeheader()
            for idx, item in enumerate(results, start=1):
                url = item.get("url", "")
                source_id = f"web_{hashlib.sha1((url + str(idx)).encode('utf-8')).hexdigest()[:10]}"
                writer.writerow(
                    {
                        "finding_id": f"finding_{hashlib.sha1((url + source_type + str(idx)).encode('utf-8')).hexdigest()[:10]}",
                        "source_id": source_id,
                        "finding_type": source_type,
                        "summary": item.get("content", ""),
                        "supports": "",
                        "challenges": "",
                        "confidence": item.get("score", ""),
                        "url": url,
                        "source_raw": "",
                    }
                )

    def _log_event(self, tool: str, args: dict[str, Any], ok: bool, output_summary: str, started: float) -> None:
        event = {
            "ts": _now(),
            "tool": tool,
            "args_summary": _summarize_args(args),
            "ok": ok,
            "duration_ms": int((time.time() - started) * 1000),
            "output_summary": output_summary[:1000],
        }
        with (self.logs_dir / "cubepi_events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _response_summary(response: dict[str, Any]) -> str:
    data = response.get("data", {}) if isinstance(response, dict) else {}
    rows = data.get("list", []) if isinstance(data, dict) else []
    total = data.get("total") if isinstance(data, dict) else None
    endpoint = response.get("endpoint", "") if isinstance(response, dict) else ""
    raw_uri = response.get("raw_uri", "") if isinstance(response, dict) else ""
    return f"endpoint={endpoint}; rows={len(rows)}; total={total}; raw_uri={raw_uri}"


def _normalize_ai_index_kwargs(method_name: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    normalized = {key: value for key, value in kwargs.items() if value not in (None, [], {})}
    try:
        requested_size = int(normalized.get("size", 50))
    except (TypeError, ValueError):
        requested_size = 50
    normalized["size"] = max(1, min(requested_size, 50))
    sort_type = normalized.get("sort_type")
    if method_name == "search_papers" and sort_type == "published_time":
        normalized["sort_type"] = "publish_time"
    if method_name == "search_institutions" and sort_type == "heat":
        normalized["sort_type"] = "index"
    return normalized


def _summarize_args(args: dict[str, Any]) -> str:
    redacted = {key: ("<redacted>" if "key" in key.lower() or "token" in key.lower() else value) for key, value in args.items()}
    return json.dumps(redacted, ensure_ascii=False, default=str)[:1000]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "item"


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    return unescape(re.sub(r"\s+", " ", match.group(1)).strip()) if match else ""


def _html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()
