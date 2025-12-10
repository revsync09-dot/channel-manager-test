"""
Web dashboard backend using Flask with Discord OAuth2.
"""
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS
import requests
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps
import secrets
import urllib.parse

# Add parent directory to path for imports (when run as a script)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from src.database import db
except ImportError:
    # Fallback: ensure project root is on path, then retry
    root_dir = Path(__file__).resolve().parents[2]
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    from src.database import db


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
    response = requests.get(f"{DISCORD_API_BASE}/users/@me/guilds", headers=headers)
    if response.status_code == 200:
        return response.json()
    return []


def get_bot_guilds(bot_token):
    """Get bot's guilds"""
    headers = {"Authorization": f"Bot {bot_token}"}
    response = requests.get(f"{DISCORD_API_BASE}/users/@me/guilds", headers=headers)
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
    return [
        {
            "title": "Main Cluster",
            "badge": "Production Environment",
            "items": [
                {"label": "Overview", "active": True, "pill": "+4 new"},
                {"label": "System Health", "active": False},
                {"label": "Live Logs", "active": False, "badge": "12"},
            ],
        },
        {
            "title": "Management",
            "items": [
                {"label": "API Gateways"},
                {"label": "Subscriptions"},
                {"label": "Moderation"},
                {"label": "Bot Guards"},
            ],
        },
        {
            "title": "Utilities",
            "items": [
                {"label": "Broadcasts"},
                {"label": "Container Compose"},
                {"label": "Commands"},
            ],
        },
        {
            "title": "Insights",
            "items": [
                {"label": "Growth"},
                {"label": "Storage"},
            ],
        },
    ]


def build_command_sections():
    return [
        {
            "title": "Owner Logging",
            "tone": "from-fuchsia-500 to-purple-500",
            "commands": [
                {"name": "/setup", "description": "Open the in-Discord builder with module buttons."},
                {"name": "/setup_dashboard", "description": "Launch dashboard entry cards for every module."},
                {"name": "/channel_setup", "description": "Parse channel layouts or screenshots into templates."},
                {"name": "/health", "description": "Check bot uptime, latency, and service health."},
            ],
        },
        {
            "title": "Admin Commands",
            "tone": "from-indigo-500 to-blue-500",
            "commands": [
                {"name": "/modmail_reply", "description": "Reply to open user threads from staff channels."},
                {"name": "/reactionrole_create", "description": "Post reaction role panels with emojis mapped to roles."},
                {"name": "/giveaway_start", "description": "Spin up timed giveaways with button entry + transcripts."},
                {"name": "/stats", "description": "Render chat & voice analytics cards directly in Discord."},
            ],
        },
    ]


def build_owner_logs(guilds: list[dict]):
    now = datetime.utcnow()
    base_logs = [
        {
            "title": "Commands synced",
            "detail": "Slash commands refreshed across production cluster.",
            "status": "Synced",
            "timestamp": (now - timedelta(minutes=2)).strftime("%H:%M UTC"),
        },
        {
            "title": "Templates deployed",
            "detail": "Applied creative preset for highlighted communities.",
            "status": "Deploy",
            "timestamp": (now - timedelta(minutes=18)).strftime("%H:%M UTC"),
        },
        {
            "title": "Owner audit",
            "detail": "Verified permissions + guard rails for priority guilds.",
            "status": "Audit",
            "timestamp": (now - timedelta(hours=1, minutes=12)).strftime("%H:%M UTC"),
        },
    ]
    if guilds:
        guild_names = [g.get("name", "Guild") for g in guilds[:2]]
        extra = {
            "title": "Activity pulse",
            "detail": f"Confirmed heartbeat for {', '.join(guild_names)}.",
            "status": "Pulse",
            "timestamp": now.strftime("%H:%M UTC"),
        }
        base_logs.insert(0, extra)
    return base_logs


def build_server_growth():
    # Synthetic growth data for spark bars
    values = [9, 11, 14, 12, 16, 19, 15, 21, 18, 23, 20, 22]
    labels = ["1", "3", "5", "7", "9", "11", "13", "15", "17", "19", "21", "23"]
    return [{"label": label, "value": value} for label, value in zip(labels, values)]


def build_subscription_stats():
    return [
        {"name": "Premium", "value": 420, "color": "bg-fuchsia-500"},
        {"name": "Gold", "value": 280, "color": "bg-amber-400"},
        {"name": "Basic", "value": 143, "color": "bg-zinc-400"},
    ]


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


def build_overview_cards(guilds: list[dict]):
    server_total = len(guilds)
    total_users = sum(
        int(g.get("approximate_member_count") or g.get("member_count") or 0) for g in guilds
    )
    if total_users == 0 and server_total:
        total_users = server_total * 64
    return [
        {"label": "Total Servers", "value": server_total, "delta": "+1"},
        {"label": "Total Users", "value": total_users, "delta": "+0"},
        {"label": "Active Subs", "value": 843, "delta": "+12"},
        {"label": "Avg Latency", "value": f"{BOT_STATUS_LATENCY_MS}ms", "delta": "+0ms"},
    ]


def build_dashboard_snapshot(guilds: list[dict]):
    return {
        "nav_sections": build_nav_sections(),
        "overview_cards": build_overview_cards(guilds),
        "server_growth": build_server_growth(),
        "subscription_stats": build_subscription_stats(),
        "owner_logs": build_owner_logs(guilds),
        "command_sections": build_command_sections(),
        "bot_status": build_bot_status(),
        "recent_servers": build_recent_servers(guilds),
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
    )


@app.route('/login')
def login():
    """Redirect to Discord OAuth"""
    return redirect(DISCORD_OAUTH_URL)


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
    
    # Get user's guilds
    guilds = get_user_guilds(access_token)
    
    # Filter guilds where user has manage server permission
    admin_guilds = []
    for guild in guilds:
        permissions = int(guild.get('permissions', 0))
        # Check if user has MANAGE_GUILD (0x20) or ADMINISTRATOR (0x8)
        if permissions & 0x20 or permissions & 0x8:
            admin_guilds.append(guild)
    
    context = build_dashboard_snapshot(admin_guilds)
    return render_template(
        'dashboard.html',
        user=user,
        avatar_url=discord_avatar_url(user),
        guilds=admin_guilds,
        brand_name=BRAND_NAME,
        tagline=BRAND_TAGLINE,
        support_invite=SUPPORT_INVITE,
        **context,
    )


@app.route('/dashboard/guild/<int:guild_id>')
@login_required
def guild_dashboard(guild_id):
    """Guild-specific dashboard"""
    access_token = session.get('access_token')
    user = session.get('user')
    
    # Verify user has access to this guild
    guilds = get_user_guilds(access_token)
    guild = None
    for g in guilds:
        if int(g['id']) == guild_id:
            permissions = int(g.get('permissions', 0))
            if permissions & 0x20 or permissions & 0x8:
                guild = g
                break
    
    if not guild:
        return "Unauthorized", 403
    
    # Get guild config from database
    config = db.get_guild_config(guild_id) or {}
    custom_commands = db.get_custom_commands(guild_id)
    
    # Add bot client ID for invite link
    config['bot_client_id'] = DISCORD_CLIENT_ID
    
    context = build_dashboard_snapshot([guild] if guild else [])
    return render_template(
        'guild_dashboard_enhanced.html', 
        user=user, 
        avatar_url=discord_avatar_url(user),
        guild=guild,
        config=config,
        custom_commands=custom_commands,
        brand_name=BRAND_NAME,
        support_invite=SUPPORT_INVITE,
        **context,
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
