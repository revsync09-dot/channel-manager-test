from src.database import Database
from datetime import datetime
import os
os.chdir('C:\\Users\\subha\\Downloads\\Channel-bot')
db=Database()
db.record_user_activity(1234,5678,chat_minutes=1,activity_date='2025-12-09')
print('inserted')
