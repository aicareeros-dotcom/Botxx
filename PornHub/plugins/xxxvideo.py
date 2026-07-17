"""
Custom scraper for xxxvideo.link
- Single video : https://xxxvideo.link/en/vu/video-name.html
- Listing page : https://xxxvideo.link/xxxx/  or  https://xxxvideo.link/en/desi/
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

BASE = "https://xxxvideo.link"
COOKIE = "_sv=1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Cookie": COOKIE,
    "Referer": BASE,
}

xv_active = {}
xv_stop = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_xxxvideo(url: str) -> bool:
    return "xxxvideo.link" in url


async def fetch(url: str) -> str:
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as c:
        r = await c.get(url)
        return r.text


def parse_duration(iso: str) -> str:
    """Convert PT14M55S → 14:55"""
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or "")
    if not m:
        return iso or "?"
    h, mn, s = m.group(1), m.group(2), m.group(3)
    parts = []
    if h: parts.append(h.zfill(2))
    parts.append((mn or "0").zfill(2))
    parts.append((s or "0").zfill(2))
    return ":".join(parts)


async def get_video_info(url: str):
    html = await fetch(url)
    title_m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    title = title_m.group(1).strip() if title_m else "Video"

    dur_m = re.search(r'"duration"\s*:\s*"([^"]+)"', html)
    duration = parse_duration(dur_m.group(1)) if dur_m else "?"

    tags_m = re.findall(r'href="/en/(?:category|tag)/[^"]+">([^<]+)</a>', html)
    tags = ", ".join(tags_m[:6]) if tags_m else ""

    mp4_m = re.search(r'(https?://[^\s"<>]+\.mp4[^\s"<>]*)', html)
    mp4_url = mp4_m.group(1) if mp4_m else None

    return title, mp4_url, tags, duration


async def get_listing_videos(url: str):
    html = await fetch(url)
    # Find video entries with title
    entries = re.findall(
        r'href="(/en/vu/[^"]+\.html)"[^>]*>\s*(?:<[^>]+>\s*)*(?:<img[^>]+alt="([^"]*)")?',
        html, re.S
    )
    # Simpler: just get hrefs and titles separately
    hrefs = re.findall(r'href="(/en/vu/[^"]+\.html)"', html)
    # Remove duplicates while keeping order
    seen = set()
    unique = []
    for h in hrefs:
        if h not in seen:
            seen.add(h)
            unique.append(h)

    # Get titles from img alt or span
    titles = re.findall(r'<(?:span|h2|h3)[^>]*class="[^"]*(?:title|name|desc)[^"]*"[^>]*>([^<]+)<', html, re.I)
    if len(titles) < len(unique):
        # fallback: derive title from URL slug
        for href in unique[len(titles):]:
            slug = href.split("/")[-1].replace(".html", "").replace("-", " ").title()
            titles.append(slug)

    results = [(titles[i] if i < len(titles) else unique[i].split("/")[-1].replace(".html","").replace("-"," ").title(),
                BASE + unique[i]) for i in range(len(unique))]

    # Next page
    next_m = re.search(r'href="([^"]+)"[^>]*>[^<]*(?:Next|next|›|>>)[^<]*</a>', html, re.I)
    next_url = None
    if next_m:
        np = next_m.group(1)
        next_url = np if np.startswith("http") else BASE + np

    return results, next_url


async def run_async(func, *args):
    return await asyncio.get_running_loop().run_in_executor(None, func, *args)


def yt_dl_direct(mp4_url: str, out_tmpl: str, msg_ref, client_ref):
    opts = {
        "outtmpl": out_tmpl,
        "format": "best",
        "quiet": True,
        "no_warnings": True,
        "http_headers": {"Cookie": COOKIE, "Referer": BASE},
        "external_downloader": "aria2c",
        "external_downloader_args": {
            "aria2c": ["-x", "16", "-s", "16", "-k", "1M"]
        },
        "progress_hooks": [lambda d: download_progress_hook(d, msg_ref, client_ref)],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([mp4_url])


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
                try: os.remove(path)
                except: pass
            return True
    return False


# ── URL filter ────────────────────────────────────────────────────────────────

def is_xv_url(flt, client, update):
    return bool(update.text and is_xxxvideo(update.text))

xv_url_filter = filters.create(is_xv_url, name="xv_url_filter")


# ── Main handler ──────────────────────────────────────────────────────────────

@Client.on_message(xv_url_filter & filters.private)
async def handle_xxxvideo(c: Client, u: Message):
    url = u.text.strip()
    user_id = u.from_user.id

    if xv_active.get(user_id):
        await u.reply_text("⚠️ Pehle se ek download chal raha hai!\n/xvstop se band karo.")
        return

    msg = await u.reply_text("🔍 xxxvideo.link check ho raha hai...")

    try:
        if "/en/vu/" in url:
            # Single video
            title, mp4_url, tags, duration = await get_video_info(url)
            if not mp4_url:
                await msg.edit_text("❌ Video URL nahi mila. Link dobara check karo.")
                return
            await msg.edit_text(
                f"📹 <b>{title}</b>\n"
                f"⏱ Duration: <code>{duration}</code>\n"
                f"🏷 Tags: {tags or 'N/A'}\n\n"
                "Download karna chahte ho?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Download", callback_data=f"xv_{url}")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
                ])
            )
        else:
            # Listing / category page
            videos, _ = await get_listing_videos(url)
            total = len(videos)
            if total == 0:
                await msg.edit_text(
                    "❌ Koi video nahi mili.\n\n"
                    "💡 Try karo:\n"
                    "<code>https://xxxvideo.link/xxxx/</code>\n"
                    "<code>https://xxxvideo.link/en/desi/</code>"
                )
                return
            slug = re.search(r'xxxvideo\.link/(?:en/)?([^/?]+)', url)
            cat = slug.group(1).replace("-", " ").title() if slug else "xxxvideo"
            await msg.edit_text(
                f"📂 <b>xxxvideo.link — {cat}</b>\n\n"
                f"🎬 Videos found: <b>{total}</b>\n\n"
                "Sabhi download karna chahte ho?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"✅ Haan, sab download karo ({total})", callback_data=f"xvbulk_{url}")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
                ])
            )
    except Exception as e:
        await msg.edit_text(f"❌ Error: <code>{str(e)[:300]}</code>")


# ── Single download callback ──────────────────────────────────────────────────

@Client.on_callback_query(filters.regex("^xv_"))
async def xv_single_dl(c: Client, q: CallbackQuery):
    video_url = q.data[3:]  # "xv_" = 3 chars
    user_id = q.from_user.id
    chat_id = q.message.chat.id

    if xv_active.get(user_id):
        await q.answer("Pehle download complete karo!", show_alert=True)
        return

    xv_active[user_id] = True
    msg = await q.message.edit_text("📥 Download shuru ho gaya...")

    try:
        title, mp4_url, tags, duration = await get_video_info(video_url)
        if not mp4_url:
            await msg.edit_text("❌ MP4 URL nahi mila.")
            return

        await run_async(yt_dl_direct, mp4_url, "downloads/%(title)s.%(ext)s", msg, c)
        caption = make_caption(
            title=title, duration=duration, tags=tags,
            site="xxxvideo.link", source_url=video_url,
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
        xv_active.pop(user_id, None)


# ── Stop ─────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("xvstop") & filters.private)
async def xv_stop_cmd(c: Client, u: Message):
    user_id = u.from_user.id
    if xv_active.get(user_id):
        xv_stop[user_id] = True
        await u.reply_text("🛑 Band ho raha hai...")
    else:
        await u.reply_text("Koi xxxvideo download nahi chal raha.")


# ── Bulk download ─────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex("^xvbulk_"))
async def xv_bulk_dl(c: Client, q: CallbackQuery):
    url = q.data[7:]  # "xvbulk_" = 7 chars
    user_id = q.from_user.id
    chat_id = q.message.chat.id

    if xv_active.get(user_id):
        await q.answer("Pehle download complete karo!", show_alert=True)
        return

    xv_active[user_id] = True
    xv_stop[user_id] = False

    slug = re.search(r'xxxvideo\.link/(?:en/)?([^/?]+)', url)
    cat = slug.group(1).replace("-", " ").title() if slug else "xxxvideo"
    summary_msg = await q.message.edit_text(f"📂 <b>xxxvideo.link — {cat}</b>\n⏳ Videos collect ho rahi hain...")

    success = failed = 0

    try:
        all_videos = []
        current_url = url
        while current_url:
            videos, next_url = await get_listing_videos(current_url)
            all_videos.extend(videos)
            current_url = next_url
            if len(all_videos) > 500:
                break

        total = len(all_videos)
        await summary_msg.edit_text(
            f"📂 <b>xxxvideo.link — {cat}</b>\n"
            f"🎬 Total: <b>{total} videos</b>\n"
            f"▶️ Download shuru!\n🛑 /xvstop se rokein"
        )

        for i, (title, video_url) in enumerate(all_videos, 1):
            if xv_stop.get(user_id):
                await summary_msg.edit_text(f"🛑 Roka gaya!\n✅ {success}/{total} | ❌ {failed}")
                break

            pmsg = await c.send_message(chat_id,
                f"⬇️ <b>{i}/{total}</b> — <b>{title[:55]}</b>\n✅ Done: {success} | ❌ Failed: {failed}")

            try:
                _, mp4_url, tags, duration = await get_video_info(video_url)
                if not mp4_url:
                    raise Exception("MP4 URL nahi mila")
                await run_async(yt_dl_direct, mp4_url, "downloads/%(title)s.%(ext)s", pmsg, c)
                caption = make_caption(
                    title=title, duration=duration, tags=tags,
                    category=cat, index=i, total=total,
                    site="xxxvideo.link", source_url=video_url,
                )
                await pmsg.edit_text("📤 Upload ho raha hai...")
                ok = await send_video_file(c, chat_id, caption)
                success += 1 if ok else 0
                failed += 0 if ok else 1
            except Exception as e:
                failed += 1
                await pmsg.edit_text(f"⚠️ Skip {i}/{total}: <code>{str(e)[:120]}</code>")
                await asyncio.sleep(2)

            await pmsg.delete()
            await asyncio.sleep(3)

            if i % 5 == 0 or i == total:
                try:
                    await summary_msg.edit_text(
                        f"📂 <b>xxxvideo.link — {cat}</b>\n"
                        f"📊 <b>{i}/{total}</b>\n✅ {success} | ❌ {failed}\n"
                        f"{'✅ Complete!' if i == total else '⏳ /xvstop se rokein'}"
                    )
                except: pass

    except Exception as e:
        await summary_msg.edit_text(f"❌ Error: <code>{str(e)[:300]}</code>")
    finally:
        xv_active.pop(user_id, None)
        xv_stop.pop(user_id, None)
