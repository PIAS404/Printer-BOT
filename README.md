# Telegram Auto Counter Bot

This bot sends unlimited messages like:
⚡ 1 Message Sent Successfully
⚡ 2 Message Sent Successfully
⚡ 3 Message Sent Successfully ...

Features:
- Auto Restart System
- Monitor Loop (Crash Recovery)
- Start/Stop Inline Buttons
- Per-message terminal logging
- Fully Async & Stable

## Run Locally

pip install -r requirements.txt
python main.py

## Deploy to Railway / Heroku / Render
Add environment variable:
BOT_TOKEN = your telegram bot token
