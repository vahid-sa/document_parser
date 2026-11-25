from abc import ABC, abstractmethod


class BaseConverter(ABC):
    @abstractmethod
    def convert_to_markdown(self, content: bytes, page_number: int) -> str:
        """صفحهٔ ``page_number`` (۰-مبنا) از سند را به Markdown تبدیل می‌کند."""
        raise NotImplementedError
