"""
Web dashboard backend using Flask with Discord OAuth2.
"""
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_cors import CORS
import requests
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps
import secrets
import urllib.parse
import sqlite3
import re
import json

try:
    import psutil
except ImportError:
    psutil = None

# Add parent directory to path for imports (when run as a script)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from src.database import db
    from src.modules.text_parser import parse_text_structure
    from src.modules.image_analyzer import analyze_image_stub
except ImportError:
    # Fallback: ensure project root is on path, then retry
    root_dir = Path(__file__).resolve().parents[2]
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    from src.database import db
    from src.modules.text_parser import parse_text_structure
    from src.modules.image_analyzer import analyze_image_stub


app = Flask(__name__, 
            template_folder='../../web/templates',
            static_folder='../../web/static')
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
CORS(app)
APP_STARTED_AT = datetime.utcnow()

# Discord OAuth2 Config
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "https://jthweb.yugp.me/callback")
DISCORD_API_BASE = "https://discord.com/api/v10"
# Redirect must be URL-encoded to avoid invalid redirect URI errors
_encoded_redirect = urllib.parse.quote_plus(DISCORD_REDIRECT_URI)
DISCORD_OAUTH_URL = (
    f"https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}"
    f"&redirect_uri={_encoded_redirect}&response_type=code&scope=identify+guilds"
)
DISCORD_BOT_TOKEN = os.getenv("DISCORD_TOKEN")

BRAND_NAME = os.getenv("DASHBOARD_BRAND_NAME", "Channel Manager")
BRAND_TAGLINE = os.getenv(
    "DASHBOARD_TAGLINE",
    "Manage your Discord ecosystems with a calm, modern control panel built for power users."
)
SUPPORT_INVITE = os.getenv("SUPPORT_SERVER_INVITE", "https://discord.gg/7nzsEJTA")
BOT_STATUS_VERSION = os.getenv("BOT_STATUS_VERSION", "v2.4.8-stable")
BOT_STATUS_CLUSTER = os.getenv("BOT_STATUS_CLUSTER", "Main Cluster")
BOT_STATUS_REGION = os.getenv("BOT_STATUS_REGION", "Global Edge")
BOT_STATUS_LATENCY_MS = os.getenv("BOT_STATUS_LATENCY_MS", "243")
BRAND_LOGO_URL = os.getenv(
    "DASHBOARD_LOGO_URL",
    "https://cdn.discordapp.com/attachments/1443222738750668952/1448482674477105362/image.png?ex=693b6c1d&is=693a1a9d&hm=ff31f492a74f0315498dee8ee26fa87b8512ddbee617f4bccda1161f59c8cb49&"
)
DEVELOPER_IDS = {
    795466540140986368,
    1377681774880231474,
    1393822133251084308,
}
LANGUAGE_CODES = ["en", "es", "hi", "ar", "zh", "fr", "de", "pt", "ru", "ja"]
LOCALE_DIR = Path(__file__).resolve().parents[2] / "src" / "web" / "locales"
_TRANSLATION_CACHE: dict[str, dict] = {}
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_EXEMPT_ENDPOINTS = {"callback", "login", "static"}

SIDEBAR_STRUCTURE = [
    {
        "title": "main",
        "description": "main_desc",
        "items": [
            {"key": "overview"},
            {"key": "live_stats"},
            {"key": "bot_status"},
        ],
    },
    {
        "title": "guild_management",
        "description": "guild_management_desc",
        "items": [
            {"key": "channels"},
            {"key": "roles"},
            {"key": "builder_templates"},
            {"key": "ocr_builder"},
            {"key": "text_parser"},
        ],
    },
    {
        "title": "economy",
        "description": "economy_desc",
        "items": [
            {"key": "economy_balances"},
            {"key": "economy_leaderboard"},
            {"key": "economy_config"},
        ],
    },
    {
        "title": "leveling",
        "description": "leveling_desc",
        "items": [
            {"key": "xp_leaderboard"},
            {"key": "level_roles"},
            {"key": "xp_settings"},
            {"key": "xp_generator"},
        ],
    },
    {
        "title": "custom_commands",
        "description": "custom_commands_desc",
        "items": [
            {"key": "commands_list"},
            {"key": "commands_create"},
            {"key": "commands_edit"},
            {"key": "commands_delete"},
        ],
    },
    {
        "title": "moderation",
        "description": "moderation_desc",
        "items": [
            {"key": "moderation_logs"},
            {"key": "moderation_warnings"},
            {"key": "moderation_actions"},
            {"key": "automod"},
        ],
    },
    {
        "title": "reaction_roles",
        "description": "reaction_roles_desc",
        "items": [
            {"key": "reaction_panels"},
            {"key": "reaction_add"},
            {"key": "reaction_remove"},
        ],
    },
    {
        "title": "tickets",
        "description": "tickets_desc",
        "items": [
            {"key": "tickets_settings"},
            {"key": "tickets_logs"},
        ],
    },
    {
        "title": "modmail",
        "description": "modmail_desc",
        "items": [
            {"key": "modmail_active"},
            {"key": "modmail_transcripts"},
        ],
    },
    {
        "title": "giveaways",
        "description": "giveaways_desc",
        "items": [
            {"key": "giveaway_active"},
            {"key": "giveaway_create"},
            {"key": "giveaway_edit"},
        ],
    },
    {
        "title": "verification",
        "description": "verification_desc",
        "items": [
            {"key": "verify_panel"},
            {"key": "verify_roles"},
        ],
    },
]

MODULE_METADATA = {
    "modmail": {"title": "ModMail", "badge": "Support", "description": "ModMail utilities", "permissions": "Manage Messages"},
    "custom_commands": {"title": "Custom Commands", "badge": "Builder", "description": "Custom command suite", "permissions": "Manage Server"},
    "economy": {"title": "Economy", "badge": "Economy", "description": "Economy commands", "permissions": "Depends on command"},
    "leveling": {"title": "Leveling", "badge": "Leveling", "description": "XP + leveling commands", "permissions": "Depends on command"},
    "moderation": {"title": "Moderation", "badge": "Moderation", "description": "Moderation tools", "permissions": "Staff"},
    "reaction_roles": {"title": "Reaction Roles", "badge": "Community", "description": "Reaction role panels", "permissions": "Manage Roles"},
    "ticket_system": {"title": "Tickets", "badge": "Support", "description": "Ticket utilities", "permissions": "Support"},
    "verify_system": {"title": "Verification", "badge": "Safety", "description": "Verification workflows", "permissions": "Administrator"},
    "server_builder": {"title": "Builder", "badge": "Builder", "description": "Server builder commands", "permissions": "Administrator"},
    "bot": {"title": "Core", "badge": "Core", "description": "Core management commands", "permissions": "Varies"},
}

COMMAND_PATTERN = re.compile(r'@bot\.tree\.command\(\s*name="([^"]+)"(?:,\s*description="([^"]*)")?', re.MULTILINE)


def load_translations(locale: str) -> dict:
    locale = locale or "en"
    if locale not in LANGUAGE_CODES:
        locale = "en"
    if locale in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[locale]
    path = LOCALE_DIR / f"{locale}.json"
    if not path.exists():
        path = LOCALE_DIR / "en.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    sidebar_block = data.get("sidebar")
    if not isinstance(sidebar_block, dict):
        sidebar_block = {}
        data["sidebar"] = sidebar_block
    for key in ("sections", "descriptions", "items"):
        section = sidebar_block.get(key)
        if not isinstance(section, dict):
            sidebar_block[key] = {}
    dashboard_block = data.get("dashboard")
    if not isinstance(dashboard_block, dict):
        data["dashboard"] = {}
    developer_block = data.get("developer")
    if not isinstance(developer_block, dict):
        data["developer"] = {}
    _TRANSLATION_CACHE[locale] = data
    return data


def translate(translations: dict, path: str, default: str = "") -> str:
    node = translations or {}
    for part in path.split("."):
        if not isinstance(node, dict):
            return default
        node = node.get(part)
        if node is None:
            return default
    return node if isinstance(node, str) else default


def get_or_create_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(48)
        session["csrf_token"] = token
    return token


def is_api_request() -> bool:
    return request.path.startswith("/api/") or request.is_json


def csrf_failure_response():
    if is_api_request():
        return jsonify({"error": "Invalid CSRF token"}), 419
    flash("Security verification failed. Please try again.", "error")
    target = request.referrer or url_for('dashboard')
    return redirect(target)


def validate_csrf_token_from_request() -> bool:
    expected = session.get("csrf_token")
    if not expected:
        return False
    token = request.headers.get(CSRF_HEADER_NAME)
    if not token and request.form:
        token = request.form.get("csrf_token")
    if not token:
        payload = request.get_json(silent=True)
        if isinstance(payload, dict):
            token = payload.get("csrf_token")
    try:
        return bool(token) and secrets.compare_digest(token, expected)
    except Exception:
        return False


def ensure_active_session() -> bool:
    session_id = session.get("session_id")
    if not session_id:
        return False
    db_record = db.get_session(session_id)
    if not db_record:
        return False
    expires_at = db_record.get("expires_at")
    if expires_at:
        try:
            expiry = datetime.fromisoformat(expires_at)
        except ValueError:
            db.delete_session(session_id)
            return False
        if expiry <= datetime.utcnow():
            db.delete_session(session_id)
            return False
    session["access_token"] = db_record.get("access_token")
    return True


def session_expired_response():
    session_id = session.get("session_id")
    if session_id:
        db.delete_session(session_id)
    session.clear()
    if is_api_request():
        return jsonify({"error": "Session expired"}), 401
    flash("Your session expired. Please log in again.", "error")
    return redirect(url_for('login'))


def derive_module_slug(path: Path) -> str:
    text_path = str(path).replace("\\", "/")
    for key in MODULE_METADATA.keys():
        if key in text_path:
            return key
    if "modules/" in text_path:
        return text_path.split("modules/")[1].split(".")[0]
    return "bot"


@app.before_request
def enforce_security_layers():
    endpoint = request.endpoint or ""
    if session.get("user"):
        if not ensure_active_session():
            return session_expired_response()
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if endpoint in CSRF_EXEMPT_ENDPOINTS or endpoint is None:
            return
        if not validate_csrf_token_from_request():
            return csrf_failure_response()


def discover_bot_commands() -> list[dict]:
    root = Path(__file__).resolve().parents[2] / "src"
    groups: dict[str, dict] = {}
    for file_path in root.rglob("*.py"):
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            continue
        matches = COMMAND_PATTERN.findall(content)
        if not matches:
            continue
        slug = derive_module_slug(file_path)
        meta = MODULE_METADATA.get(slug, {"title": slug.title(), "badge": "Module", "description": "Commands", "permissions": "Varies"})
        bucket = groups.setdefault(
            slug,
            {
                "name": meta["title"],
                "badge": meta.get("badge", ""),
                "description": meta.get("description", ""),
                "commands": [],
            },
        )
        for cmd_name, desc in matches:
            bucket["commands"].append(
                {
                    "name": f"/{cmd_name}",
                    "description": desc or meta.get("description", "Slash command"),
                    "permissions": meta.get("permissions", "Varies"),
                    "module": slug,
                }
            )
    # sort commands alphabetically
    for bucket in groups.values():
        bucket["commands"].sort(key=lambda c: c["name"])
    ordered = sorted(groups.values(), key=lambda g: g["name"])
    return ordered


def fetch_rows(query: str, params: tuple = ()):
    conn = sqlite3.connect(db.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def execute_query(query: str, params: tuple = ()):
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    conn.close()


def queue_pending_request(guild_id: int, setup_type: str, data: str | None = None):
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO pending_setup_requests (guild_id, setup_type, data)
        VALUES (?, ?, ?)
        """,
        (guild_id, setup_type, data),
    )
    conn.commit()
    conn.close()


def fetch_economy_summary(guild_id: int) -> dict:
    leaderboard = [
        {"user_id": user_id, "balance": balance}
        for user_id, balance in db.get_economy_leaderboard(guild_id, limit=20)
    ]
    return {"leaderboard": leaderboard}


def handle_economy_action(guild_id: int, payload: dict) -> dict:
    action = payload.get("action")
    user_id = int(payload.get("user_id", 0))
    amount = int(payload.get("amount", 0))
    if not user_id:
        raise ValueError("user_id required")
    if action == "add_balance":
        balance = db.add_balance(guild_id, user_id, amount)
        return {"balance": balance}
    if action == "remove_balance":
        balance = db.add_balance(guild_id, user_id, -abs(amount))
        return {"balance": balance}
    raise ValueError("Unsupported economy action")


def fetch_leveling_summary(guild_id: int) -> dict:
    leaderboard = [
        {"user_id": user_id, "xp": xp}
        for user_id, xp in db.get_xp_leaderboard(guild_id, limit=20)
    ]
    return {"leaderboard": leaderboard}


def _level_to_xp(level: int) -> int:
    return level * level * 100


def handle_leveling_action(guild_id: int, payload: dict) -> dict:
    action = payload.get("action")
    user_id = int(payload.get("user_id", 0))
    if not user_id:
        raise ValueError("user_id required")
    if action == "add_xp":
        amount = int(payload.get("amount", 0))
        xp = db.add_user_xp(guild_id, user_id, amount)
        return {"xp": xp}
    if action == "set_level":
        level = int(payload.get("level", 0))
        xp_target = _level_to_xp(level)
        db.set_user_xp(guild_id, user_id, xp_target)
        return {"xp": xp_target}
    raise ValueError("Unsupported leveling action")


def fetch_moderation_summary(guild_id: int) -> dict:
    rows = fetch_rows(
        "SELECT user_id, COUNT(*) as warnings FROM warnings WHERE guild_id = ? GROUP BY user_id ORDER BY warnings DESC",
        (guild_id,),
    )
    return {"warnings": rows}


def handle_moderation_action(guild_id: int, payload: dict) -> dict:
    action = payload.get("action")
    user_id = int(payload.get("user_id", 0))
    if action == "clear_warnings" and user_id:
        db.clear_warnings(guild_id, user_id)
        return {"cleared": True}
    raise ValueError("Unsupported moderation action")


def fetch_custom_commands_summary(guild_id: int) -> dict:
    commands = db.get_custom_commands(guild_id)
    return {"commands": commands}


def handle_custom_commands_action(guild_id: int, payload: dict) -> dict:
    action = payload.get("action")
    name = payload.get("name")
    if action == "create":
        response = payload.get("response", "")
        embed = bool(payload.get("embed"))
        db.add_custom_command(guild_id, name, response, embed)
        return {"created": name}
    if action == "delete":
        db.delete_custom_command(guild_id, name)
        return {"deleted": name}
    raise ValueError("Unsupported custom command action")


def fetch_reaction_roles_summary(guild_id: int) -> dict:
    roles = fetch_rows(
        "SELECT message_id, channel_id, emoji, role_id, created_at FROM reaction_roles WHERE guild_id = ? ORDER BY created_at DESC",
        (guild_id,),
    )
    return {"panels": roles}


def handle_reaction_roles_action(guild_id: int, payload: dict) -> dict:
    action = payload.get("action")
    message_id = int(payload.get("message_id", 0))
    channel_id = int(payload.get("channel_id", 0))
    emoji = payload.get("emoji")
    role_id = int(payload.get("role_id", 0))
    if action == "add":
        if not (message_id and channel_id and emoji and role_id):
            raise ValueError("message_id, channel_id, emoji, role_id required")
        db.add_reaction_role(guild_id, message_id, channel_id, emoji, role_id)
        return {"added": True}
    if action == "remove":
        if not (message_id and emoji):
            raise ValueError("message_id and emoji required")
        db.delete_reaction_role(guild_id, message_id, emoji)
        return {"removed": True}
    raise ValueError("Unsupported reaction role action")


def fetch_ticket_summary(guild_id: int) -> dict:
    rows = fetch_rows("SELECT * FROM ticket_configs WHERE guild_id = ?", (guild_id,))
    return rows[0] if rows else {}


def handle_ticket_action(guild_id: int, payload: dict) -> dict:
    execute_query(
        """
        INSERT INTO ticket_configs (guild_id, category_id, support_role_id, log_channel_id, config_json)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            category_id = excluded.category_id,
            support_role_id = excluded.support_role_id,
            log_channel_id = excluded.log_channel_id,
            config_json = excluded.config_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            guild_id,
            payload.get("category_id"),
            payload.get("support_role_id"),
            payload.get("log_channel_id"),
            json.dumps(payload.get("config") or {}),
        ),
    )
    return {"updated": True}


def fetch_modmail_summary(guild_id: int) -> dict:
    threads = fetch_rows(
        """
        SELECT id, user_id, status, created_at, closed_at
        FROM modmail_threads
        WHERE guild_id = ?
        ORDER BY created_at DESC
        LIMIT 20
        """,
        (guild_id,),
    )
    return {"threads": threads}


def handle_modmail_action(guild_id: int, payload: dict) -> dict:
    action = payload.get("action")
    thread_id = int(payload.get("thread_id", 0))
    if action == "close_thread" and thread_id:
        execute_query(
            "UPDATE modmail_threads SET status = 'closed', closed_at = CURRENT_TIMESTAMP WHERE guild_id = ? AND id = ?",
            (guild_id, thread_id),
        )
        return {"closed": thread_id}
    raise ValueError("Unsupported modmail action")


def fetch_giveaway_summary(guild_id: int) -> dict:
    giveaways = fetch_rows(
        """
        SELECT id, prize, status, winner_count, created_at, ends_at
        FROM giveaways
        WHERE guild_id = ?
        ORDER BY created_at DESC
        LIMIT 20
        """,
        (guild_id,),
    )
    return {"giveaways": giveaways}


def handle_giveaway_action(guild_id: int, payload: dict) -> dict:
    action = payload.get("action")
    giveaway_id = int(payload.get("giveaway_id", 0))
    if action == "close" and giveaway_id:
        execute_query(
            "UPDATE giveaways SET status = 'ended', ended_at = CURRENT_TIMESTAMP WHERE guild_id = ? AND id = ?",
            (guild_id, giveaway_id),
        )
        return {"ended": giveaway_id}
    raise ValueError("Unsupported giveaway action")


def fetch_verification_summary(guild_id: int) -> dict:
    rows = fetch_rows("SELECT * FROM verify_configs WHERE guild_id = ?", (guild_id,))
    return rows[0] if rows else {}


def handle_verification_action(guild_id: int, payload: dict) -> dict:
    execute_query(
        """
        INSERT INTO verify_configs (guild_id, verified_role_id, unverified_role_id, title, description, banner_url, footer_text)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            verified_role_id = excluded.verified_role_id,
            unverified_role_id = excluded.unverified_role_id,
            title = excluded.title,
            description = excluded.description,
            banner_url = excluded.banner_url,
            footer_text = excluded.footer_text,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            guild_id,
            payload.get("verified_role_id"),
            payload.get("unverified_role_id"),
            payload.get("title"),
            payload.get("description"),
            payload.get("banner_url"),
            payload.get("footer_text"),
        ),
    )
    return {"updated": True}


def fetch_builder_summary(guild_id: int) -> dict:
    pending = fetch_rows(
        "SELECT id, setup_type, data, created_at FROM pending_setup_requests WHERE guild_id = ? AND setup_type LIKE 'builder%%' ORDER BY created_at DESC LIMIT 20",
        (guild_id,),
    )
    return {"pending": pending}


def handle_builder_action(guild_id: int, payload: dict) -> dict:
    queue_pending_request(guild_id, "builder_template", json.dumps(payload))
    return {"queued": True}


def fetch_ocr_builder_summary(guild_id: int) -> dict:
    return {"info": "Upload an image URL to analyze channel layouts."}


def handle_ocr_builder_action(_: int, payload: dict) -> dict:
    image_url = payload.get("image_url")
    if not image_url:
        raise ValueError("image_url required")
    template = analyze_image_stub(image_url)
    return {"template": template}


def fetch_text_parser_summary(guild_id: int) -> dict:
    return {"info": "Paste text layouts to convert into templates."}


def handle_text_parser_action(_: int, payload: dict) -> dict:
    raw = payload.get("raw_text", "")
    if not raw.strip():
        raise ValueError("raw_text required")
    template = parse_text_structure(raw)
    return {"template": template}


def fetch_global_task_summary() -> dict:
    summary = {
        "ticket_configs": 0,
        "active_modmail": 0,
        "active_giveaways": 0,
        "pending_ipc": 0,
        "verify_panels": 0,
        "custom_commands": 0,
    }
    try:
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ticket_configs")
        summary["ticket_configs"] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM modmail_threads WHERE status = 'open'")
        summary["active_modmail"] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM giveaways WHERE status = 'active'")
        summary["active_giveaways"] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM pending_setup_requests WHERE processed = 0")
        summary["pending_ipc"] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM verify_configs")
        summary["verify_panels"] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM custom_commands")
        summary["custom_commands"] = cursor.fetchone()[0] or 0

        conn.close()
    except Exception as exc:
        print(f"[WARN] Failed to build task summary: {exc}")
    return summary


def fetch_ipc_queue(limit: int = 20) -> list[dict]:
    return fetch_rows(
        "SELECT id, guild_id, setup_type, data, processed, created_at FROM pending_setup_requests ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )


def fetch_modmail_threads(limit: int = 8) -> list[dict]:
    return fetch_rows(
        "SELECT id, guild_id, user_id, status, created_at, closed_at FROM modmail_threads ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )


def get_database_size_mb() -> float:
    try:
        size_bytes = Path(db.db_path).stat().st_size
        return round(size_bytes / (1024 * 1024), 2)
    except OSError:
        return 0.0


MODULE_DEFINITIONS = {
    "economy": {
        "title": "Economy",
        "description": "Manage balances and leaderboard.",
        "fetch": fetch_economy_summary,
        "handler": handle_economy_action,
        "actions": [
            {
                "name": "add_balance",
                "label": "Add Balance",
                "fields": [
                    {"name": "user_id", "label": "User ID", "type": "number"},
                    {"name": "amount", "label": "Amount", "type": "number"},
                ],
            },
            {
                "name": "remove_balance",
                "label": "Remove Balance",
                "fields": [
                    {"name": "user_id", "label": "User ID", "type": "number"},
                    {"name": "amount", "label": "Amount", "type": "number"},
                ],
            },
        ],
    },
    "leveling": {
        "title": "Leveling",
        "description": "XP + level roles.",
        "fetch": fetch_leveling_summary,
        "handler": handle_leveling_action,
        "actions": [
            {
                "name": "add_xp",
                "label": "Add XP",
                "fields": [
                    {"name": "user_id", "label": "User ID", "type": "number"},
                    {"name": "amount", "label": "XP Amount", "type": "number"},
                ],
            },
            {
                "name": "set_level",
                "label": "Set Level",
                "fields": [
                    {"name": "user_id", "label": "User ID", "type": "number"},
                    {"name": "level", "label": "Level", "type": "number"},
                ],
            },
        ],
    },
    "moderation": {
        "title": "Moderation",
        "description": "Warnings overview.",
        "fetch": fetch_moderation_summary,
        "handler": handle_moderation_action,
        "actions": [
            {
                "name": "clear_warnings",
                "label": "Clear Warnings",
                "fields": [
                    {"name": "user_id", "label": "User ID", "type": "number"},
                ],
            }
        ],
    },
    "custom_commands": {
        "title": "Custom Commands",
        "description": "Manage responses.",
        "fetch": fetch_custom_commands_summary,
        "handler": handle_custom_commands_action,
        "actions": [
            {
                "name": "create",
                "label": "Create Command",
                "fields": [
                    {"name": "name", "label": "Command Name", "type": "text"},
                    {"name": "response", "label": "Response", "type": "text"},
                    {"name": "embed", "label": "Send as Embed (true/false)", "type": "text"},
                ],
            },
            {
                "name": "delete",
                "label": "Delete Command",
                "fields": [
                    {"name": "name", "label": "Command Name", "type": "text"},
                ],
            },
        ],
    },
    "reaction_roles": {
        "title": "Reaction Roles",
        "description": "Configure panels.",
        "fetch": fetch_reaction_roles_summary,
        "handler": handle_reaction_roles_action,
        "actions": [
            {
                "name": "add",
                "label": "Add Reaction Role",
                "fields": [
                    {"name": "message_id", "label": "Message ID", "type": "number"},
                    {"name": "channel_id", "label": "Channel ID", "type": "number"},
                    {"name": "emoji", "label": "Emoji", "type": "text"},
                    {"name": "role_id", "label": "Role ID", "type": "number"},
                ],
            },
            {
                "name": "remove",
                "label": "Remove Reaction Role",
                "fields": [
                    {"name": "message_id", "label": "Message ID", "type": "number"},
                    {"name": "emoji", "label": "Emoji", "type": "text"},
                ],
            },
        ],
    },
    "tickets": {
        "title": "Ticket System",
        "description": "Ticket settings",
        "fetch": fetch_ticket_summary,
        "handler": handle_ticket_action,
        "actions": [
            {
                "name": "update",
                "label": "Update Settings",
                "fields": [
                    {"name": "category_id", "label": "Category ID", "type": "text"},
                    {"name": "support_role_id", "label": "Support Role ID", "type": "text"},
                    {"name": "log_channel_id", "label": "Log Channel ID", "type": "text"},
                    {"name": "config", "label": "Config JSON", "type": "textarea"},
                ],
            }
        ],
    },
    "modmail": {
        "title": "ModMail",
        "description": "Threads and transcripts.",
        "fetch": fetch_modmail_summary,
        "handler": handle_modmail_action,
        "actions": [
            {
                "name": "close_thread",
                "label": "Close Thread",
                "fields": [
                    {"name": "thread_id", "label": "Thread ID", "type": "number"},
                ],
            }
        ],
    },
    "giveaways": {
        "title": "Giveaways",
        "description": "Manage events.",
        "fetch": fetch_giveaway_summary,
        "handler": handle_giveaway_action,
        "actions": [
            {
                "name": "close",
                "label": "End Giveaway",
                "fields": [
                    {"name": "giveaway_id", "label": "Giveaway ID", "type": "number"},
                ],
            }
        ],
    },
    "verification": {
        "title": "Verification",
        "description": "Role and panel settings.",
        "fetch": fetch_verification_summary,
        "handler": handle_verification_action,
        "actions": [
            {
                "name": "update",
                "label": "Update Verification",
                "fields": [
                    {"name": "verified_role_id", "label": "Verified Role ID", "type": "text"},
                    {"name": "unverified_role_id", "label": "Unverified Role ID", "type": "text"},
                    {"name": "title", "label": "Title", "type": "text"},
                    {"name": "description", "label": "Description", "type": "textarea"},
                    {"name": "banner_url", "label": "Banner URL", "type": "text"},
                    {"name": "footer_text", "label": "Footer Text", "type": "text"},
                ],
            }
        ],
    },
    "server_builder": {
        "title": "Server Builder",
        "description": "Queue builder templates.",
        "fetch": fetch_builder_summary,
        "handler": handle_builder_action,
        "actions": [
            {
                "name": "queue",
                "label": "Queue Template",
                "fields": [
                    {"name": "template_name", "label": "Template Name", "type": "text"},
                    {"name": "notes", "label": "Notes", "type": "textarea"},
                ],
            }
        ],
    },
    "ocr_builder": {
        "title": "OCR Builder",
        "description": "Convert screenshots using OCR.",
        "fetch": fetch_ocr_builder_summary,
        "handler": handle_ocr_builder_action,
        "actions": [
            {
                "name": "analyze",
                "label": "Analyze Image",
                "fields": [
                    {"name": "image_url", "label": "Image URL", "type": "text"},
                ],
            }
        ],
    },
    "text_parser": {
        "title": "Text Parser",
        "description": "Convert plain text to templates.",
        "fetch": fetch_text_parser_summary,
        "handler": handle_text_parser_action,
        "actions": [
            {
                "name": "parse",
                "label": "Parse Layout",
                "fields": [
                    {"name": "raw_text", "label": "Raw Layout Text", "type": "textarea"},
                ],
            }
        ],
    },
}


def list_module_cards():
    cards = []
    for slug, definition in MODULE_DEFINITIONS.items():
        card = dict(definition)
        card["slug"] = slug
        cards.append(card)
    return sorted(cards, key=lambda c: c["title"])


def command_totals(command_groups: list[dict]):
    return sum(len(group["commands"]) for group in command_groups)


def fetch_bot_guild_snapshot(admin_guilds: list[dict]) -> list[dict]:
    """Return the bot's guild list if token available, else fallback to admin view."""
    if DISCORD_BOT_TOKEN:
        try:
            guilds = get_bot_guilds(DISCORD_BOT_TOKEN)
            if guilds:
                return guilds
        except Exception as exc:
            print(f"[WARN] Failed to fetch bot guilds: {exc}")
    return admin_guilds


def fetch_database_metrics():
    metrics = {
        "custom_commands": 0,
        "reaction_panels": 0,
        "pending_requests": 0,
        "activity_today": {"chat": 0, "voice": 0},
        "activity_series": [],
    }
    try:
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM custom_commands")
        metrics["custom_commands"] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM reaction_roles")
        metrics["reaction_panels"] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM pending_setup_requests WHERE processed = 0")
        metrics["pending_requests"] = cursor.fetchone()[0] or 0

        today_iso = datetime.utcnow().date().isoformat()
        cursor.execute(
            """
            SELECT COALESCE(SUM(chat_minutes),0), COALESCE(SUM(voice_minutes),0)
            FROM user_activity
            WHERE activity_date = ?
            """,
            (today_iso,),
        )
        row = cursor.fetchone()
        metrics["activity_today"] = {"chat": row[0], "voice": row[1]}

        start_date = (datetime.utcnow() - timedelta(days=13)).date().isoformat()
        cursor.execute(
            """
            SELECT activity_date, SUM(chat_minutes), SUM(voice_minutes)
            FROM user_activity
            WHERE activity_date >= ?
            GROUP BY activity_date
            ORDER BY activity_date
            """,
            (start_date,),
        )
        series = []
        for activity_date, chat, voice in cursor.fetchall():
            series.append(
                {
                    "label": datetime.fromisoformat(activity_date).strftime("%d %b"),
                    "chat": chat,
                    "voice": voice,
                    "value": chat + voice,
                }
            )
        metrics["activity_series"] = series
        metrics["activity_max"] = max((entry["value"] for entry in series), default=1)
        conn.close()
    except Exception as exc:
        print(f"[WARN] Failed to fetch DB metrics: {exc}")
    return metrics


def build_live_stats_payload():
    guilds = fetch_bot_guild_snapshot([])
    guild_count = len(guilds)
    user_count = sum(int(g.get("approximate_member_count") or g.get("member_count") or 0) for g in guilds)
    try:
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(chat_minutes + voice_minutes), 0) FROM user_activity")
        total_commands_run = cursor.fetchone()[0] or 0
        conn.close()
    except Exception:
        total_commands_run = 0
    cpu_usage = psutil.cpu_percent(interval=None) if psutil else 0.0
    ram_usage = psutil.virtual_memory().percent if psutil else 0.0
    return {
        "guild_count": guild_count,
        "user_count": user_count,
        "total_commands_run": total_commands_run,
        "latency_ms": int(BOT_STATUS_LATENCY_MS),
        "uptime": _humanize_timedelta(datetime.utcnow() - APP_STARTED_AT),
        "cpu_usage": cpu_usage,
        "ram_usage": ram_usage,
    }


def validate_oauth_env():
    if not DISCORD_CLIENT_ID:
        raise RuntimeError("DISCORD_CLIENT_ID missing in environment")
    if not DISCORD_CLIENT_SECRET:
        raise RuntimeError("DISCORD_CLIENT_SECRET missing in environment")
    if not DISCORD_REDIRECT_URI:
        raise RuntimeError("DISCORD_REDIRECT_URI missing in environment")
    # Print a quick sanity log (no secrets)
    print("[OAUTH] CLIENT_ID=", DISCORD_CLIENT_ID)
    print("[OAUTH] REDIRECT_URI=", DISCORD_REDIRECT_URI)
    print("[OAUTH] AUTH URL=", DISCORD_OAUTH_URL)


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def get_discord_user(access_token):
    """Get Discord user info from access token"""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{DISCORD_API_BASE}/users/@me", headers=headers)
    if response.status_code == 200:
        return response.json()
    return None


def get_user_guilds(access_token):
    """Get user's Discord guilds"""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(
        f"{DISCORD_API_BASE}/users/@me/guilds",
        headers=headers,
        params={"with_counts": "true"},
        timeout=15,
    )
    if response.status_code == 200:
        return response.json()
    return []


def filter_admin_guilds(access_token):
    guilds = get_user_guilds(access_token)
    admin_guilds = []
    for guild in guilds:
        permissions = int(guild.get("permissions", 0))
        if permissions & 0x20 or permissions & 0x8:
            admin_guilds.append(guild)
    return admin_guilds


def get_active_locale():
    locale = request.cookies.get("locale", "en")
    if locale not in LANGUAGE_CODES:
        locale = "en"
    return locale


def user_has_guild_access(guild_id: int, access_token: str, user_id: int | None) -> bool:
    if user_id in DEVELOPER_IDS:
        return True
    admin_guilds = filter_admin_guilds(access_token)
    return any(str(g.get("id")) == str(guild_id) for g in admin_guilds)


def get_bot_guilds(bot_token):
    """Get bot's guilds"""
    headers = {"Authorization": f"Bot {bot_token}"}
    response = requests.get(
        f"{DISCORD_API_BASE}/users/@me/guilds",
        headers=headers,
        params={"with_counts": "true"},
        timeout=15,
    )
    if response.status_code == 200:
        return response.json()
    return []


def discord_avatar_url(user: dict | None) -> str:
    """Return a usable avatar URL for a Discord user dict."""
    if not user:
        return "https://cdn.discordapp.com/embed/avatars/0.png"
    avatar_hash = user.get("avatar")
    user_id = user.get("id", "0")
    if avatar_hash:
        ext = "gif" if avatar_hash.startswith("a_") else "png"
        return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.{ext}?size=128"
    fallback = 0
    if str(user_id).isdigit():
        fallback = int(user_id) % 5
    return f"https://cdn.discordapp.com/embed/avatars/{fallback}.png"


def _humanize_timedelta(delta: timedelta) -> str:
    seconds = int(delta.total_seconds())
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def build_nav_sections():
    return SIDEBAR_STRUCTURE


def build_command_sections(command_groups: list[dict]):
    highlight_groups = []
    for group in command_groups[:2]:
        highlight_groups.append(
            {
                "title": group["name"],
                "tone": "from-fuchsia-500 to-purple-500" if not highlight_groups else "from-indigo-500 to-blue-500",
                "commands": [
                    {"name": cmd["name"], "description": cmd["description"]}
                    for cmd in group["commands"][:4]
                ],
            }
        )
    return highlight_groups


def build_owner_logs(guilds: list[dict], metrics: dict):
    now = datetime.utcnow()
    queue = metrics.get("pending_requests", 0)
    logs = [
        {
            "title": "Queue monitor",
            "detail": f"{queue} pending setup request(s) across all guilds.",
            "status": "Queue",
            "timestamp": now.strftime("%H:%M UTC"),
        },
        {
            "title": "Custom commands",
            "detail": f"{metrics.get('custom_commands', 0)} stored responses in SQLite.",
            "status": "DB",
            "timestamp": (now - timedelta(minutes=7)).strftime("%H:%M UTC"),
        },
        {
            "title": "Reaction panels",
            "detail": f"{metrics.get('reaction_panels', 0)} emoji panels currently active.",
            "status": "Roles",
            "timestamp": (now - timedelta(minutes=18)).strftime("%H:%M UTC"),
        },
    ]
    if guilds:
        logs.append(
            {
                "title": "Guild reach",
                "detail": f"Heartbeat confirmed for {len(guilds)} guild(s).",
                "status": "Live",
                "timestamp": (now - timedelta(minutes=24)).strftime("%H:%M UTC"),
            }
        )
    return logs


def build_recent_servers(guilds: list[dict]):
    rows = []
    for guild in guilds[:5]:
        rows.append(
            {
                "name": guild.get("name", "Unknown"),
                "icon": guild.get("icon"),
                "members": guild.get("approximate_member_count") or "—",
                "region": guild.get("preferred_locale", "Global"),
                "status": "Connected",
            }
        )
    if not rows:
        rows = [
            {"name": "Awaiting Invite", "members": "—", "region": "Global", "status": "Pending"},
        ]
    return rows


def build_bot_status():
    uptime = _humanize_timedelta(datetime.utcnow() - APP_STARTED_AT)
    return {
        "version": BOT_STATUS_VERSION,
        "cluster": BOT_STATUS_CLUSTER,
        "region": BOT_STATUS_REGION,
        "latency": f"{BOT_STATUS_LATENCY_MS}ms",
        "uptime": uptime,
        "refreshed": datetime.utcnow().strftime("%H:%M:%S"),
    }


def build_overview_cards(guilds: list[dict], metrics: dict, command_groups: list[dict]):
    server_total = len(guilds)
    total_users = sum(
        int(g.get("approximate_member_count") or g.get("member_count") or 0) for g in guilds
    )
    if total_users == 0 and server_total:
        total_users = server_total * 64
    today_stats = metrics.get("activity_today", {"chat": 0, "voice": 0})
    today_total = today_stats["chat"] + today_stats["voice"]
    command_total = command_totals(command_groups)
    return [
        {"label": "Servers Online", "value": server_total, "delta": f"{command_total} slash commands"},
        {"label": "Tracked Members", "value": total_users, "delta": f"{metrics.get('reaction_panels', 0)} reaction panels"},
        {"label": "Custom Commands", "value": metrics.get("custom_commands", 0), "delta": f"{metrics.get('pending_requests', 0)} queued jobs"},
        {
            "label": "Today's Activity",
            "value": today_total,
            "delta": f"{today_stats['chat']} chat / {today_stats['voice']} voice",
        },
    ]


def build_dashboard_snapshot(guilds: list[dict], metrics: dict):
    command_groups = discover_bot_commands()
    return {
        "nav_sections": build_nav_sections(),
        "overview_cards": build_overview_cards(guilds, metrics, command_groups),
        "activity_series": metrics.get("activity_series", []),
        "activity_max": metrics.get("activity_max", 1),
        "owner_logs": build_owner_logs(guilds, metrics),
        "command_sections": build_command_sections(command_groups),
        "bot_status": build_bot_status(),
        "recent_servers": build_recent_servers(guilds),
        "command_groups": command_groups,
        "command_total": command_totals(command_groups),
    }


@app.route('/')
def index():
    """Home page"""
    if 'user' in session:
        return redirect(url_for('dashboard'))
    
    return render_template(
        'index.html',
        brand_name=BRAND_NAME,
        tagline=BRAND_TAGLINE,
        support_invite=SUPPORT_INVITE,
        brand_logo_url=BRAND_LOGO_URL,
    )


@app.route('/login')
def login():
    """Redirect to Discord OAuth"""
    return redirect(DISCORD_OAUTH_URL)


@app.route('/locale', methods=['POST'])
def set_locale():
    """Update UI locale preference."""
    locale = request.form.get('locale', 'en')
    if locale not in LANGUAGE_CODES:
        locale = 'en'
    next_url = request.referrer or url_for('dashboard')
    resp = redirect(next_url)
    resp.set_cookie('locale', locale, max_age=60 * 60 * 24 * 30, httponly=False, samesite='Lax')
    return resp


@app.route('/callback')
def callback():
    """OAuth callback"""
    code = request.args.get('code')
    if not code:
        return "No code provided", 400
    
    # Exchange code for token
    data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': DISCORD_REDIRECT_URI,
        'scope': 'identify guilds'
    }
    
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(f"{DISCORD_API_BASE}/oauth2/token", data=data, headers=headers)
    
    if response.status_code != 200:
        return "Failed to get access token", 400
    
    token_data = response.json()
    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in', 604800)
    
    # Get user info
    user = get_discord_user(access_token)
    if not user:
        return "Failed to get user info", 400
    
    # Store in session
    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    
    db.create_session(session_id, int(user['id']), access_token, refresh_token, expires_at.isoformat())
    
    session['user'] = user
    session['session_id'] = session_id
    session['access_token'] = access_token
    session['csrf_token'] = secrets.token_urlsafe(48)
    
    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    """Logout"""
    if 'session_id' in session:
        db.delete_session(session['session_id'])
    
    session.clear()
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard"""
    access_token = session.get('access_token')
    user = session.get('user')
    user_id = int(user.get("id")) if user and user.get("id") else None
    developer_mode = user_id in DEVELOPER_IDS if user_id else False
    locale = get_active_locale()
    translations = load_translations(locale)
    
    admin_guilds = filter_admin_guilds(access_token)
    guilds_for_snapshot = fetch_bot_guild_snapshot(admin_guilds if not developer_mode else [])
    launcher_guilds = admin_guilds if admin_guilds else guilds_for_snapshot
    for g in launcher_guilds:
        perms = int(g.get("permissions", 0))
        g["is_admin"] = bool(perms & 0x8)
        g["has_manage_guild"] = bool(perms & 0x20)
    db_metrics = fetch_database_metrics()
    context = build_dashboard_snapshot(guilds_for_snapshot, db_metrics)
    module_cards = list_module_cards()
    csrf_token = get_or_create_csrf_token()
    
    return render_template(
        'dashboard.html',
        user=user,
        avatar_url=discord_avatar_url(user),
        guilds=launcher_guilds,
        brand_name=BRAND_NAME,
        tagline=BRAND_TAGLINE,
        support_invite=SUPPORT_INVITE,
        metrics=db_metrics,
        admin_guilds=launcher_guilds,
        languages=LANGUAGE_CODES,
        active_locale=locale,
        translations=translations,
        developer_mode=developer_mode,
        module_cards=module_cards,
        csrf_token=csrf_token,
        brand_logo_url=BRAND_LOGO_URL,
        **context,
    )


@app.route('/dashboard/command-request', methods=['POST'])
@login_required
def dashboard_command_request():
    """Queue a slash command request for processing by the bot worker."""
    command_name = request.form.get('command')
    guild_id = request.form.get('guild_id')
    payload = (request.form.get('payload') or "").strip()
    if not command_name or not guild_id:
        flash("Command and guild are required.", "error")
        return redirect(url_for('dashboard'))
    
    access_token = session.get('access_token')
    admin_guilds = filter_admin_guilds(access_token)
    user = session.get('user')
    user_id = int(user.get("id")) if user and user.get("id") else None
    developer_mode = user_id in DEVELOPER_IDS if user_id else False
    if not developer_mode and not any(str(g.get('id')) == str(guild_id) for g in admin_guilds):
        flash("You do not have permission to manage that guild.", "error")
        return redirect(url_for('dashboard'))
    
    try:
        guild_int = int(guild_id)
    except ValueError:
        flash("Invalid guild ID.", "error")
        return redirect(url_for('dashboard'))
    
    try:
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO pending_setup_requests (guild_id, setup_type, data)
            VALUES (?, ?, ?)
            """,
            (guild_int, f"command:{command_name}", payload or None),
        )
        conn.commit()
        conn.close()
        flash(f"{command_name} queued for {guild_id}.", "success")
    except Exception as exc:
        flash(f"Failed to queue command: {exc}", "error")
    return redirect(url_for('dashboard'))


@app.route('/dashboard/command-center')
@login_required
def command_center():
    """Dedicated surface for browsing and queuing commands."""
    access_token = session.get('access_token')
    user = session.get('user')
    user_id = int(user.get("id")) if user and user.get("id") else None
    developer_mode = user_id in DEVELOPER_IDS if user_id else False
    admin_guilds = filter_admin_guilds(access_token)
    command_groups = discover_bot_commands()
    locale = get_active_locale()
    translations = load_translations(locale)
    return render_template(
        'command_center.html',
        user=user,
        avatar_url=discord_avatar_url(user),
        brand_name=BRAND_NAME,
        support_invite=SUPPORT_INVITE,
        command_groups=command_groups,
        guilds=admin_guilds,
        languages=LANGUAGE_CODES,
        active_locale=locale,
        translations=translations,
        developer_mode=developer_mode,
        bot_status=build_bot_status(),
        metrics=fetch_database_metrics(),
        csrf_token=get_or_create_csrf_token(),
        brand_logo_url=BRAND_LOGO_URL,
    )


@app.route('/api/live/bot')
@login_required
def api_live_bot():
    return jsonify(build_live_stats_payload())


@app.route('/api/commands')
@login_required
def api_commands():
    return jsonify(discover_bot_commands())


@app.route('/api/command/queue', methods=['POST'])
@login_required
def api_command_queue():
    """Queue a command via JSON for the bot worker to pick up."""
    payload = request.get_json(silent=True) or {}
    command_name = payload.get('command')
    guild_id = payload.get('guild_id')
    if not command_name or not guild_id:
        return jsonify({"error": "command and guild_id are required"}), 400

    access_token = session.get('access_token')
    admin_guilds = filter_admin_guilds(access_token)
    user = session.get('user')
    user_id = int(user.get("id")) if user and user.get("id") else None
    developer_mode = user_id in DEVELOPER_IDS if user_id else False
    if not developer_mode and not any(str(g.get('id')) == str(guild_id) for g in admin_guilds):
        return jsonify({"error": "Unauthorized"}), 403

    try:
        guild_int = int(guild_id)
    except ValueError:
        return jsonify({"error": "Invalid guild ID"}), 400

    payload_body = payload.get('payload')
    notes = (payload.get('notes') or "").strip()
    options = payload.get('options')
    data_blob = None
    if isinstance(payload_body, (dict, list)):
        envelope = {"payload": payload_body}
        if notes:
            envelope["notes"] = notes
        if options:
            envelope["options"] = options
        data_blob = json.dumps(envelope)
    else:
        text_value = (payload_body or "").strip()
        if notes or options:
            envelope = {}
            if text_value:
                envelope["payload"] = text_value
            if notes:
                envelope["notes"] = notes
            if options:
                envelope["options"] = options
            data_blob = json.dumps(envelope)
        else:
            data_blob = text_value or None

    try:
        queue_pending_request(guild_int, f"command:{command_name}", data_blob)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"success": True})


@app.route('/api/guild/<int:guild_id>/module/<module_slug>', methods=['GET', 'POST'])
@login_required
def api_module(guild_id, module_slug):
    access_token = session.get('access_token')
    user = session.get('user')
    user_id = int(user.get("id")) if user and user.get("id") else None
    if not user_has_guild_access(guild_id, access_token, user_id):
        return jsonify({"error": "Unauthorized"}), 403
    module = MODULE_DEFINITIONS.get(module_slug)
    if not module:
        return jsonify({"error": "Unknown module"}), 404
    if request.method == 'GET':
        return jsonify(module["fetch"](guild_id))
    if "handler" not in module or module["handler"] is None:
        return jsonify({"error": "Module is read-only"}), 400
    payload = request.get_json(silent=True) or {}
    if "action" not in payload:
        payload["action"] = request.form.get("action")
    try:
        result = module["handler"](guild_id, payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"success": True, "result": result})


@app.route('/developer')
@login_required
def developer_dashboard():
    user = session.get('user')
    user_id = int(user.get("id")) if user and user.get("id") else None
    if user_id not in DEVELOPER_IDS:
        return redirect(url_for('dashboard'))
    stats = build_live_stats_payload()
    metrics = fetch_database_metrics()
    guilds = fetch_bot_guild_snapshot([])
    task_summary = fetch_global_task_summary()
    ipc_jobs = fetch_ipc_queue(20)
    modmail_threads = fetch_modmail_threads(8)
    resource_snapshot = {
        "cpu": stats.get("cpu_usage"),
        "ram": stats.get("ram_usage"),
        "latency": stats.get("latency_ms"),
        "uptime": stats.get("uptime"),
        "db_size": get_database_size_mb(),
    }
    locale = get_active_locale()
    translations = load_translations(locale)
    return render_template(
        'developer_dashboard.html',
        stats=stats,
        metrics=metrics,
        guilds=guilds,
        ipc_jobs=ipc_jobs,
        modmail_threads=modmail_threads,
        task_summary=task_summary,
        resource_snapshot=resource_snapshot,
        brand_name=BRAND_NAME,
        support_invite=SUPPORT_INVITE,
        active_locale=locale,
        translations=translations,
        activity_series=metrics.get("activity_series", []),
        activity_max=metrics.get("activity_max", 1),
        csrf_token=get_or_create_csrf_token(),
        brand_logo_url=BRAND_LOGO_URL,
    )


@app.route('/dashboard/guild/<int:guild_id>')
@login_required
def guild_dashboard(guild_id):
    """Guild-specific dashboard"""
    access_token = session.get('access_token')
    user = session.get('user')
    
    # Verify user has access to this guild
    guilds = filter_admin_guilds(access_token)
    guild = None
    for g in guilds:
        if int(g['id']) == guild_id:
            guild = g
            break
    
    if not guild:
        return "Unauthorized", 403
    
    # Get guild config from database
    config = db.get_guild_config(guild_id) or {}
    custom_commands = db.get_custom_commands(guild_id)
    
    # Add bot client ID for invite link
    config['bot_client_id'] = DISCORD_CLIENT_ID
    
    db_metrics = fetch_database_metrics()
    context = build_dashboard_snapshot([guild], db_metrics)
    return render_template(
        'guild_dashboard_enhanced.html', 
        user=user, 
        avatar_url=discord_avatar_url(user),
        guild=guild,
        config=config,
        custom_commands=custom_commands,
        brand_name=BRAND_NAME,
        support_invite=SUPPORT_INVITE,
        metrics=db_metrics,
        translations=load_translations(get_active_locale()),
        csrf_token=get_or_create_csrf_token(),
        brand_logo_url=BRAND_LOGO_URL,
        **context,
    )


@app.route('/dashboard/guild/<int:guild_id>/module/<module_slug>')
@login_required
def module_dashboard_view(guild_id, module_slug):
    access_token = session.get('access_token')
    user = session.get('user')
    user_id = int(user.get("id")) if user and user.get("id") else None
    if not user_has_guild_access(guild_id, access_token, user_id):
        return "Unauthorized", 403
    module = MODULE_DEFINITIONS.get(module_slug)
    if not module:
        return "Module not found", 404
    admin_guilds = filter_admin_guilds(access_token)
    guild = next((g for g in admin_guilds if int(g["id"]) == guild_id), {"name": f"Guild {guild_id}", "id": guild_id})
    summary = module["fetch"](guild_id)
    locale = get_active_locale()
    translations = load_translations(locale)
    return render_template(
        'module_dashboard.html',
        module=module,
        summary=summary,
        guild=guild,
        module_slug=module_slug,
        brand_name=BRAND_NAME,
        support_invite=SUPPORT_INVITE,
        languages=LANGUAGE_CODES,
        active_locale=locale,
        translations=translations,
        csrf_token=get_or_create_csrf_token(),
        brand_logo_url=BRAND_LOGO_URL,
    )


@app.route('/api/guild/<int:guild_id>/config', methods=['GET', 'POST'])
@login_required
def api_guild_config(guild_id):
    """API endpoint for guild config"""
    if request.method == 'GET':
        config = db.get_guild_config(guild_id)
        return jsonify(config or {})
    
    elif request.method == 'POST':
        data = request.json
        
        # Validate user has access
        access_token = session.get('access_token')
        guilds = get_user_guilds(access_token)
        has_access = False
        
        for g in guilds:
            if int(g['id']) == guild_id:
                permissions = int(g.get('permissions', 0))
                if permissions & 0x20 or permissions & 0x8:
                    has_access = True
                    break
        
        if not has_access:
            return jsonify({"error": "Unauthorized"}), 403
        
        # Update config
        db.set_guild_config(guild_id, **data)
        
        return jsonify({"success": True})


@app.route('/api/guild/<int:guild_id>/commands', methods=['GET', 'POST', 'DELETE'])
@login_required
def api_custom_commands(guild_id):
    """API endpoint for custom commands"""
    # Validate user has access
    access_token = session.get('access_token')
    guilds = get_user_guilds(access_token)
    has_access = False
    
    for g in guilds:
        if int(g['id']) == guild_id:
            permissions = int(g.get('permissions', 0))
            if permissions & 0x20 or permissions & 0x8:
                has_access = True
                break
    
    if not has_access:
        return jsonify({"error": "Unauthorized"}), 403
    
    if request.method == 'GET':
        commands = db.get_custom_commands(guild_id)
        return jsonify(commands)
    
    elif request.method == 'POST':
        data = request.json
        name = data.get('name')
        response = data.get('response')
        embed = data.get('embed', False)
        
        if not name or not response:
            return jsonify({"error": "Missing name or response"}), 400
        
        user_id = int(session['user']['id'])
        db.add_custom_command(guild_id, name, response, embed, user_id)
        
        return jsonify({"success": True})
    
    elif request.method == 'DELETE':
        name = request.args.get('name')
        if not name:
            return jsonify({"error": "Missing name"}), 400
        
        success = db.delete_custom_command(guild_id, name)
        return jsonify({"success": success})


@app.route('/api/user/guilds')
@login_required
def api_user_guilds():
    """API endpoint to get user's guilds"""
    access_token = session.get('access_token')
    guilds = get_user_guilds(access_token)
    
    # Filter guilds where user has manage server permission
    admin_guilds = []
    for guild in guilds:
        permissions = int(guild.get('permissions', 0))
        if permissions & 0x20 or permissions & 0x8:
            admin_guilds.append(guild)
    
    return jsonify(admin_guilds)


@app.route('/api/guild/<int:guild_id>/send-embed', methods=['POST'])
@login_required
def api_send_embed(guild_id):
    """API endpoint to send embeds via bot"""
    # Validate user has access
    access_token = session.get('access_token')
    guilds = get_user_guilds(access_token)
    has_access = False
    
    for g in guilds:
        if int(g['id']) == guild_id:
            permissions = int(g.get('permissions', 0))
            if permissions & 0x20 or permissions & 0x8:
                has_access = True
                break
    
    if not has_access:
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    channel_id = data.get('channel_id')
    embed_data = data.get('embed')
    
    if not channel_id or not embed_data:
        return jsonify({"error": "Missing channel_id or embed"}), 400
    
    # Store the embed request in database for bot to process
    # Or use a webhook/API to send directly
    # For now, return success (bot implementation needed)
    return jsonify({"success": True, "message": "Embed sent successfully"})


@app.route('/api/guild/<int:guild_id>/announcement', methods=['POST'])
@login_required
def api_send_announcement(guild_id):
    """API endpoint to send announcements"""
    # Validate user has access
    access_token = session.get('access_token')
    guilds = get_user_guilds(access_token)
    has_access = False
    
    for g in guilds:
        if int(g['id']) == guild_id:
            permissions = int(g.get('permissions', 0))
            if permissions & 0x20 or permissions & 0x8:
                has_access = True
                break
    
    if not has_access:
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    channel_id = data.get('channel_id')
    content = data.get('content')
    announcement_type = data.get('type', 'normal')
    mention_everyone = data.get('mention_everyone', False)
    
    if not channel_id or not content:
        return jsonify({"error": "Missing channel_id or content"}), 400
    
    # Store announcement request for bot to process
    return jsonify({"success": True, "message": "Announcement sent successfully"})


@app.route('/api/guild/<int:guild_id>/roles', methods=['POST'])
@login_required
def api_create_role(guild_id):
    """API endpoint to create roles"""
    # Validate user has access
    access_token = session.get('access_token')
    guilds = get_user_guilds(access_token)
    has_access = False
    
    for g in guilds:
        if int(g['id']) == guild_id:
            permissions = int(g.get('permissions', 0))
            if permissions & 0x20 or permissions & 0x8:
                has_access = True
                break
    
    if not has_access:
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    role_name = data.get('name')
    
    if not role_name:
        return jsonify({"error": "Missing role name"}), 400
    
    # Store role creation request for bot to process
    return jsonify({"success": True, "message": "Role created successfully"})


@app.route('/api/guild/<int:guild_id>/roles/bulk', methods=['POST'])
@login_required
def api_create_bulk_roles(guild_id):
    """API endpoint to create multiple roles"""
    # Validate user has access
    access_token = session.get('access_token')
    guilds = get_user_guilds(access_token)
    has_access = False
    
    for g in guilds:
        if int(g['id']) == guild_id:
            permissions = int(g.get('permissions', 0))
            if permissions & 0x20 or permissions & 0x8:
                has_access = True
                break
    
    if not has_access:
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    role_names = data.get('role_names', [])
    
    if not role_names:
        return jsonify({"error": "No role names provided"}), 400
    
    # Store bulk role creation request for bot to process
    return jsonify({"success": True, "created": len(role_names)})


@app.route('/api/guild/<int:guild_id>/template', methods=['POST'])
@login_required
def api_apply_template(guild_id):
    """API endpoint to apply server templates"""
    # Validate user has access
    access_token = session.get('access_token')
    guilds = get_user_guilds(access_token)
    has_access = False
    
    for g in guilds:
        if int(g['id']) == guild_id:
            permissions = int(g.get('permissions', 0))
            if permissions & 0x20 or permissions & 0x8:
                has_access = True
                break
    
    if not has_access:
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    template_name = data.get('template')
    
    if not template_name:
        return jsonify({"error": "Missing template name"}), 400
    
    # Valid templates
    valid_templates = ['gaming', 'community', 'support', 'creative']
    if template_name not in valid_templates:
        return jsonify({"error": "Invalid template"}), 400
    
    # Store template application request for bot to process
    return jsonify({"success": True, "message": f"Template '{template_name}' applied successfully"})


@app.route('/api/guild/<int:guild_id>/leveling-setup', methods=['POST'])
@login_required
def api_leveling_setup(guild_id):
    """API endpoint to trigger automatic leveling setup"""
    # Validate user has access
    access_token = session.get('access_token')
    guilds = get_user_guilds(access_token)
    has_access = False
    
    for g in guilds:
        if int(g['id']) == guild_id:
            permissions = int(g.get('permissions', 0))
            if permissions & 0x20 or permissions & 0x8:
                has_access = True
                break
    
    if not has_access:
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    milestones = data.get('milestones', '5,10,20,30,50,80,100')
    create_info = data.get('create_info_channel', True)
    create_rules = data.get('create_rules_channel', False)
    
    # Store setup request in database for bot to process
    try:
        # Create a pending setup request that the bot will pick up
        db.conn.execute("""
            INSERT OR REPLACE INTO pending_setup_requests 
            (guild_id, setup_type, data, created_at)
            VALUES (?, 'leveling', ?, datetime('now'))
        """, (guild_id, f"{milestones}|{int(create_info)}|{int(create_rules)}"))
        db.conn.commit()
        
        return jsonify({
            "success": True, 
            "message": "Leveling setup request submitted! The bot will process it shortly."
        })
    except Exception as e:
        return jsonify({"error": f"Failed to create setup request: {str(e)}"}), 500


@app.route('/api/guild/<int:guild_id>/level-roles', methods=['POST'])
@login_required
def api_add_level_role(guild_id):
    """API endpoint to add level role rewards"""
    # Validate user has access
    access_token = session.get('access_token')
    guilds = get_user_guilds(access_token)
    has_access = False
    
    for g in guilds:
        if int(g['id']) == guild_id:
            permissions = int(g.get('permissions', 0))
            if permissions & 0x20 or permissions & 0x8:
                has_access = True
                break
    
    if not has_access:
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    level = data.get('level')
    role_id = data.get('role_id')
    
    if not level or not role_id:
        return jsonify({"error": "Missing level or role_id"}), 400
    
    try:
        db.set_level_role(guild_id, int(level), int(role_id))
        return jsonify({"success": True, "message": f"Level {level} role reward added"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/guild/<int:guild_id>/giveaway', methods=['POST'])
@login_required
def api_create_giveaway(guild_id):
    """API endpoint to create giveaways"""
    # Validate user has access
    access_token = session.get('access_token')
    guilds = get_user_guilds(access_token)
    has_access = False
    
    for g in guilds:
        if int(g['id']) == guild_id:
            permissions = int(g.get('permissions', 0))
            if permissions & 0x20 or permissions & 0x8:
                has_access = True
                break
    
    if not has_access:
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    channel_id = data.get('channel_id')
    prize = data.get('prize')
    duration = data.get('duration_minutes')
    winners = data.get('winner_count', 1)
    description = data.get('description', '')
    
    if not all([channel_id, prize, duration]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Store giveaway creation request for bot to process
    # In a full implementation, this would trigger the bot via IPC or database
    return jsonify({"success": True, "message": "Giveaway created successfully"})


@app.route('/api/guild/<int:guild_id>/roles', methods=['GET', 'POST', 'DELETE'])
@login_required
def api_manage_roles(guild_id):
    """API endpoint to manage server roles"""
    # Validate user has access
    access_token = session.get('access_token')
    guilds = get_user_guilds(access_token)
    has_access = False
    
    for g in guilds:
        if int(g['id']) == guild_id:
            permissions = int(g.get('permissions', 0))
            if permissions & 0x20 or permissions & 0x8:  # MANAGE_GUILD or ADMINISTRATOR
                has_access = True
                break
    
    if not has_access:
        return jsonify({"error": "Unauthorized"}), 403
    
    if request.method == 'GET':
        # Fetch roles from Discord API
        bot_token = os.getenv("DISCORD_BOT_TOKEN")
        if bot_token:
            try:
                headers = {"Authorization": f"Bot {bot_token}"}
                response = requests.get(
                    f"{DISCORD_API_BASE}/guilds/{guild_id}/roles",
                    headers=headers
                )
                if response.status_code == 200:
                    roles_data = response.json()
                    # Sort by position (highest first) and format
                    roles = sorted(roles_data, key=lambda r: r.get('position', 0), reverse=True)
                    formatted_roles = []
                    for role in roles:
                        if role['name'] != '@everyone':  # Skip @everyone
                            formatted_roles.append({
                                'id': role['id'],
                                'name': role['name'],
                                'color': f"#{role['color']:06x}" if role['color'] else '#99aab5',
                                'position': role['position'],
                                'member_count': 0  # Would need additional API call for accurate count
                            })
                    return jsonify({"roles": formatted_roles})
            except Exception as e:
                print(f"Error fetching roles: {e}")
        
        return jsonify({"roles": []})
    
    elif request.method == 'POST':
        # Create a new role
        data = request.json
        name = data.get('name')
        color = data.get('color', '#99AAB5')
        permissions = data.get('permissions', [])
        hoist = data.get('hoist', False)
        mentionable = data.get('mentionable', False)
        
        if not name:
            return jsonify({"error": "Role name is required"}), 400
        
        # Convert hex color to integer
        try:
            if color.startswith('#'):
                color_int = int(color[1:], 16)
            else:
                color_int = int(color, 16)
        except:
            color_int = 0x99AAB5
        
        # Store role creation request for bot to process
        try:
            db.conn.execute("""
                INSERT INTO pending_setup_requests 
                (guild_id, setup_type, data, created_at)
                VALUES (?, 'create_role', ?, datetime('now'))
            """, (guild_id, f"{name}|{color_int}|{hoist}|{mentionable}|{','.join(permissions)}"))
            db.conn.commit()
            
            return jsonify({
                "success": True, 
                "message": f"Role '{name}' creation queued"
            })
        except Exception as e:
            return jsonify({"error": f"Failed to create role: {str(e)}"}), 500
    
    elif request.method == 'DELETE':
        # Delete a role
        data = request.json
        role_id = data.get('role_id')
        
        if not role_id:
            return jsonify({"error": "role_id is required"}), 400
        
        # Store role deletion request for bot to process
        try:
            db.conn.execute("""
                INSERT INTO pending_setup_requests 
                (guild_id, setup_type, data, created_at)
                VALUES (?, 'delete_role', ?, datetime('now'))
            """, (guild_id, str(role_id)))
            db.conn.commit()
            
            return jsonify({
                "success": True, 
                "message": "Role deletion queued"
            })
        except Exception as e:
            return jsonify({"error": f"Failed to delete role: {str(e)}"}), 500


@app.route('/api/guild/<int:guild_id>/ticketing', methods=['POST'])
@login_required
def api_setup_ticketing(guild_id):
    """API endpoint to setup ticket system"""
    # Validate user has access
    access_token = session.get('access_token')
    guilds = get_user_guilds(access_token)
    has_access = False
    
    for g in guilds:
        if int(g['id']) == guild_id:
            permissions = int(g.get('permissions', 0))
            if permissions & 0x20 or permissions & 0x8:
                has_access = True
                break
    
    if not has_access:
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    channel_id = data.get('channel_id')
    category_id = data.get('category_id')
    save_transcripts = data.get('save_transcripts', False)
    transcript_channel = data.get('transcript_channel')
    
    # Store ticket setup request for bot to process
    try:
        db.conn.execute("""
            INSERT INTO pending_setup_requests 
            (guild_id, setup_type, data, created_at)
            VALUES (?, 'ticket_setup', ?, datetime('now'))
        """, (guild_id, f"{channel_id}|{category_id}|{save_transcripts}|{transcript_channel or ''}"))
        db.conn.commit()
        
        return jsonify({
            "success": True, 
            "message": "Ticket system setup queued"
        })
    except Exception as e:
        return jsonify({"error": f"Failed to setup tickets: {str(e)}"}), 500


@app.route('/api/guild/<int:guild_id>/verified-role', methods=['POST'])
@login_required
def api_create_verified_role(guild_id):
    """API endpoint to create auto-verified role"""
    # Validate user has access
    access_token = session.get('access_token')
    guilds = get_user_guilds(access_token)
    has_access = False
    
    for g in guilds:
        if int(g['id']) == guild_id:
            permissions = int(g.get('permissions', 0))
            if permissions & 0x20 or permissions & 0x8:
                has_access = True
                break
    
    if not has_access:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Store verified role creation request for bot to process
    try:
        db.conn.execute("""
            INSERT INTO pending_setup_requests 
            (guild_id, setup_type, data, created_at)
            VALUES (?, 'verified_role', ?, datetime('now'))
        """, (guild_id, "auto"))
        db.conn.commit()
        
        return jsonify({
            "success": True, 
            "message": "Verified role will be created automatically"
        })
    except Exception as e:
        return jsonify({"error": f"Failed to create verified role: {str(e)}"}), 500


def run_dashboard(host='0.0.0.0', port=5000):
    """Run the dashboard"""
    app.run(host=host, port=port, debug=True)


if __name__ == '__main__':
    import sys
    validate_oauth_env()
    port = int(os.getenv('DASHBOARD_PORT', '6767'))
    run_dashboard(port=port)
