import asyncio
import io
import random
from typing import Any, Dict, List, Set

import discord


class GiveawayState:
    def __init__(self):
        self.giveaways: Dict[int, Dict[int, Dict[str, Any]]] = {}  # guild_id -> message_id -> data
        self.tasks: Dict[int, asyncio.Task] = {}
        self.bot: discord.Client | None = None


STATE = GiveawayState()


def init_giveaway(bot: discord.Client) -> None:
    STATE.bot = bot


def _get_guild_giveaways(guild_id: int) -> Dict[int, Dict[str, Any]]:
    return STATE.giveaways.setdefault(guild_id, {})


async def handle_giveaway_button(interaction: discord.Interaction) -> bool:
    data = getattr(interaction, "data", {}) or {}
    cid = data.get("custom_id") if isinstance(data, dict) else getattr(interaction, "custom_id", "")
    if not cid.startswith("giveaway-enter:"):
        return False
    parts = cid.split(":")
    if len(parts) != 2:
        return False

    msg_id = int(parts[1])
    giveaway = _get_guild_giveaways(interaction.guild_id).get(msg_id)
    if not giveaway:
        await _safe_response(interaction, content="This giveaway is no longer active.", ephemeral=True)
        return True

    entrants: Set[int] = giveaway.setdefault("entrants", set())
    entrants.add(interaction.user.id)

    # Try to update entry count live
    bot = STATE.bot
    if bot:
        try:
            channel = bot.get_channel(giveaway["channel_id"]) or await bot.fetch_channel(giveaway["channel_id"])
            message = await channel.fetch_message(msg_id)
            if message and message.embeds:
                embed = message.embeds[0]
                new_embed = discord.Embed(title=embed.title, description=embed.description, color=embed.color)
                for f in embed.fields:
                    if f.name.lower() == "entries":
                        new_embed.add_field(name=f.name, value=str(len(entrants)), inline=f.inline)
                    else:
                        new_embed.add_field(name=f.name, value=f.value, inline=f.inline)
                if embed.footer:
                    new_embed.set_footer(text=embed.footer.text or "")
                if embed.image and embed.image.url:
                    new_embed.set_image(url=embed.image.url)
                await message.edit(embed=new_embed)
        except Exception:
            pass

    await _safe_response(interaction, content="You are entered!", ephemeral=True)
    return True


async def start_giveaway(
    channel: discord.abc.Messageable,
    guild_id: int,
    prize: str,
    duration_minutes: int,
    description: str | None,
) -> int:
    embed = discord.Embed(
        title="𝙎𝙀𝙍𝙑𝙀𝙍 𝙂𝙄𝙑𝙀𝘼𝙒𝘼𝙔",
        description=description or "Join the giveaway!",
        color=0x9C66FF,
    )
    embed.add_field(name="Prize", value=prize, inline=True)
    embed.add_field(name="Duration", value=f"{duration_minutes} minutes", inline=True)
    embed.add_field(name="Entries", value="0", inline=True)
    embed.set_footer(text="Click Enter to participate")

    message = await channel.send(embed=embed)
    view = discord.ui.View(timeout=None)
    button = discord.ui.Button(label="Enter", style=discord.ButtonStyle.primary, custom_id=f"giveaway-enter:{message.id}")
    view.add_item(button)
    try:
        await message.edit(view=view)
    except Exception:
        pass

    giveaway_data = {
        "prize": prize,
        "description": description,
        "message_id": message.id,
        "channel_id": message.channel.id,
        "guild_id": guild_id,
        "entrants": set(),  # user ids
        "done": False,
    }
    _get_guild_giveaways(guild_id)[message.id] = giveaway_data

    task = asyncio.create_task(_schedule_end(guild_id, message.id, duration_minutes))
    STATE.tasks[message.id] = task
    return message.id


async def _schedule_end(guild_id: int, message_id: int, duration_minutes: int):
    await asyncio.sleep(max(0, duration_minutes * 60))
    await end_giveaway(guild_id, message_id, auto=True)


async def end_giveaway_command(interaction: discord.Interaction, message_id: int | None = None):
    if not interaction.guild:
        await _safe_response(interaction, content="Use this in a server.", ephemeral=True)
        return
    giveaways = _get_guild_giveaways(interaction.guild_id)
    if message_id is None and giveaways:
        message_id = next(iter(giveaways))
    if not message_id or message_id not in giveaways:
        await _safe_response(interaction, content="No active giveaway found.", ephemeral=True)
        return
    await end_giveaway(interaction.guild_id, message_id, interaction=interaction, auto=False)


async def end_giveaway(guild_id: int, message_id: int, interaction: discord.Interaction | None = None, auto: bool = False):
    giveaways = _get_guild_giveaways(guild_id)
    giveaway = giveaways.get(message_id)
    if not giveaway or giveaway.get("done"):
        return
    giveaway["done"] = True
    entrants: List[int] = list(giveaway.get("entrants", []))
    winner_id = random.choice(entrants) if entrants else None

    bot: discord.Client | None = STATE.bot
    channel = bot.get_channel(giveaway["channel_id"]) if bot else None
    if channel is None and bot:
        try:
            channel = await bot.fetch_channel(giveaway["channel_id"])
        except Exception:
            channel = None
    embed = discord.Embed(
        title="Giveaway Ended",
        description=giveaway.get("description") or "",
        color=0x22C55E,
    )
    embed.add_field(name="Prize", value=giveaway.get("prize", "N/A"), inline=True)
    embed.add_field(name="Entries", value=str(len(entrants)), inline=True)
    embed.add_field(name="Winner", value=f"<@{winner_id}>" if winner_id else "No entries", inline=False)
    embed.add_field(name="Transcript", value="Attached HTML file", inline=False)

    transcript = _build_transcript_html(giveaway, entrants, winner_id)
    file = discord.File(io.BytesIO(transcript.encode("utf-8")), filename="giveaway_transcript.html")

    if channel:
        try:
            await channel.send(embed=embed, file=file)
        except Exception:
            pass
    if interaction:
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, file=file, ephemeral=True)
        except Exception:
            pass

    task = STATE.tasks.pop(message_id, None)
    if task:
        task.cancel()
    giveaways.pop(message_id, None)


def _build_transcript_html(giveaway: Dict[str, Any], entrants: List[int], winner_id: int | None) -> str:
    entries_html = "".join([f"<li>{uid}</li>" for uid in entrants]) or "<li>No entries</li>"
    winner_html = f"<p>Winner: {winner_id}</p>" if winner_id else "<p>No winner</p>"
    return f"""
<!doctype html>
<html><head><meta charset="utf-8"><title>Giveaway Transcript</title></head>
<body>
<h1>Giveaway Transcript</h1>
<p>Prize: {giveaway.get('prize','')}</p>
<p>Description: {giveaway.get('description','')}</p>
{winner_html}
<h2>Entrants</h2>
<ul>{entries_html}</ul>
</body></html>
"""


async def _safe_response(interaction: discord.Interaction, **kwargs) -> None:
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(**kwargs)
        else:
            await interaction.followup.send(**kwargs)
    except Exception:
        return
