---

# MEPP (Minimal External Ping Panel)

MEPP is a lightweight, asynchronous Python-based monitoring system that pings internal devices and pushes status updates to AWS SQS for remote consumption. Ideal for hybrid environments where internal addresses are not directly reachable from the cloud.

---

## 🔧 Requirements

* Python 3.8+
* AWS account with permissions for SQS and EC2
* Pip for dependency management
* AWS CLI for authentication (`aws configure`)

---

## 🔑 AWS Authentication Setup

Before using MEPP, ensure your system can authenticate with AWS services by configuring the AWS CLI:

```bash
aws configure
```

You’ll be prompted to enter:

* **AWS Access Key ID**
* **AWS Secret Access Key**
* **Default region name** (e.g., `us-east-1`)
* **Default output format** (can be left blank or set to `json`)

This will create a credentials file at `~/.aws/credentials` used by Boto3.

---

## 📦 Setup

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `requirements.txt` file with:

```txt
boto3
python-dotenv
ping3
flask
openpyxl
watchdog
```

---

## 🔐 Environment Configuration

Create two separate `.env` files for each component.

### For `meppc_queuer.py` (Collector):

```
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/my-queue
AWS_REGION=us-east-1
```

### For `meppc_viewer.py` (Viewer):

```
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/my-queue
AWS_REGION=us-east-1
```

---

## 🗃 CSV Format

Your `default.csv` should look like:

```
Hostname,IP,Monitor,Comment
Router1,10.0.0.1,TRUE,Core Router
Switch1,10.0.0.2,TRUE,Access Layer
TestDevice,10.0.0.3,FALSE,Temporarily ignored
```

---

## 🚀 Running the Collector (On-Prem or Privately)

```bash
python meppc_queuer.py -f default.csv
```

This script will asynchronously ping all monitored devices and push the results to your SQS queue every 5 seconds.

---

## ☁️ Deploying the Viewer to AWS EC2

### Step-by-Step:

1. **Launch EC2 Instance**

   * Use Amazon Linux 2 or Ubuntu
   * Instance type: `t2.micro` (eligible for free tier)
   * Allow port `5025` in security group

2. **Install prerequisites on EC2**

   ```bash
   sudo yum update -y   # or sudo apt update
   sudo yum install python3-pip -y  # or sudo apt install python3-pip
   pip3 install -r requirements.txt
   ```

3. **Set environment**

   ```bash
   export SQS_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/123456789012/my-queue"
   export AWS_REGION="us-east-1"
   ```

4. **Run Flask viewer**

   ```bash
   sudo python3 meppc_viewer.py
   ```

5. **Run Flask viewer in headless mode**

   ```bash
   sudo nohup python3 meppc_viewer.py > output.log 2>&1 &
   ```

   **Stop Flask viewer in headless mode**

   ```bash
   ps aux | grep meppc_viewer.py
   sudo kill <PID>
   ```

6. **Access the dashboard**

   * Visit `http://<your-ec2-public-ip>:80`

---

## 📬 SQS Setup

1. Go to AWS SQS Console.
2. Create a **Standard Queue** (e.g., `mepp-status-queue`).
3. Copy the **Queue URL** into your `.env` files.
4. Ensure your EC2 IAM role (or credentials) has the following permissions:

   * `sqs:ReceiveMessage`
   * `sqs:SendMessage`
   * `sqs:DeleteMessage`
   * `sqs:GetQueueAttributes`

---

## ✅ Features

* Asynchronous ICMP pinging with majority rule
* Optional device comments
* Dynamic live updates in Flask dashboard
* Real-time host status display with ✅ and ❌
* CSV-based configuration
* Hybrid-friendly architecture using AWS SQS

---
