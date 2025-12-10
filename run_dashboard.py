"""
Standalone script to run just the web dashboard.
Use this if you want to run the dashboard separately from the bot.
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.web.dashboard import run_dashboard

if __name__ == '__main__':
    print("🌐 Starting Channel Manager Dashboard...")
    print("📍 Dashboard will be available at: http://localhost:5000")
    print("🔑 Make sure your .env file has DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, and FLASK_SECRET_KEY configured")
    print("")
    
    port = int(os.getenv('DASHBOARD_PORT', 5000))
    run_dashboard(host='0.0.0.0', port=port)
