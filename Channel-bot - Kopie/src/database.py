"""
Database models for bot configuration and data storage.
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


class Database:
    def __init__(self, db_path: str = "bot_data.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Guild configs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guild_configs (
                guild_id INTEGER PRIMARY KEY,
                prefix TEXT DEFAULT '!',
                modlog_channel_id INTEGER,
                welcome_channel_id INTEGER,
                welcome_message TEXT,
                leave_message TEXT,
                auto_role_id INTEGER,
                config_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Custom commands
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                command_name TEXT NOT NULL,
                response TEXT NOT NULL,
                embed INTEGER DEFAULT 0,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, command_name)
            )
        """)
        
        # Reaction roles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reaction_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                emoji TEXT NOT NULL,
                role_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, message_id, emoji)
            )
        """)
        
        # Warnings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Modmail threads
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS modmail_threads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                closed_by INTEGER
            )
        """)
        
        # Modmail messages
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS modmail_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                is_staff INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (thread_id) REFERENCES modmail_threads(id)
            )
        """)
        
        # Verify configs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verify_configs (
                guild_id INTEGER PRIMARY KEY,
                verified_role_id INTEGER,
                unverified_role_id INTEGER,
                title TEXT,
                description TEXT,
                banner_url TEXT,
                footer_text TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Ticket configs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticket_configs (
                guild_id INTEGER PRIMARY KEY,
                category_id INTEGER,
                support_role_id INTEGER,
                log_channel_id INTEGER,
                config_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Giveaways
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                prize TEXT NOT NULL,
                description TEXT,
                duration_minutes INTEGER NOT NULL,
                winner_count INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active',
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ends_at TIMESTAMP NOT NULL,
                ended_at TIMESTAMP
            )
        """)
        
        # Giveaway entries
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS giveaway_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                giveaway_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(giveaway_id, user_id),
                FOREIGN KEY (giveaway_id) REFERENCES giveaways(id)
            )
        """)
        
        # Auto-moderation rules
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS automod_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                rule_type TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                action TEXT NOT NULL,
                threshold INTEGER,
                config_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Dashboard sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # User economy balances
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_economy (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                balance INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        
        # User XP and levels
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_xp (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                xp INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        
        # Level role rewards
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS level_roles (
                guild_id INTEGER NOT NULL,
                level INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, level)
            )
        """)
        
        # Pending setup requests (for dashboard -> bot communication)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_setup_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                setup_type TEXT NOT NULL,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed INTEGER DEFAULT 0
            )
        """)
        
        # User activity logs (chat + voice by date)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                activity_date TEXT NOT NULL DEFAULT (DATE('now')),
                chat_minutes INTEGER NOT NULL DEFAULT 0,
                voice_minutes INTEGER NOT NULL DEFAULT 0,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_user_activity_unique
            ON user_activity (guild_id, user_id, activity_date)
        """)
        
        conn.commit()
        conn.close()
    
    # Guild Config Methods
    def get_guild_config(self, guild_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM guild_configs WHERE guild_id = ?", (guild_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            config = dict(row)
            if config.get('config_json'):
                config['extra'] = json.loads(config['config_json'])
            return config
        return None
    
    def set_guild_config(self, guild_id: int, **kwargs):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Extract extra config
        extra = kwargs.pop('extra', None)
        if extra:
            kwargs['config_json'] = json.dumps(extra)
        
        # Build update query
        fields = ', '.join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [guild_id]
        
        cursor.execute(f"""
            INSERT INTO guild_configs (guild_id, {', '.join(kwargs.keys())})
            VALUES (?, {', '.join(['?'] * len(kwargs))})
            ON CONFLICT(guild_id) DO UPDATE SET {fields}, updated_at = CURRENT_TIMESTAMP
        """, [guild_id] + list(kwargs.values()) + values)
        
        conn.commit()
        conn.close()
    
    def get_user_activity_summary(
        self,
        guild_id: int,
        user_id: int,
        start_date: str,
        end_date: str,
    ) -> List[Dict]:
        """
        Return summed chat and voice minutes for a user between two dates inclusive.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT
                activity_date,
                SUM(chat_minutes) AS chat_minutes,
                SUM(voice_minutes) AS voice_minutes
            FROM user_activity
            WHERE guild_id = ? AND user_id = ? AND activity_date BETWEEN ? AND ?
            GROUP BY activity_date
            ORDER BY activity_date ASC
        """, (guild_id, user_id, start_date, end_date))
        
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def has_user_activity(self, guild_id: int, user_id: int) -> bool:
        """Return True if the user has any recorded activity entries."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM user_activity WHERE guild_id = ? AND user_id = ? LIMIT 1",
            (guild_id, user_id),
        )
        exists = cursor.fetchone() is not None
        conn.close()
        return exists

    def record_user_activity(
        self,
        guild_id: int,
        user_id: int,
        chat_minutes: int = 0,
        voice_minutes: int = 0,
        activity_date: str | None = None,
    ) -> None:
        """Insert or update chat/voice minute totals for a specific date."""
        if chat_minutes == 0 and voice_minutes == 0:
            return
        entry_date = activity_date or datetime.utcnow().date().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_activity (guild_id, user_id, activity_date, chat_minutes, voice_minutes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id, activity_date) DO UPDATE SET
                chat_minutes = chat_minutes + ?,
                voice_minutes = voice_minutes + ?,
                recorded_at = CURRENT_TIMESTAMP
        """, (
            guild_id,
            user_id,
            entry_date,
            chat_minutes,
            voice_minutes,
            chat_minutes,
            voice_minutes,
        ))
        conn.commit()
        conn.close()

    # Custom Commands Methods
    def add_custom_command(self, guild_id: int, name: str, response: str, embed: bool = False, created_by: int = None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO custom_commands (guild_id, command_name, response, embed, created_by)
            VALUES (?, ?, ?, ?, ?)
        """, (guild_id, name.lower(), response, int(embed), created_by))
        
        conn.commit()
        conn.close()
    
    def get_custom_commands(self, guild_id: int) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM custom_commands WHERE guild_id = ?", (guild_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def delete_custom_command(self, guild_id: int, name: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM custom_commands WHERE guild_id = ? AND command_name = ?", (guild_id, name.lower()))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        return deleted
    
    # Reaction Roles Methods
    def add_reaction_role(self, guild_id: int, message_id: int, channel_id: int, emoji: str, role_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO reaction_roles (guild_id, message_id, channel_id, emoji, role_id)
            VALUES (?, ?, ?, ?, ?)
        """, (guild_id, message_id, channel_id, emoji, role_id))
        
        conn.commit()
        conn.close()
    
    def get_reaction_roles(self, guild_id: int, message_id: int) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM reaction_roles WHERE guild_id = ? AND message_id = ?", (guild_id, message_id))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def delete_reaction_role(self, guild_id: int, message_id: int, emoji: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM reaction_roles WHERE guild_id = ? AND message_id = ? AND emoji = ?",
                      (guild_id, message_id, emoji))
        
        conn.commit()
        conn.close()
    
    # Warnings Methods
    def add_warning(self, guild_id: int, user_id: int, moderator_id: int, reason: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO warnings (guild_id, user_id, moderator_id, reason)
            VALUES (?, ?, ?, ?)
        """, (guild_id, user_id, moderator_id, reason))
        
        conn.commit()
        conn.close()
    
    def get_warnings(self, guild_id: int, user_id: int) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC",
                      (guild_id, user_id))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def clear_warnings(self, guild_id: int, user_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM warnings WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        
        conn.commit()
        conn.close()
    
    # Dashboard Sessions
    def create_session(self, session_id: str, user_id: int, access_token: str, refresh_token: str, expires_at: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO dashboard_sessions (session_id, user_id, access_token, refresh_token, expires_at)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, user_id, access_token, refresh_token, expires_at))
        
        conn.commit()
        conn.close()
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM dashboard_sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def delete_session(self, session_id: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM dashboard_sessions WHERE session_id = ?", (session_id,))
        
        conn.commit()
        conn.close()
    
    # Economy Methods
    def get_user_balance(self, guild_id: int, user_id: int) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT balance FROM user_economy WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else 0
    
    def add_balance(self, guild_id: int, user_id: int, amount: int) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO user_economy (guild_id, user_id, balance)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                balance = balance + ?,
                updated_at = CURRENT_TIMESTAMP
        """, (guild_id, user_id, amount, amount))
        
        cursor.execute("SELECT balance FROM user_economy WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        balance = cursor.fetchone()[0]
        
        conn.commit()
        conn.close()
        return balance
    
    def get_economy_leaderboard(self, guild_id: int, limit: int = 10) -> List[tuple]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT user_id, balance FROM user_economy
            WHERE guild_id = ?
            ORDER BY balance DESC
            LIMIT ?
        """, (guild_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    # XP/Leveling Methods
    def get_user_xp(self, guild_id: int, user_id: int) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT xp FROM user_xp WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else 0
    
    def add_user_xp(self, guild_id: int, user_id: int, amount: int) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO user_xp (guild_id, user_id, xp)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                xp = xp + ?,
                updated_at = CURRENT_TIMESTAMP
        """, (guild_id, user_id, amount, amount))
        
        cursor.execute("SELECT xp FROM user_xp WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        xp = cursor.fetchone()[0]
        
        conn.commit()
        conn.close()
        return xp
    
    def set_user_xp(self, guild_id: int, user_id: int, xp: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO user_xp (guild_id, user_id, xp)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                xp = ?,
                updated_at = CURRENT_TIMESTAMP
        """, (guild_id, user_id, xp, xp))
        
        conn.commit()
        conn.close()
    
    def get_xp_leaderboard(self, guild_id: int, limit: int = 10) -> List[tuple]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT user_id, xp FROM user_xp
            WHERE guild_id = ?
            ORDER BY xp DESC
            LIMIT ?
        """, (guild_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def set_level_role(self, guild_id: int, level: int, role_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO level_roles (guild_id, level, role_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, level) DO UPDATE SET
                role_id = ?,
                created_at = CURRENT_TIMESTAMP
        """, (guild_id, level, role_id, role_id))
        
        conn.commit()
        conn.close()
    
    def get_level_role(self, guild_id: int, level: int) -> Optional[int]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT role_id FROM level_roles WHERE guild_id = ? AND level = ?", (guild_id, level))
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else None
    
    def get_all_level_roles(self, guild_id: int) -> List[tuple]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT level, role_id FROM level_roles WHERE guild_id = ? ORDER BY level ASC", (guild_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def remove_level_role(self, guild_id: int, level: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM level_roles WHERE guild_id = ? AND level = ?", (guild_id, level))
        
        conn.commit()
        conn.close()


# Global database instance
db = Database()
