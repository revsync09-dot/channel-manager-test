import os
import threading
import time
from collections import defaultdict
from typing import Any, Dict, List

import discord

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except Exception:  
    FileSystemEventHandler = None
    Observer = None

LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID", "1447010974652694750")
EMBED_COLOR = 0x22C55E
DEBOUNCE_SECONDS = 7
IGNORED_PATTERNS = ("node_modules", ".git", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "logs")


def start_change_logger(client: discord.Client, root_dir: str | None = None) -> Any:
    if not Observer or not FileSystemEventHandler:
        return None

    root = root_dir or os.getcwd()
    queue: List[Dict[str, str]] = []
    lock = threading.Lock()
    timer: list[Any] = [None]

    class Handler(FileSystemEventHandler):
        def on_any_event(self, event):
            if event.is_directory:
                return
            if any(part in event.src_path for part in IGNORED_PATTERNS):
                return
            rel = os.path.relpath(event.src_path, root).replace("\\", "/")
            with lock:
                queue.append({"type": event.event_type, "file": rel})
                if timer[0] is None:
                    timer[0] = threading.Timer(DEBOUNCE_SECONDS, flush)
                    timer[0].start()

    def summarize(events: List[Dict[str, str]]):
        counts = {"add": 0, "change": 0, "unlink": 0, "ext": defaultdict(int), "files": {"add": [], "change": [], "unlink": []}}
        for ev in events:
            key = "change"
            if ev["type"] in ("created", "added"):
                key = "add"
            elif ev["type"] in ("deleted", "removed"):
                key = "unlink"
            counts[key] += 1
            ext = os.path.splitext(ev["file"])[1].replace(".", "").lower() or "misc"
            counts["ext"][ext] += 1
            counts["files"][key].append(ev["file"])
        total = counts["add"] + counts["change"] + counts["unlink"]
        return counts, total

    async def send_embed(events: List[Dict[str, str]]):
        channel = None
        if LOG_CHANNEL_ID.isdigit():
            channel = client.get_channel(int(LOG_CHANNEL_ID))
            if not channel:
                try:
                    channel = await client.fetch_channel(int(LOG_CHANNEL_ID))
                except Exception:
                    channel = None
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        counts, total = summarize(events)
        actions = []
        if counts["add"]:
            actions.append(f"added {counts['add']}")
        if counts["change"]:
            actions.append(f"updated {counts['change']}")
        if counts["unlink"]:
            actions.append(f"removed {counts['unlink']}")
        headline = f"Workspace touched {total} item(s) ({', '.join(actions)})." if total else "No recent changes logged."
        top_exts = sorted(counts["ext"].items(), key=lambda x: x[1], reverse=True)[:3]
        highlights = ", ".join(f"{label}: {num}" for label, num in top_exts) if top_exts else ""

        def format_list(items: List[str]) -> str:
            if not items:
                return "-"
            sliced = items[:8]
            more = f"\n+{len(items) - 8} more" if len(items) > 8 else ""
            return "\n".join(f"- `{name}`" for name in sliced) + more

        embed = discord.Embed(
            title="Workspace update",
            description="\n".join(filter(None, [headline, f"Highlights: {highlights}" if highlights else ""])),
            color=EMBED_COLOR,
        )
        embed.add_field(name="Added", value=format_list(counts["files"]["add"]), inline=False)
        embed.add_field(name="Updated", value=format_list(counts["files"]["change"]), inline=False)
        embed.add_field(name="Removed", value=format_list(counts["files"]["unlink"]), inline=False)
        embed.set_footer(text="Automated change log • Channel Manager")
        embed.timestamp = discord.utils.utcnow()
        try:
            await channel.send(embed=embed)
        except Exception:
            return

    def flush():
        with lock:
            events = list(queue)
            queue.clear()
            timer[0] = None
        if not events:
            return
        try:
            loop = client.loop
            loop.create_task(send_embed(events))
        except Exception:
            return

    observer = Observer()
    observer.schedule(Handler(), root, recursive=True)
    observer.daemon = True
    observer.start()
    return observer


def stop_change_logger(observer: Any) -> None:
    if observer:
        try:
            observer.stop()
            observer.join(timeout=2)
        except Exception:
            pass
