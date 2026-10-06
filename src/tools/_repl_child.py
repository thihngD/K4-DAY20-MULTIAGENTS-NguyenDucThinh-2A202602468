"""Tiến trình con của PythonREPLTool. Chạy bằng `python -I`, đọc {"code", "variables"} từ stdin.

Ghi kết quả JSON {"ok", "stdout", "error"} ra stdout thật ở dòng cuối. Mọi print của script được gom lại,
không lẫn với kết quả. Tiến trình riêng nên có thể bị dừng cứng khi quá thời gian.
"""
import builtins
import io
import json
import sys
from contextlib import redirect_stdout

ALLOWED = {"sqlite3", "csv", "json", "math", "statistics", "datetime", "collections", "re",
           "matplotlib", "matplotlib.pyplot", "itertools"}
SAFE_BUILTINS = ["abs", "all", "any", "bool", "dict", "enumerate", "filter", "float", "int", "isinstance", "len",
                 "list", "map", "max", "min", "print", "range", "round", "set", "sorted", "str", "sum", "tuple", "zip",
                 "ValueError", "KeyError", "IndexError", "TypeError", "ZeroDivisionError", "Exception"]


def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name not in ALLOWED and name.split(".")[0] not in ALLOWED:
        raise ImportError(f"import of {name} is not allowed")
    return __import__(name, globals, locals, fromlist, level)


def main() -> None:
    request = json.loads(sys.stdin.read())
    import matplotlib
    matplotlib.use("Agg")                       # lưu ảnh ra tệp, không mở cửa sổ
    safe = {name: getattr(builtins, name) for name in SAFE_BUILTINS}
    safe["__import__"] = safe_import
    variables = request.get("variables", {})
    env = {"__builtins__": safe, **variables}

    def connect_db():
        """Kết nối chỉ đọc tới cơ sở dữ liệu bán hàng (đã đúng tham số uri=True)."""
        import sqlite3
        return sqlite3.connect(variables["DB_URI"], uri=True)

    env["connect_db"] = connect_db
    buffer = io.StringIO()
    result = {"ok": True, "stdout": "", "error": None}
    try:
        with redirect_stdout(buffer):
            exec(compile(request["code"], "<repl>", "exec"), env)
    except BaseException as exc:  # noqa: BLE001 - mọi lỗi của script được trả về để agent sửa
        result = {"ok": False, "stdout": buffer.getvalue(), "error": f"{type(exc).__name__}: {exc}"}
    else:
        result["stdout"] = buffer.getvalue()
    sys.__stdout__.write("\n" + json.dumps(result, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
