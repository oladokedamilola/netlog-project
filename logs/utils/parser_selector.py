from logs.parsers.apache import ApacheParser
from logs.parsers.nginx import NginxParser
from logs.parsers.iis import IISParser

def get_parser(log_type, file_path):
    if log_type == "apache":
        return ApacheParser(file_path)
    elif log_type == "nginx":
        return NginxParser(file_path)
    elif log_type == "iis":
        return IISParser(file_path)
    else:
        raise ValueError("Unknown log type")
