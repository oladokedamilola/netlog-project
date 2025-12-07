import re
from datetime import datetime
from .base import BaseParser

class IISParser(BaseParser):

    def parse_line(self, line):
        parts = line.split()

        try:
            date = parts[0]
            time = parts[1]
            ip = parts[2]
            method = parts[3]
            url = parts[4]
            status = parts[5]

            timestamp = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M:%S")

            return {
                "ip": ip,
                "timestamp": timestamp,
                "method": method,
                "url": url,
                "status": int(status),
                "user_agent": "",  # IIS rarely logs user agent in the same line
            }
        except:
            return None
