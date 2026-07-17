"""
Beautiful caption formatter for all downloaded videos.
Uses Telegram HTML formatting for rich display.
"""


def make_caption(
    title: str,
    duration: str = "",
    uploader: str = "",
    tags: str = "",
    category: str = "",
    index: int = 0,
    total: int = 0,
    source_url: str = "",
    site: str = "",
) -> str:
    lines = []

    # ── Title ─────────────────────────────────────────────────────────
    lines.append(f"╔══《 🎬 <b>VIDEO INFO</b> 》══╗")
    lines.append(f"")
    lines.append(f"📌 <b>Title:</b>")
    lines.append(f"┃  <i>{title}</i>")
    lines.append(f"")

    # ── Details ───────────────────────────────────────────────────────
    if uploader:
        lines.append(f"👤 <b>Uploader :</b>  <code>{uploader}</code>")
    if duration:
        lines.append(f"⏱ <b>Duration  :</b>  <code>{duration}</code>")
    if category:
        lines.append(f"📂 <b>Category  :</b>  <code>{category}</code>")
    if tags:
        lines.append(f"🏷 <b>Tags      :</b>  {tags}")
    if index and total:
        bar = progress_bar(index, total)
        lines.append(f"🔢 <b>Video     :</b>  <code>{index}/{total}</code>  {bar}")

    # ── Source ────────────────────────────────────────────────────────
    lines.append(f"")
    if site:
        lines.append(f"🌐 <b>Site:</b> <code>{site}</code>")
    if source_url:
        short = source_url[:60] + "..." if len(source_url) > 60 else source_url
        lines.append(f"🔗 <a href='{source_url}'>Source Link</a>")

    lines.append(f"")
    lines.append(f"╚══《 🤖 <b>@X_gender_bot</b> 》══╝")

    return "\n".join(lines)


def progress_bar(current: int, total: int, length: int = 8) -> str:
    if total == 0:
        return ""
    filled = int(length * current / total)
    bar = "█" * filled + "░" * (length - filled)
    pct = int(100 * current / total)
    return f"[{bar}] {pct}%"


def make_download_progress(title: str, current: str, total_size: str, speed: str, eta: str, percent: str) -> str:
    return (
        f"╔══《 📥 <b>DOWNLOADING</b> 》══╗\n"
        f"\n"
        f"🎬 <b>{title[:50]}</b>\n"
        f"\n"
        f"📦 <b>Size    :</b>  <code>{total_size}</code>\n"
        f"⚡ <b>Speed   :</b>  <code>{speed}</code>\n"
        f"⏳ <b>ETA     :</b>  <code>{eta}</code>\n"
        f"📊 <b>Done    :</b>  <code>{current}</code> / <code>{total_size}</code>\n"
        f"\n"
        f"╚══《 🤖 @X_gender_bot 》══╝"
    )
