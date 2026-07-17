import time
import asyncio
import threading
from pyrogram.errors import MessageNotModified, FloodWait

# Last update time per message id to avoid flood
_last_update: dict = {}
UPDATE_INTERVAL = 5  # seconds between Telegram edits


def humanbytes(size):
    if not size:
        return "?"
    power = 2 ** 10
    raised_to_pow = 0
    dict_power_n = {0: "B", 1: "KiB", 2: "MiB", 3: "GiB", 4: "TiB"}
    while size > power:
        size /= power
        raised_to_pow += 1
    return f"{round(size, 2)} {dict_power_n[raised_to_pow]}"


def progress_bar(percent_str: str, length: int = 10) -> str:
    try:
        pct = float(percent_str.strip().replace("%", ""))
    except Exception:
        return "░" * length + " 0%"
    filled = int(length * pct / 100)
    bar = "█" * filled + "░" * (length - filled)
    return f"{bar} {pct:.1f}%"


def build_progress_text(d: dict) -> str:
    status = d.get("status", "")
    filename = d.get("filename", "")
    # Clean filename — just show last part
    if filename:
        filename = filename.split("/")[-1]
        if len(filename) > 40:
            filename = filename[:37] + "..."

    downloaded = d.get("downloaded_bytes", 0) or 0
    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0

    dl_str = humanbytes(downloaded)
    total_str = humanbytes(total) if total else "?"
    speed = d.get("speed") or 0
    speed_str = humanbytes(speed) + "/s" if speed else "?"
    eta = d.get("eta")
    if eta:
        mins, secs = divmod(int(eta), 60)
        hours, mins = divmod(mins, 60)
        eta_str = f"{hours}h {mins}m {secs}s" if hours else f"{mins}m {secs}s" if mins else f"{secs}s"
    else:
        eta_str = "?"

    pct = 0.0
    if total and downloaded:
        pct = downloaded / total * 100
    pct_str = f"{pct:.1f}%"
    bar = progress_bar(pct_str)

    return (
        f"╔══《 📥 <b>DOWNLOADING</b> 》══╗\n"
        f"\n"
        f"🎬 <code>{filename}</code>\n"
        f"\n"
        f"📊 <b>Progress  :</b>\n"
        f"┃  {bar}\n"
        f"\n"
        f"📦 <b>Downloaded:</b>  <code>{dl_str}</code> / <code>{total_str}</code>\n"
        f"⚡ <b>Speed     :</b>  <code>{speed_str}</code>\n"
        f"⏳ <b>ETA       :</b>  <code>{eta_str}</code>\n"
        f"\n"
        f"╚══《 🤖 @X_gender_bot 》══╝"
    )


def edit_msg(client, message, text):
    try:
        client.loop.create_task(message.edit(text))
    except FloodWait as e:
        client.loop.create_task(asyncio.sleep(e.value))
    except (MessageNotModified, TypeError):
        pass
    except Exception:
        pass


def download_progress_hook(d, message, client):
    if d.get("status") != "downloading":
        return

    msg_id = getattr(message, "id", id(message))
    now = time.time()
    last = _last_update.get(msg_id, 0)

    if now - last < UPDATE_INTERVAL:
        return

    _last_update[msg_id] = now
    text = build_progress_text(d)
    threading.Thread(target=edit_msg, args=(client, message, text), daemon=True).start()
