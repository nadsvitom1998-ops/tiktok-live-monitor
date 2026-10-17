"""TikTok live notifier for GitHub Actions. Watch list and state are non-secret."""
import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from TikTokLive import TikTokLiveClient

ACCOUNTS = ("alena_polevaya", "myza.muza")
STATE_FILE = Path(__file__).with_name("state.json")


def send_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        raise RuntimeError("Configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID secrets")
    payload = urlencode({"chat_id": chat_id, "text": message, "disable_web_page_preview": "true"}).encode()
    req = Request(f"https://api.telegram.org/bot{token}/sendMessage", data=payload, method="POST")
    with urlopen(req, timeout=20) as response:
        data = json.load(response)
        if not data.get("ok"):
            raise RuntimeError(f"Telegram returned an error: {data.get('description', 'unknown')}")


async def is_live(username: str) -> bool:
    client = TikTokLiveClient(unique_id=f"@{username}")
    return bool(await asyncio.wait_for(client.is_live(), timeout=35))


async def run() -> None:
    if os.getenv("TEST_NOTIFICATION") == "true":
        send_telegram("✅ Тест TikTok LIVE Monitor: уведомления работают!\nОтслеживаются @alena_polevaya и @myza.muza")
        print("Test notification sent")
        return

    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    errors = []
    for username in ACCOUNTS:
        previous = state.get(username, False)
        try:
            current = await is_live(username)
            print(f"@{username}: {'LIVE' if current else 'offline'}")
            if current and not previous:
                send_telegram(f"🔴 @{username} сейчас в прямом эфире TikTok!\nhttps://www.tiktok.com/@{username}/live")
                print(f"Notification sent for @{username}")
            state[username] = current
        except Exception as exc:
            # Do NOT record offline on API errors; prevents false re-alerts.
            print(f"Unable to check @{username}: {type(exc).__name__}: {exc}")
            errors.append(username)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if errors:
        raise RuntimeError("TikTok status unavailable for: " + ", ".join(errors))


if __name__ == "__main__":
    asyncio.run(run())
