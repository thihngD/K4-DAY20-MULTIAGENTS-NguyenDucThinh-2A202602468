"""Lớp nền cho mọi agent: tên, mô hình và logger riêng."""
from .logs import get_logger


class BaseAgent:
    def __init__(self, name: str, model=None):
        self.name = name
        self.model = model
        self.logger = get_logger(name)
