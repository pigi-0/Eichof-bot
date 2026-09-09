import os
import json
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from bs4 import BeautifulSoup

# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------
URL = "https://www.studentroom.ch/en/offer-eichhof"
STATE_FILE = "rooms.json"

EMAIL_SENDER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.environ.get("RECIPIENT_EMAIL")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# The room sizes we want to check (3, 4, 5 person apartments)
ROOM_SIZES_TO_CHECK = ["3", "4", "5"]

# ------------------------------------------------------------
# CORE LOGIC
# ------------------------------------------------------------
def fetch_rooms_via_ajax(zimmer_size=""):
    """
    Sends the exact POST request the website uses to filter rooms.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": URL,
        "Origin": "https://www.studentroom.ch",
    }
    
    payload = {
        "cmd": "cimmotool_immotool_immotool_search",
        "dsmid": "518083",
        "cimmotool_zimmer": zimmer_size,  # "3", "4", or "5"
        "cimmotool_bezug": "",
        "cimmotool_status": "1",          # 1 = free
        "cimmotool_zuordnung": "2",       # 2 = Open
    }

    response = requests.post(URL, headers=headers, data=payload, timeout=15)
    response.raise_for_status()
    return response.text

def extract_room_ids(html_fragment):
    """
    Parses the HTML to find room House numbers and Room numbers.
    """
    soup = BeautifulSoup(html_fragment, "html.parser")
    rows = soup.select(".list.scroll .row")
    
    if not rows:
        return []
    
    room_ids = []
    for row in rows:
        if "Kein Datensatz gefunden" in row.get_text():
            continue  # Skip empty state
        
        house = row.select_one(".spalte8")
        room_no = row.select_one(".spalte6")
        
        if house and room_no:
            house_text = house.get_text(strip=True)
            room_text = room_no.get_text(strip=True)
            unique_id = f"{house_text}_{room_text}"  # e.g., "15A_01"
            room_ids.append(unique_id)
        else:
            # Fallback if the structure changes slightly
            room_ids.append(row.get_text(strip=True)[:60])
    
    return room_ids

def load_previous_ids():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return []

def save_current_ids(ids):
    with open(STATE_FILE, "w") as f:
        json.dump(ids, f)

def send_email(new_rooms):
    subject = f"🚨 NEW ROOM at Eichhof! - {datetime.now().strftime('%H:%M')}"
    body = f"New room(s) detected!\n\nIDs: {', '.join(new_rooms)}\n\nBook now: {URL}"
    
    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECIPIENT
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
    print("📧 Email sent!")

def main():
    print(f"🕒 Checking for rooms at {datetime.now()}...")
    
    all_current_ids = []
    
    for size in ROOM_SIZES_TO_CHECK:
        print(f"   🔍 Checking {size}-person apartments...")
        try:
            html = fetch_rooms_via_ajax(zimmer_size=size)
            ids = extract_room_ids(html)
            print(f"      Found {len(ids)} available room(s).")
            all_current_ids.extend(ids)
        except Exception as e:
            print(f"      ❌ Error: {e}")
    
    current_ids = list(set(all_current_ids))
    print(f"✅ Total unique rooms found: {len(current_ids)}")

    previous_ids = load_previous_ids()
    new_rooms = list(set(current_ids) - set(previous_ids))

    if new_rooms:
        print(f"🆕 New rooms: {new_rooms}")
        send_email(new_rooms)
        save_current_ids(current_ids)
    else:
        print("ℹ️ No new rooms.")
        save_current_ids(current_ids)  # Keep cache fresh

if __name__ == "__main__":
    main()