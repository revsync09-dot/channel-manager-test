import sqlite3
conn=sqlite3.connect('bot_data.db')
cursor=conn.cursor()
cursor.execute('SELECT guild_id,user_id,activity_date,chat_minutes,voice_minutes FROM user_activity')
print(cursor.fetchall())
conn.close()
