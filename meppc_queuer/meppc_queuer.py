import os
import csv
import json
import time
import boto3
import argparse
import asyncio
import ipaddress
import re
from ping3 import ping
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")  # e.g., https://sqs.us-east-1.amazonaws.com/123456789012/my-queue
REGION_NAME = os.getenv("AWS_REGION", "us-east-1")
PING_TIMEOUT = 1  # seconds
PING_SIZE = 25  # bytes
SEND_INTERVAL = 5  # seconds between updates

# Initialize SQS
sqs = boto3.client("sqs", region_name=REGION_NAME)

class AddressValidator:
    def __init__(self):
        self.counter = 1

    def is_valid_domain(self, domain: str) -> bool:
        pattern = re.compile(
            r"^(?!\-)(?:[a-zA-Z0-9\-]{1,63}(?<!\-)\.)+[a-zA-Z]{2,}$"
        )
        return bool(pattern.fullmatch(domain))

    def validate_or_generate(self, input_str: str) -> str:
        try:
            ipaddress.ip_address(input_str)
            return input_str
        except ValueError:
            if self.is_valid_domain(input_str):
                return input_str
            else:
                generated = f"noAddress{self.counter}.ip"
                self.counter += 1
                return generated

def load_csv(file_path):
    validator = AddressValidator()
    hosts = []
    with open(file_path, newline='') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader, None)
        for row in reader:
            if len(row) >= 3:
                hostname, ip, monitor = row[0], row[1], row[2].strip().upper()
                comment = row[3] if len(row) > 3 else ""
                if hostname and ip and monitor == "TRUE":
                    hosts.append((hostname, validator.validate_or_generate(ip), comment, monitor))
                elif monitor == "FALSE":
                    hosts.append((hostname, validator.validate_or_generate(ip), f"NOT RESPONDING PRIOR TO START OF CHANGE. {comment}", monitor))

    return hosts

def send_to_sqs(hostname, ip, status, ping_time, comment):
    message = {
        "hostname": hostname,
        "ip": ip,
        "status": status,
        "ping_time": ping_time,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "comment": comment
    }
    sqs.send_message(
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=json.dumps(message)
    )

async def async_ping_host(ip):
    loop = asyncio.get_running_loop()
    results = await asyncio.gather(
        loop.run_in_executor(None, ping, ip, PING_TIMEOUT, PING_SIZE),
        loop.run_in_executor(None, ping, ip, PING_TIMEOUT, PING_SIZE),
        loop.run_in_executor(None, ping, ip, PING_TIMEOUT, PING_SIZE),
    )
    successes = [round(r * 1000, 2) for r in results if r and not isinstance(r, bool)]
    if len(successes) >= 2:
        return "Up", round(sum(successes) / len(successes), 2)
    return "Down", None

async def run_collector(hosts):
    while True:
        tasks = []
        for hostname, ip, comment in hosts:
            tasks.append(asyncio.create_task(async_ping_host(ip)))

        results = await asyncio.gather(*tasks)

        for (hostname, ip, comment, monitor), (status, ping_time) in zip(hosts, results):
            print(f"[SEND] {ip} - {status} - {ping_time} ms")
            send_to_sqs(hostname, ip, status, ping_time, comment, monitor)

        await asyncio.sleep(SEND_INTERVAL)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collector for MEPP")
    parser.add_argument("-f", "--file", default="default.csv", help="CSV file with hosts to monitor")
    args = parser.parse_args()

    if not SQS_QUEUE_URL:
        raise EnvironmentError("Missing SQS_QUEUE_URL in environment variables.")

    hosts = load_csv(args.file)
    print(f"Loaded {len(hosts)} hosts from {args.file}")
    asyncio.run(run_collector(hosts))
