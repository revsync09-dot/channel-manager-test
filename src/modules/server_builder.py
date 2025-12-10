from typing import Any, Dict, List

import discord


async def build_server_from_template(guild: discord.Guild, template: Dict[str, Any]) -> None:
    role_id_map = await _ensure_roles(guild, template.get("roles", []))

    for category in template.get("categories", []):
        category_name = _sanitize_name(category.get("name") or "Category")
        category_channel = await guild.create_category(category_name)

        for channel_data in category.get("channels", []):
            name = _sanitize_name(channel_data.get("name") or "channel")
            is_voice = _is_voice_type(channel_data.get("type"))
            overwrites = _build_overwrites(channel_data.get("overwrites"), guild, role_id_map)

            if is_voice:
                await guild.create_voice_channel(
                    name=name,
                    category=category_channel,
                    overwrites=overwrites,
                    reason="Channel Manager template build",
                )
            else:
                await _create_text_channel_safe(
                    guild,
                    name=name,
                    category=category_channel,
                    topic=channel_data.get("topic"),
                    nsfw=bool(channel_data.get("nsfw")),
                    slowmode=channel_data.get("slowmode") or 0,
                    overwrites=overwrites,
                )


async def create_roles(guild: discord.Guild, roles: List[Dict[str, Any]]) -> List[discord.Role]:
    created: List[discord.Role] = []
    for role_data in roles:
        perms = _normalize_permissions(role_data.get("permissions"))
        role = await guild.create_role(
            name=role_data.get("name") or "role",
            colour=discord.Colour(role_data.get("color") or 0),
            hoist=bool(role_data.get("hoist", False)),
            mentionable=bool(role_data.get("mentionable", True)),
            permissions=perms,
            reason="Channel Manager role import",
        )
        created.append(role)
    return created


async def template_from_guild(guild: discord.Guild) -> Dict[str, Any]:
    categories: List[Dict[str, Any]] = []
    roles = await guild.fetch_roles()
    channels = await guild.fetch_channels()

    role_templates: List[Dict[str, Any]] = []
    for role in sorted(roles, key=lambda r: r.position):
        role_templates.append(
            {
                "refId": str(role.id),
                "name": role.name,
                "color": role.color.value,
                "hoist": role.hoist,
                "mentionable": role.mentionable,
                "permissions": str(role.permissions.value),
                "position": role.position,
                "isEveryone": role.id == guild.default_role.id,
            }
        )

    category_map: Dict[int, Dict[str, Any]] = {}
    for channel in sorted(channels, key=lambda c: c.position):
        if isinstance(channel, discord.CategoryChannel):
            category_map[channel.id] = {"name": channel.name, "channels": []}

    for channel in sorted(channels, key=lambda c: c.position):
        parent_id = getattr(channel, "category_id", None)
        if not parent_id or parent_id not in category_map or isinstance(channel, discord.CategoryChannel):
            continue

        parent = category_map[parent_id]
        overwrites_list: List[Dict[str, str]] = []
        for target, overwrite in channel.overwrites.items():
            if not isinstance(target, discord.Role):
                continue
            allow, deny = overwrite.pair()
            overwrites_list.append(
                {
                    "roleRefId": str(target.id),
                    "allow": str(allow.value),
                    "deny": str(deny.value),
                }
            )

        parent["channels"].append(
            {
                "name": channel.name,
                "type": "voice" if isinstance(channel, discord.VoiceChannel) else "text",
                "topic": getattr(channel, "topic", None),
                "nsfw": getattr(channel, "nsfw", False),
                "slowmode": getattr(channel, "slowmode_delay", 0),
                "overwrites": overwrites_list,
            }
        )

    categories.extend(category_map.values())
    return {
        "roles": role_templates,
        "categories": categories,
        "summary": f"{len(categories)} categories copied",
    }


def _build_overwrites(overwrites_data: Any, guild: discord.Guild, role_map: Dict[str, int]) -> Dict[discord.Role, discord.PermissionOverwrite]:
    overwrites: Dict[discord.Role, discord.PermissionOverwrite] = {}
    if not overwrites_data:
        return overwrites

    for ow in overwrites_data:
        ref_id = str(ow.get("roleRefId"))
        mapped_role_id = role_map.get(ref_id) or (guild.default_role.id if ref_id == "everyone" else None)
        if not mapped_role_id:
            continue
        role = guild.get_role(int(mapped_role_id))
        if not role:
            continue
        allow_perms = _normalize_permissions(ow.get("allow"))
        deny_perms = _normalize_permissions(ow.get("deny"))
        overwrites[role] = discord.PermissionOverwrite.from_pair(allow_perms, deny_perms)
    return overwrites


async def _ensure_roles(guild: discord.Guild, role_templates: List[Dict[str, Any]]) -> Dict[str, int]:
    mapping: Dict[str, int] = {"everyone": guild.default_role.id}
    for tpl in role_templates:
        if tpl.get("isEveryone") or str(tpl.get("refId")) == str(guild.default_role.id):
            mapping[str(tpl.get("refId"))] = guild.default_role.id
            continue
        role = await guild.create_role(
            name=tpl.get("name") or "role",
            colour=discord.Colour(tpl.get("color") or 0),
            hoist=bool(tpl.get("hoist")),
            mentionable=bool(tpl.get("mentionable", True)),
            permissions=_normalize_permissions(tpl.get("permissions")),
            reason="Channel Manager role mapping",
        )
        mapping[str(tpl.get("refId"))] = role.id
    return mapping


def _normalize_permissions(value: Any) -> discord.Permissions:
    if isinstance(value, discord.Permissions):
        return value
    try:
        return discord.Permissions(int(value))
    except Exception:
        return discord.Permissions.none()


def _sanitize_name(name: str) -> str:
    trimmed = (name or "").strip()
    if not trimmed:
        return "channel"
    return trimmed[:90]


def _is_voice_type(type_value: Any) -> bool:
    if isinstance(type_value, int):
        return type_value == 2
    return str(type_value).lower() == "voice"


async def _create_text_channel_safe(
    guild: discord.Guild,
    name: str,
    category: discord.CategoryChannel,
    topic: str | None,
    nsfw: bool,
    slowmode: int,
    overwrites: Dict[discord.Role, discord.PermissionOverwrite],
) -> discord.TextChannel:
    payload = {
        "name": name,
        "category": category,
        "topic": (topic or "")[:1024] if topic else None,
        "nsfw": nsfw,
        "slowmode_delay": max(0, int(slowmode or 0)),
        "overwrites": overwrites,
        "reason": "Channel Manager template build",
    }
    try:
        return await guild.create_text_channel(**payload)
    except discord.HTTPException:
        payload.pop("topic", None)
        return await guild.create_text_channel(**payload)
