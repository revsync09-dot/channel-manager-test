import asyncio
import json
import math
import os
import sqlite3
import sys
import urllib.parse
from datetime import datetime, timedelta
from typing import Any, Dict, List

import aiohttp
import base64
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from .modules.text_parser import parse_text_structure
from .modules.server_builder import build_server_from_template, create_roles, template_from_guild
from .modules.ticket_system import handle_ticket_select, send_ticket_panel_to_channel
from .modules.verify_system import (
    init_verify_state,
    handle_verify_button,
    post_verify_panel,
    update_verify_config,
    get_verify_config,
    build_verify_embed,
)
from .modules.giveaway import init_giveaway, handle_giveaway_button, start_giveaway, end_giveaway_command as end_gw_command
from .modules.change_logger import start_change_logger, stop_change_logger
from .modules.modmail import init_modmail, setup_modmail_commands
from .modules.reaction_roles import init_reaction_roles, setup_reaction_role_commands
from .modules.moderation import setup_moderation_commands
from .modules.custom_commands import init_custom_commands, setup_custom_command_commands
from .modules.economy import init_economy
from .modules.leveling import init_leveling
from .modules.image_analyzer import analyze_image_stub
from .database import db

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
EMBED_COLOR = 0x22C55E
RULES_ACCENT_COLOR = 0x9C66FF  # Purple accent similar to screenshot
EMBED_THUMB = (
    "https://media.discordapp.net/attachments/1443222738750668952/1446618834638471259/Channel-manager.png"
)
BRAND_LOGO_URL = os.getenv(
    "DASHBOARD_LOGO_URL",
    "https://cdn.discordapp.com/attachments/1443222738750668952/1448482674477105362/image.png?ex=693b6c1d&is=693a1a9d&hm=ff31f492a74f0315498dee8ee26fa87b8512ddbee617f4bccda1161f59c8cb49&",
)
MAX_CHANNELS = 500
MAX_ROLES = 200
STARTED_AT = discord.utils.utcnow()
RULES_DEFAULT = {
    "titleText": "Server Rules",
    "welcomeTitle": "Welcome!",
    "welcomeBody": (
        "Thanks for being here. These rules are the basics for keeping things safe, friendly, and fun for everyone."
    ),
    "descriptionText": (
        "If something isn’t covered below, staff may apply common-sense judgment to protect the community. "
        "Questions or concerns? Ask the team before it becomes an issue."
    ),
    "categories": [
        {
            "emoji": "\U0001F4D8",
            "color": "red",
            "title": "General Guidelines",
            "description": (
                "Be kind and on-topic. No spam/NSFW/hate speech. Follow staff direction and use the right channels."
            ),
        },
        {
            "emoji": "\U0001F7E9",
            "color": "green",
            "title": "Minor Offenses",
            "description": (
                "- Light spam or emoji flooding\n- Off-topic messages\n- Mild language/low-effort trolling\n"
                "Likely: warning or short mute."
            ),
        },
        {
            "emoji": "\U0001F7E7",
            "color": "orange",
            "title": "Moderate Offenses",
            "description": (
                "- Advertising without permission\n- Impersonation\n- Ignoring staff direction\n- Disturbing content\n"
                "Likely: timeout, mute, or kick."
            ),
        },
        {
            "emoji": "\U0001F7E5",
            "color": "red",
            "title": "Major Offenses",
            "description": (
                "- Hate/harassment/threats\n- Doxxing/personal info\n- Severe NSFW/illegal content\n- Raid/ban evasion\n"
                "Likely: ban and report to Discord."
            ),
        },
    ],
    "bannerUrl": None,
    "footerText": None,
}
RULES_STATE: dict[int, dict] = {}
CHAT_MINUTES_PER_MESSAGE = 1
VOICE_SESSION_STARTS: dict[tuple[int, int], datetime] = {}
STATS_EMBED_COLOR = 0x2F3136
QUICKCHART_CREATE_URL = "https://quickchart.io/chart/create"
STAT_WINDOW_DAYS = 30

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)
bot.db = db


async def process_pending_setups():
    """Background task to process pending setup requests from dashboard"""
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        try:
            # Check for pending setup requests
            conn = sqlite3.connect(db.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, guild_id, setup_type, data 
                FROM pending_setup_requests 
                WHERE processed = 0
            """)
            
            requests = cursor.fetchall()
            
            for request_id, guild_id, setup_type, data in requests:
                guild = bot.get_guild(guild_id)
                if not guild:
                    # Mark as processed even if guild not found
                    cursor.execute("UPDATE pending_setup_requests SET processed = 1 WHERE id = ?", (request_id,))
                    conn.commit()
                    continue
                
                if setup_type == 'leveling':
                    try:
                        # Parse data: "5,10,20|1|0" -> milestones, create_info, create_rules
                        parts = data.split('|')
                        milestones_str = parts[0]
                        create_info = bool(int(parts[1])) if len(parts) > 1 else True
                        create_rules = bool(int(parts[2])) if len(parts) > 2 else False
                        
                        # Parse milestones
                        milestones = [int(m.strip()) for m in milestones_str.split(',')]
                        
                        # Import leveling module functions
                        from modules.leveling import create_leveling_roles, create_leveling_info_channel, create_rules_info_channel
                        
                        # Create roles
                        await create_leveling_roles(guild, milestones, bot.leveling, bot)
                        
                        # Create channels if requested
                        if create_info:
                            await create_leveling_info_channel(guild, bot)
                        if create_rules:
                            await create_rules_info_channel(guild)
                        
                        # Mark as processed
                        cursor.execute("UPDATE pending_setup_requests SET processed = 1 WHERE id = ?", (request_id,))
                        conn.commit()
                        
                        print(f"✅ Processed leveling setup for guild {guild_id}")
                    except Exception as e:
                        print(f"❌ Error processing leveling setup for guild {guild_id}: {e}")
                        # Mark as processed to avoid infinite retries
                        cursor.execute("UPDATE pending_setup_requests SET processed = 1 WHERE id = ?", (request_id,))
                        conn.commit()
                
                elif setup_type == 'create_role':
                    try:
                        # Parse data: "name|color_int|hoist|mentionable|permissions"
                        parts = data.split('|')
                        name = parts[0]
                        color_int = int(parts[1]) if len(parts) > 1 else 0x99AAB5
                        hoist = parts[2] == 'True' if len(parts) > 2 else False
                        mentionable = parts[3] == 'True' if len(parts) > 3 else False
                        
                        # Create role
                        role = await guild.create_role(
                            name=name,
                            color=discord.Color(color_int),
                            hoist=hoist,
                            mentionable=mentionable,
                            reason="Created via dashboard"
                        )
                        
                        cursor.execute("UPDATE pending_setup_requests SET processed = 1 WHERE id = ?", (request_id,))
                        conn.commit()
                        print(f"✅ Created role '{name}' for guild {guild_id}")
                    except Exception as e:
                        print(f"❌ Error creating role for guild {guild_id}: {e}")
                        cursor.execute("UPDATE pending_setup_requests SET processed = 1 WHERE id = ?", (request_id,))
                        conn.commit()
                
                elif setup_type == 'delete_role':
                    try:
                        role_id = int(data)
                        role = guild.get_role(role_id)
                        if role:
                            await role.delete(reason="Deleted via dashboard")
                            print(f"✅ Deleted role {role_id} from guild {guild_id}")
                        
                        cursor.execute("UPDATE pending_setup_requests SET processed = 1 WHERE id = ?", (request_id,))
                        conn.commit()
                    except Exception as e:
                        print(f"❌ Error deleting role for guild {guild_id}: {e}")
                        cursor.execute("UPDATE pending_setup_requests SET processed = 1 WHERE id = ?", (request_id,))
                        conn.commit()
                
                elif setup_type == 'verified_role':
                    try:
                        # Create a verified role with appropriate permissions
                        role = await guild.create_role(
                            name="✅ Verified",
                            color=discord.Color(0x43B581),  # Green
                            hoist=False,
                            mentionable=False,
                            reason="Auto-created verified role"
                        )
                        
                        # Store in config for verification system
                        config = db.get_guild_config(guild_id) or {}
                        config['verified_role_id'] = role.id
                        db.update_guild_config(guild_id, config)
                        
                        cursor.execute("UPDATE pending_setup_requests SET processed = 1 WHERE id = ?", (request_id,))
                        conn.commit()
                        print(f"✅ Created verified role for guild {guild_id}")
                    except Exception as e:
                        print(f"❌ Error creating verified role for guild {guild_id}: {e}")
                        cursor.execute("UPDATE pending_setup_requests SET processed = 1 WHERE id = ?", (request_id,))
                        conn.commit()
                
                elif setup_type == 'ticket_setup':
                    try:
                        # Parse data: "channel_id|category_id|save_transcripts|transcript_channel"
                        parts = data.split('|')
                        panel_channel_id = int(parts[0]) if parts[0] else None
                        category_id = int(parts[1]) if len(parts) > 1 and parts[1] else None
                        
                        if panel_channel_id:
                            from modules.ticket_system import send_ticket_panel_to_channel
                            channel = guild.get_channel(panel_channel_id)
                            if channel:
                                # Send ticket panel
                                await send_ticket_panel_to_channel(bot, channel)
                        
                        # Store config
                        if category_id:
                            config = db.get_guild_config(guild_id) or {}
                            config['ticket_category_id'] = category_id
                            db.update_guild_config(guild_id, config)
                        
                        cursor.execute("UPDATE pending_setup_requests SET processed = 1 WHERE id = ?", (request_id,))
                        conn.commit()
                        print(f"✅ Setup ticket system for guild {guild_id}")
                    except Exception as e:
                        print(f"❌ Error setting up tickets for guild {guild_id}: {e}")
                        cursor.execute("UPDATE pending_setup_requests SET processed = 1 WHERE id = ?", (request_id,))
                        conn.commit()
            
            conn.close()
        except Exception as e:
            print(f"Error in process_pending_setups: {e}")
        
        # Check every 10 seconds
        await asyncio.sleep(10)


@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
    except Exception:
        pass
    print(f"Bot logged in as {bot.user}")
    
    # Store app info for owner checks
    bot._app_info = await bot.application_info()
    
    bot._change_observer = start_change_logger(bot)
    init_verify_state(bot)
    init_giveaway(bot)
    init_modmail(bot)
    init_reaction_roles(bot)
    init_custom_commands(bot)
    init_economy(bot)
    init_leveling(bot)
    setup_modmail_commands(bot)
    setup_reaction_role_commands(bot)
    setup_moderation_commands(bot)
    setup_custom_command_commands(bot)
    await send_ticket_panel_to_channel(bot)
    
    # Start background task for processing dashboard requests
    bot.loop.create_task(process_pending_setups())
    
    print("✅ All modules loaded successfully!")
    print(f"💰 Economy system enabled")
    print(f"📊 Leveling system enabled")
    print(f"🔄 Dashboard request processor started")
    print(f"🌐 Dashboard: Run the web dashboard separately with 'python -m src.web.dashboard'")


@bot.event
async def on_disconnect():
    observer = getattr(bot, "_change_observer", None)
    if observer:
        stop_change_logger(observer)


@bot.event
async def on_guild_join(guild: discord.Guild):
    try:
        owner = guild.owner or await guild.fetch_owner()
        bot_name = bot.user.name if bot.user else "Channel Manager"
        embed = discord.Embed(
            title=f"Thank you for adding {bot_name} ⚡ to {guild.name}!",
            description="Get ready to upgrade moderation, automation und dashboard workflows.",
            color=EMBED_COLOR,
        )
        embed.set_thumbnail(url=EMBED_THUMB)
        embed.add_field(
            name="🕹️ How to Interact",
            value=(
                f"• Mention me: @{bot_name}⚡ followed by your question.\n"
                "• Use the prefix `bb` plus your prompt (e.g., `bb hello`).\n"
                "• Reply to one of my answers so the conversation keeps context."
            ),
            inline=False,
        )
        embed.add_field(
            name="🛡️ Core Systems",
            value=(
                "• ĐY'ª Modmail: Private threads between users and staff with transcript history.\n"
                "• ĐYZđ Reaction Roles: Set auto-roles per emoji panel using `/reactionrole_*` commands.\n"
                "• ĐY\"ù Moderation: Kick, ban, timeout, warn, purge, slowmode + logging with `/modlog`.\n"
                "• ƒsT‹÷? Custom Commands: Build commands with `{user}`, `{server}`, `{channel}` variables."
            ),
            inline=False,
        )
        embed.add_field(
            name="⚙️ Automation & Growth",
            value=(
                "• ĐY'ø Economy: Custom currency, daily rewards, pay/transfer, leaderboard + admin tools.\n"
                "• ĐY\"S Leveling: XP per message, level role rewards, rank announcements and quick setup.\n"
                "• ĐYZ% Giveaways & Tickets: Timed giveaways, entries with ĐYZ%, plus ticket panels and transcripts."
            ),
            inline=False,
        )
        embed.add_field(
            name="🌐 Dashboard & Templates",
            value=(
                "• Secure Discord OAuth login with server-specific config.\n"
                "• Server templates (Gaming, Community, Support, Creative) plus Embed maker + Announcements.\n"
                "• Real-time moderation, welcome/leave messages, auto-roles und prefix settings."
            ),
            inline=False,
        )
        embed.set_footer(text="Channel Manager · CHECK `README.md` für Details + `FEATURES.md` für alle Systeme")
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Support Server",
                style=discord.ButtonStyle.link,
                url="https://discord.gg/zjr3Umcu",
            )
        )
        await owner.send(embed=embed, view=view)
    except Exception:
        return


@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        handled_ticket = await handle_ticket_select(interaction)
        if handled_ticket:
            return
        handled_verify = await handle_verify_button(interaction)
        if handled_verify:
            return
        handled_gw = await handle_giveaway_button(interaction)
        if handled_gw:
            return


@bot.event
async def on_message(message: discord.Message):
    if not message.guild or message.author.bot:
        return
    _record_message_activity(message)
    config = get_verify_config(message.guild.id)
    verify_role_id = config.get("verifiedRole")
    unverified_role_id = config.get("unverifiedRole")
    member = message.author if isinstance(message.author, discord.Member) else None
    if not member:
        return
    if any(str(r.id) == str(verify_role_id) for r in member.roles):
        return
    bot_member = message.guild.me
    if not bot_member:
        return
    perms = message.channel.permissions_for(bot_member)
    if perms.manage_messages:
        try:
            await message.delete()
        except Exception:
            pass
    try:
        notify = await message.channel.send(
            f"{message.author.mention}, please verify first using /verify to get access."
        )
        await asyncio.sleep(5)
        await notify.delete()
    except Exception:
        return


def _record_message_activity(message: discord.Message) -> None:
    if not message.guild or message.author.bot:
        return
    try:
        activity_date = message.created_at.date().isoformat()
        db.record_user_activity(
            message.guild.id,
            message.author.id,
            chat_minutes=CHAT_MINUTES_PER_MESSAGE,
            activity_date=activity_date,
        )
    except Exception:  # pragma: no cover
        print("Failed to record chat activity for", message.author.id, "in", message.guild.id)
        return


@bot.event
async def on_member_join(member: discord.Member):
    config = get_verify_config(member.guild.id)
    unverified_role_id = config.get("unverifiedRole")
    if unverified_role_id and str(unverified_role_id).isdigit():
        role = member.guild.get_role(int(unverified_role_id))
        if role:
            try:
                await member.add_roles(role, reason="Auto assign unverified role on join")
            except Exception:
                pass


def _commit_voice_session(guild_id: int, user_id: int, start: datetime, end: datetime) -> None:
    duration = (end - start).total_seconds()
    if duration <= 0:
        return
    minutes = max(1, math.ceil(duration / 60))
    db.record_user_activity(
        guild_id,
        user_id,
        voice_minutes=minutes,
        activity_date=start.date().isoformat(),
    )


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member.bot:
        return
    guild = member.guild
    if not guild:
        return
    key = (guild.id, member.id)
    now = discord.utils.utcnow()
    before_channel = before.channel
    after_channel = after.channel
    if before_channel is None and after_channel is not None:
        VOICE_SESSION_STARTS[key] = now
        return
    if before_channel is not None and after_channel is None:
        start = VOICE_SESSION_STARTS.pop(key, None)
        if start:
            _commit_voice_session(guild.id, member.id, start, now)
        return
    if before_channel and after_channel and before_channel.id != after_channel.id:
        start = VOICE_SESSION_STARTS.pop(key, None)
        if start:
            _commit_voice_session(guild.id, member.id, start, now)
        VOICE_SESSION_STARTS[key] = now


# helper used by rule commands
async def _is_owner_or_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    owner_id = interaction.guild.owner_id
    if not owner_id:
        try:
            owner = await interaction.guild.fetch_owner()
            owner_id = owner.id
        except Exception:
            owner_id = None
    if owner_id == interaction.user.id:
        return True
    member = interaction.user if isinstance(interaction.user, discord.Member) else await interaction.guild.fetch_member(interaction.user.id)
    if member and member.guild_permissions.administrator:
        return True
    app_info = getattr(bot, '_app_info', None)
    if app_info and hasattr(app_info, 'owner'):
        if app_info.owner and app_info.owner.id == interaction.user.id:
            return True
        if hasattr(app_info, 'team') and app_info.team:
            return any(m.id == interaction.user.id for m in app_info.team.members)
    return False


class RulesView(discord.ui.View):
    def __init__(self, config: dict):
        super().__init__(timeout=None)
        self.add_item(RulesSelect(config))


class RulesSelect(discord.ui.Select):
    def __init__(self, config: dict):
        options = []
        for index, item in enumerate(config.get("categories", [])):
            emoji_val = _safe_emoji(item.get("emoji"))
            opt_kwargs = {
                "label": item.get("title", "Item"),
                "description": item.get("description", "")[:100],
                "value": str(index),
            }
            if emoji_val:
                opt_kwargs["emoji"] = emoji_val
            options.append(discord.SelectOption(**opt_kwargs))
        if not options:
            options.append(discord.SelectOption(label="No categories set", value="0"))
        super().__init__(placeholder="Make a selection", min_values=1, max_values=1, options=options, custom_id="rules-select")
        self.config = config

    async def callback(self, interaction: discord.Interaction):
        choice_index = int(self.values[0])
        detail_embed = _build_rules_detail(choice_index, self.config)
        await interaction.response.send_message(embed=detail_embed, ephemeral=True)


class RulesTextModal(discord.ui.Modal, title="Update Rules Texts"):
    def __init__(self, config: dict):
        super().__init__(timeout=None)
        self.title_input = discord.ui.TextInput(
            label="Title",
            custom_id="rules_title",
            default=config.get("titleText", "Server Rules"),
            max_length=100,
        )
        self.welcome_input = discord.ui.TextInput(
            label="Welcome line",
            custom_id="rules_welcome",
            default=config.get("welcomeTitle", "Welcome!"),
            max_length=100,
        )
        self.body_input = discord.ui.TextInput(
            label="Welcome body",
            custom_id="rules_body",
            style=discord.TextStyle.long,
            default=config.get("welcomeBody", "")[:400],
            max_length=400,
        )
        self.desc_input = discord.ui.TextInput(
            label="Notes paragraph",
            custom_id="rules_desc",
            style=discord.TextStyle.long,
            default=config.get("descriptionText", "")[:400],
            max_length=400,
        )
        self.add_item(self.title_input)
        self.add_item(self.welcome_input)
        self.add_item(self.body_input)
        self.add_item(self.desc_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        config = _get_rules_config(interaction.guild_id)
        config.update(
            {
                "titleText": str(self.title_input),
                "welcomeTitle": str(self.welcome_input),
                "welcomeBody": str(self.body_input),
                "descriptionText": str(self.desc_input),
            }
        )
        _set_rules_config(interaction.guild_id, config)
        await interaction.response.send_message("Rules texts updated.", ephemeral=True)


class RulesBulkModal(discord.ui.Modal, title="Update up to 5 rules"):
    def __init__(self):
        super().__init__(timeout=None)
        self.rule1 = discord.ui.TextInput(label="Rule 1 (Title | Description)", required=False, max_length=300)
        self.rule2 = discord.ui.TextInput(label="Rule 2 (Title | Description)", required=False, max_length=300)
        self.rule3 = discord.ui.TextInput(label="Rule 3 (Title | Description)", required=False, max_length=300)
        self.rule4 = discord.ui.TextInput(label="Rule 4 (Title | Description)", required=False, max_length=300)
        self.rule5 = discord.ui.TextInput(label="Rule 5 (Title | Description)", required=False, max_length=300)
        for item in (self.rule1, self.rule2, self.rule3, self.rule4, self.rule5):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return
        entries = [self.rule1, self.rule2, self.rule3, self.rule4, self.rule5]
        palette = ["\U0001F7E6", "\U0001F7E9", "\U0001F7E7", "\U0001F7E5", "\U0001F7EA"]
        categories = []
        for idx, entry in enumerate(entries):
            text = str(entry).strip()
            if not text:
                continue
            parts = text.split("|", 1)
            title = parts[0].strip()[:100] if parts else f"Rule {idx+1}"
            description = parts[1].strip()[:500] if len(parts) > 1 else "Details for this rule."
            categories.append(
                {
                    "emoji": palette[idx % len(palette)],
                    "color": "red",
                    "title": title or f"Rule {idx+1}",
                    "description": description,
                }
            )
        if not categories:
            await interaction.response.send_message("No rules provided.", ephemeral=True)
            return
        config = _get_rules_config(interaction.guild_id)
        config["categories"] = categories
        _set_rules_config(interaction.guild_id, config)
        await interaction.response.send_message(f"Updated {len(categories)} rules.", ephemeral=True)


SETUP_COMMAND_GROUPS = {
    "server": {
        "label": "Server Setup & Utilities",
        "emoji": "🧱",
        "description": "Templates, cleanup helpers, dashboards, and diagnostics.",
        "commands": [
            ("/setup", "Open this in-Discord module panel."),
            ("/setup_dashboard", "Open the dashboard and module buttons."),
            ("/channel_setup", "Parse text or screenshot layouts into templates."),
            ("/help", "Show channel builder + text import snippets."),
            ("/health", "Check bot status, uptime, and latency."),
            ("/stats", "Recent chat + voice stats (per guild)."),
            ("/sync", "Force slash-command sync (Admin only)."),
            ("/delete_channel", "Danger: remove all channels/categories."),
            ("/delete_roles", "Danger: remove custom roles below the bot."),
        ],
    },
    "moderation": {
        "label": "Moderation & Safety",
        "emoji": "🛡️",
        "description": "Core moderation commands handled by the bot.",
        "commands": [
            ("/kick", "Kick a member with optional reason."),
            ("/ban", "Ban + optionally prune recent messages."),
            ("/unban", "Remove a ban via user ID."),
            ("/timeout", "Timeout a member for a duration."),
            ("/untimeout", "Clear any active timeout."),
            ("/warn", "Issue a warning with a reason."),
            ("/warnings", "List warnings for a member."),
            ("/clearwarnings", "Remove all warnings for a member."),
            ("/purge", "Bulk-delete a number of messages."),
            ("/slowmode", "Set channel slowmode seconds."),
            ("/modlog", "Configure the moderation log channel."),
        ],
    },
    "tickets": {
        "label": "Tickets & Modmail",
        "emoji": "🎫",
        "description": "Support workflows for tickets and inboxes.",
        "commands": [
            ("/ticket", "Create a ticket channel for a category."),
            ("/ticket_close", "Close a ticket with optional reason."),
            ("/ticket_setup", "Post/setup the ticket panel."),
            ("/modmail_reply", "Reply to an active modmail thread."),
            ("/modmail_close", "Close the current modmail thread."),
            ("/modmail_contact", "Start a modmail with a member."),
        ],
    },
    "verification": {
        "label": "Verification & Rules",
        "emoji": "✅",
        "description": "Keep onboarding tidy with buttons + dropdowns.",
        "commands": [
            ("/verify", "Post the verification panel."),
            ("/verify_setup", "Owner/admin setup for roles + banners."),
            ("/verify_post", "Send verify panel to a channel."),
            ("/verify_role", "Pick verified/unverified roles."),
            ("/rules", "Post rules panel with dropdown selector."),
            ("/rules_setup", "Configure rules text, banners, and colors."),
        ],
    },
    "giveaways": {
        "label": "Giveaways",
        "emoji": "🎉",
        "description": "Schedule, draw, and archive giveaways.",
        "commands": [
            ("/giveaway_start", "Start a giveaway (duration, winners, prize)."),
            ("/giveaway_end", "Force-end a giveaway and show transcript."),
        ],
    },
    "custom_roles": {
        "label": "Custom Commands & Roles",
        "emoji": "🎭",
        "description": "Flexible automations for text triggers and roles.",
        "commands": [
            ("/customcmd_create", "Add a custom command response."),
            ("/customcmd_edit", "Update an existing custom command."),
            ("/customcmd_delete", "Remove a custom command."),
            ("/customcmd_list", "List all custom commands."),
            ("/customcmd_info", "Inspect a specific custom command."),
            ("/reactionrole_create", "Create a reaction-role panel."),
            ("/reactionrole_add", "Add a role/emoji to a panel."),
            ("/reactionrole_remove", "Remove a role/emoji from a panel."),
            ("/reactionrole_list", "List configured reaction-role panels."),
        ],
    },
    "logging": {
        "label": "Logging & Extras",
        "emoji": "📜",
        "description": "Track changes and keep history tidy.",
        "commands": [
            ("/changelog_start", "Start logging changes into a channel."),
            ("/changelog_stop", "Stop change logging."),
        ],
    },
}


def _format_command_list(command_pairs):
    return "\n".join(f"- `{name}` — {desc}" for name, desc in command_pairs)


class SetupModulesActionView(discord.ui.View):
    """Interactive helper to show per-module command lists."""

    def __init__(self, author_id: int):
        super().__init__(timeout=240)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the user who opened this panel can use these buttons.", ephemeral=True
            )
            return False
        return True

    async def _send_group_embed(self, interaction: discord.Interaction, group_key: str):
        group = SETUP_COMMAND_GROUPS[group_key]
        embed = discord.Embed(
            title=f"{group['emoji']} {group['label']}",
            description=group["description"],
            color=EMBED_COLOR,
        )
        embed.add_field(name="Commands", value=_format_command_list(group["commands"]), inline=False)
        embed.set_footer(text="Run these slash commands directly in Discord to configure the module.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _send_all_commands(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Full Command Reference",
            description="Every major Channel Manager slash command grouped by module.",
            color=EMBED_COLOR,
        )
        for group in SETUP_COMMAND_GROUPS.values():
            embed.add_field(
                name=f"{group['emoji']} {group['label']}",
                value=_format_command_list(group["commands"]),
                inline=False,
            )
        embed.set_footer(text="Use /help for text import snippets any time.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Server Setup", style=discord.ButtonStyle.secondary, custom_id="setup_cmd_server")
    async def server_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send_group_embed(interaction, "server")

    @discord.ui.button(label="Moderation", style=discord.ButtonStyle.secondary, custom_id="setup_cmd_moderation")
    async def moderation_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send_group_embed(interaction, "moderation")

    @discord.ui.button(label="Verify & Rules", style=discord.ButtonStyle.secondary, custom_id="setup_cmd_verify")
    async def verification_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send_group_embed(interaction, "verification")

    @discord.ui.button(label="Giveaways", style=discord.ButtonStyle.secondary, custom_id="setup_cmd_giveaways")
    async def giveaways_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send_group_embed(interaction, "giveaways")

    @discord.ui.button(label="Tickets & Modmail", style=discord.ButtonStyle.secondary, row=1, custom_id="setup_cmd_tickets")
    async def tickets_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send_group_embed(interaction, "tickets")

    @discord.ui.button(label="Custom Cmds & Roles", style=discord.ButtonStyle.secondary, row=1, custom_id="setup_cmd_custom")
    async def custom_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send_group_embed(interaction, "custom_roles")

    @discord.ui.button(label="Logging & Extras", style=discord.ButtonStyle.secondary, row=1, custom_id="setup_cmd_logging")
    async def logging_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send_group_embed(interaction, "logging")

    @discord.ui.button(label="All Commands", style=discord.ButtonStyle.success, row=2, custom_id="setup_cmd_all")
    async def all_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send_all_commands(interaction)


class SetupDashboardView(discord.ui.View):
    """Buttons for the /setup_dashboard command."""

    def __init__(self, dashboard_url: str, author_id: int):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.add_item(
            discord.ui.Button(
                label="Open Dashboard",
                style=discord.ButtonStyle.link,
                url=dashboard_url,
            )
        )
        self.add_item(
            discord.ui.Button(
                label="Support Server",
                style=discord.ButtonStyle.link,
                url="https://discord.gg/zjr3Umcu",
            )
        )

    @discord.ui.button(label="/setup", style=discord.ButtonStyle.primary, custom_id="setup_dashboard_modules")
    async def modules_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the user who opened this panel can view it.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=_build_setup_modules_embed(),
            view=SetupModulesActionView(self.author_id),
            ephemeral=True,
        )


def _build_setup_modules_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Setup Modules Overview",
        description=(
            "Preview giveaway setup, text import, rules, verification, and tickets.\n"
            "Use the buttons below to open an in-Discord command reference for every module."
        ),
        color=EMBED_COLOR,
    )
    embed.set_thumbnail(url=EMBED_THUMB)
    embed.add_field(
        name="Giveaway Setup",
        value=(
            "- `/giveaway_start` and `/giveaway_end`\n"
            "- Dashboard timers, prize pools, and transcripts\n"
            "- Works with template buttons for seasonal drops"
        ),
        inline=False,
    )
    embed.add_field(
        name="Text Import Builder",
        value=(
            "- Paste layouts in **Dashboard -> Templates -> Text Import**\n"
            "- Use the snippet from `/setup` or `/setup_dashboard` to clone categories\n"
            "- Supports channel topics and hidden sections"
        ),
        inline=False,
    )
    embed.add_field(
        name="Verification & Rules",
        value=(
            "- `/verify`, `/verify_setup`, `/rules`, `/rules_setup`\n"
            "- Configure banners, roles, buttons, and dropdowns\n"
            "- Keeps verification clean with ephemeral replies"
        ),
        inline=False,
    )
    embed.add_field(
        name="Tickets, Modmail, Utilities",
        value=(
            "- Ticket workflows, escalation roles, and archives\n"
            "- Modmail routing and auto replies\n"
            "- Leveling, button roles, announcements, embeds"
        ),
        inline=False,
    )
    embed.set_footer(text="Tap /setup anytime for this overview and module buttons.")
    return embed


class ChannelSetupView(discord.ui.View):
    """Buttons for parsing text layouts or analyzing screenshots."""

    def __init__(self, author_id: int):
        super().__init__(timeout=240)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the user who opened this panel can use these buttons.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Paste Text Layout", style=discord.ButtonStyle.primary, custom_id="channel_setup_text")
    async def text_parser_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ChannelTextImportModal())

    @discord.ui.button(label="Analyze Image", style=discord.ButtonStyle.secondary, custom_id="channel_setup_image")
    async def image_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ChannelImageAnalyzeModal())


class ChannelTextImportModal(discord.ui.Modal, title="Channel Text Parser"):
    def __init__(self):
        super().__init__(timeout=None)
        self.layout_input = discord.ui.TextInput(
            label="Channel layout text",
            style=discord.TextStyle.long,
            placeholder="INFORMATION (category)\n  #announcements\n  #rules\n\nSUPPORT (category)\n  #help-desk",
            max_length=1900,
        )
        self.add_item(self.layout_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = str(self.layout_input).strip()
        if not raw:
            await interaction.response.send_message("No layout text provided.", ephemeral=True)
            return
        try:
            template = parse_text_structure(raw)
        except Exception as error:
            await interaction.response.send_message(f"Failed to parse text: {error}", ephemeral=True)
            return
        await _send_template_preview(interaction, "Text Parser", template)


class ChannelImageAnalyzeModal(discord.ui.Modal, title="Analyze Channel Screenshot"):
    def __init__(self):
        super().__init__(timeout=None)
        self.url_input = discord.ui.TextInput(
            label="Image URL",
            placeholder="https://example.com/server-layout.png",
            max_length=300,
        )
        self.add_item(self.url_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        url = str(self.url_input).strip()
        if not url:
            await interaction.response.send_message("Provide an image URL to analyze.", ephemeral=True)
            return
        loop = asyncio.get_running_loop()
        template = await loop.run_in_executor(None, analyze_image_stub, url)
        await _send_template_preview(interaction, "Image Analyzer", template)


def _build_template_preview_embed(source_label: str, template: Dict[str, Any]) -> discord.Embed:
    categories = template.get("categories") or []
    roles = template.get("roles") or []
    total_channels = sum(len(cat.get("channels", [])) for cat in categories)
    summary_text = template.get("summary") or f"{len(categories)} categories / {total_channels} channels"
    embed = discord.Embed(
        title=f"{source_label} Result",
        description=summary_text,
        color=EMBED_COLOR,
    )
    preview_lines: List[str] = []
    for category in categories[:4]:
        channels = category.get("channels", [])
        channel_preview = ", ".join(f"`{ch.get('name', 'channel')}`" for ch in channels[:3])
        preview_lines.append(
            f"**{category.get('name', 'Category')}** ({len(channels)} ch) {channel_preview}".strip()
        )
    embed.add_field(name="Categories Preview", value="\n".join(preview_lines) or "No categories detected.", inline=False)
    if roles:
        embed.add_field(name="Roles Detected", value=f"{len(roles)} role definition(s) found.", inline=False)
    embed.set_footer(text="Apply directly via the button below or import from Dashboard > Templates > Text Import.")
    return embed


def _build_channel_setup_intro_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Channel Setup Wizard",
        description=(
            "Use the buttons below to parse raw text layouts or analyze a screenshot.\n"
            "You'll get a summarized template that can be imported into the dashboard."
        ),
        color=EMBED_COLOR,
    )
    embed.add_field(
        name="Text Parser",
        value="Paste plain text or copied channel lists. Works great with sample snippets from `/help`.",
        inline=False,
    )
    embed.add_field(
        name="Image Analyzer",
        value="Provide a public image URL. OCR will try to detect categories/channels from the screenshot.",
        inline=False,
    )
    embed.set_footer(text="After reviewing the preview, open the dashboard to apply the template.")
    return embed


class ChannelTemplateActionView(discord.ui.View):
    """Actions available after parsing channel templates."""

    def __init__(self, template: Dict[str, Any], author_id: int, guild_id: int | None, source_label: str):
        super().__init__(timeout=240)
        self.template = template
        self.author_id = author_id
        self.guild_id = guild_id
        self.source_label = source_label

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the user who generated this template can use these buttons.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Apply Template (Create Channels)", style=discord.ButtonStyle.success)
    async def apply_template(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            await interaction.response.send_message("Run this inside a server to build channels.", ephemeral=True)
            return
        if self.guild_id and interaction.guild_id != self.guild_id:
            await interaction.response.send_message(
                "This template belongs to another server. Run `/channel_setup` here to generate a fresh copy.",
                ephemeral=True,
            )
            return
        if not await _is_owner_or_admin(interaction):
            await interaction.response.send_message("Only the server owner or admins can apply templates.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await build_server_from_template(interaction.guild, self.template)
        except Exception as error:
            await interaction.followup.send(f"Failed to build template: {error}", ephemeral=True)
            return

        cat_count = len(self.template.get("categories") or [])
        channel_count = sum(len(cat.get("channels", [])) for cat in self.template.get("categories", []))
        await interaction.followup.send(
            f"✅ Applied **{cat_count}** categories / **{channel_count}** channels from {self.source_label}. "
            "Use the dashboard if you need to fine-tune ordering or roles.",
            ephemeral=True,
        )


async def _send_template_preview(
    interaction: discord.Interaction, source_label: str, template: Dict[str, Any]
) -> None:
    embed = _build_template_preview_embed(source_label, template)
    view = ChannelTemplateActionView(template, interaction.user.id, interaction.guild_id, source_label)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="setup_dashboard", description="Load a prebuilt server template (customize via dashboard).")
async def setup_dashboard_command(interaction: discord.Interaction):
    if not await _is_owner_or_admin(interaction):
        await interaction.response.send_message("Only the server owner or admins can use this command.", ephemeral=True)
        return
    
    dashboard_url = os.getenv("DASHBOARD_URL", "https://jthweb.yugp.me:6767")
    
    embed = discord.Embed(
        title="Setup Dashboard",
        description=(
            "**Welcome to Channel Manager!**\n\n"
            "Build or refresh your server with pre-built templates using the dashboard.\n\n"
            "**Available Templates:**\n"
            "- Gaming Server · matches + scrims ready\n"
            "- Community Server · hangouts and clubs\n"
            "- Support Server · structured ticket hub\n"
            "- Creative Server · artist-friendly boards\n\n"
            "**Quick Start:**\n"
            "1. Run `/setup_dashboard` or hit the dashboard button\n"
            "2. Login with your Discord account\n"
            "3. Pick a server + template bundle\n"
            "4. Customize channels, roles, and modules\n\n"
            "**Features:**\n"
            "- Server templates & channel builder\n"
            "- Custom commands + automation\n"
            "- Moderation, logs, announcements\n"
            "- Role manager & embed maker\n"
        ),
        color=EMBED_COLOR,
    )
    embed.set_thumbnail(url=EMBED_THUMB)
    embed.add_field(
        name="Module Snapshot",
        value=(
            "- Giveaway setup (timers, winners, rerolls)\n"
            "- Text import/export for channels and roles\n"
            "- Verification, ticketing, leveling, announcements\n"
            "- Embed maker, auto mod, and other dashboard tools"
        ),
        inline=False,
    )
    embed.add_field(
        name="Need text import help?",
        value=(
            "Use `/setup` (or the button below) to open an embed with giveaway setup notes, "
            "text import examples, and module-by-module guidance."
        ),
        inline=False,
    )
    embed.set_footer(text="All bot customization happens via the web dashboard")
    
    view = SetupDashboardView(dashboard_url, interaction.user.id)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="setup", description="Show the in-Discord setup panel with module buttons.")
async def setup_command(interaction: discord.Interaction):
    if not await _is_owner_or_admin(interaction):
        await interaction.response.send_message("Only the server owner or admins can use this command.", ephemeral=True)
        return

    view = SetupModulesActionView(interaction.user.id)
    overview_embed = _build_setup_modules_embed()
    await interaction.response.send_message(embed=overview_embed, view=view, ephemeral=True)


@bot.tree.command(name="channel_setup", description="Parse text or screenshot layouts into templates.")
async def channel_setup_command(interaction: discord.Interaction):
    if not await _is_owner_or_admin(interaction):
        await interaction.response.send_message("Only the server owner or admins can use this command.", ephemeral=True)
        return

    embed = _build_channel_setup_intro_embed()
    view = ChannelSetupView(interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="sync", description="Sync slash commands (Admin+).")
@app_commands.checks.has_permissions(administrator=True)
async def sync_command(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        synced = await bot.tree.sync()
        await interaction.followup.send(f"✅ Synced {len(synced)} command(s) globally.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to sync: {e}", ephemeral=True)


@bot.tree.command(name="health", description="Show bot status.")
async def health_command(interaction: discord.Interaction):
    if not await _is_owner_or_admin(interaction):
        await _safe_send(interaction, content="Only the server owner or admins can use this command.", ephemeral=True)
        return

    status = getattr(bot, "status", discord.Status.online).name
    ping = max(0, round(bot.latency * 1000)) if hasattr(bot, "latency") else 0
    guild_count = len(bot.guilds)
    channel_count = sum(len(guild.channels) for guild in bot.guilds)
    uptime_seconds = int((discord.utils.utcnow() - STARTED_AT).total_seconds())
    uptime_parts = (
        f"{uptime_seconds // 86400}d "
        f"{(uptime_seconds % 86400) // 3600}h "
        f"{(uptime_seconds % 3600) // 60}m "
        f"{uptime_seconds % 60}s"
    )

    embed = discord.Embed(title="Channel Manager Health", color=EMBED_COLOR)
    embed.set_thumbnail(url=EMBED_THUMB)
    embed.add_field(name="Status", value=str(status), inline=True)
    embed.add_field(name="Ping", value=f"{ping} ms", inline=True)
    embed.add_field(name="Uptime", value=uptime_parts, inline=True)
    embed.add_field(name="Servers", value=str(guild_count), inline=True)
    embed.add_field(name="Channels (cached)", value=str(channel_count), inline=True)
    embed.add_field(name="Runtime", value=f"Python {sys.version.split()[0]} | discord.py {discord.__version__}", inline=False)
    embed.set_footer(text="Channel Manager - system health")
    embed.timestamp = discord.utils.utcnow()

    await _safe_send(interaction, embed=embed, ephemeral=True)


@bot.tree.command(name="help", description="Show a short help message.")
async def help_command(interaction: discord.Interaction):
    channel_example = (
        "INFORMATION (category)\n"
        "  #announcements\n"
        "  #bot-info\n\n"
        "SUPPORT (category)\n"
        "  #create-ticket\n"
        "  #help\n"
        "  #bug-report\n\n"
        "COMMUNITY (category)\n"
        "  #general\n"
        "  #showcase\n"
    )

    roles_block = (
        "STAFF & ADMIN (roles)\n"
        "  Owner | Color: #ff0000 | Permissions: [Administrator, Manage Server, Manage Roles]\n"
        "  Moderator | Color: #ff944d | Permissions: [Kick Members, Ban Members, Timeout Members, Manage Messages]"
    )

    embed = discord.Embed(title="Channel Builder Help", color=EMBED_COLOR)
    embed.set_thumbnail(url=EMBED_THUMB)
    embed.description = "\n".join(
        [
            "1) Run /setup (or /setup_dashboard) and pick what you need.",
            "2) Roles import example:",
            "```",
            roles_block,
            "```",
            "3) For text import, paste something like this:",
            "```",
            channel_example,
            "```",
            "Notes:",
            "- Bot must be in the source server to clone.",
            "- Max around 500 channels per server.",
            "- Bot needs Manage Channels and Manage Roles permissions.",
            "",
            "Rules module:",
            "- /rules to show the rules panel",
            "- /rules_setup (owner) to configure texts, rules, and banner via buttons",
            "",
            "Verify module:",
            "- /verify to show the verify panel (uses per-server config)",
            "- /verify_setup (owner) to set unverified/verified roles, banner, footer",
            "",
            "Giveaway module:",
            "- /giveaway_start (owner) to start a giveaway (prize/duration/description)",
            "- /giveaway_end (owner) to end and get transcript",
            "",
            "Channel builder tips:",
            "- Use `/channel_setup` to parse text or screenshot layouts and apply them instantly.",
        ]
    )
    for group in SETUP_COMMAND_GROUPS.values():
        embed.add_field(
            name=f"{group['emoji']} {group['label']}",
            value=_format_command_list(group["commands"]),
            inline=False,
        )
    embed.set_footer(text="Channel Manager - simple help")
    await _safe_send(interaction, embed=embed, ephemeral=True)


@bot.tree.command(name="rules", description="Show server rules with a selector.")
async def rules_command(interaction: discord.Interaction):
    if not interaction.guild:
        await _safe_send(interaction, content="Use this in a server.", ephemeral=True)
        return
    config = _get_rules_config(interaction.guild_id)
    rules_embed = _build_rules_embed(config)
    view = RulesView(config)
    await _safe_send(interaction, embed=rules_embed, view=view, ephemeral=False)

    if interaction.guild and interaction.user.id == interaction.guild.owner_id:
        owner_embed = discord.Embed(
            title="Rules panel posted",
            description=(
                "Only you see this note.\n"
                "- Embed + dropdown show rules; clicks give details (ephemeral) so the channel stays clean.\n"
                "- Use /rules_setup to manage texts, rules, and banner (owner only).\n"
                "- Planned dashboard will mirror these fields. Only this server sees its own banner/config."
            ),
            color=EMBED_COLOR,
        )
        owner_embed.set_footer(text="Owner note - Channel Manager")
        await interaction.followup.send(embed=owner_embed, ephemeral=True)


class RulesBannerModal(discord.ui.Modal, title="Set Rules Banner URL"):
    def __init__(self):
        super().__init__(timeout=None)
        self.url_input = discord.ui.TextInput(label="Banner image URL (leave empty to remove)", required=False)
        self.add_item(self.url_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return
        config = _get_rules_config(interaction.guild_id)
        url = str(self.url_input).strip()
        config["bannerUrl"] = url if url else None
        _set_rules_config(interaction.guild_id, config)
        msg = "Banner updated." if url else "Banner removed."
        await interaction.response.send_message(msg, ephemeral=True)


class RulesFooterModal(discord.ui.Modal, title="Set Rules Footer"):
    def __init__(self):
        super().__init__(timeout=None)
        self.footer_input = discord.ui.TextInput(
            label="Footer text (optional)",
            required=False,
            max_length=120,
            placeholder="e.g. Be respectful to everyone."
        )
        self.add_item(self.footer_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return
        config = _get_rules_config(interaction.guild_id)
        footer_val = str(self.footer_input).strip()
        config["footerText"] = footer_val if footer_val else None
        _set_rules_config(interaction.guild_id, config)
        msg = "Footer updated." if footer_val else "Footer cleared."
        await interaction.response.send_message(msg, ephemeral=True)


class VerifySetupModal(discord.ui.Modal, title="Verify Setup"):
    def __init__(self):
        super().__init__(timeout=None)
        self.unverified = discord.ui.TextInput(label="Unverified role ID (optional)", required=False, max_length=20)
        self.verified = discord.ui.TextInput(label="Verified role ID (required)", required=True, max_length=20)
        self.title_input = discord.ui.TextInput(label="Title", required=False, max_length=100, default="Verify to access")
        self.desc_input = discord.ui.TextInput(label="Description", required=False, style=discord.TextStyle.long, default="Click verify to unlock access.")
        self.banner_input = discord.ui.TextInput(label="Banner URL (optional)", required=False)
        for item in (self.unverified, self.verified, self.title_input, self.desc_input, self.banner_input):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return
        config = get_verify_config(interaction.guild_id)
        config.update(
            {
                "unverifiedRole": str(self.unverified).strip() or None,
                "verifiedRole": str(self.verified).strip() or None,
                "title": str(self.title_input).strip() or "Verify to access",
                "description": str(self.desc_input).strip() or "Click verify to unlock access.",
                "bannerUrl": str(self.banner_input).strip() or None,
            }
        )
        update_verify_config(interaction.guild_id, config)
        preview = build_verify_embed(config)
        await interaction.response.send_message("Verify settings saved. Preview below.", embed=preview, ephemeral=True)


class RulesSetupView(discord.ui.View):
    def __init__(self, config: dict):
        super().__init__(timeout=300)
        self.config = config
        self.add_item(RulesSetupTextButton())
        self.add_item(RulesSetupBulkButton())
        self.add_item(RulesSetupBannerButton())
        self.add_item(RulesSetupClearBannerButton())
        self.add_item(RulesSetupFooterButton())


class RulesSetupTextButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.primary, label="Edit Texts")

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not await _is_owner_or_admin(interaction):
            await interaction.response.send_message("Only the server owner can edit rules.", ephemeral=True)
            return
        modal = RulesTextModal(_get_rules_config(interaction.guild_id))
        await interaction.response.send_modal(modal)


class RulesSetupBulkButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.secondary, label="Bulk Rules")

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not await _is_owner_or_admin(interaction):
            await interaction.response.send_message("Only the server owner can edit rules.", ephemeral=True)
            return
        await interaction.response.send_modal(RulesBulkModal())


class RulesSetupBannerButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.success, label="Set Banner")

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not await _is_owner_or_admin(interaction):
            await interaction.response.send_message("Only the server owner can edit rules.", ephemeral=True)
            return
        await interaction.response.send_modal(RulesBannerModal())


class RulesSetupClearBannerButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.danger, label="Clear Banner")

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not await _is_owner_or_admin(interaction):
            await interaction.response.send_message("Only the server owner can edit rules.", ephemeral=True)
            return
        config = _get_rules_config(interaction.guild_id)
        config["bannerUrl"] = None
        _set_rules_config(interaction.guild_id, config)
        await interaction.response.send_message("Banner removed.", ephemeral=True)


class RulesSetupFooterButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.secondary, label="Set Footer")

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not await _is_owner_or_admin(interaction):
            await interaction.response.send_message("Only the server owner can edit rules.", ephemeral=True)
            return
        await interaction.response.send_modal(RulesFooterModal())


@bot.tree.command(name="rules_setup", description="Admin+: configure rules (texts, categories, banner) in one place.")
@app_commands.check(_is_owner_or_admin)
async def rules_setup_command(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Use this in a server.", ephemeral=True)
        return
    await _ensure_defer(interaction, ephemeral=True)
    config = _get_rules_config(interaction.guild_id)
    cats = config.get("categories", [])
    summary = "\n".join([f"{idx+1}) {c.get('title','')}" for idx, c in enumerate(cats)]) or "No categories set yet."
    banner = config.get("bannerUrl") or "None"
    embed = discord.Embed(
        title="Rules Setup",
        description=(
            "Manage all rules settings here. Buttons below let you edit texts, bulk rules, and banner.\n"
            f"Current banner: {banner}"
        ),
        color=EMBED_COLOR,
    )
    embed.add_field(name="Rules overview", value=summary, inline=False)
    embed.set_footer(text="Owner only - changes apply to this server only")
    await interaction.followup.send(embed=embed, view=RulesSetupView(config), ephemeral=True)


@rules_setup_command.error
async def rules_setup_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    await _safe_send(interaction, content="Only the server owner can use /rules_setup inside a server.", ephemeral=True)


@bot.tree.command(name="verify", description="Show the verify panel.")
async def verify_command(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Use this in a server.", ephemeral=True)
        return
    config = get_verify_config(interaction.guild_id)
    embed = build_verify_embed(config)
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(custom_id="verify-accept", style=discord.ButtonStyle.success, label="Verify"))
    await _safe_send(interaction, embed=embed, view=view, ephemeral=False)


@bot.tree.command(name="verify_setup", description="Owner: configure verify roles/banner/footer.")
async def verify_setup_command(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Use this in a server.", ephemeral=True)
        return
    if not await _is_owner_or_admin(interaction):
        await _safe_send(
            interaction,
            content="Only the server owner or admins can use /verify_setup. If you believe you have access, try again after I finish syncing.",
            ephemeral=True,
        )
        return
    await interaction.response.send_modal(VerifySetupModal())


@bot.tree.command(name="giveaway_start", description="Admin+: start a giveaway.")
@app_commands.check(_is_owner_or_admin)
async def giveaway_start_command(
    interaction: discord.Interaction,
    prize: str,
    duration_minutes: app_commands.Range[int, 1, 10080],
    description: str | None = None,
):
    if not interaction.guild:
        await interaction.response.send_message("Use this in a server.", ephemeral=True)
        return
    await _ensure_defer(interaction, ephemeral=True)
    msg_id = await start_giveaway(interaction.channel, interaction.guild.id, prize, duration_minutes, description)
    await interaction.followup.send(f"Giveaway started (message ID: {msg_id}).", ephemeral=True)


@giveaway_start_command.error
async def giveaway_start_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    await _safe_send(interaction, content="Only the server owner can start a giveaway.", ephemeral=True)


@bot.tree.command(name="giveaway_end", description="Admin+: end a giveaway and get transcript.")
@app_commands.check(_is_owner_or_admin)
@app_commands.describe(message_id="Message ID of the giveaway (leave empty for latest)")
async def giveaway_end_command(interaction: discord.Interaction, message_id: int | None = None):
    await _ensure_defer(interaction, ephemeral=True)
    await end_gw_command(interaction, message_id)


@giveaway_end_command.error
async def giveaway_end_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    await _safe_send(interaction, content="Only the server owner can end a giveaway.", ephemeral=True)
@bot.tree.command(name="delete_channel", description="Delete all channels and categories in this server.")
async def delete_channels_command(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Please run this inside a server.", ephemeral=True)
        return
    if not await _is_owner_or_admin(interaction):
        await interaction.response.send_message("Only the server owner or admins can use this command.", ephemeral=True)
        return

    await interaction.response.send_message("Deleting all channels and categories...", ephemeral=True)
    bot_member = interaction.guild.me
    if not bot_member:
        await interaction.followup.send("Bot member not found in guild.", ephemeral=True)
        return
    channels = await interaction.guild.fetch_channels()
    delete_tasks = []
    for ch in channels:
        if getattr(ch, "permissions_for", None) and ch.permissions_for(bot_member).manage_channels:
            delete_tasks.append(ch.delete(reason="Requested by /delete_channel"))
    await asyncio.gather(*delete_tasks, return_exceptions=True)
    await interaction.followup.send(f"Delete finished. Channels/categories removed: {len(delete_tasks)}.", ephemeral=True)


@bot.tree.command(name="delete_roles", description="Delete all deletable roles (except @everyone/managed/above bot).")
async def delete_roles_command(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("Please run this inside a server.", ephemeral=True)
        return
    if not await _is_owner_or_admin(interaction):
        await interaction.response.send_message("Only the server owner or admins can use this command.", ephemeral=True)
        return

    await interaction.response.send_message("Deleting roles (skipping @everyone, managed, and above my role)...", ephemeral=True)
    me = interaction.guild.me or await interaction.guild.fetch_member(bot.user.id)
    my_top_pos = me.top_role.position if me else 0

    roles = await interaction.guild.fetch_roles()
    delete_tasks = []
    for role in roles:
        if role.id == interaction.guild.default_role.id:
            continue
        if role.managed:
            continue
        if role.position >= my_top_pos:
            continue
        delete_tasks.append(role.delete(reason="Requested by /delete_roles"))
    await asyncio.gather(*delete_tasks, return_exceptions=True)
    await interaction.followup.send(f"Delete finished. Roles removed: {len(delete_tasks)}.", ephemeral=True)



def _ensure_template_safe(template: Any) -> None:
    if not template or not isinstance(template, dict) or not isinstance(template.get("categories"), list):
        raise ValueError("Template is not valid.")
    channel_count = sum(len(cat.get("channels", [])) for cat in template.get("categories", []))
    role_count = len(template.get("roles", [])) if isinstance(template.get("roles"), list) else 0
    if channel_count > MAX_CHANNELS:
        raise ValueError(f"Too many channels ({channel_count}). Discord limit is around 500.")
    if role_count > MAX_ROLES:
        raise ValueError(f"Too many roles ({role_count}).")


async def _fetch_avatar_data(url: str) -> str | None:
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=10) as resp:
                resp.raise_for_status()
                data = await resp.read()
                content_type = resp.headers.get("Content-Type", "image/png")
        except Exception:  # pragma: no cover
            return None
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


@bot.tree.command(name="stats", description="Show recent chat and voice activity.")
@app_commands.describe(user="User to query (defaults to you)", days="Number of days to show (1-30)")
async def stats_command(
    interaction: discord.Interaction,
    user: discord.User | None = None,
    days: app_commands.Range[int, 1, 30] = STAT_WINDOW_DAYS,
):
    if not interaction.guild:
        await _safe_send(interaction, content="Please run this in a server.", ephemeral=True)
        return
    target = user or interaction.user
    await _ensure_defer(interaction)

    window_days = days
    today = discord.utils.utcnow().date()
    start_date = today - timedelta(days=window_days - 1)
    date_series = [start_date + timedelta(days=i) for i in range(window_days)]
    summary_rows = db.get_user_activity_summary(
        interaction.guild.id,
        target.id,
        start_date.isoformat(),
        today.isoformat(),
    )
    has_any_activity = bool(summary_rows) or db.has_user_activity(interaction.guild.id, target.id)
    if not has_any_activity:
        await _safe_send(interaction, content="No activity data found for this user.", ephemeral=True)
        return

    activity_map = {
        row["activity_date"]: (
            int(row.get("chat_minutes") or 0),
            int(row.get("voice_minutes") or 0),
        )
        for row in summary_rows
    }
    chat_values: list[int] = []
    voice_values: list[int] = []
    for single_day in date_series:
        iso_day = single_day.isoformat()
        chat, voice = activity_map.get(iso_day, (0, 0))
        chat_values.append(chat)
        voice_values.append(voice)

    total_days = len(chat_values) or 1
    today_chat = chat_values[-1]
    today_voice = voice_values[-1]
    avg_chat = sum(chat_values) / total_days
    avg_voice = sum(voice_values) / total_days
    labels = [day.isoformat() for day in date_series]

    chart_data = {
        "labels": labels,
        "datasets": [
            {
                "label": "Chat Minutes",
                "borderColor": "#3498db",
                "backgroundColor": "#3498db",
                "borderWidth": 3,
                "tension": 0.3,
                "pointRadius": 3,
                "pointBackgroundColor": "#3498db",
                "data": chat_values,
                "fill": False,
                "spanGaps": True,
            },
            {
                "label": "Voice Minutes",
                "borderColor": "#2ecc71",
                "backgroundColor": "#2ecc71",
                "borderWidth": 3,
                "tension": 0.3,
                "pointRadius": 3,
                "pointBackgroundColor": "#2ecc71",
                "data": voice_values,
                "fill": False,
                "spanGaps": True,
            },
        ],
    }

    avatar = getattr(getattr(target, "display_avatar", target.avatar), "url", None)
    avatar_data = await _fetch_avatar_data(avatar) if avatar else None

    header_plugin = (
        '{'
        '"id":"statsHeader",'
        '"beforeDraw":function(chart){'
        "const ctx=chart.ctx;"
        "const opts=chart.config.options.plugins.statsHeader||{};"
        "const width=chart.width;"
        "const height=chart.height;"
        "ctx.save();"
        "ctx.fillStyle='white';"
        "ctx.fillRect(0,0,width,height);"
        "const drawAvatar=function(img){"
        "const centerX=40+35;"
        "const centerY=35+35;"
        "const radius=35;"
        "ctx.save();"
        "ctx.beginPath();"
        "ctx.arc(centerX,centerY,radius,0,Math.PI*2);"
        "ctx.closePath();"
        "ctx.clip();"
        "ctx.drawImage(img,40,35,radius*2,radius*2);"
        "ctx.restore();"
        "ctx.save();"
        "ctx.beginPath();"
        "ctx.arc(centerX,centerY,radius,0,Math.PI*2);"
        "ctx.lineWidth=2;"
        "ctx.strokeStyle='#ddd';"
        "ctx.stroke();"
        "ctx.restore();"
        "};"
        "let avatarDrawn=false;"
        "const renderAvatar=function(img){"
        "if(avatarDrawn)return;"
        "avatarDrawn=true;"
        "drawAvatar(img);"
        "};"
        "const drawHeader=function(){"
        "ctx.save();"
        "ctx.font='bold 26px Sans-serif';"
        "ctx.fillStyle='#000';"
        "ctx.textBaseline='middle';"
        "ctx.fillText(opts.username||'',100,50);"
        "ctx.font='16px Sans-serif';"
        "ctx.fillStyle='#555';"
        "const avgChat=parseFloat(opts.avgChat)||0;"
        "const avgVoice=parseFloat(opts.avgVoice)||0;"
        "ctx.fillText('Today\\'s Activity — Chat '+(opts.todayChat||0)+' min, Voice '+(opts.todayVoice||0)+' min',100,85);"
        "ctx.fillText('30-Day Average — Chat '+avgChat.toFixed(1)+' min, Voice '+avgVoice.toFixed(1)+' min',100,115);"
        "ctx.restore();"
        "};"
        "ctx.save();"
        "ctx.strokeStyle='#ddd';"
        "ctx.lineWidth=1;"
        "ctx.beginPath();"
        "ctx.moveTo(0,150);"
        "ctx.lineTo(width,150);"
        "ctx.stroke();"
        "ctx.restore();"
        "let headerDrawn=false;"
        "const renderHeader=function(){"
        "if(headerDrawn)return;"
        "headerDrawn=true;"
        "drawHeader();"
        "};"
        "if(opts.avatarData){"
        "const img=new Image();"
        "img.onload=function(){"
        "renderAvatar(img);"
        "renderHeader();"
        "};"
        "img.src=opts.avatarData;"
        "if(img.complete){"
        "renderAvatar(img);"
        "renderHeader();"
        "}"
        "}else{"
        "renderHeader();"
        "}"
        "ctx.restore();"
        "}"
        "}"
    )

    options = {
        "responsive": True,
        "maintainAspectRatio": False,
        "interaction": {"mode": "index", "intersect": False},
        "layout": {"padding": {"top": 170, "left": 40, "right": 40, "bottom": 40}},
        "scales": {
            "x": {
                "grid": {"color": "rgba(0,0,0,0.05)"},
                "ticks": {"color": "#333333", "maxRotation": 0, "minRotation": 0},
            },
            "y": {
                "grid": {"color": "rgba(0,0,0,0.05)"},
                "ticks": {"color": "#333333"},
            },
        },
        "plugins": {
            "legend": {
                "position": "bottom",
                "labels": {"color": "#333333", "boxWidth": 12, "usePointStyle": True},
            },
            "statsHeader": {
                "avatarData": avatar_data,
                "username": f"{target.display_name}",
                "todayChat": today_chat,
                "todayVoice": today_voice,
                "avgChat": avg_chat,
                "avgVoice": avg_voice,
            },
        },
    }
    config_str = (
        "{"
        '"type":"line",'
        f'"data":{json.dumps(chart_data)},'
        f'"options":{json.dumps(options)},'
        f'"plugins":[{header_plugin}]'
        "}"
    )
    chart_request_payload = {
        "chart": config_str,
        "backgroundColor": "white",
        "width": 900,
        "height": 700,
        "format": "png",
        "version": 2,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                QUICKCHART_CREATE_URL,
                json=chart_request_payload,
                timeout=10,
            ) as response:
                resp_text = await response.text()
                resp_data = None
                try:
                    resp_data = json.loads(resp_text)
                except Exception:
                    resp_data = {}
                if response.status != 200 or "url" not in resp_data:
                    print("QuickChart create failed", response.status, resp_text)
                    raise aiohttp.ClientError("quickchart create failed")
                chart_url = resp_data["url"]
    except Exception as exc:
        print("QuickChart request failed:", exc)
        await _safe_send(
            interaction,
            content="Unable to render the activity chart right now. Please try again later.",
            ephemeral=True,
        )
        return

    target_name = getattr(target, "display_name", None) or getattr(target, "name", str(target))
    embed_title = (
        "Your Activity Statistics"
        if target.id == interaction.user.id
        else f"{target_name}'s Activity Statistics"
    )
    summary_lines = (
        f"Today's Activity - Chat: **{today_chat}** min, Voice: **{today_voice}** min\n"
        f"{window_days}-Day Average - Chat: **{avg_chat:.1f}** min, Voice: **{avg_voice:.1f}** min"
    )
    embed = discord.Embed(title=embed_title, description=summary_lines, color=STATS_EMBED_COLOR)
    embed.set_image(url=chart_url)
    await _safe_send(interaction, embed=embed)


def _build_rules_embed(config: dict) -> discord.Embed:
    embed = discord.Embed(
        title=config.get("titleText", "Server Rules"),
        color=RULES_ACCENT_COLOR,
    )
    welcome = config.get("welcomeTitle", "Welcome to the server!")
    body = config.get("welcomeBody", "")
    desc = config.get("descriptionText", "")
    embed.description = f"**{welcome}**\n\n{body}\n\n{desc}".strip()
    banner_url = config.get("bannerUrl")
    if banner_url and _valid_banner(banner_url):
        embed.set_image(url=str(banner_url))
    footer = config.get("footerText")
    if footer:
        embed.set_footer(text=str(footer)[:120])
    return embed


def _build_rules_detail(choice_index: int, config: dict) -> discord.Embed:
    categories = config.get("categories", [])
    if choice_index < 0 or choice_index >= len(categories):
        return discord.Embed(title="Rules", description="No details available.", color=EMBED_COLOR)
    item = categories[choice_index]
    embed = discord.Embed(color=RULES_ACCENT_COLOR)
    embed.title = item.get("title", "Details")
    embed.description = item.get("description", "")
    footer = config.get("footerText") or "Questions? Ask staff for clarification."
    embed.set_footer(text=str(footer)[:120])
    return embed


def _get_rules_config(guild_id: int | None) -> dict:
    base = RULES_STATE.get(guild_id) if guild_id and guild_id in RULES_STATE else None
    if not base:
        return _sanitize_rules_config({**RULES_DEFAULT})
    merged = _sanitize_rules_config({**RULES_DEFAULT, **base})
    return merged


def _set_rules_config(guild_id: int | None, config: dict) -> None:
    if guild_id is None:
        return
    RULES_STATE[guild_id] = _sanitize_rules_config({**config})


async def _ensure_defer(interaction: discord.Interaction, ephemeral: bool = False) -> None:
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
    except Exception:
        return


async def _safe_send(interaction: discord.Interaction, **kwargs) -> None:
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(**kwargs)
        else:
            await interaction.followup.send(**kwargs)
    except Exception:
        return


def _safe_emoji(value: Any):
    if not value:
        return None
    try:
        return discord.PartialEmoji.from_str(str(value))
    except Exception:
        return None


def _sanitize_rules_config(config: dict) -> dict:
    categories = []
    for item in config.get("categories", []):
        emoji_val = _safe_emoji(item.get("emoji"))
        categories.append(
            {
                "emoji": emoji_val,
                "color": item.get("color", "red"),
                "title": str(item.get("title", "Item"))[:100],
                "description": str(item.get("description", ""))[:500],
            }
        )
    config["categories"] = categories
    banner = config.get("bannerUrl")
    config["bannerUrl"] = banner if banner and _valid_banner(str(banner)) else None
    footer = config.get("footerText")
    if footer:
        config["footerText"] = str(footer)[:120]
    else:
        config["footerText"] = None
    return config


def _is_image_link(url: str) -> bool:
    if not url:
        return False
    lowered = url.lower()
    if lowered.startswith("data:image/") and "base64," in lowered:
        return True
    if not lowered.startswith(("http://", "https://")):
        return False
    trimmed = lowered.split("?", 1)[0]
    return trimmed.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))


def _valid_banner(url: str) -> bool:
    if not url:
        return False
    if len(url) > 2048:
        return False
    return _is_image_link(url)


if not TOKEN:
    print("Please set DISCORD_TOKEN inside .env")
    sys.exit(1)

bot.run(TOKEN)











