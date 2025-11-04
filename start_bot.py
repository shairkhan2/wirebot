#!/usr/bin/env python3
"""
Simple startup script for WireBot
This bypasses the test and starts the bot directly
"""
import os
import sys
import logging

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_requirements():
    """Check basic requirements before starting"""
    print("🔍 Checking requirements...")
    
    # Check if we can import telegram
    try:
        from telegram import Update
        print("✅ Telegram bot library available")
    except ImportError:
        print("❌ Telegram bot library not found. Run: pip install python-telegram-bot==20.7")
        return False
    
    # Check if config exists
    from config import config
    if not config.get('bot_token') or config.get('bot_token') == 'YOUR_BOT_TOKEN_HERE':
        print("❌ Bot token not configured. Please update wirebot_config.json")
        return False
    
    if not config.get('owner_id'):
        print("❌ Owner ID not configured. Please update wirebot_config.json")
        return False
    
    print("✅ Configuration looks good")
    
    # Check WireGuard script
    wg_script = config.get('wireguard.script_path', 'wireguard.sh')
    if not os.path.exists(wg_script):
        print(f"⚠️ WireGuard script not found at {wg_script}")
    else:
        print("✅ WireGuard script found")
    
    return True

def main():
    """Main startup function"""
    print("🤖 WireBot Startup")
    print("=" * 40)
    
    if not check_requirements():
        print("\n❌ Requirements check failed. Please fix the issues above.")
        return 1
    
    print("\n🚀 Starting WireBot...")
    
    try:
        from main import WireBot
        bot = WireBot()
        bot.run()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
        return 0
    except Exception as e:
        print(f"\n❌ Error starting bot: {e}")
        logging.exception("Bot startup error")
        return 1

if __name__ == "__main__":
    sys.exit(main())
