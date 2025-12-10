import os
from typing import Dict, Tuple

import discord

TICKET_PARENT_CHANNEL_ID = os.getenv("TICKET_PARENT_CHANNEL_ID", "")
TICKET_PING_ROLE_ID = os.getenv("TICKET_PING_ROLE_ID", "")
ALLOWED_GUILD_ID = os.getenv("ALLOWED_GUILD_ID", "")
EMBED_COLOR = 0x22C55E


async def send_ticket_panel(interaction: discord.Interaction) -> None:
    if not interaction.guild:
        await interaction.response.send_message("Use this inside a server.", ephemeral=True)
        return
    if ALLOWED_GUILD_ID and interaction.guild.id != int(ALLOWED_GUILD_ID):
        await interaction.response.send_message("Ticket system is only available in the main server.", ephemeral=True)
        return

    container, panel_channel = await _resolve_target_channels(interaction.guild)
    if not container or not panel_channel:
        await interaction.response.send_message("Ticket channel not found or not text-based.", ephemeral=True)
        return

    await panel_channel.send(embed=_ticket_embed(), view=_ticket_view())
    await interaction.response.send_message(f"Ticket panel posted in {panel_channel.mention}.", ephemeral=True)


async def send_ticket_panel_to_channel(client: discord.Client) -> None:
    if not ALLOWED_GUILD_ID:
        return
    guild = client.get_guild(int(ALLOWED_GUILD_ID))
    if not guild:
        return
    _, panel_channel = await _resolve_target_channels(guild)
    if not panel_channel:
        return
    try:
        await panel_channel.send(embed=_ticket_embed(), view=_ticket_view())
    except Exception:
        return


async def handle_ticket_select(interaction: discord.Interaction) -> bool:
    data = getattr(interaction, "data", {}) or {}
    custom_id = data.get("custom_id") if isinstance(data, dict) else getattr(interaction, "custom_id", "")
    if custom_id != "ticket-select":
        return False

    if not interaction.guild:
        await interaction.response.send_message("Ticket system is only available in a server.", ephemeral=True)
        return True
    if ALLOWED_GUILD_ID and interaction.guild.id != int(ALLOWED_GUILD_ID):
        await interaction.response.send_message("Ticket system is only available in the main server.", ephemeral=True)
        return True
    if not _is_in_ticket_area(interaction):
        await interaction.response.send_message("Use the designated ticket channel to open tickets.", ephemeral=True)
        return True

    selected = (interaction.data.get("values") or ["Support"])[0] if isinstance(interaction.data, dict) else "Support"
    modal = _TicketModal(selected)
    await interaction.response.send_modal(modal)
    return True


class _TicketModal(discord.ui.Modal, title="New Ticket"):
    def __init__(self, category_choice: str):
        super().__init__(timeout=None)
        self.category_choice = category_choice or "Support"
        self.description = discord.ui.TextInput(
            label="Describe your request",
            custom_id="ticket_description",
            style=discord.TextStyle.long,
            max_length=1000,
            required=True,
        )
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        description = (self.description.value or "No description provided").strip()
        await _create_ticket(interaction, self.category_choice, description)


async def _create_ticket(interaction: discord.Interaction, category_input: str, description: str) -> None:
    if not interaction.guild:
        await interaction.response.send_message("Please use this inside a server.", ephemeral=True)
        return
    if ALLOWED_GUILD_ID and interaction.guild.id != int(ALLOWED_GUILD_ID):
        await interaction.response.send_message("Ticket system is only available in the main server.", ephemeral=True)
        return
    if not _is_in_ticket_area(interaction):
        await interaction.response.send_message("Tickets can only be opened in the designated channel.", ephemeral=True)
        return

    container, _ = await _resolve_target_channels(interaction.guild)
    if not container:
        await interaction.response.send_message("Ticket channel/category not found or invalid.", ephemeral=True)
        return

    parent_id = container.id if isinstance(container, discord.CategoryChannel) else container.parent_id or container.id
    if not parent_id:
        await interaction.response.send_message("No valid ticket category/parent found.", ephemeral=True)
        return

    opener_id = interaction.user.id
    channel_name = f"ticket-{interaction.user.name}".lower().replace(" ", "-")[:90]

    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.guild.get_member(opener_id) or interaction.user: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        ),
    }
    if TICKET_PING_ROLE_ID.isdigit():
        ping_role = interaction.guild.get_role(int(TICKET_PING_ROLE_ID))
        if ping_role:
            overwrites[ping_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )

    parent_category = container if isinstance(container, discord.CategoryChannel) else getattr(container, "category", None)

    ticket_channel = await interaction.guild.create_text_channel(
        name=channel_name,
        category=parent_category,
        overwrites=overwrites,
        reason=f"Ticket by {interaction.user} - {category_input}",
    )

    ping_role = f"<@&{TICKET_PING_ROLE_ID}>" if TICKET_PING_ROLE_ID.isdigit() else ""
    embed = discord.Embed(
        title="Ticket opened",
        description="Thank you, we received your request and will be with you shortly.",
        color=EMBED_COLOR,
    )
    embed.add_field(name="Requester", value=f"{interaction.user} ({interaction.user.id})", inline=True)
    embed.add_field(name="Category", value=category_input, inline=True)
    embed.add_field(name="Status", value="Open", inline=True)
    embed.add_field(name="Description", value=description[:1024], inline=False)
    embed.timestamp = discord.utils.utcnow()

    await ticket_channel.send(content=f"{ping_role} {interaction.user}".strip(), embed=embed)
    await interaction.response.send_message(f"Ticket created: {ticket_channel.mention}", ephemeral=True)


def _is_in_ticket_area(interaction: discord.Interaction) -> bool:
    channel = interaction.channel
    if not channel or not TICKET_PARENT_CHANNEL_ID.isdigit():
        return True  # no parent configured, allow everywhere
    return channel.id == int(TICKET_PARENT_CHANNEL_ID) or getattr(channel, "category_id", None) == int(TICKET_PARENT_CHANNEL_ID)


async def _resolve_target_channels(guild: discord.Guild) -> Tuple[discord.abc.GuildChannel | None, discord.abc.GuildChannel | None]:
    if not TICKET_PARENT_CHANNEL_ID.isdigit():
        return None, None

    container = guild.get_channel(int(TICKET_PARENT_CHANNEL_ID))
    if not container:
        try:
            container = await guild.fetch_channel(int(TICKET_PARENT_CHANNEL_ID))
        except Exception:
            container = None
    if not container:
        return None, None

    if isinstance(container, discord.TextChannel):
        return container, container

    if isinstance(container, discord.CategoryChannel):
        panel_channel = None
        for ch in container.text_channels:
            panel_channel = ch
            break
        if panel_channel:
            return container, panel_channel
        created = await guild.create_text_channel(
            name="ticket-panel",
            category=container,
            reason="Ticket panel channel auto-created",
        )
        return container, created

    return None, None


def _ticket_embed() -> discord.Embed:
    embed = discord.Embed(
        title="Need help?",
        description="Pick a category below and tell us what you need. We will respond as soon as possible.",
        color=EMBED_COLOR,
    )
    embed.add_field(name="Support", value="General help and questions", inline=True)
    embed.add_field(name="Bug Report", value="Report an issue or glitch", inline=True)
    embed.add_field(name="Other", value="Everything else", inline=True)
    embed.set_footer(text="Channel Manager Tickets")
    return embed


def _ticket_view() -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    select = discord.ui.Select(
        custom_id="ticket-select",
        placeholder="Choose a ticket category...",
        options=[
            discord.SelectOption(label="Support", value="Support", description="General help and questions"),
            discord.SelectOption(label="Bug Report", value="Bug Report", description="Report an issue"),
            discord.SelectOption(label="Other", value="Other", description="Anything else"),
        ],
    )
    view.add_item(select)
    return view
