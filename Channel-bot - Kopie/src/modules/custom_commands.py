"""
Custom commands module - allow servers to create their own bot commands.
"""
import discord
from discord import app_commands
from typing import Dict, List


# Store custom commands: {guild_id: {"command_name": {"response": str, "embed": bool}}}
CUSTOM_COMMANDS: Dict[int, Dict[str, dict]] = {}


def init_custom_commands(bot):
    """Initialize custom commands system"""
    
    @bot.listen("on_message")
    async def on_message(message: discord.Message):
        if message.author.bot or not message.guild:
            return
        
        # Check for custom command trigger
        if not message.content.startswith("!"):
            return
        
        parts = message.content[1:].split(maxsplit=1)
        if not parts:
            return
        
        command_name = parts[0].lower()
        
        # Check if custom command exists
        guild_id = message.guild.id
        if guild_id not in CUSTOM_COMMANDS:
            return
        
        if command_name not in CUSTOM_COMMANDS[guild_id]:
            return
        
        cmd_data = CUSTOM_COMMANDS[guild_id][command_name]
        response = cmd_data.get("response", "")
        
        # Replace variables
        response = response.replace("{user}", message.author.mention)
        response = response.replace("{user.name}", message.author.name)
        response = response.replace("{server}", message.guild.name)
        response = response.replace("{channel}", message.channel.mention)
        
        if cmd_data.get("embed", False):
            embed = discord.Embed(
                description=response,
                color=0x5865F2
            )
            await message.channel.send(embed=embed)
        else:
            await message.channel.send(response)


def add_custom_command(guild_id: int, name: str, response: str, embed: bool = False):
    """Add a custom command"""
    if guild_id not in CUSTOM_COMMANDS:
        CUSTOM_COMMANDS[guild_id] = {}
    
    CUSTOM_COMMANDS[guild_id][name.lower()] = {
        "response": response,
        "embed": embed
    }


def remove_custom_command(guild_id: int, name: str) -> bool:
    """Remove a custom command"""
    if guild_id not in CUSTOM_COMMANDS:
        return False
    
    if name.lower() not in CUSTOM_COMMANDS[guild_id]:
        return False
    
    del CUSTOM_COMMANDS[guild_id][name.lower()]
    return True


def get_custom_commands(guild_id: int) -> Dict[str, dict]:
    """Get all custom commands for a guild"""
    return CUSTOM_COMMANDS.get(guild_id, {})


def setup_custom_command_commands(bot):
    """Setup custom command slash commands"""
    
    @bot.tree.command(name="customcmd_create", description="Create a custom command")
    @app_commands.describe(
        name="Command name (without !)",
        response="Command response",
        embed="Send as embed (default: False)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def customcmd_create(
        interaction: discord.Interaction,
        name: str,
        response: str,
        embed: bool = False
    ):
        # Validate command name
        if not name.isalnum() and "_" not in name:
            await interaction.response.send_message("❌ Command name must be alphanumeric.", ephemeral=True)
            return
        
        if len(name) > 32:
            await interaction.response.send_message("❌ Command name too long (max 32 characters).", ephemeral=True)
            return
        
        # Check if command already exists
        existing = get_custom_commands(interaction.guild_id)
        if name.lower() in existing:
            await interaction.response.send_message(f"❌ Command `!{name}` already exists. Use `/customcmd_edit` to modify it.", ephemeral=True)
            return
        
        add_custom_command(interaction.guild_id, name, response, embed)
        
        await interaction.response.send_message(
            f"✅ Created custom command `!{name}`\n"
            f"**Response:** {response[:100]}{'...' if len(response) > 100 else ''}\n"
            f"**Embed:** {embed}\n\n"
            f"Available variables: `{{user}}`, `{{user.name}}`, `{{server}}`, `{{channel}}`",
            ephemeral=True
        )
    
    
    @bot.tree.command(name="customcmd_edit", description="Edit an existing custom command")
    @app_commands.describe(
        name="Command name to edit",
        response="New response (optional)",
        embed="Send as embed (optional)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def customcmd_edit(
        interaction: discord.Interaction,
        name: str,
        response: str = None,
        embed: bool = None
    ):
        existing = get_custom_commands(interaction.guild_id)
        if name.lower() not in existing:
            await interaction.response.send_message(f"❌ Command `!{name}` doesn't exist.", ephemeral=True)
            return
        
        cmd_data = existing[name.lower()]
        
        if response is not None:
            cmd_data["response"] = response
        
        if embed is not None:
            cmd_data["embed"] = embed
        
        await interaction.response.send_message(
            f"✅ Updated custom command `!{name}`\n"
            f"**Response:** {cmd_data['response'][:100]}{'...' if len(cmd_data['response']) > 100 else ''}\n"
            f"**Embed:** {cmd_data['embed']}",
            ephemeral=True
        )
    
    
    @bot.tree.command(name="customcmd_delete", description="Delete a custom command")
    @app_commands.describe(name="Command name to delete")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def customcmd_delete(interaction: discord.Interaction, name: str):
        if remove_custom_command(interaction.guild_id, name):
            await interaction.response.send_message(f"✅ Deleted custom command `!{name}`", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Command `!{name}` doesn't exist.", ephemeral=True)
    
    
    @bot.tree.command(name="customcmd_list", description="List all custom commands")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def customcmd_list(interaction: discord.Interaction):
        commands = get_custom_commands(interaction.guild_id)
        
        if not commands:
            await interaction.response.send_message("No custom commands configured.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"Custom Commands for {interaction.guild.name}",
            color=0x5865F2
        )
        
        for cmd_name, cmd_data in commands.items():
            response_preview = cmd_data["response"][:100]
            if len(cmd_data["response"]) > 100:
                response_preview += "..."
            
            embed.add_field(
                name=f"!{cmd_name}",
                value=f"{response_preview}\n*Embed: {cmd_data['embed']}*",
                inline=False
            )
        
        embed.set_footer(text=f"Total: {len(commands)} commands")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    
    @bot.tree.command(name="customcmd_info", description="Get detailed info about a custom command")
    @app_commands.describe(name="Command name")
    async def customcmd_info(interaction: discord.Interaction, name: str):
        commands = get_custom_commands(interaction.guild_id)
        
        if name.lower() not in commands:
            await interaction.response.send_message(f"❌ Command `!{name}` doesn't exist.", ephemeral=True)
            return
        
        cmd_data = commands[name.lower()]
        
        embed = discord.Embed(
            title=f"Custom Command: !{name}",
            color=0x5865F2
        )
        embed.add_field(name="Response", value=cmd_data["response"], inline=False)
        embed.add_field(name="Embed", value=str(cmd_data["embed"]), inline=True)
        embed.add_field(
            name="Available Variables",
            value="`{user}`, `{user.name}`, `{server}`, `{channel}`",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
