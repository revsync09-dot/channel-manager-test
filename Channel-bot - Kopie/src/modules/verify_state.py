from typing import Any, Dict

import discord

VERIFY_DEFAULT: Dict[str, Any] = {
    "unverifiedRole": None,
    "verifiedRole": None,
    "bannerUrl": None,
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
