# generate_test_log.py
import random
from datetime import datetime, timedelta

ips = [f"192.168.1.{i}" for i in range(1, 51)]
urls = ["/index.html", "/about.html", "/products", "/api/data", "/images/logo.png", 
        "/css/style.css", "/js/app.js", "/contact", "/blog/post-1", "/dashboard"]
methods = ["GET", "POST", "PUT", "DELETE"]
status_codes = [200, 200, 200, 200, 301, 302, 400, 401, 403, 404, 500]

start_date = datetime(2026, 3, 1, 0, 0, 0)

with open("large_traffic.log", "w") as f:
    for i in range(1000):
        ip = random.choice(ips)
        timestamp = start_date + timedelta(minutes=i)
        method = random.choice(methods)
        url = random.choice(urls)
        status = random.choice(status_codes)
        size = random.randint(100, 10000)
        
        log_line = f'{ip} - - [{timestamp.strftime("%d/%b/%Y:%H:%M:%S +0000")}] "{method} {url} HTTP/1.1" {status} {size}\n'
        f.write(log_line)