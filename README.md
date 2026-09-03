# SIH 2026 Submission Monitor (Telegram Alert Bot) 🚀

A lightweight, robust, and production-ready Python bot that monitors the **Smart India Hackathon (SIH)** portal for problem statement submission updates and sends instant alerts directly to your **Telegram**.

---

## 🌟 Features

- **Accurate Count Extraction**: Extracts the exact `X/500` submission count fraction using BeautifulSoup and regex, preventing false matching of Serial Numbers (`S.No 47`).
- **Real-Time Telegram Alerts**: Dispatches rich HTML alerts with delta increase (`+X`), progress percentage, and remaining slots.
- **Resilient Polling Loop**: Periodic non-blocking polling (e.g., every 5 minutes / 300s) that gracefully recovers from transient network or server timeouts.
- **Smart Notification Filtering**: Only triggers an alert when the submission count strictly increases (`current_count > last_count`).
- **Auto-Discovery Utility**: Automatically detects your Telegram Chat ID using `python sih_monitor.py --get-chat-id`.

---

## 🛠️ Installation & Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Credentials in `.env`
Edit the [`.env`](.env) file with your details:
```env
SIH_PS_URL=https://www.sih.gov.in/sih2026PS
PS_CODE=SIH26047
PS_TITLE=Patient Case-Taking Software
MAX_CAPACITY=500
POLL_INTERVAL_SECONDS=300

TELEGRAM_BOT_TOKEN=8887654158:AAEgwGkf08b-YLbQek1-o002BO-ZzOPtnAQ
TELEGRAM_CHAT_ID=6478945265
```

---

## 🚀 Running the Monitor

```bash
python sih_monitor.py
```

### Useful CLI Commands:
- **Discover your Telegram Chat ID:**
  ```bash
  python sih_monitor.py --get-chat-id
  ```

---

## 📋 Telegram Alert Format Preview

```
🚨 SIH SUBMISSION ALERT: NEW ENTRY! 🚨

📌 Problem Statement: Patient Case-Taking Software
🆔 PS ID: SIH26047

📈 Submission Count: 2 ➡️ 3 (+1)
🎯 Capacity: 0.6% (3/500)
⏳ Slots Remaining: 497
🕒 Time: 03 Sep 2026, 09:15:00 PM

🔗 Open SIH Portal
```
