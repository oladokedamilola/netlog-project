import re
from .base import BaseParser
from datetime import datetime

APACHE_REGEX = re.compile(
    r'(?P<ip>\S+) \S+ \S+ \[(?P<timestamp>.*?)\] '
    r'"(?P<method>\S+)? (?P<url>\S+)? \S+" '
    r'(?P<status>\d{3}) \S+ "(?P<user_agent>.*)"'
)

class ApacheParser(BaseParser):

    def parse_timestamp(self, raw_ts):
        return datetime.strptime(raw_ts, "%d/%b/%Y:%H:%M:%S %z")

    def parse_line(self, line):
        match = APACHE_REGEX.match(line)
        if not match:
            return None

        data = match.groupdict()

        return {
            "ip": data.get("ip"),
            "timestamp": self.parse_timestamp(data.get("timestamp")),
            "method": data.get("method"),
            "url": data.get("url"),
            "status": int(data.get("status")),
            "user_agent": data.get("user_agent"),
        }
