"""Công cụ cho Code Agent: REPL Python có sandbox, tạo file và sửa file trong thư mục đầu ra.

Sandbox REPL gồm ba lớp:
1. kiểm tra đầu vào: chỉ import các module trong ALLOWED_MODULES; chặn exec, eval, open, __dunder__...;
2. script chạy trong TIẾN TRÌNH CON (`python -I _repl_child.py`) có timeout: quá giờ thì bị kill cứng;
3. trong tiến trình con: builtins đã được giới hạn, import bị kiểm tra lại; stdout bị cắt ở MAX_OUTPUT ký tự.
Đây không phải cách ly ở mức hệ điều hành (không có container, mạng vẫn có thể mở). Xem báo cáo, mục hạn chế.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from .base_tool import BaseTool

ALLOWED_MODULES = {"sqlite3", "csv", "json", "math", "statistics", "datetime", "collections", "re",
                   "matplotlib", "matplotlib.pyplot", "itertools"}
FORBIDDEN_NAMES = re.compile(r"\b(exec|eval|open|compile|__\w+__|globals|locals|getattr|setattr|input)\b")
IMPORT_LINE = re.compile(r"^\s*(?:import\s+([\w.]+)|from\s+([\w.]+)\s+import)", re.M)
CHILD = Path(__file__).with_name("_repl_child.py")
MAX_OUTPUT = 10_000
TIMEOUT = 20.0          # giây; gồm cả thời gian khởi động matplotlib trong tiến trình con


class PythonREPLTool(BaseTool):
    def __init__(self):
        super().__init__("python_repl", "Run a short Python script in a sandbox (allowed imports only).")

    def validate_input(self, input_dict: dict) -> None:
        code = input_dict.get("code")
        if not isinstance(code, str) or not code.strip():
            raise ValueError("code must be a non-empty string")
        for m in IMPORT_LINE.finditer(code):
            module = m.group(1) or m.group(2)
            if module not in ALLOWED_MODULES and module.split(".")[0] not in ALLOWED_MODULES:
                raise ValueError(f"import of {module} is not allowed")
        if FORBIDDEN_NAMES.search(code):
            raise ValueError("code uses a forbidden name")

    def invoke(self, input_dict: dict) -> dict:
        self.validate_input(input_dict)
        payload = json.dumps({"code": input_dict["code"], "variables": dict(input_dict.get("variables") or {})})
        try:
            proc = subprocess.run([sys.executable, "-I", str(CHILD)], input=payload, capture_output=True,
                                  text=True, timeout=TIMEOUT, encoding="utf-8")
        except subprocess.TimeoutExpired:           # subprocess.run đã kill tiến trình con
            return {"status": "error", "error": f"timeout after {TIMEOUT}s"}
        last = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
        try:
            result = json.loads(last)
        except json.JSONDecodeError:
            return {"status": "error", "error": (proc.stderr or "child process failed").strip()[-2000:]}
        if not result.get("ok"):
            return {"status": "error", "error": result.get("error"), "stdout": result.get("stdout", "")[:MAX_OUTPUT]}
        return {"status": "success", "stdout": result.get("stdout", "")[:MAX_OUTPUT]}


class _OutputFileTool(BaseTool):
    def __init__(self, name: str, description: str, base_path: str | Path):
        super().__init__(name, description)
        self.base = Path(base_path).resolve()
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, filename: str) -> Path:
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError("filename must be a non-empty string")
        if filename.startswith(("/", "\\")) or ".." in Path(filename).parts or re.match(r"^[A-Za-z]:", filename):
            raise ValueError("invalid filename")
        if not re.fullmatch(r"[A-Za-z0-9_\-./]+", filename):
            raise ValueError("filename has forbidden characters")
        target = (self.base / filename).resolve()
        if self.base not in target.parents:
            raise ValueError("path escapes the output folder")
        return target


class CreateFileTool(_OutputFileTool):
    MAX_BYTES = 1_000_000

    def __init__(self, base_path: str | Path):
        super().__init__("create_file", "Create a new text file in the output folder.", base_path)

    def validate_input(self, input_dict: dict) -> None:
        self._path(input_dict.get("filename", ""))
        if len(str(input_dict.get("content", "")).encode("utf-8")) > self.MAX_BYTES:
            raise ValueError("content is too large")

    def invoke(self, input_dict: dict) -> dict:
        self.validate_input(input_dict)
        target = self._path(input_dict["filename"])
        target.parent.mkdir(parents=True, exist_ok=True)
        content = str(input_dict.get("content", ""))
        target.write_text(content, encoding="utf-8")
        return {"status": "success", "path": str(target), "size": len(content)}


class EditFileTool(_OutputFileTool):
    def __init__(self, base_path: str | Path):
        super().__init__("edit_file", "Replace text in an existing file of the output folder.", base_path)

    def validate_input(self, input_dict: dict) -> None:
        target = self._path(input_dict.get("filename", ""))
        if not target.is_file():
            raise ValueError("file does not exist")
        if not input_dict.get("old"):
            raise ValueError("old text must not be empty")

    def invoke(self, input_dict: dict) -> dict:
        self.validate_input(input_dict)
        target = self._path(input_dict["filename"])
        text = target.read_text(encoding="utf-8")
        count = text.count(input_dict["old"])
        if count == 0:
            return {"status": "error", "error": "old text not found"}
        target.write_text(text.replace(input_dict["old"], str(input_dict.get("new", ""))), encoding="utf-8")
        return {"status": "success", "replacements": count, "path": str(target)}
