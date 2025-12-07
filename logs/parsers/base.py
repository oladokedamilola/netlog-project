import re
from datetime import datetime

class BaseParser:

    def __init__(self, file_path):
        self.file_path = file_path

    def parse_timestamp(self, raw):
        """Override this method in child classes."""
        raise NotImplementedError

    def parse_line(self, line):
        """Override this method in child classes."""
        raise NotImplementedError

    def parse_file(self):
        """Reads file line by line and yields parsed rows."""
        with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parsed = self.parse_line(line)
                if parsed:
                    yield parsed
