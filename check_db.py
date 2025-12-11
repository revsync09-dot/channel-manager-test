import sqlite3
conn=sqlite3.connect('bot_data.db')
cursor=conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print(cursor.fetchall())
try:
    cursor.execute('SELECT guild_id,user_id,activity_date,chat_minutes,voice_minutes FROM user_activity')
    print(cursor.fetchall())
except Exception as exc:
    print('query failed', exc)
conn.close()
