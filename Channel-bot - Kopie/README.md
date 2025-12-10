# Channel Manager 🤖

**Made by Dudwig, Red_thz, and JThweb**

*A powerful Discord bot with advanced moderation, automation, and a beautiful web dashboard.*

---

## 🌟 Features

### 🚀 Server Templates
- **Gaming Server** - Voice channels, LFG, game categories
- **Community Server** - Discussion channels, events, social features
- **Support Server** - Ticket system, FAQ, help channels
- **Creative Server** - Showcase areas, feedback forums, collaboration
- Apply templates with one click from dashboard
- Automatic channel and role creation

### 🌐 Web Dashboard
- **Discord OAuth Login** - Secure authentication
- **Server Setup Templates** - Quick server configuration
- **Embed Maker** - Create embeds with live preview
- **Announcement System** - Send announcements to channels
- **Role Manager** - Create and manage roles with permissions
- **Custom Commands** - Full command management interface
- **Bot Invite Button** - Easy bot invitation with proper permissions
- **Modern UI** - Discord-themed responsive design

### 💬 Modmail System
- Private user-to-moderator communication
- Automatic thread management
- Staff reply system
- Message history and transcripts

### 🎭 Reaction Roles
- Automated role assignment via reactions
- Multiple roles per message
- Easy setup with slash commands
- Visual reaction role panels

### 🔨 Advanced Moderation
- **Actions:** Kick, Ban, Timeout, Warn, Purge
- **Logging:** Comprehensive mod action logs
- **Warnings:** Track user warnings with history
- **Slowmode:** Channel slowmode management
- **Auto-DM:** Notifies users of mod actions

### ⚙️ Custom Commands
- Create server-specific commands
- Variable support: `{user}`, `{user.name}`, `{server}`, `{channel}`, `{membercount}`
- Embed responses
- Dashboard and slash command management

### 💰 Economy System
- **Currency**: Customizable name and emoji
- **Daily Rewards**: Users claim daily currency
- **Work Command**: Earn money with cooldown
- **Transfers**: Pay other users
- **Leaderboard**: Top richest members
- **Admin Controls**: Add/remove money

### 📊 XP & Leveling
- **Message XP**: Earn XP from chatting (with cooldown)
- **Level Roles**: Auto-assign roles at certain levels
- **Leaderboards**: View top ranked members
- **Progress Tracking**: Beautiful rank cards
- **Customizable**: Set XP ranges per message
- **Level Announcements**: Optional level-up messages

### 🎉 Enhanced Giveaways
- **Timed Giveaways**: Set duration in minutes
- **Multiple Winners**: Choose winner count
- **Entry Tracking**: 🎉 reaction to enter
- **Admin Controls**: End giveaways early
- **Dashboard Integration**: Create from web interface

### 🎟️ Ticket System
- Support ticket creation
- Category-based tickets
- Staff role assignment
- Ticket transcripts

### ✅ Verification System
- Role-based verification
- Custom verification messages
- Banner and footer customization
- Auto-role on verify

### 🎉 Giveaways
- Timed giveaways
- Automatic winner selection
- Entry tracking
- Winner transcripts

### 🌐 Web Dashboard
- **Discord OAuth2** authentication
- **Manage servers** from web interface
- **Configure everything** - commands, moderation, welcome messages
- **Modern UI** - Beautiful Discord-themed design
- **Real-time updates** - Changes sync instantly
- **Mobile responsive** - Works on all devices

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Discord Bot Token
- Discord Application (for OAuth)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd channel-manager
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
```bash
copy .env.example .env
# Edit .env with your credentials
```

**Important:** Update `.env` with:
- Your Discord bot token
- OAuth client ID and secret
- Production domain (default: `https://jthweb.yugp.me:6767`)

4. **Run the bot**

**Recommended: Start everything together**
```bash
python app.py
```

This will start both:
- Discord bot (all commands and features)
- Web dashboard (on port 6767)

**Alternative: Run separately**
```bash
# Terminal 1 - Bot
python -m src.bot

# Terminal 2 - Dashboard
python run_dashboard.py
```

5. **First Time Setup**
- Invite the bot to your server (use dashboard invite button)
- Run `/setup` (or `/setup_dashboard`) in Discord to open the setup panel and dashboard links
- Visit the dashboard to configure your server
- Apply a template or customize manually

6. **Access dashboard**
```
Production: https://jthweb.yugp.me:6767
Local: http://localhost:6767
```

---

## 📝 Configuration

### Required Environment Variables

```env
# Discord Bot
DISCORD_TOKEN=your_bot_token

# Dashboard OAuth
DISCORD_CLIENT_ID=your_client_id
DISCORD_CLIENT_SECRET=your_client_secret
DISCORD_REDIRECT_URI=https://jthweb.yugp.me:6767/callback

# Security
FLASK_SECRET_KEY=random_secret_key
```

### Getting OAuth Credentials

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your application
3. Go to **OAuth2** section
4. Add redirect URL: `https://jthweb.yugp.me:6767/callback`
5. Copy Client ID and Client Secret
6. Add to `.env` file

---

## 📚 Commands

### Server Building
- `/setup` - Open the in-Discord module overview + buttons for every command group
- `/setup_dashboard` - Open server builder panel plus the same `/setup` buttons
- `/channel_setup` - Parse text or screenshot layouts to generate templates
- `/delete_channel` - Delete all channels
- `/delete_roles` - Delete all roles
- `/health` - Bot status and health check
- `/help` - Command help

### Modmail
- `/modmail_reply <message>` - Reply to thread
- `/modmail_close [reason]` - Close thread
- `/modmail_contact <user> <message>` - Start thread

### Reaction Roles
- `/reactionrole_create` - Create panel
- `/reactionrole_add <msg_id> <emoji> <role>` - Add role
- `/reactionrole_remove <msg_id> <emoji>` - Remove role
- `/reactionrole_list` - List all

### Moderation
- `/kick <member> [reason]` - Kick member
- `/ban <member> [reason]` - Ban member
- `/unban <user_id>` - Unban user
- `/timeout <member> <minutes>` - Timeout member
- `/warn <member> [reason]` - Warn member
- `/warnings <member>` - View warnings
- `/clearwarnings <member>` - Clear warnings
- `/purge <amount>` - Delete messages
- `/modlog <channel>` - Set log channel
- `/slowmode <seconds>` - Set slowmode

### Custom Commands
- `/customcmd_create <name> <response>` - Create command
- `/customcmd_edit <name>` - Edit command
- `/customcmd_delete <name>` - Delete command
- `/customcmd_list` - List commands
- `/customcmd_info <name>` - Command info

### Other Systems
- `/rules` - Show rules panel
- `/rules_setup` - Configure rules
- `/verify` - Show verify panel
- `/verify_setup` - Configure verification
- `/giveaway_start` - Start giveaway
- `/giveaway_end` - End giveaway

---

## 🎨 Dashboard Features

### Overview
- Server statistics
- Quick actions
- Bot status

### Custom Commands
- Create/edit commands
- Variable support
- Embed toggle

### Moderation
- Set mod log channel
- View available commands
- Configure auto-mod

### Reaction Roles
- Setup instructions
- Manage existing roles

### Verification
- Configure roles
- Custom messages
- Banner/footer

### Welcome/Leave
- Set welcome channel
- Custom messages
- Auto-role on join

### Settings
- Command prefix
- Auto-role configuration
- Bot customization

---

## 🗄️ Database

The bot uses SQLite for data persistence:

**Stored Data:**
- Guild configurations
- Custom commands
- Reaction roles
- User warnings
- Modmail threads
- Dashboard sessions
- Verification configs
- Ticket configs
- Giveaway data

**Location:** `bot_data.db` (auto-created)

---

## 🎯 Permissions

### Bot Permissions Required
- Manage Channels
- Manage Roles
- Kick Members
- Ban Members
- Moderate Members (Timeout)
- Manage Messages
- Send Messages
- Embed Links
- Attach Files
- Add Reactions
- Use External Emojis

### Invite Link
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=8&scope=bot%20applications.commands
```
*Replace `YOUR_CLIENT_ID` with your bot's client ID*

---

## 📱 Screenshots

### Dashboard
Beautiful Discord-themed web interface with modern design.

### Modmail
Private communication channels between users and staff.

### Reaction Roles
Automated role assignment with visual panels.

---

## 🔒 Security

- Discord OAuth2 authentication
- Session-based security
- Permission-based access control
- Secure token storage
- Role hierarchy enforcement
- CORS protection

---

## 🐛 Troubleshooting

### Bot won't start
- Check `DISCORD_TOKEN` in `.env`
- Verify bot has necessary intents enabled
- Check Python version (3.8+)

### Dashboard won't load
- Verify OAuth credentials in `.env`
- Check if port 5000 is available
- Ensure redirect URI matches exactly

### Commands not working
- Run `/help` to verify bot is online
- Check bot has required permissions
- Verify slash commands are synced

---

## 📄 License

This project is made by Dudwig, Red_thz, and JThweb. 

**Important:** Anyone claiming this as their own work may face legal action or Discord Terms of Service violations.

---

## 🆘 Support

For issues or questions:
1. Check [FEATURES.md](FEATURES.md) for detailed documentation
2. Verify `.env` configuration
3. Check console for error messages
4. Ensure bot has correct permissions

---

## 🎉 Credits

**Developers:**
- Dudwig
- Red_thz
- JThweb

**Technologies:**
- discord.py
- Flask
- SQLite
- Discord OAuth2

---

## 🔄 Updates

Stay tuned for future features:
- Auto-moderation system
- Advanced analytics
- Music commands
- Economy system
- Leveling system
- And much more!

---

**Enjoy your powerful Discord bot! 🚀**
