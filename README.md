# 🤖 WireBot - Enhanced WireGuard Management Bot

A comprehensive Telegram bot for managing WireGuard VPN servers with a user-friendly menu interface, advanced user management, and full feature set.

## ✨ Features

### 🎯 Core Functionality
- **Menu-Driven Interface**: Interactive inline keyboards for easy navigation
- **Full Client Management**: Add, remove, list clients with QR codes as images
- **Server Monitoring**: Real-time status, connection stats, and system info
- **Advanced User Management**: Username/ID support with granular permissions
- **Backup & Restore**: Complete configuration backup system with file downloads
- **Config File Integration**: Sends config content in code format alongside files

### 📱 User Interface
- **Main Dashboard**: Server status overview with quick actions
- **Client Management**: Visual client list with connection status and QR codes
- **Server Configuration**: View and download server config files
- **User Management**: Multi-user authorization with custom limits
- **Interactive Flows**: Menu-driven client and user creation (no commands needed)

### 🔒 Security & Access Control
- **Environment-Based Config**: Secure credential management with .env files
- **Owner-Only Admin**: Critical operations restricted to bot owner
- **Granular User Limits**: Per-user client limits, rate limits, and permissions
- **Username Support**: Add users by @username or User ID
- **Audit Logging**: Track all bot operations
- **Input Validation**: Comprehensive sanitization and validation

### 🎨 Enhanced Features
- **QR Code Images**: PNG QR codes with robust sending (multiple fallback methods)
- **Username Display**: Friendly @username display in all user lists
- **Config Content**: View configuration files in formatted code blocks
- **File Downloads**: Direct file downloads for configs and backups
- **Permission Toggles**: Easy enable/disable of user permissions
- **Smart Navigation**: Breadcrumb navigation with cancel/retry options

## 🚀 Quick Start

### Prerequisites
- Ubuntu/Debian/CentOS server with root access
- Python 3.8+ installed
- Telegram Bot Token (from @BotFather)
- Your Telegram User ID (get from @userinfobot)

### 📦 Installation

1. **Clone the repository:**
```bash
git clone https://github.com/shairkhan2/wirebot.git
cd wirebot
```

2. **Install dependencies:**
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install system dependencies (Ubuntu/Debian)
sudo apt update
sudo apt install -y qrencode libqrencode-dev

# For CentOS/RHEL
# sudo yum install -y qrencode qrencode-devel
```

3. **Configure environment variables:**
```bash
# Copy the example environment file
cp env.example .env

# Edit the .env file with your credentials
nano .env
```

4. **Set up your .env file:**
```env
# Required: Get from @BotFather
BOT_TOKEN=your_bot_token_here

# Required: Your Telegram User ID (get from @userinfobot)
OWNER_ID=your_user_id_here

# Optional: Additional authorized users (comma-separated)
AUTHORIZED_USERS=user_id_1,user_id_2

# Optional: Custom limits
MAX_CLIENTS_PER_USER=50
RATE_LIMIT_PER_USER=20
```

5. **Make the WireGuard script executable:**
```bash
chmod +x wireguard.sh
```

6. **Start the bot:**
```bash
python start_bot.py
```

### 🔧 Advanced Setup

1. **Clone and Setup**
```bash
cd /root
git clone https://github.com/shairkhan2/wirebot.git # or download files
cd wirebot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **Configure Bot**
Edit `config.py` or let it auto-create `wirebot_config.json`:
```json
{
  "bot_token": "YOUR_BOT_TOKEN_HERE",
  "owner_id": YOUR_TELEGRAM_USER_ID,
  "authorized_users": [YOUR_TELEGRAM_USER_ID]
}
```

3. **Install WireGuard** (if not already installed)
```bash
# Make sure wireguard.sh is executable
chmod +x wireguard.sh

# Start the bot
python main.py
```

4. **First Run**
- Send `/start` to your bot
- Use `/install` to set up WireGuard (owner only)
- Start managing clients through the menu interface

## 📖 Usage Guide

### 🎮 Commands

| Command | Description | Access Level |
|---------|-------------|--------------|
| `/start` | Show main menu dashboard | All users |
| `/help` | Display help information | All users |
| `/status` | Quick server status | All users |
| `/add_client` | Add new VPN client | All users |
| `/install` | Install WireGuard | Owner only |
| `/add_user` | Authorize new user | Owner only |
| `/users` | List authorized users | Owner only |

### 🖱️ Menu Navigation

**Main Menu Options:**
- 👥 **Client Management**: Add, remove, list clients
- 📊 **Server Status**: System and WireGuard status
- ⚙️ **Server Config**: Configuration management
- 📋 **Connection Stats**: Real-time statistics
- 💾 **Backup & Restore**: Configuration backups
- 🔒 **User Management**: Multi-user administration

**Client Management:**
- ➕ **Menu-Driven Creation**: Complete client setup without typing commands
- 📋 List Clients: View all clients with real-time connection status  
- 🗑️ Remove Client: Safe deletion with confirmation dialogs
- 📱 QR Code Images: High-quality PNG QR codes for easy mobile scanning
- 📄 Config Files: Download .conf files + formatted text for easy copying
- 🎯 **One-Click Defaults**: Smart DNS selection with examples and quick options

### 📊 Monitoring Features

**Server Status Display:**
- System uptime and resource usage
- WireGuard service status
- Network interface information
- Client connection overview

**Connection Statistics:**
- Total and active client counts
- Data transfer statistics (upload/download)
- Real-time connection status
- Last seen timestamps

## 🔧 Configuration

### Bot Configuration (`wirebot_config.json`)
```json
{
  "bot_token": "YOUR_BOT_TOKEN",
  "owner_id": "your_user_id",
  "authorized_users": ["your_user_id", "other_user_id"],
  "wireguard": {
    "script_path": "/root/wirebot/wireguard.sh",
    "config_path": "/etc/wireguard/wg0.conf",
    "export_paths": ["/root/", "/home/shair/", "~/", "/tmp/"]
  },
  "features": {
    "multi_user": true,
    "monitoring": true,
    "backup": true,
    "audit_log": true
  },
  "limits": {
    "max_clients": 100,
    "rate_limit": 10
  }
}
```

### WireGuard Script Configuration
The bot uses the enhanced `wireguard.sh` script with these features:
- Automatic client management
- QR code generation
- Configuration backup
- Multi-platform support

## 🐛 Troubleshooting

### Common Issues

**Config File Not Found After Creation:**
- ✅ **FIXED**: Bot now uses proper path detection
- Automatically searches multiple possible locations
- Matches WireGuard script's export directory logic

**Permission Denied:**
- Ensure bot runs with appropriate sudo access
- Check file permissions on wireguard.sh
- Verify WireGuard installation

**Bot Not Responding:**
- Check bot token in configuration
- Verify network connectivity
- Review logs for error messages

### Debug Mode
Enable detailed logging by setting log level to DEBUG in `main.py`:
```python
logging.basicConfig(level=logging.DEBUG)
```

## 🔄 Backup & Recovery

### Automatic Backups
- Use the "💾 Backup & Restore" menu option
- Creates timestamped tar.gz archives
- Includes server and all client configurations
- Downloadable through Telegram

### Manual Backup
```bash
# Backup WireGuard configs
tar -czf wireguard_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
  /etc/wireguard/ \
  /root/*.conf \
  /home/*/client*.conf
```

## 🚀 Advanced Features

### Multi-User Management
- Owner can authorize additional users
- Granular permission system
- Audit trail for all operations
- User-specific rate limiting

### Monitoring & Statistics
- Real-time connection monitoring
- Bandwidth usage tracking
- System resource monitoring
- Historical data collection

### API Integration
- Extensible architecture for custom integrations
- Webhook support for external monitoring
- REST API endpoints (future feature)

## 📝 Development

### Project Structure
```
wirebot/
├── main.py              # Main bot application
├── config.py            # Configuration management
├── wireguard_manager.py # WireGuard operations
├── menu_handlers.py     # Menu system and callbacks
├── utils.py             # Utility functions
├── wireguard.sh         # WireGuard installation script
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

### Adding New Features
1. Add functionality to appropriate module
2. Update menu handlers if needed
3. Add configuration options
4. Update help documentation
5. Test thoroughly

## 📄 License

This project is released under the MIT License. See LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Support

For support and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review the logs for error details

## 🎉 Acknowledgments

- Based on the WireGuard installation script by hwdsl2
- Uses python-telegram-bot library
- Inspired by the need for better WireGuard management tools

---

**Made with ❤️ for the WireGuard community**
