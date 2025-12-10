# Channel Manager - Complete Feature Guide

## 🌐 Web Dashboard

### Overview
Modern, Discord-themed web dashboard for complete bot management. Access at `https://jthweb.yugp.me:6767`

### Features

#### 🔐 Authentication
- **Discord OAuth2** - Secure login with Discord account
- **Session Management** - Persistent sessions with automatic refresh
- **Permission Checking** - Only server admins/owners can access

#### 🚀 Server Setup Templates

**Gaming Server Template**
- 5 voice channels (General, Squad, Ranked, Chill, AFK)
- Game-specific text channels (#looking-for-game, #game-news, #strategies)
- Roles: Member, Veteran, VIP, Game-specific roles
- Categories organized by game type

**Community Server Template**
- Welcome and rules channels
- Discussion channels (#general, #off-topic, #suggestions)
- Events and announcements
- Social features (#introductions, #selfies, #media)
- Roles: Member, Active, Helper, Supporter

**Support Server Template**
- Ticket system setup
- FAQ channels
- Help categories (Technical, Billing, General)
- Staff roles (Support Team, Moderator, Administrator)
- Announcement channels

**Creative Server Template**
- Showcase channels (#art, #writing, #music, #projects)
- Feedback forums
- Collaboration areas (#commissions, #collabs, #resources)
- Critique channels
- Roles: Artist, Writer, Musician, Designer

#### 📝 Embed Maker
**Live Preview** - See your embed as you build it

**Customization Options:**
- Title and description
- Color picker
- Author name and icon
- Thumbnail and image URLs
- Footer text and icon
- Timestamps
- Export to JSON
- Send directly to channel

#### 📢 Announcement System
- Send to specific channels by ID
- Normal text or embed format
- Optional @everyone mention
- Preview before sending
- History tracking

#### 🎭 Role Manager
**Single Role Creation:**
- Custom name and color
- Permission selection (kick, ban, manage channels, etc.)
- Hoist option (display separately)
- Mentionable setting

**Bulk Role Creation:**
- Create multiple roles at once
- One role name per line
- Automatic color assignment
- Default permissions

**Available Permissions:**
- Kick Members
- Ban Members
- Manage Channels
- Manage Roles
- Manage Messages
- Mention Everyone

#### ⚙️ Custom Commands
**Command Builder:**
- Name and response text
- Text or embed output
- Variable support:
  - `{user}` - Mentions the user
  - `{user.name}` - Username
  - `{server}` - Server name
  - `{channel}` - Channel name
  - `{membercount}` - Total members

**Command Management:**
- View all commands
- Edit existing commands
- Delete commands
- Test responses

#### 🔨 Moderation Settings
- Set mod log channel
- View available commands
- Configure auto-moderation

#### 👋 Welcome & Leave Messages
- Welcome channel configuration
- Custom welcome message with variables
- Leave message customization
- Auto-role on join

#### ⚙️ Bot Settings
- Custom command prefix
- Auto-role assignment
- Channel configurations
- Permission overrides

---

## 💬 Discord Commands

### Server Setup
- `/setup` - Opens the in-discord setup embed with module buttons
- `/setup_dashboard` - Opens the dashboard with template options and interactive `/setup` command buttons
- `/channel_setup` - Parses text or screenshot layouts into templates
- `/sync` - Syncs slash commands (admin only)

### Moderation
- `/kick <user> [reason]` - Kick a member
- `/ban <user> [reason] [delete_days]` - Ban a member
- `/unban <user_id>` - Unban a user by ID
- `/timeout <user> <duration> [reason]` - Timeout a member
- `/untimeout <user>` - Remove timeout
- `/warn <user> <reason>` - Warn a member
- `/warnings <user>` - View warnings for a user
- `/clearwarnings <user>` - Clear all warnings
- `/purge <amount>` - Delete multiple messages
- `/slowmode <seconds>` - Set channel slowmode
- `/modlog [channel]` - Configure mod log channel

### Modmail
- `/modmail_reply <message>` - Reply to a modmail thread
- `/modmail_close` - Close active modmail thread
- `/modmail_contact <user> <message>` - Start modmail with user
- **DM the bot** - Automatically creates modmail thread

### Reaction Roles
- `/reactionrole_create <channel> <title> <description>` - Create reaction role panel
- `/reactionrole_add <message_id> <role> <emoji>` - Add role reaction
- `/reactionrole_remove <message_id> <emoji>` - Remove role reaction
- `/reactionrole_list` - List all reaction roles

### Custom Commands
- `/customcmd_create <name> <response>` - Create custom command
- `/customcmd_edit <name> <response>` - Edit command response
- `/customcmd_delete <name>` - Delete custom command
- `/customcmd_list` - List all custom commands
- `/customcmd_info <name>` - View command details

### Tickets
- `/ticket <category> <subject>` - Create a support ticket
- `/ticket_close [reason]` - Close ticket channel
- `/ticket_setup` - Setup ticket system

### Verification
- `/verify_setup` - Configure verification system
- `/verify_post <channel>` - Post verification panel
- `/verify_role <role>` - Set verification role
- **Click button** - Users click to verify

### Giveaways
- `/giveaway_start <duration> <winners> <prize>` - Start giveaway
- `/giveaway_end <message_id>` - End giveaway early
- **React with 🎉** - Enter giveaway

### Rules System
- `/rules` - View server rules
- `/rules_setup` - Configure rules (admin only)

### Change Logging
- `/changelog_start <channel>` - Start logging changes
- `/changelog_stop` - Stop logging changes

---

## 🗄️ Database Schema

### Guild Configs
- Prefix, auto-role, welcome/leave messages
- Channel IDs (welcome, modlog, etc.)
- Feature toggles

### Custom Commands
- Command name and response
- Embed flag
- Creator ID and timestamp

### Reaction Roles
- Message ID and role mappings
- Emoji configurations

### Warnings
- User ID, reason, moderator
- Timestamp and guild tracking

### Modmail Threads
- Thread IDs, user associations
- Message history
- Open/closed status

### Verification Configs
- Role IDs, channel settings
- Custom messages and banners

### Tickets
- Category mappings
- Staff role assignments
- Transcript storage

### Giveaways
- Prize, duration, winner count
- Entry tracking
- Message IDs

---

## 🎨 UI/UX Features

### Modern Design
- Discord-themed color scheme
- Gradient text effects
- Smooth animations
- Hover effects

### Responsive Layout
- Mobile-friendly sidebar
- Adaptive grid layouts
- Touch-optimized buttons
- Responsive forms

### User Experience
- Real-time notifications
- Live embed preview
- Inline validation
- Loading states
- Error handling

### Accessibility
- Keyboard navigation
- ARIA labels
- Color contrast compliance
- Screen reader support

---

## 🔧 Technical Details

### Backend
- **Flask 3.0+** - Web framework
- **Discord.py 2.4+** - Bot framework
- **SQLite** - Database
- **Python-dotenv** - Environment management
- **Flask-CORS** - API security

### Frontend
- **Vanilla JavaScript** - No framework dependencies
- **Modern CSS** - Variables, Grid, Flexbox
- **Inter Font** - Clean typography
- **Responsive Design** - Mobile-first approach

### Security
- OAuth2 authentication
- Session management
- CSRF protection
- Permission validation
- Secure token storage

### Performance
- Lazy loading
- Efficient queries
- Cached configurations
- Optimized assets
- Minimal API calls

---

## 🚀 Deployment

### Production Setup
1. Set environment variables for production domain
2. Configure SSL/TLS certificates
3. Update OAuth redirect URIs in Discord Developer Portal
4. Set `DASHBOARD_URL=https://jthweb.yugp.me:6767`
5. Run with `python app.py`

### Port Configuration
Default port: `6767`
Change via `DASHBOARD_PORT` environment variable

### Domain Setup
Update these in `.env`:
```env
DISCORD_REDIRECT_URI=https://jthweb.yugp.me:6767/callback
DASHBOARD_URL=https://jthweb.yugp.me:6767
```

---

## 📊 Permissions Required

### Bot Permissions (Integer: 8)
- Administrator (for full functionality)

### Recommended Permissions (Integer: 1099511627775)
- Manage Roles
- Manage Channels
- Kick Members
- Ban Members
- Manage Messages
- Read Messages
- Send Messages
- Embed Links
- Attach Files
- Add Reactions
- Manage Webhooks

### User Permissions
- Manage Server (0x20) or Administrator (0x8)
- Required to access dashboard
- Bot checks on every API request

---

## 🐛 Troubleshooting

### OAuth Not Working
1. Verify client ID and secret in `.env`
2. Check redirect URI matches Discord Developer Portal
3. Ensure URL encoding is correct
4. Clear browser cookies and retry

### Bot Not Responding
1. Check bot token is correct
2. Verify intents are enabled in Developer Portal
3. Ensure bot has necessary permissions
4. Run `/sync` to sync slash commands

### Dashboard Not Loading
1. Check port 6767 is not in use
2. Verify all environment variables are set
3. Check Flask secret key is generated
4. Review console for error messages

### Templates Not Applying
1. Ensure bot has Administrator permission
2. Check channel/role limits not exceeded
3. Verify template data is valid
4. Review bot logs for errors

---

## 🎯 Future Enhancements

### Planned Features
- Auto-moderation rules
- Custom embed templates library
- Scheduled announcements
- Server analytics dashboard
- Backup and restore system
- Multi-language support
- Advanced logging filters
- Role hierarchy manager

### Community Requests
- Voice channel management
- Advanced ticket categories
- Giveaway scheduler
- Custom verification flows
- Integration with other bots
- API for external tools

---

## 📞 Support

For help with Channel Manager:
1. Check this documentation
2. Review error messages in console
3. Verify environment configuration
4. Test with `/setup` (or `/setup_dashboard`) command in Discord
5. Contact bot developers

---

**Made with ❤️ by Dudwig, Red_thz, and JThweb**
**Only for you and your Commoinouty***
