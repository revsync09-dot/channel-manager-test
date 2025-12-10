import random
import re
import time
from typing import Any, Dict, List

import discord


def parse_text_structure(raw: str) -> Dict[str, Any]:
    lines = [normalize_line(line.rstrip()) for line in raw.splitlines()]
    lines = [line for line in lines if line]

    template: Dict[str, Any] = {"categories": [], "roles": []}
    current_category: Dict[str, Any] | None = None

    for line in lines:
        if is_role_line(line):
            role = build_role_from_line(line)
            if role:
                template["roles"].append(role)
            continue

        trimmed = normalize_line(line.strip())
        is_channel = looks_like_channel(trimmed)
        is_category = is_category_line(trimmed) or (not is_channel and not trimmed.startswith("-"))

        if is_category:
            current_category = {"name": clean_category_name(trimmed), "channels": []}
            template["categories"].append(current_category)
            continue

        if current_category is None:
            current_category = {"name": "General", "channels": []}
            template["categories"].append(current_category)

        channel = build_channel_from_line(trimmed)
        current_category["channels"].append(channel)

    total_channels = sum(len(cat["channels"]) for cat in template["categories"])
    template["summary"] = f"{len(template['categories'])} categories / {total_channels} channels"
    return template


def looks_like_channel(line: str) -> bool:
    normalized = normalize_line(line)
    has_pipe = "|" in normalized
    has_hash = bool(re.search(r"#\S+", normalized))
    has_type = bool(re.search(r"type:\s*(text|voice)", normalized, re.IGNORECASE))
    has_voice_word = bool(re.search(r"\bvoice\b", normalized, re.IGNORECASE))
    return has_pipe or has_hash or has_type or has_voice_word


def build_channel_from_line(line: str) -> Dict[str, Any]:
    normalized = normalize_line(line)
    is_voice = bool(re.search(r"type:\s*voice", normalized, re.IGNORECASE) or re.search(r"\bvoice\b", normalized, re.IGNORECASE))
    without_prefix = re.sub(r"^[-\s|]+", "", normalized)
    hash_match = re.search(r"#([\w-]+)", normalized)

    prefix_before_hash = ""
    if hash_match and hash_match.start() is not None:
        prefix_before_hash = normalized[: hash_match.start()]
        prefix_before_hash = re.sub(r"[|]", " ", prefix_before_hash).strip()

    base_name = hash_match.group(1) if hash_match else re.sub(r"^#?", "", without_prefix.split("|")[0]).strip()
    if not base_name:
        base_name = without_prefix.split()[0] if without_prefix else "channel"

    name_part = f"{prefix_before_hash}-{base_name}" if prefix_before_hash else base_name
    safe_name = slugify_preserve(name_part or base_name)
    topic = extract_topic(normalized) or suggest_description(safe_name, is_voice)
    perms = extract_permissions(normalized)
    overwrites = None
    if perms:
        allow_bits = permissions_to_bitfield(perms).value
        overwrites = [
            {
                "roleRefId": "everyone",
                "allow": str(allow_bits),
                "deny": "0",
            }
        ]

    return {
        "name": safe_name or "channel",
        "type": "voice" if is_voice else "text",
        "topic": topic,
        "private": False,
        "overwrites": overwrites,
    }


def clean_category_name(name: str) -> str:
    normalized = normalize_line(re.sub(r"\(category\)", "", name, flags=re.IGNORECASE))
    no_pipes = re.sub(r"[|#]", " ", normalized)
    clean = re.sub(r"\s{2,}", " ", no_pipes).strip()
    return clean or "Category"


def slugify_preserve(text: str) -> str:
    if not text:
        return "channel"
    normalized = normalize_line(text).strip()
    spaced = re.sub(r"[|]", " ", normalized)
    spaced = re.sub(r"\s+", " ", spaced)
    safe = re.sub(r"\s+", "-", spaced)
    safe = re.sub(r"-+", "-", safe).strip("-")
    return safe.lower() or "channel"


def suggest_description(name: str, is_voice: bool) -> str:
    key = name.lower()
    if "welcome" in key:
        return "Welcome channel with server info."
    if "rules" in key:
        return "Server rules."
    if "announce" in key or "news" in key:
        return "Announcements."
    if "chat" in key or "general" in key:
        return "General chat."
    if "support" in key:
        return "Support channel."
    if is_voice:
        return "A voice channel for talking."
    return "Auto generated description."


def is_role_line(line: str) -> bool:
    return bool(re.search(r"color:\s*#", line, re.IGNORECASE))


def build_role_from_line(line: str) -> Dict[str, Any] | None:
    color_match = re.search(r"color:\s*(#[0-9a-fA-F]{6})", line, re.IGNORECASE)
    if not color_match:
        return None
    color = int(color_match.group(1).replace("#", ""), 16)
    perms = extract_permissions(line)
    name_part = line.replace(color_match.group(0), "")
    name_part = re.sub(r"Permissions:\s*\[[^\]]*\]", "", name_part, flags=re.IGNORECASE).strip()
    clean_name = re.sub(r"\s{2,}", " ", name_part).strip()
    if not clean_name:
        return None

    unique_ref = f"role-{int(time.time())}-{random.randint(1000,9999)}"
    return {
        "refId": unique_ref,
        "name": clean_name,
        "color": color,
        "hoist": False,
        "mentionable": True,
        "permissions": str(permissions_to_bitfield(perms).value),
        "isEveryone": False,
    }


def extract_permissions(line: str) -> List[str]:
    match = re.search(r"permissions:\s*\[([^\]]*)\]", line, re.IGNORECASE)
    if not match:
        return []
    return [p.strip() for p in match.group(1).split(",") if p.strip()]


def permissions_to_bitfield(perms: List[str]) -> discord.Permissions:
    mapped: List[str] = []
    for perm in perms:
        norm = re.sub(r"\(.*?\)", "", perm).strip().lower()
        match norm:
            case "administrator" | "manage server":
                mapped.append("administrator")
            case "manage roles":
                mapped.append("manage_roles")
            case "manage channels":
                mapped.append("manage_channels")
            case "manage webhooks":
                mapped.append("manage_webhooks")
            case "manage emojis" | "manage emojis and stickers":
                mapped.append("manage_emojis")
            case "ban members":
                mapped.append("ban_members")
            case "kick members":
                mapped.append("kick_members")
            case "view audit log":
                mapped.append("view_audit_log")
            case "manage messages":
                mapped.append("manage_messages")
            case "manage threads":
                mapped.append("manage_threads")
            case "mention everyone":
                mapped.append("mention_everyone")
            case "timeout members" | "moderate members" | "mute members":
                mapped.append("moderate_members")
            case "priority speaker":
                mapped.append("priority_speaker")
            case "send messages":
                mapped.append("send_messages")
            case "read message history":
                mapped.append("read_message_history")
            case "view channel" | "read channels":
                mapped.append("view_channel")
            case "connect":
                mapped.append("connect")
            case "speak":
                mapped.append("speak")
            case "stream":
                mapped.append("stream")
            case "use voice activity":
                mapped.append("use_voice_activation")
            case "embed links":
                mapped.append("embed_links")
            case "attach files":
                mapped.append("attach_files")
            case "use external emojis":
                mapped.append("use_external_emojis")
            case "use external stickers":
                mapped.append("use_external_stickers")
            case "use application commands":
                mapped.append("use_application_commands")
            case "add reactions":
                mapped.append("add_reactions")
            case "manage events":
                mapped.append("manage_events")
            case "change nickname":
                mapped.append("change_nickname")
            case "move members":
                mapped.append("move_members")
            case _:
                continue
    return discord.Permissions(**{name: True for name in mapped})


def normalize_line(text: str) -> str:
    return (
        text.replace("\ufeff", "")
        .replace("\u200b", "")
        .replace("\u00a0", " ")
        .replace(":", " :")
        .strip()
    )


def extract_topic(line: str) -> str | None:
    match = re.search(r"-\s+(.+)", line)
    return match.group(1).strip() if match else None


def is_category_line(line: str) -> bool:
    return bool(re.search(r"\(category\)", line, re.IGNORECASE))
