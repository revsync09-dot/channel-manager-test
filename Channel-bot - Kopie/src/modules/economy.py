"""
Economy and currency system for the bot.
"""
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import random


class EconomySystem:
    def __init__(self, db):
        self.db = db
        self.daily_cooldowns = {}
        self.work_cooldowns = {}
    
    def get_balance(self, guild_id: int, user_id: int) -> int:
        """Get user's balance"""
        return self.db.get_user_balance(guild_id, user_id)
    
    def add_money(self, guild_id: int, user_id: int, amount: int) -> int:
        """Add money to user's balance"""
        return self.db.add_balance(guild_id, user_id, amount)
    
    def remove_money(self, guild_id: int, user_id: int, amount: int) -> bool:
        """Remove money from user's balance"""
        balance = self.get_balance(guild_id, user_id)
        if balance >= amount:
            self.db.add_balance(guild_id, user_id, -amount)
            return True
        return False
    
    def transfer_money(self, guild_id: int, from_user: int, to_user: int, amount: int) -> bool:
        """Transfer money between users"""
        if self.remove_money(guild_id, from_user, amount):
            self.add_money(guild_id, to_user, amount)
            return True
        return False
    
    def can_daily(self, guild_id: int, user_id: int) -> bool:
        """Check if user can claim daily reward"""
        key = f"{guild_id}_{user_id}"
        if key in self.daily_cooldowns:
            return datetime.utcnow() >= self.daily_cooldowns[key]
        return True
    
    def claim_daily(self, guild_id: int, user_id: int, amount: int = 1000) -> int:
        """Claim daily reward"""
        key = f"{guild_id}_{user_id}"
        self.daily_cooldowns[key] = datetime.utcnow() + timedelta(days=1)
        return self.add_money(guild_id, user_id, amount)
    
    def can_work(self, guild_id: int, user_id: int) -> bool:
        """Check if user can work"""
        key = f"{guild_id}_{user_id}"
        if key in self.work_cooldowns:
            return datetime.utcnow() >= self.work_cooldowns[key]
        return True
    
    def work(self, guild_id: int, user_id: int) -> tuple[int, str]:
        """Work for money"""
        key = f"{guild_id}_{user_id}"
        self.work_cooldowns[key] = datetime.utcnow() + timedelta(hours=1)
        
        jobs = [
            ("delivered pizza", 50, 150),
            ("fixed a computer", 75, 200),
            ("walked dogs", 40, 120),
            ("mowed lawns", 60, 180),
            ("washed cars", 45, 135),
            ("streamed on Twitch", 80, 250),
            ("coded a website", 100, 300),
        ]
        
        job_name, min_pay, max_pay = random.choice(jobs)
        amount = random.randint(min_pay, max_pay)
        self.add_money(guild_id, user_id, amount)
        
        return amount, job_name
    
    def get_leaderboard(self, guild_id: int, limit: int = 10):
        """Get economy leaderboard"""
        return self.db.get_economy_leaderboard(guild_id, limit)


def setup_economy_commands(bot, economy: EconomySystem):
    """Setup economy slash commands"""
    
    @bot.tree.command(name="balance", description="Check your balance")
    @app_commands.describe(user="User to check balance for")
    async def balance_command(interaction: discord.Interaction, user: discord.User = None):
        target = user or interaction.user
        balance = economy.get_balance(interaction.guild_id, target.id)
        
        config = bot.db.get_guild_config(interaction.guild_id) or {}
        currency_name = config.get("currency_name", "coins")
        currency_emoji = config.get("currency_emoji", "💰")
        
        embed = discord.Embed(
            title=f"{currency_emoji} Balance",
            description=f"{target.mention} has **{balance:,}** {currency_name}",
            color=0x2ECC71
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="daily", description="Claim your daily reward")
    async def daily_command(interaction: discord.Interaction):
        if not economy.can_daily(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("❌ You've already claimed your daily reward! Come back tomorrow.", ephemeral=True)
            return
        
        config = bot.db.get_guild_config(interaction.guild_id) or {}
        daily_amount = config.get("daily_amount", 1000)
        currency_name = config.get("currency_name", "coins")
        currency_emoji = config.get("currency_emoji", "💰")
        
        balance = economy.claim_daily(interaction.guild_id, interaction.user.id, daily_amount)
        
        embed = discord.Embed(
            title="✅ Daily Reward Claimed!",
            description=f"You received **{daily_amount:,}** {currency_name}\nNew balance: **{balance:,}** {currency_emoji}",
            color=0x2ECC71
        )
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="work", description="Work for money")
    async def work_command(interaction: discord.Interaction):
        if not economy.can_work(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("❌ You're tired! Take a break and try again in an hour.", ephemeral=True)
            return
        
        config = bot.db.get_guild_config(interaction.guild_id) or {}
        currency_name = config.get("currency_name", "coins")
        currency_emoji = config.get("currency_emoji", "💰")
        
        amount, job = economy.work(interaction.guild_id, interaction.user.id)
        balance = economy.get_balance(interaction.guild_id, interaction.user.id)
        
        embed = discord.Embed(
            title="💼 Work Complete!",
            description=f"You {job} and earned **{amount:,}** {currency_name}\nNew balance: **{balance:,}** {currency_emoji}",
            color=0x3498DB
        )
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="pay", description="Give money to another user")
    @app_commands.describe(user="User to pay", amount="Amount to pay")
    async def pay_command(interaction: discord.Interaction, user: discord.User, amount: int):
        if amount <= 0:
            await interaction.response.send_message("❌ Amount must be positive!", ephemeral=True)
            return
        
        if user.id == interaction.user.id:
            await interaction.response.send_message("❌ You can't pay yourself!", ephemeral=True)
            return
        
        if user.bot:
            await interaction.response.send_message("❌ You can't pay bots!", ephemeral=True)
            return
        
        config = bot.db.get_guild_config(interaction.guild_id) or {}
        currency_name = config.get("currency_name", "coins")
        currency_emoji = config.get("currency_emoji", "💰")
        
        if economy.transfer_money(interaction.guild_id, interaction.user.id, user.id, amount):
            embed = discord.Embed(
                title="💸 Payment Successful!",
                description=f"{interaction.user.mention} paid {user.mention} **{amount:,}** {currency_name} {currency_emoji}",
                color=0x2ECC71
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Insufficient balance!", ephemeral=True)
    
    @bot.tree.command(name="leaderboard", description="View economy leaderboard")
    async def leaderboard_command(interaction: discord.Interaction):
        config = bot.db.get_guild_config(interaction.guild_id) or {}
        currency_name = config.get("currency_name", "coins")
        currency_emoji = config.get("currency_emoji", "💰")
        
        leaders = economy.get_leaderboard(interaction.guild_id)
        
        if not leaders:
            await interaction.response.send_message("No economy data yet!", ephemeral=True)
            return
        
        description = ""
        for i, (user_id, balance) in enumerate(leaders, 1):
            user = await bot.fetch_user(user_id)
            medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"**{i}.**"
            description += f"{medal} {user.mention} - **{balance:,}** {currency_name}\n"
        
        embed = discord.Embed(
            title=f"{currency_emoji} Economy Leaderboard",
            description=description,
            color=0xF1C40F
        )
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="addmoney", description="Add money to a user (Admin only)")
    @app_commands.describe(user="User to give money", amount="Amount to add")
    async def addmoney_command(interaction: discord.Interaction, user: discord.User, amount: int):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permission!", ephemeral=True)
            return
        
        config = bot.db.get_guild_config(interaction.guild_id) or {}
        currency_name = config.get("currency_name", "coins")
        
        balance = economy.add_money(interaction.guild_id, user.id, amount)
        await interaction.response.send_message(f"✅ Added **{amount:,}** {currency_name} to {user.mention}\nNew balance: **{balance:,}**", ephemeral=True)
    
    @bot.tree.command(name="removemoney", description="Remove money from a user (Admin only)")
    @app_commands.describe(user="User to remove money from", amount="Amount to remove")
    async def removemoney_command(interaction: discord.Interaction, user: discord.User, amount: int):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permission!", ephemeral=True)
            return
        
        config = bot.db.get_guild_config(interaction.guild_id) or {}
        currency_name = config.get("currency_name", "coins")
        
        if economy.remove_money(interaction.guild_id, user.id, amount):
            balance = economy.get_balance(interaction.guild_id, user.id)
            await interaction.response.send_message(f"✅ Removed **{amount:,}** {currency_name} from {user.mention}\nNew balance: **{balance:,}**", ephemeral=True)
        else:
            await interaction.response.send_message("❌ User doesn't have enough balance!", ephemeral=True)


def init_economy(bot):
    """Initialize economy system"""
    economy = EconomySystem(bot.db)
    bot.economy = economy
    setup_economy_commands(bot, economy)
    return economy
