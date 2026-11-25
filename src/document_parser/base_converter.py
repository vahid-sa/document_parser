from abc import ABC, abstractmethod


class BaseConverter(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def convert_to_markdown(self, content: bytes) -> str:
        ...
