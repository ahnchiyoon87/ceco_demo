"""Structured logger that persists large payloads without caller-side truncation."""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
from datetime import datetime
from typing import Any
from typing import Optional


class SmartLogger:
    """Write structured logs and spill large payloads into detail files."""

    SMART_LOGGER_BLACKLIST_MESSAGES: list[str] = []
    LEVEL_PRIORITY = {
        "DEBUG": 0,
        "INFO": 1,
        "WARNING": 2,
        "ERROR": 3,
        "CRITICAL": 4,
    }
    _instance: "SmartLogger | None" = None

    @classmethod
    def instance(cls) -> "SmartLogger":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def log(
        cls,
        level: str,
        message: Any,
        category: str | None = None,
        params: Any = None,
        max_inline_chars: int = 100,
    ) -> None:
        cls.instance()._log(level, message, category, params, max_inline_chars)

    def __init__(
        self,
        main_log_path: str | None = None,
        detail_log_dir: str | None = None,
        min_level: str | None = None,
        include_all_min_level: str | None = None,
        console_output: bool | None = None,
        file_output: bool | None = None,
        remove_log_on_create: bool | None = None,
        blacklist_messages: Optional[Any] = None,
    ) -> None:
        self.main_log_path = self._get_env_variable(
            main_log_path,
            "MAIN_LOG_PATH",
            "logs/backend/app_flow.jsonl",
        )
        self.detail_log_dir = self._get_env_variable(
            detail_log_dir,
            "DETAIL_LOG_DIR",
            "logs/backend/details",
        )
        self.min_level = self._get_env_variable(min_level, "MIN_LEVEL", "INFO")
        self.include_all_min_level = self._get_env_variable(
            include_all_min_level,
            "INCLUDE_ALL_MIN_LEVEL",
            "ERROR",
        )
        self.console_output = self._get_env_variable(
            str(console_output) if console_output is not None else None,
            "CONSOLE_OUTPUT",
            "True",
        ) == "True"
        self.file_output = self._get_env_variable(
            str(file_output) if file_output is not None else None,
            "FILE_OUTPUT",
            "True",
        ) == "True"
        self.remove_log_on_create = self._get_env_variable(
            str(remove_log_on_create) if remove_log_on_create is not None else None,
            "REMOVE_LOG_ON_CREATE",
            "False",
        ) == "True"
        self.blacklist_messages = self._load_blacklist_messages(blacklist_messages)

        self._lock = threading.Lock()
        self._last_timestamp: str | None = None
        self._timestamp_counter = 0
        self._startup_status_logged = False

        if self.file_output:
            self._prepare_output_dirs()

    def _prepare_output_dirs(self) -> None:
        dir_paths = [os.path.dirname(self.main_log_path), self.detail_log_dir]
        for dir_path in dir_paths:
            if not dir_path:
                continue
            if self.remove_log_on_create and os.path.exists(dir_path):
                shutil.rmtree(dir_path)
        for dir_path in dir_paths:
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)

    def _ensure_output_dirs(self) -> None:
        dir_paths = [os.path.dirname(self.main_log_path), self.detail_log_dir]
        for dir_path in dir_paths:
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)

    def _get_env_variable(self, direct_value: Optional[str], env_key: str, default: str) -> str:
        if direct_value is not None:
            return direct_value
        return os.environ.get(f"SMART_LOGGER_{env_key}", default)

    def _load_blacklist_messages(self, direct_value: Optional[Any] = None) -> list[str]:
        raw = direct_value
        if raw is None:
            raw = os.environ.get("SMART_LOGGER_BLACKLIST_MESSAGES")
            if raw is None:
                return self.SMART_LOGGER_BLACKLIST_MESSAGES

        if raw is None:
            return []
        if isinstance(raw, str):
            raw_str = raw.strip()
            if not raw_str:
                return []
            try:
                parsed = json.loads(raw_str)
                items = parsed if isinstance(parsed, list) else []
            except Exception:
                items = [item.strip() for item in raw_str.split(",")]
        else:
            try:
                items = list(raw)
            except Exception:
                items = []

        result: list[str] = []
        for item in items:
            if item is None:
                continue
            normalized = str(item).strip()
            if normalized:
                result.append(normalized)
        return result

    def _is_message_blacklisted(self, message: Any) -> bool:
        if not self.blacklist_messages:
            return False
        normalized = "" if message is None else str(message)
        if not normalized:
            return False
        return any(needle in normalized for needle in self.blacklist_messages)

    def _generate_unique_trace_id(self) -> str:
        current_timestamp = str(int(time.time()))
        if self._last_timestamp == current_timestamp:
            self._timestamp_counter += 1
            return f"{current_timestamp}_{self._timestamp_counter}"
        self._last_timestamp = current_timestamp
        self._timestamp_counter = 1
        return f"{current_timestamp}_1"

    def _save_detail_payload(self, trace_id: str, payload: Any) -> str | None:
        if not self.file_output:
            return None

        self._ensure_output_dirs()
        filename = f"{trace_id}.json"
        filepath = os.path.join(self.detail_log_dir, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as file_handle:
                json.dump(payload, file_handle, ensure_ascii=False, indent=2, default=str)
            return filename
        except Exception as exc:  # pragma: no cover - passthrough filesystem failure
            return f"Error saving detail: {exc}"

    def _should_log(self, level: str) -> bool:
        level_priority = self.LEVEL_PRIORITY.get(level.upper(), 1)
        min_priority = self.LEVEL_PRIORITY.get(self.min_level.upper(), 0)
        return level_priority >= min_priority

    def _should_include_all(self, level: str) -> bool:
        level_priority = self.LEVEL_PRIORITY.get(level.upper(), 1)
        min_priority = self.LEVEL_PRIORITY.get(self.include_all_min_level.upper(), 3)
        return level_priority >= min_priority

    def log_startup_status(self) -> None:
        should_log = False
        with self._lock:
            if not self._startup_status_logged:
                self._startup_status_logged = True
                should_log = True

        if not should_log:
            return

        startup_level = self.min_level.upper()
        if startup_level not in self.LEVEL_PRIORITY:
            startup_level = "INFO"

        self._log(
            level=startup_level,
            message="SmartLogger initialized during backend startup",
            category="backend_status",
            params={
                "phase": "startup",
                "pid": os.getpid(),
                "main_log_path": self.main_log_path,
                "detail_log_dir": self.detail_log_dir,
                "min_level": self.min_level,
                "include_all_min_level": self.include_all_min_level,
                "console_output": self.console_output,
                "file_output": self.file_output,
                "remove_log_on_create": self.remove_log_on_create,
                "blacklist_message_count": len(self.blacklist_messages),
            },
        )

    def _log(
        self,
        level: str,
        message: Any,
        category: str | None = None,
        params: Any = None,
        max_inline_chars: int = 100,
    ) -> None:
        if self._is_message_blacklisted(f"{message}{category or ''}"):
            return
        if not self._should_log(level):
            return

        log_entry: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": "" if message is None else str(message),
        }
        if category:
            log_entry["category"] = category

        if params is not None:
            params_str = str(params)
            if len(params_str) <= max_inline_chars or self._should_include_all(level):
                log_entry["params"] = params
            else:
                with self._lock:
                    trace_id = self._generate_unique_trace_id()
                    detail_filename = self._save_detail_payload(trace_id, params)
                if isinstance(detail_filename, str) and detail_filename.startswith("Error"):
                    log_entry["detail_save_error"] = detail_filename
                    log_entry["params"] = params
                elif detail_filename is None:
                    log_entry["detail_save_error"] = "file_output_disabled"
                    log_entry["params"] = params
                else:
                    log_entry["has_detail_file"] = True
                    log_entry["detail_ref"] = detail_filename

        if self.file_output:
            with self._lock:
                self._ensure_output_dirs()
                with open(self.main_log_path, "a", encoding="utf-8") as file_handle:
                    file_handle.write(
                        json.dumps(log_entry, ensure_ascii=False, default=str) + "\n"
                    )

        if self.console_output:
            category_str = f"[{category}]" if category else ""
            if "params" in log_entry:
                print(f"[{level}]{category_str} {message} {log_entry['params']}")
            elif log_entry.get("detail_ref"):
                print(
                    f"[{level}]{category_str} {message} "
                    f"(detail_ref={log_entry['detail_ref']})"
                )
            else:
                print(f"[{level}]{category_str} {message}")
