import os
import boto3
import json
import time
from flask import Flask, render_template_string, jsonify
from collections import defaultdict, deque
from dotenv import load_dotenv

app = Flask(__name__)

# Load environment variables
load_dotenv()

QUEUE_URL = os.getenv("SQS_QUEUE_URL")
AWS_REGION  = os.getenv("AWS_REGION", "us-east-1")

# Initialize SQS
sqs = boto3.client("sqs", region_name=AWS_REGION)

# In-memory store for host states
status_history = defaultdict(lambda: deque(maxlen=10))
latest_status = {}

def poll_sqs():
    while True:
        response = sqs.receive_message(
            QueueUrl=QUEUE_URL,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=10
        )

        messages = response.get("Messages", [])
        for message in messages:
            try:
                body = json.loads(message["Body"])
                hostname = body["hostname"]
                ip = body["ip"]
                status = body["status"]
                ping_time = body["ping_time"]
                timestamp = body["timestamp"]
                monitor = body["monitor"]
                comment = body.get("comment", "")

                # Update memory
                latest_status[ip] = {
                    "hostname": hostname,
                    "ip": ip,
                    "status": status,
                    "ping_time": ping_time,
                    "timestamp": timestamp,
                    "comment": comment,
                    "monitor": monitor,
                    "timeline": list(status_history[ip])
                }
                status_history[ip].append(status)

            except Exception as e:
                print("Failed to process message:", e)

            # Delete processed message
            sqs.delete_message(
                QueueUrl=QUEUE_URL,
                ReceiptHandle=message["ReceiptHandle"]
            )

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MEPP Viewer Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; }
    table { border-collapse: collapse; width: 90%; margin: auto; }
    th, td { padding: 10px; text-align: center; border: 1px solid #ddd; }
    th { background-color: #f4f4f4; }
    .up { background-color: #c8e6c9; }
    .down { background-color: #ffcdd2; }
    .monitor { background-color: #d3d3d3; }
    .timestamp { font-weight: bold; text-align: center; margin-bottom: 10px; }
    .row-flash {
        animation: flash 0.5s ease-in-out;
    }
    .switch {
      position: relative;
      display: inline-block;
      width: 48px;
      height: 24px;
      vertical-align: middle;
    }
    .switch input {
      opacity: 0;
      width: 0;
      height: 0;
    }
    .slider {
      position: absolute;
      cursor: pointer;
      top: 0; left: 0; right: 0; bottom: 0;
      background-color: #ccc;
      transition: .3s;
      border-radius: 24px;
    }
    .slider:before {
      position: absolute;
      content: "";
      height: 18px; width: 18px;
      left: 3px; bottom: 3px;
      background-color: white;
      transition: .3s;
      border-radius: 50%;
      box-shadow: 0 1px 4px rgba(0,0,0,0.15);
    }
    input:checked + .slider {
      background-color: #4CAF50;
    }
    input:checked + .slider:before {
      transform: translateX(24px);
    }
    @keyframes flash {
        0%   { opacity: 1; }
        50%  { opacity: 0.3; }
        100% { opacity: 1; }
    }

  </style>
  <script>
    let currentSortColumn = null;
    let currentSortDirection = "asc";

    function updateSortIndicators() {
      const ths = document.querySelectorAll("th");
      ths.forEach((th, index) => {
        let indicator = th.querySelector(".sort-indicator");
        if (!indicator) {
          indicator = document.createElement("span");
          indicator.className = "sort-indicator";
          th.appendChild(indicator);
        }
        if (index === currentSortColumn) {
          indicator.textContent = currentSortDirection === "asc" ? "▲" : "▼";
        } else {
          indicator.textContent = "";
        }
      });
    }

    function sortTable(n) {
      if (currentSortColumn === n) {
        currentSortDirection = currentSortDirection === "asc" ? "desc" : "asc";
      } else {
        currentSortColumn = n;
        currentSortDirection = "asc";
      }
      updateSortIndicators();
      fetchStatus();
    }

    async function fetchStatus() {
      const response = await fetch("/api/status");
      let data = await response.json();

      if (currentSortColumn !== null) {
        const getValue = (row, idx) => {
          switch (idx) {
            case 1: return row.hostname;
            case 2: return row.ip;
            case 3: return row.status;
            case 4: return row.ping_time ?? 0;
            case 5: return row.comment;
            default: return "";
          }
        };

        data.sort((a, b) => {
          const valA = getValue(a, currentSortColumn);
          const valB = getValue(b, currentSortColumn);
          const aVal = typeof valA === "string" ? valA.toLowerCase() : valA;
          const bVal = typeof valB === "string" ? valB.toLowerCase() : valB;

          if (aVal < bVal) return currentSortDirection === "asc" ? -1 : 1;
          if (aVal > bVal) return currentSortDirection === "asc" ? 1 : -1;
          return 0;
        });
      }

      const hideUnmonitored = document.getElementById("hideUnmonitored")?.checked;

      const tbody = document.querySelector("tbody");
      tbody.innerHTML = "";

      data.forEach((row, index) => {
        if (hideUnmonitored && row.monitor === "FALSE") return; // **Hide unmonitored rows**

        if (row.monitor === "FALSE") {
            row.status = "monitor";
        }

        const tr = document.createElement("tr");
        tr.className = row.status === "Up" ? "up" : row.status === "monitor" ? "monitor" : "down";
        tr.innerHTML = `
          <td>${index + 1}</td>
          <td>${row.hostname}</td>
          <td>${row.ip}</td>
          <td>${row.status === "Up" ? "✅" : "❌"}</td>
          <td>${row.ping_time ?? "N/A"}</td>
          <td>${row.timeline.map(s => s === "Up" ? "✅" : "❌").join("")}</td>
          <td>${row.comment}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    async function clearStatus() {
      await fetch("/api/clear", { method: "POST" });
      fetchStatus();
    }

    setInterval(fetchStatus, 5000);
    window.onload = () => {
      fetchStatus();
      updateSortIndicators();
    };
  </script>
</head>
<body>
  <h2 style="text-align:center;">MEPPC Dashboard</h2>

  <div class="timestamp">Current Time (live): <span id="timestamp"></span></div>

  <div style="text-align:center; margin: 10px;">
    <label style="font-size:1.1em;">
      <span style="vertical-align:middle;">Hide monitor only rows</span>
      <label class="switch">
        <input type="checkbox" id="hideUnmonitored" onchange="fetchStatus()">
        <span class="slider"></span>
      </label>
    </label>
    <button onclick="clearStatus()" style="margin-left:18px;">Clear Dashboard</button>
  </div>

  <table>
    <thead>
      <tr>
        <th onclick="sortTable(0)">Index</th>
        <th onclick="sortTable(1)">Hostname</th>
        <th onclick="sortTable(2)">IP Address</th>
        <th onclick="sortTable(3)">Status</th>
        <th onclick="sortTable(4)">Response Time (ms)</th>
        <th>Timeline</th>
        <th onclick="sortTable(5)">Comment</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>

  <script>
    setInterval(() => {
      const now = new Date();
      const options = {
        timeZone: "America/New_York",
        hour12: false,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
      };
      const formatter = new Intl.DateTimeFormat([], options);
      document.getElementById("timestamp").textContent = formatter.format(now).replace(",", "");
    }, 1000);
  </script>
</body>
</html>
'''

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/status")
def api_status():
    return jsonify(list(latest_status.values()))

@app.route("/api/clear", methods=["POST"])
def clear_status():
    latest_status.clear()
    status_history.clear()
    return jsonify({"message": "Cleared"})

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=poll_sqs, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=80)
