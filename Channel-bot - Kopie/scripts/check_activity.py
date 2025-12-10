import argparse
import sqlite3


def parse_args():
    parser = argparse.ArgumentParser(description="Show recent entries from the user_activity table.")
    parser.add_argument("--limit", type=int, default=10, help="Number of rows to display (default: 10)")
    parser.add_argument("--guild", type=int, help="Filter by guild ID")
    parser.add_argument("--user", type=int, help="Filter by user ID")
    parser.add_argument("--path", default="bot_data.db", help="Database file path")
    return parser.parse_args()


def main():
    args = parse_args()
    conn = sqlite3.connect(args.path)
    cursor = conn.cursor()
    query = """
        SELECT guild_id, user_id, activity_date, chat_minutes, voice_minutes, recorded_at
        FROM user_activity
    """
    filters = []
    values = []
    if args.guild:
        filters.append("guild_id = ?")
        values.append(args.guild)
    if args.user:
        filters.append("user_id = ?")
        values.append(args.user)
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY recorded_at DESC LIMIT ?"
    values.append(args.limit)

    cursor.execute(query, values)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("No rows found.")
        return

    for guild_id, user_id, activity_date, chat_min, voice_min, recorded_at in rows:
        print(f"{activity_date} | guild={guild_id} user={user_id} chat={chat_min} voice={voice_min} recorded={recorded_at}")


if __name__ == "__main__":
    main()
