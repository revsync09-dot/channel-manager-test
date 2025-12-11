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
    VERIFY_STATE[guild_id] = {**VERIFY_DEFAULT, **config}
