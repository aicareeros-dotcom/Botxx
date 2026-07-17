"""
Custom scraper for xxxtophd.com
- Single video: https://xxxtophd.com/video?id=XXXXXX
- Category page: https://xxxtophd.com/indian/
"""

import os
import re
import asyncio
import httpx
import yt_dlp

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

from PornHub.plugins.function import download_progress_hook
from PornHub.plugins.caption import make_caption

BASE = "https://xxxtophd.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": BASE,
}

xxx_active = {}
xxx_stop = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_xxxtophd(url: str) -> bool:
    return "xxxtophd.com" in url


async def fetch(url: str) -> str:
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:
        r = await client.get(url)
        return r.text


async def get_page_videos(url: str):
    """Return list of (title, video_page_url) from a category/listing page."""
    html = await fetch(url)
    entries = re.findall(
        r'href="(video\?id=[^"]+)"[^>]*>.*?<span class="th-desc">([^<]+)</span>',
        html, re.S
    )
    results = [(title.strip(), f"{BASE}/{href}") for href, title in entries]

    next_page = re.search(r'href="([^"]+)"[^>]*>\s*(?:Next|next|›)\s*<', html, re.I)
    next_url = None
    if next_page:
        np = next_page.group(1)
        next_url = np if np.startswith("http") else BASE + "/" + np.lstrip("/")

    return results, next_url


async def extract_embed_url(video_page_url: str):
    """Scrape video page → find iframe embed URL."""
    html = await fetch(video_page_url)

    title_m = re.search(r'<h2>([^<]+)</h2>', html)
    title = title_m.group(1).strip() if title_m else "Video"

    duration_m = re.search(r'<span>Duration:</span>\s*([\d:]+)', html)
    duration = duration_m.group(1).strip() if duration_m else "?"

    tags_m = re.findall(r'<a class="btn"[^>]+>([^<]+)</a>', html)
    tags = ", ".join(tags_m[:6]) if tags_m else ""

    iframe_m = re.search(r'<iframe src="([^"]+)"', html)
    embed_url = iframe_m.group(1).strip() if iframe_m else None

    return title, embed_url, tags, duration


async def run_async(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)


def yt_download(url: str, out_tmpl: str, msg_ref, client_ref):
    opts = {
        "outtmpl": out_tmpl,
        "format": "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "concurrent_fragment_downloads": 16,
        "external_downloader": "aria2c",
        "external_downloader_args": {
            "aria2c": ["-x", "16", "-s", "16", "-k", "1M", "--min-split-size=1M"]
        },
        "progress_hooks": [lambda d: download_progress_hook(d, msg_ref, client_ref)],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])


async def send_video_file(c: Client, chat_id: int, caption: str) -> bool:
    for file in os.listdir("downloads"):
        if file.endswith((".mp4", ".mkv", ".webm")):
            path = os.path.join("downloads", file)
            try:
                await c.send_video(chat_id, path, caption=caption, supports_streaming=True)
            except FloodWait as e:
                await asyncio.sleep(e.value + 2)
                await c.send_video(chat_id, path, caption=caption, supports_streaming=True)
            finally:
                try:
                    os.remove(path)
                except Exception:
                    pass
            return True
    return False


# ── URL filter ────────────────────────────────────────────────────────────────

def is_xxx_url(flt, client, update):
    return bool(update.text and is_xxxtophd(update.text))

xxx_url_filter = filters.create(is_xxx_url, name="xxx_url_filter")


# ── Main handler ──────────────────────────────────────────────────────────────

@Client.on_message(xxx_url_filter & filters.private)
async def handle_xxxtophd(c: Client, u: Message):
    url = u.text.strip()
    user_id = u.from_user.id

    if xxx_active.get(user_id):
        await u.reply_text("⚠️ Pehle se ek download chal raha hai!\n/xxxstop se band karo.")
        return

    msg = await u.reply_text("🔍 xxxtophd.com check ho raha hai...")

    try:
        # ── Single video ──────────────────────────────────────────────
        if "video?id=" in url:
            title, embed_url, tags, duration = await extract_embed_url(url)
            if not embed_url:
                await msg.edit_text("❌ Video player nahi mila is page pe.")
                return

            await msg.edit_text(
                f"📹 <b>{title}</b>\n"
                f"⏱ Duration: <code>{duration}</code>\n"
                f"🏷 Tags: {tags}\n\n"
                "Download karna chahte ho?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Download", callback_data=f"xxx_{url}")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
                ])
            )

        # ── Category / listing page ───────────────────────────────────
        else:
            videos, _ = await get_page_videos(url)
            total = len(videos)
            if total == 0:
                await msg.edit_text("❌ Koi video nahi mili is page pe.\n\nNote: Specific category URL bhejo jaise:\n<code>https://xxxtophd.com/indian/</code>")
                return

            page_title_m = re.search(r'xxxtophd\.com/([^/?]+)', url)
            cat = page_title_m.group(1).replace("-", " ").title() if page_title_m else "xxxtophd"

            await msg.edit_text(
                f"📂 <b>xxxtophd.com — {cat}</b>\n\n"
                f"🎬 Videos found: <b>{total}</b>\n\n"
                "Sabhi videos download karna chahte ho?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        f"✅ Haan, sab download karo ({total} videos)",
                        callback_data=f"xxxbulk_{url}"
                    )],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
                ])
            )

    except Exception as e:
        await msg.edit_text(f"❌ Error: <code>{str(e)[:300]}</code>")


# ── Single download callback ──────────────────────────────────────────────────

@Client.on_callback_query(filters.regex("^xxx_"))
async def xxx_single_download(c: Client, q: CallbackQuery):
    video_url = q.data[4:]  # strip "xxx_"
    user_id = q.from_user.id
    chat_id = q.message.chat.id

    if xxx_active.get(user_id):
        await q.answer("Pehle download complete karo!", show_alert=True)
        return

    xxx_active[user_id] = True
    msg = await q.message.edit_text("📥 Download shuru ho gaya...")

    try:
        title, embed_url, tags, duration = await extract_embed_url(video_url)
        if not embed_url:
            await msg.edit_text("❌ Embed URL nahi mila.")
            return

        await run_async(yt_download, embed_url, "downloads/%(title)s.%(ext)s", msg, c)
        caption = make_caption(
            title=title, duration=duration, tags=tags,
            site="xxxtophd.com", source_url=video_url,
        )
        await msg.edit_text("📤 Upload ho raha hai...")
        ok = await send_video_file(c, chat_id, caption)
        if not ok:
            await msg.edit_text("❌ File download nahi hui.")
        else:
            await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Error: <code>{str(e)[:300]}</code>")
    finally:
        xxx_active.pop(user_id, None)


# ── Stop command ──────────────────────────────────────────────────────────────

@Client.on_message(filters.command("xxxstop") & filters.private)
async def xxx_stop_cmd(c: Client, u: Message):
    user_id = u.from_user.id
    if xxx_active.get(user_id):
        xxx_stop[user_id] = True
        await u.reply_text("🛑 Band ho raha hai...")
    else:
        await u.reply_text("Koi xxxtophd download nahi chal raha.")


# ── Bulk download callback ─────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex("^xxxbulk_"))
async def xxx_bulk_download(c: Client, q: CallbackQuery):
    url = q.data[8:]  # "xxxbulk_" = 8 chars
    user_id = q.from_user.id
    chat_id = q.message.chat.id

    if xxx_active.get(user_id):
        await q.answer("Pehle download complete karo!", show_alert=True)
        return

    xxx_active[user_id] = True
    xxx_stop[user_id] = False

    page_title_m = re.search(r'xxxtophd\.com/([^/?]+)', url)
    cat = page_title_m.group(1).replace("-", " ").title() if page_title_m else "xxxtophd"

    summary_msg = await q.message.edit_text(
        f"📂 <b>xxxtophd.com — {cat}</b>\n⏳ Videos collect ho rahi hain..."
    )

    success = 0
    failed = 0

    try:
        # Collect all pages
        all_videos = []
        current_url = url
        while current_url:
            videos, next_url = await get_page_videos(current_url)
            all_videos.extend(videos)
            current_url = next_url
            if len(all_videos) > 500:
                break

        total = len(all_videos)
        await summary_msg.edit_text(
            f"📂 <b>xxxtophd.com — {cat}</b>\n"
            f"🎬 Total: <b>{total} videos</b>\n"
            f"▶️ Download shuru!\n"
            f"🛑 Rokne ke liye: /xxxstop"
        )

        for i, (title, video_url) in enumerate(all_videos, 1):
            if xxx_stop.get(user_id):
                await summary_msg.edit_text(
                    f"🛑 <b>Roka gaya!</b>\n\n"
                    f"✅ Downloaded: {success}/{total}\n"
                    f"❌ Failed: {failed}"
                )
                break

            progress_msg = await c.send_message(
                chat_id,
                f"⬇️ <b>{i}/{total}</b> — <b>{title[:60]}</b>\n\n"
                f"✅ Done: {success} | ❌ Failed: {failed}"
            )

            try:
                _, embed_url, tags, duration = await extract_embed_url(video_url)
                if not embed_url:
                    raise Exception("Embed URL nahi mila")

                await run_async(yt_download, embed_url, "downloads/%(title)s.%(ext)s", progress_msg, c)

                caption = make_caption(
                    title=title, duration=duration, tags=tags,
                    category=cat, index=i, total=total,
                    site="xxxtophd.com", source_url=video_url,
                )

                await progress_msg.edit_text("📤 Upload ho raha hai...")
                ok = await send_video_file(c, chat_id, caption)
                success += 1 if ok else 0
                failed += 0 if ok else 1

            except Exception as e:
                failed += 1
                await progress_msg.edit_text(f"⚠️ Skip ({i}/{total}): <code>{str(e)[:150]}</code>")
                await asyncio.sleep(2)

            await progress_msg.delete()
            await asyncio.sleep(3)

            if i % 5 == 0 or i == total:
                try:
                    await summary_msg.edit_text(
                        f"📂 <b>xxxtophd.com — {cat}</b>\n"
                        f"📊 Progress: <b>{i}/{total}</b>\n"
                        f"✅ Downloaded: {success}\n"
                        f"❌ Failed: {failed}\n\n"
                        f"{'✅ Sab complete!' if i == total else '⏳ Chal raha hai... /xxxstop se rokein'}"
                    )
                except Exception:
                    pass

    except Exception as e:
        await summary_msg.edit_text(f"❌ Error: <code>{str(e)[:300]}</code>")
    finally:
        xxx_active.pop(user_id, None)
        xxx_stop.pop(user_id, None)
