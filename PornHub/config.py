import os
from typing import List

API_ID: int = int(os.environ.get("API_ID", "0"))
API_HASH: str = os.environ.get("API_HASH", "")
TOKEN: str = os.environ.get("BOT_TOKEN", "")

log_chat: int = int(os.environ.get("LOG_CHAT", "0"))
sub_chat: str = os.environ.get("SUB_CHAT", "")
sudoers: List[int] = [
    int(x.strip()) for x in os.environ.get("SUDOERS", "0").split(",") if x.strip()
]
prefixs: List[str] = ["/", "!", ".", "$", "-"]
