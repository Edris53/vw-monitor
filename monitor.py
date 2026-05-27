import os
import hashlib
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
from datetime import datetime

TARGET_URL   = "https://www.volkswagen-dubai.com/en.html"
SNAPSHOT_FILE = "snapshot.txt"

NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL")
SMTP_HOST    = os.environ.get("SMTP_HOST")
SMTP_PORT    = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER    = os.environ.get("SMTP_USER")
SMTP_PASS    = os.environ.get("SMTP_PASS")

def fetch_site(url):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; VWMonitor/1.0)"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "meta", "head"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return " ".join(text.split())

def hash_content(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def load_snapshot():
    if not os.path.exists(SNAPSHOT_FILE):
        return None
    with open(SNAPSHOT_FILE, "r") as f:
        lines = f.read().strip().splitlines()
    if len(lines) < 2:
        return None
    return {"hash": lines[0], "timestamp": lines[1]}

def save_snapshot(content_hash):
    with open(SNAPSHOT_FILE, "w") as f:
        f.write(content_hash + "\n")
        f.write(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC") + "\n")

def send_email(subject, body):
    if not all([NOTIFY_EMAIL, SMTP_HOST, SMTP_USER, SMTP_PASS]):
        print("Email config missing - skipping.")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, NOTIFY_EMAIL, msg.as_string())
    print(f"Email sent to {NOTIFY_EMAIL}")

def main():
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{now}] Fetching {TARGET_URL}...")
    try:
        content = fetch_site(TARGET_URL)
    except Exception as e:
        print(f"Failed to fetch site: {e}")
        raise SystemExit(1)
    current_hash = hash_content(content)
    print(f"Fetched - hash: {current_hash[:12]}...")
    snapshot = load_snapshot()
    if snapshot is None:
        print("No snapshot found - saving baseline.")
        save_snapshot(current_hash)
        print("Baseline saved.")
        return
    if current_hash == snapshot["hash"]:
        print(f"No change detected (matches snapshot from {snapshot['timestamp']})")
        return
    print("CHANGE DETECTED!")
    subject = f"[VW Monitor] Website change detected - {now}"
    body = (
        f"A change was detected on your Volkswagen Dubai website.\n\n"
        f"URL: {TARGET_URL}\n"
        f"Detected at: {now}\n"
        f"Last clean snapshot: {snapshot['timestamp']}\n\n"
        f"Review the site immediately: {TARGET_URL}"
    )
    send_email(subject, body)
    save_snapshot(current_hash)
    print("Snapshot updated.")

if __name__ == "__main__":
    main()
