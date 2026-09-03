"""
SIH Problem Statement (PS ID: SIH26047) Submission Monitor & Telegram Alert Bot.
================================================================================
Monitors the Smart India Hackathon (SIH) portal for submission count updates
and sends real-time Telegram notifications when submissions increase.
"""

import os
import re
import sys
import time
import logging
from datetime import datetime
from typing import Optional, Tuple
import urllib3

# Ensure Windows terminal handles emojis and UTF-8 characters cleanly
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Suppress insecure SSL warnings for government portal fallback requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()


# ==============================================================================
# CONFIGURATION & CREDENTIALS
# ==============================================================================

# Telegram Bot Credentials
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8887654158:AAEgwGkf08b-YLbQek1-o002BO-ZzOPtnAQ").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Target Problem Statement Details
TARGET_PS_ID = os.getenv("PS_CODE", "SIH26047").strip()
TARGET_PS_TITLE = os.getenv("PS_TITLE", "Patient Case-Taking Software").strip()
MAX_CAPACITY = int(os.getenv("MAX_CAPACITY", "500"))

# Target URLs (Handles 2026/2024 portals and fallbacks)
TARGET_URLS = [
    os.getenv("SIH_PS_URL", "https://www.sih.gov.in/sih2026PS").strip(),
    "https://sih.gov.in/sih2024PS",
    "https://sih.gov.in",
]

# Polling Interval (in seconds - 300s = 5 minutes)
CHECK_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))

# Browser-mimicking HTTP headers
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


# ==============================================================================
# LOGGING SETUP
# ==============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("sih_monitor.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("SIHMonitor")


# ==============================================================================
# DATA EXTRACTION & SCRAPING MODULE
# ==============================================================================

class SIHScraper:
    """Extracts submission count and capacity for a given problem statement ID."""

    def __init__(self, target_ps_code: str = TARGET_PS_ID):
        self.target_ps_code = target_ps_code.strip()
        raw_num = "".join(ch for ch in self.target_ps_code if ch.isdigit())
        self.ps_variants = list(filter(None, [
            self.target_ps_code,
            raw_num,
            f"SIH{raw_num}" if raw_num else "",
            f"SIH-{raw_num}" if raw_num else "",
        ]))

    def extract_submission_count(self, html: str) -> Optional[Tuple[int, int]]:
        """
        Fixed Data Extraction Strategy:
        Forces exact 'X/Y' fraction pattern matching to prevent S.No column matching.
        """
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        # Find row containing PS Code
        for variant in self.ps_variants:
            matched_tds = soup.find_all(
                lambda tag: tag.name == "td" and variant.lower() in tag.get_text(strip=True).lower()
            )
            for td in matched_tds:
                parent_tr = td.find_parent("tr")
                if not parent_tr:
                    continue

                # Iterate through all cells in row
                for cell in parent_tr.find_all("td"):
                    text = cell.get_text(strip=True)
                    # STRICT MATCHing for fraction pattern 'X / Y' or 'X/Y' (e.g., 2/500)
                    match = re.search(r"(\d+)\s*/\s*(\d+)", text)
                    if match:
                        count = int(match.group(1))
                        capacity = int(match.group(2))
                        return count, capacity

        # Fallback Proximity Regex for direct X/500 pattern search
        for variant in self.ps_variants:
            idx = html.lower().find(variant.lower())
            if idx != -1:
                chunk = html[idx: idx + 800]
                match = re.search(r"(\d+)\s*/\s*(\d+)", chunk)
                if match:
                    return int(match.group(1)), int(match.group(2))

        return None

    def fetch_page(self, urls=TARGET_URLS) -> Optional[str]:
        """Fetches raw HTML from SIH portal with timeout and retry handling."""
        for url in urls:
            for attempt in range(1, 4):
                try:
                    response = requests.get(
                        url,
                        headers=HTTP_HEADERS,
                        timeout=25,
                        verify=False  # Handles government SSL certificate trust chains
                    )
                    if response.status_code == 200 and len(response.text) > 1000:
                        return response.text
                    else:
                        logger.warning(f"[Scraper] HTTP {response.status_code} received from {url}")
                except requests.exceptions.RequestException as e:
                    logger.warning(f"[Scraper] Request error for {url} (Attempt {attempt}/3): {e}")
                    time.sleep(2 ** attempt)
        return None

    def get_count_and_capacity(self) -> Optional[Tuple[int, int]]:
        """Fetches portal page and extracts (count, capacity)."""
        html = self.fetch_page()
        if html:
            return self.extract_submission_count(html)
        return None


# ==============================================================================
# TELEGRAM NOTIFICATION MODULE
# ==============================================================================

def send_telegram_message(text: str, bot_token: str = BOT_TOKEN, chat_id: str = CHAT_ID) -> bool:
    """
    Sends an HTML-formatted message to Telegram using the official Bot API.
    """
    if not bot_token or not chat_id:
        logger.warning("[Telegram] Notification skipped: BOT_TOKEN or CHAT_ID is not configured.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        data = response.json()
        if response.status_code == 200 and data.get("ok"):
            logger.info(f"[Telegram] Notification delivered to Chat ID: {chat_id}")
            return True
        else:
            logger.error(f"[Telegram] API error response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"[Telegram] Network error sending notification: {e}")
        return False


def send_welcome_message(initial_count: Optional[int], ps_id: str, ps_title: str, max_cap: int = MAX_CAPACITY):
    """
    Sends a clean welcome message on script initialization.
    """
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")
    count_str = f"<b>{initial_count}</b> / {max_cap}" if initial_count is not None else "<i>Checking...</i>"
    
    welcome_text = (
        f"🤖 <b>SIH Submission Monitor Initialized</b>\n\n"
        f"📌 <b>Problem Statement:</b> {ps_title}\n"
        f"🆔 <b>PS ID:</b> <code>{ps_id}</code>\n"
        f"📊 <b>Initial Count:</b> {count_str}\n"
        f"⏱ <b>Check Frequency:</b> Every {CHECK_INTERVAL_SECONDS} seconds\n"
        f"🕒 <b>Started At:</b> {now}\n\n"
        f"<i>✅ You will receive alerts whenever the submission count increases.</i>"
    )
    return send_telegram_message(welcome_text)


def send_count_increase_alert(
    ps_id: str,
    ps_title: str,
    previous_count: int,
    new_count: int,
    max_capacity: int = MAX_CAPACITY,
):
    """
    Sends an instant alert when submissions strictly increase.
    """
    delta = new_count - previous_count
    percentage = (new_count / max_capacity * 100) if max_capacity > 0 else 0.0
    remaining = max(0, max_capacity - new_count)
    now = datetime.now().strftime("%d %b %Y, %I:%M:%S %p")

    alert_text = (
        f"🚨 <b>SIH SUBMISSION ALERT: NEW ENTRY!</b> 🚨\n\n"
        f"📌 <b>Problem Statement:</b> {ps_title}\n"
        f"🆔 <b>PS ID:</b> <code>{ps_id}</code>\n\n"
        f"📈 <b>Submission Count:</b> <b>{previous_count}</b> ➡️ <b>{new_count}</b> (<b>+{delta}</b>)\n"
        f"🎯 <b>Capacity:</b> {percentage:.1f}% ({new_count}/{max_capacity})\n"
        f"⏳ <b>Slots Remaining:</b> {remaining}\n"
        f"🕒 <b>Time:</b> {now}\n\n"
        f"🔗 <a href=\"https://www.sih.gov.in\">Open SIH Portal</a>"
    )
    return send_telegram_message(alert_text)


# ==============================================================================
# HELPER: AUTO-DISCOVER CHAT ID
# ==============================================================================

def check_for_telegram_updates():
    """Fetches recent bot interactions to help user find their Chat ID."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    try:
        res = requests.get(url, timeout=10).json()
        updates = res.get("result", [])
        if not updates:
            print("\n[!] No messages found yet.")
            print("    👉 Open Telegram, search for @sihcountbot, and click START.")
            print("    Then run this command again.\n")
            return None
        
        print("\nRecent messages received by bot:")
        detected_id = None
        for u in updates:
            msg = u.get("message") or u.get("channel_post")
            if msg:
                chat = msg.get("chat", {})
                detected_id = str(chat.get("id"))
                name = chat.get("first_name") or chat.get("title") or "User"
                print(f" • Chat ID: {detected_id} ({name}) | Text: '{msg.get('text', '')}'")
        return detected_id
    except Exception as e:
        logger.error(f"Error checking Telegram updates: {e}")
        return None


# ==============================================================================
# MAIN POLLING LOOP
# ==============================================================================

def monitor():
    """
    Main polling loop that tracks submission counts and sends notifications.
    """
    global CHAT_ID

    print("=" * 70)
    print("      SIH26047 SUBMISSION MONITOR & TELEGRAM ALERT BOT")
    print("=" * 70)
    print(f"Target PS ID       : {TARGET_PS_ID}")
    print(f"Target PS Title    : {TARGET_PS_TITLE}")
    print(f"Poll Interval      : {CHECK_INTERVAL_SECONDS} seconds")
    print(f"Telegram Bot       : @sihcountbot")
    print(f"Telegram Chat ID   : {CHAT_ID if CHAT_ID else 'NOT SET (Attempting auto-discovery...)'}")
    print("=" * 70)

    # Auto-discover Chat ID if not set
    if not CHAT_ID:
        detected = check_for_telegram_updates()
        if detected:
            CHAT_ID = detected
            logger.info(f"Auto-configured CHAT_ID to {CHAT_ID}")
        else:
            logger.warning("CHAT_ID is not configured. Running in log-only mode until CHAT_ID is set.")

    scraper = SIHScraper(TARGET_PS_ID)

    # Initialize last_count on first successful check
    last_count: Optional[int] = None
    logger.info("Performing initial check on SIH portal...")

    initial_result = scraper.get_count_and_capacity()
    if initial_result is not None:
        initial_count, cap = initial_result
        last_count = initial_count
        logger.info(f"✅ Baseline established: PS {TARGET_PS_ID} currently has {last_count}/{cap} submissions.")
        
        # Send initial welcome message
        if CHAT_ID:
            send_welcome_message(last_count, TARGET_PS_ID, TARGET_PS_TITLE, cap)
    else:
        logger.warning("Could not retrieve submission count during initial check. Will retry in loop.")

    cycle = 1
    logger.info("Entering continuous monitoring loop. Press Ctrl+C to exit.\n")

    while True:
        try:
            # Wait for next interval
            time.sleep(CHECK_INTERVAL_SECONDS)
            
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"--- [Cycle #{cycle} @ {timestamp_str}] Checking SIH Portal ---")

            result = scraper.get_count_and_capacity()

            if result is not None:
                current_count, current_cap = result
                logger.info(f"Status: PS {TARGET_PS_ID} = {current_count}/{current_cap} (Last recorded: {last_count})")

                # Smart Notification Logic: Only alert when current_count > last_count
                if last_count is not None and current_count > last_count:
                    delta = current_count - last_count
                    logger.info(f"🚨 SUBMISSION COUNT INCREASED! (+{delta} submissions). Dispatching Telegram alert...")

                    success = send_count_increase_alert(
                        ps_id=TARGET_PS_ID,
                        ps_title=TARGET_PS_TITLE,
                        previous_count=last_count,
                        new_count=current_count,
                        max_capacity=current_cap or MAX_CAPACITY,
                    )

                    if success:
                        logger.info("✅ Telegram alert delivered successfully.")
                    else:
                        logger.warning("❌ Failed to deliver Telegram alert.")

                    # Update state
                    last_count = current_count

                elif last_count is None:
                    # First time receiving a valid count if initial check had failed
                    last_count = current_count
                    logger.info(f"Baseline established: {last_count} submissions.")
                    if CHAT_ID:
                        send_welcome_message(last_count, TARGET_PS_ID, TARGET_PS_TITLE, current_cap)
                else:
                    logger.info("No change in submission count. Sleeping until next cycle...")

            else:
                logger.warning(f"Could not locate or parse 'X/Y' count for {TARGET_PS_ID} this cycle.")

            cycle += 1

        except KeyboardInterrupt:
            print("\n[!] Monitor stopped by user (Ctrl+C). Exiting cleanly.")
            break
        except Exception as err:
            logger.error(f"Unexpected exception in monitoring loop: {err}", exc_info=True)
            time.sleep(10)  # Brief pause to prevent rapid looping on fatal errors


if __name__ == "__main__":
    if "--get-chat-id" in sys.argv:
        check_for_telegram_updates()
        sys.exit(0)
        
    monitor()
