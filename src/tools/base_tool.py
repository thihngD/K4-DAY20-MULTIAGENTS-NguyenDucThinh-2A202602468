"""Lớp nền cho mọi tool: tên, mô tả (LLM đọc để biết khi nào dùng), kiểm tra đầu vào trước khi chạy."""


class BaseTool:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def validate_input(self, input_dict: dict) -> None:
        """Ném ValueError nếu đầu vào không hợp lệ. Mỗi tool ghi đè hàm này."""
        raise NotImplementedError

    def invoke(self, input_dict: dict) -> dict:
        """Chạy tool. Trả về dict có khóa `status` ("success" hoặc "error")."""
        raise NotImplementedError
