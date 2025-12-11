from typing import Any, Dict

import os
import discord

DEFAULT_VERIFY_BANNER = os.getenv(
    "DASHBOARD_LOGO_URL",
    "https://cdn.discordapp.com/attachments/1443222738750668952/1448482674477105362/image.png?ex=693b6c1d&is=693a1a9d&hm=ff31f492a74f0315498dee8ee26fa87b8512ddbee617f4bccda1161f59c8cb49&",
)

VERIFY_DEFAULT: Dict[str, Any] = {
    "unverifiedRole": None,
    "verifiedRole": None,
    "bannerUrl": DEFAULT_VERIFY_BANNER,
    "footerText": None,
    "title": "Verify to access",
    "description": "Click verify to unlock chat access. This keeps the server safe from spam.",
}

VERIFY_STATE: Dict[int, Dict[str, Any]] = {}


def init_verify_state(bot: discord.Client) -> None:
    return


def get_verify_config(guild_id: int | None) -> Dict[str, Any]:
    if guild_id is None:
        return {**VERIFY_DEFAULT}
    base = VERIFY_STATE.get(guild_id)
    if not base:
        return {**VERIFY_DEFAULT}
    merged = {**VERIFY_DEFAULT, **base}
    return merged


def update_verify_config(guild_id: int | None, config: Dict[str, Any]) -> None:
    if guild_id is None:
        return
    VERIFY_STATE[guild_id] = _sanitize_config({**VERIFY_DEFAULT, **config})


def _sanitize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    banner = config.get("bannerUrl")
    config["bannerUrl"] = banner or DEFAULT_VERIFY_BANNER
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


def build_verify_embed(config: Dict[str, Any]) -> discord.Embed:
    embed = discord.Embed(
        title=config.get("title") or "Verify to access",
        description=config.get("description") or VERIFY_DEFAULT["description"],
        color=0x22C55E,
    )
    banner = config.get("bannerUrl") or DEFAULT_VERIFY_BANNER
    if banner and _is_image_link(banner):
        embed.set_image(url=str(banner))
    footer = config.get("footerText")
    if footer:
        embed.set_footer(text=str(footer)[:120], icon_url=DEFAULT_VERIFY_BANNER)
    else:
        embed.set_footer(text="Channel Manager Verification", icon_url=DEFAULT_VERIFY_BANNER)
    return embed


async def handle_verify_button(interaction: discord.Interaction) -> bool:
    data: Any = getattr(interaction, "data", {}) or {}
    custom_id = data.get("custom_id") if isinstance(data, dict) else getattr(interaction, "custom_id", "")
    if custom_id != "verify-accept":
        return False

    if not interaction.guild:
        await interaction.response.send_message("This button works only in a server.", ephemeral=True)
        return True

    config = get_verify_config(interaction.guild_id)
    verified_role_id = config.get("verifiedRole")
    unverified_role_id = config.get("unverifiedRole")
    if not verified_role_id:
        await interaction.response.send_message("Verification role not configured. Please ask the server owner.", ephemeral=True)
        return True

    member = interaction.user if isinstance(interaction.user, discord.Member) else interaction.guild.get_member(interaction.user.id)
    if not member:
        await interaction.response.send_message("Cannot verify this user here.", ephemeral=True)
        return True

    role = interaction.guild.get_role(int(verified_role_id)) if str(verified_role_id).isdigit() else None
    if not role:
        try:
            role = await interaction.guild.fetch_role(int(verified_role_id))
        except Exception:
            role = None
    if not role:
        await interaction.response.send_message("Verification role not found.", ephemeral=True)
        return True

    bot_member = interaction.guild.me
    if not bot_member or not bot_member.guild_permissions.manage_roles or bot_member.top_role <= role:
        await interaction.response.send_message("Bot is missing Manage Roles or role hierarchy is too low.", ephemeral=True)
        return True

    try:
        await member.add_roles(role, reason="User verified via verify button")
        if unverified_role_id and str(unverified_role_id).isdigit():
            unr = interaction.guild.get_role(int(unverified_role_id))
            if unr:
                await member.remove_roles(unr, reason="User verified via verify button")
    except Exception:
        await interaction.response.send_message("Failed to update roles for verification.", ephemeral=True)
        return True

    await interaction.response.send_message("Verification successful. Welcome!", ephemeral=True)
    return True


async def post_verify_panel(target, config: Dict[str, Any]) -> None:
    embed = build_verify_embed(config)
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(custom_id="verify-accept", style=discord.ButtonStyle.success, label="Verify"))
    await target.send(embed=embed, view=view)
