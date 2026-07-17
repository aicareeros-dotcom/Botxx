import os
import asyncio
import yt_dlp

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)
from pyrogram.errors import ChatAdminRequired, UserNotParticipant, ChatWriteForbidden, FloodWait

from PornHub.config import log_chat, sub_chat
from PornHub.plugins.function import download_progress_hook
from PornHub.plugins.caption import make_caption

if not os.path.exists("downloads"):
    os.makedirs("downloads")

# user_id -> True means stop requested
active = {}
stop_flags = {}


async def run_async(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args, **kwargs)


CUSTOM_SITES = ["xxxtophd.com", "xxxvideo.link"]

def is_url(filter, client, update):
    if update.text and ("http://" in update.text or "https://" in update.text):
        # Custom site plugins handle these separately
        for site in CUSTOM_SITES:
            if site in update.text:
                return False
        return True
    return False

url_filter = filters.create(is_url, name="url_filter")


# ── Subscribe check ──────────────────────────────────────────────────────────

@Client.on_message(filters.incoming & filters.private, group=-1)
@Client.on_edited_message(filters.incoming & filters.private, group=-1)
async def subscribe_channel(c: Client, u: Message):
    if not sub_chat:
        return
    try:
        try:
            await c.get_chat_member(sub_chat, u.from_user.id)
        except UserNotParticipant:
            join_url = (
                "https://t.me/" + sub_chat
                if sub_chat.isalpha()
                else (await c.get_chat(sub_chat)).invite_link
            )
            try:
                await u.reply_text(
                    f"Hi {u.from_user.first_name}!\n\nBot use karne ke liye pehle channel join karo!",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("• Join Channel •", url=join_url)]]
                    ),
                )
                await u.stop_propagation()
            except ChatWriteForbidden:
                pass
    except ChatAdminRequired:
        await c.send_message(log_chat, "Channel admin rights nahi hain!")


# ── URL handler: detect single video vs playlist/category ───────────────────

@Client.on_message(url_filter & filters.private)
async def handle_url(c: Client, u: Message):
    url = u.text.strip()
    user_id = u.from_user.id

    if user_id in active and active[user_id]:
        await u.reply_text("⚠️ Pehle se ek download chal raha hai!\n/stop se band karo.")
        return

    msg = await u.reply_text("🔍 Link check ho raha hai...")

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "ignoreerrors": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await run_async(ydl.extract_info, url, False)

        if not info:
            await msg.edit_text("❌ Kuch nahi mila is link mein.")
            return

        # ── Playlist / Category ──────────────────────────────────────────
        if info.get("_type") in ("playlist", "multi_video") or info.get("entries"):
            entries = list(info.get("entries") or [])
            entries = [e for e in entries if e]  # filter None
            total = len(entries)

            if total == 0:
                await msg.edit_text("❌ Is category mein koi video nahi mili.")
                return

            title = info.get("title") or info.get("webpage_url_domain") or "Category"
            await msg.edit_text(
                f"📂 <b>{title}</b>\n\n"
                f"🎬 Total videos: <b>{total}</b>\n\n"
                "Sabhi videos download karna chahte ho?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"✅ Haan, sab download karo ({total} videos)", callback_data=f"bulk_{url}")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
                ])
            )

        # ── Single Video ─────────────────────────────────────────────────
        else:
            video_title = info.get("title", "Video")
            duration = info.get("duration") or 0
            mins, secs = divmod(int(duration), 60)
            uploader = info.get("uploader") or info.get("channel") or "Unknown"

            await msg.edit_text(
                f"📹 <b>{video_title}</b>\n"
                f"👤 Uploader: <code>{uploader}</code>\n"
                f"⏱ Duration: <code>{mins}:{secs:02d}</code>\n\n"
                "Download karna chahte ho?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Download", callback_data=f"dl_{url}")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
                ])
            )

    except yt_dlp.utils.DownloadError as e:
        err = str(e)
        if "Unsupported URL" in err:
            await msg.edit_text(
                "❌ <b>Yeh link supported nahi hai!</b>\n\n"
                "📌 <b>Kya check karo:</b>\n"
                "• Homepage mat bhejo, <b>specific video ka link</b> bhejo\n"
                "• Ya category page ka link bhejo\n"
                "• Supported: xnxx.com, xvideos.com, xhamster.com, pornhub.com, etc.\n\n"
                "✅ <b>Example:</b>\n"
                "<code>https://www.xnxx.com/video-abc123/title</code>"
            )
        else:
            await msg.edit_text(f"❌ <b>Error:</b>\n<code>{err[:300]}</code>")
    except Exception as e:
        await msg.edit_text(f"❌ Kuch galat hua:\n<code>{str(e)[:300]}</code>")


# ── Cancel ───────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex("^cancel$"))
async def cancel_cb(c: Client, q: CallbackQuery):
    await q.message.edit_text("❌ Cancel kar diya!")


# ── Stop command ─────────────────────────────────────────────────────────────

@Client.on_message(filters.command("stop") & filters.private)
async def stop_download(c: Client, u: Message):
    user_id = u.from_user.id
    if user_id in active and active[user_id]:
        stop_flags[user_id] = True
        await u.reply_text("🛑 Download band ho raha hai... current video ke baad rukega.")
    else:
        await u.reply_text("Koi download chal nahi raha.")


# ── Single video download ─────────────────────────────────────────────────────

async def download_and_send(c: Client, chat_id: int, url: str, msg, caption: str, user_id: int):
    """Download one video and send it. Returns True on success."""
    output_template = "downloads/%(title)s.%(ext)s"
    ydl_opts = {
        "outtmpl": output_template,
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
        "progress_hooks": [lambda d: download_progress_hook(d, msg, c)],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await run_async(ydl.download, [url])

        for file in os.listdir("downloads"):
            if file.endswith((".mp4", ".mkv", ".webm")):
                filepath = os.path.join("downloads", file)
                await msg.edit_text("📤 Upload ho raha hai...")
                try:
                    await c.send_video(
                        chat_id,
                        filepath,
                        caption=caption,
                        supports_streaming=True,
                    )
                except FloodWait as e:
                    await asyncio.sleep(e.value + 2)
                    await c.send_video(chat_id, filepath, caption=caption, supports_streaming=True)
                finally:
                    os.remove(filepath)
                return True

        return False

    except Exception as e:
        await msg.edit_text(f"⚠️ Skip: <code>{str(e)[:200]}</code>")
        return False


# ── Bulk (category) download ──────────────────────────────────────────────────

@Client.on_callback_query(filters.regex("^bulk_"))
async def bulk_download(c: Client, q: CallbackQuery):
    url = q.data[5:]
    user_id = q.from_user.id
    chat_id = q.message.chat.id

    if user_id in active and active[user_id]:
        await q.answer("Pehle download complete karo!", show_alert=True)
        return

    active[user_id] = True
    stop_flags[user_id] = False

    summary_msg = await q.message.edit_text("⏳ Videos ki list la raha hun...")

    try:
        # Get full list with actual URLs
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "ignoreerrors": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await run_async(ydl.extract_info, url, False)

        entries = [e for e in (info.get("entries") or []) if e]
        total = len(entries)
        category_title = info.get("title") or "Category"

        await summary_msg.edit_text(
            f"📂 <b>{category_title}</b>\n"
            f"🎬 Total: <b>{total} videos</b>\n\n"
            f"▶️ Download shuru ho gaya!\n"
            f"🛑 Rokne ke liye: /stop"
        )

        success_count = 0
        fail_count = 0

        for i, entry in enumerate(entries, 1):
            # Check stop flag
            if stop_flags.get(user_id):
                await summary_msg.edit_text(
                    f"🛑 <b>Download roka gaya!</b>\n\n"
                    f"✅ Downloaded: {success_count}/{total}\n"
                    f"❌ Failed: {fail_count}"
                )
                break

            video_url = entry.get("url") or entry.get("webpage_url") or f"https://www.youtube.com/watch?v={entry.get('id','')}"
            video_title = entry.get("title") or f"Video {i}"
            uploader = entry.get("uploader") or entry.get("channel") or "Unknown"
            duration = entry.get("duration") or 0
            mins, secs = divmod(int(duration), 60)

            # Progress message
            progress_msg = await c.send_message(
                chat_id,
                f"⬇️ <b>Downloading {i}/{total}</b>\n\n"
                f"📹 <b>{video_title}</b>\n"
                f"👤 {uploader}\n"
                f"⏱ {mins}:{secs:02d}\n\n"
                f"✅ Done: {success_count} | ❌ Failed: {fail_count}"
            )

            caption = (
                f"📹 <b>{video_title}</b>\n"
                f"👤 <b>Uploader:</b> {uploader}\n"
                f"📂 <b>Category:</b> {category_title}\n"
                f"🔢 <b>Video:</b> {i}/{total}\n"
                f"🔗 <b>Source:</b> {video_url}"
            )

            ok = await download_and_send(c, chat_id, video_url, progress_msg, caption, user_id)
            if ok:
                success_count += 1
            else:
                fail_count += 1

            await progress_msg.delete()

            # Small delay between downloads to avoid flood
            await asyncio.sleep(3)

            # Update summary every 5 videos
            if i % 5 == 0 or i == total:
                try:
                    await summary_msg.edit_text(
                        f"📂 <b>{category_title}</b>\n"
                        f"📊 Progress: <b>{i}/{total}</b>\n"
                        f"✅ Downloaded: {success_count}\n"
                        f"❌ Failed: {fail_count}\n\n"
                        f"{'✅ Sab complete!' if i == total else '⏳ Chal raha hai... /stop se rokein'}"
                    )
                except Exception:
                    pass

    except Exception as e:
        await summary_msg.edit_text(f"❌ Error: <code>{str(e)[:300]}</code>")
    finally:
        active.pop(user_id, None)
        stop_flags.pop(user_id, None)


# ── Single video download callback ───────────────────────────────────────────

@Client.on_callback_query(filters.regex("^dl_"))
async def single_download(c: Client, q: CallbackQuery):
    url = q.data[3:]
    user_id = q.from_user.id
    chat_id = q.message.chat.id

    if user_id in active and active[user_id]:
        await q.answer("Pehle download complete karo!", show_alert=True)
        return

    active[user_id] = True
    msg = await q.message.edit_text("📥 Download shuru ho gaya...")

    try:
        # Get info for caption
        ydl_info_opts = {"quiet": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(ydl_info_opts) as ydl:
            info = await run_async(ydl.extract_info, url, False)

        video_title = info.get("title", "Video")
        uploader = info.get("uploader") or info.get("channel") or "Unknown"
        duration = info.get("duration") or 0
        mins, secs = divmod(int(duration), 60)

        caption = make_caption(
            title=video_title, uploader=uploader,
            duration=f"{mins}:{secs:02d}", source_url=url,
        )

        ok = await download_and_send(c, chat_id, url, msg, caption, user_id)
        if not ok:
            await msg.edit_text("❌ File download nahi hui.")

    except Exception as e:
        await msg.edit_text(f"❌ Error:\n<code>{str(e)[:300]}</code>")
    finally:
        active.pop(user_id, None)
        await msg.delete()
