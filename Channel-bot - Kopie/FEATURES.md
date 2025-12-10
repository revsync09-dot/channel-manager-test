# Channel Manager - Feature Documentation

## 🚀 New Features Added

### 1. 💬 Modmail System
Private user-to-moderator communication system.

**Commands:**
- `/modmail_reply <message>` - Reply to a modmail thread
- `/modmail_close [reason]` - Close a modmail thread
- `/modmail_contact <user> <message>` - Start a modmail thread with a user

**How it works:**
- Users DM the bot to open a modmail thread
- Creates a private channel in "Modmail" category
- Staff can reply using `/modmail_reply`
- Threads can be closed and archived

### 2. 🎭 Reaction Roles
Automated role assignment based on reactions.

**Commands:**
- `/reactionrole_create <channel> <title> [description]` - Create reaction role panel
- `/reactionrole_add <message_id> <emoji> <role>` - Add a reaction role
- `/reactionrole_remove <message_id> <emoji>` - Remove a reaction role
- `/reactionrole_list` - List all reaction roles

**Setup:**
1. Create a panel with `/reactionrole_create`
2. Add reactions with `/reactionrole_add`
3. Users react to get roles automatically

### 3. 🔨 Advanced Moderation
Comprehensive moderation toolkit with logging.

**Commands:**
- `/kick <member> [reason]` - Kick a member
- `/ban <member> [reason] [delete_days]` - Ban a member
- `/unban <user_id> [reason]` - Unban a user
- `/timeout <member> <duration> [reason]` - Timeout a member (1-40320 minutes)
- `/untimeout <member> [reason]` - Remove timeout
- `/warn <member> [reason]` - Warn a member
- `/warnings <member>` - View member warnings
- `/clearwarnings <member>` - Clear all warnings
- `/purge <amount>` - Delete messages (1-100)
- `/modlog <channel>` - Set moderation log channel
- `/slowmode <seconds> [channel]` - Set slowmode (0-21600 seconds)

**Features:**
- All actions are logged to configured mod log channel
- DMs users when they're moderated
- Warnings system with history
- Role hierarchy checks

### 4. ⚙️ Custom Commands
Create server-specific commands with custom responses.

**Commands:**
- `/customcmd_create <name> <response> [embed]` - Create custom command
- `/customcmd_edit <name> [response] [embed]` - Edit existing command
- `/customcmd_delete <name>` - Delete a command
- `/customcmd_list` - List all custom commands
- `/customcmd_info <name>` - Get command details

**Variables:**
- `{user}` - Mentions the user
- `{user.name}` - User's display name
- `{server}` - Server name
- `{channel}` - Channel mention

**Example:**
```
/customcmd_create ping "Pong! {user}, bot latency is low!" false
```
Users can then use: `!ping`

### 5. 🌐 Web Dashboard
Beautiful web interface with Discord OAuth authentication.

**Features:**
- Discord OAuth2 login
- Manage all your servers
- Configure bot settings per server
- Create/edit custom commands
- Set moderation log channels
- Configure welcome/leave messages
- Modern, responsive UI

**Setup:**
1. Add credentials to `.env`:
   ```
   DISCORD_CLIENT_ID=your_client_id
   DISCORD_CLIENT_SECRET=your_client_secret
   DISCORD_REDIRECT_URI=http://localhost:5000/callback
   FLASK_SECRET_KEY=random_secret_key
   ```

2. Run dashboard:
   ```bash
   python -m src.web.dashboard
   ```

3. Visit `http://localhost:5000`

**Dashboard Sections:**
- Overview - Quick stats and actions
- Custom Commands - Create/manage commands
- Moderation - Configure mod log
- Reaction Roles - Setup instructions
- Verification - Configure verification system
- Welcome/Leave - Set messages and channels
- Settings - Bot prefix, auto-role

### 6. 🗄️ Database System
SQLite database for persistent storage.

**Stores:**
- Guild configurations
- Custom commands
- Reaction roles
- User warnings
- Modmail threads and messages
- Dashboard sessions
- Verify configs
- Ticket configs
- Giveaways and entries

**Location:** `bot_data.db` (auto-created)

## 📋 Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure `.env`:
```bash
cp .env.example .env
# Edit .env with your values
```

3. Run the bot:
```bash
python -m src.bot
```

4. Run the dashboard (separate terminal):
```bash
python -m src.web.dashboard
```

## 🎨 Dashboard UI Features

- **Modern Design** - Clean, Discord-themed interface
- **Responsive** - Works on mobile, tablet, desktop
- **Real-time Updates** - Changes reflect immediately
- **Secure** - OAuth2 authentication
- **Permission-Based** - Only shows servers you manage

## 🔒 Security

- Dashboard requires Discord OAuth
- Only shows servers where user has manage permissions
- Session-based authentication
- Secure token storage in database
- CORS protection enabled

## 📝 Notes

- All moderation commands respect role hierarchy
- Bot needs appropriate permissions for each feature
- Dashboard updates may require bot restart to take effect
- Modmail creates channels automatically
- Database is backed up automatically

## 🆘 Support

For issues or questions:
1. Check bot has correct permissions
2. Verify .env configuration
3. Check console for error messages
4. Ensure database file is writable

## 🎯 Coming Soon

- Auto-moderation (spam detection, link filtering)
- Advanced analytics dashboard
- Music commands
- Economy system
- Leveling system
- Scheduled messages
- Server backups

Enjoy your enhanced Discord bot! 🚀
