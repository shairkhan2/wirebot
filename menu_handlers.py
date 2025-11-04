"""
Menu system handlers for WireBot
"""
import logging
import os
from typing import Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes, ConversationHandler
from config import config
from wireguard_manager import wg_manager
from utils import format_file_size, format_duration, escape_markdown

logger = logging.getLogger(__name__)

# Conversation states
WAITING_CLIENT_NAME, WAITING_DNS_SERVERS, WAITING_CONFIRM_REMOVE = range(3)

class MenuHandler:
    """Handles all menu interactions and callbacks"""
    
    @staticmethod
    def create_main_menu() -> InlineKeyboardMarkup:
        """Create the main menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("👥 Client Management", callback_data="menu_clients"),
                InlineKeyboardButton("📊 Server Status", callback_data="menu_status")
            ],
            [
                InlineKeyboardButton("⚙️ Server Config", callback_data="menu_config"),
                InlineKeyboardButton("📋 Connection Stats", callback_data="menu_stats")
            ],
            [
                InlineKeyboardButton("💾 Backup & Restore", callback_data="menu_backup"),
                InlineKeyboardButton("🔒 User Management", callback_data="menu_users")
            ],
            [
                InlineKeyboardButton("ℹ️ Help", callback_data="menu_help"),
                InlineKeyboardButton("🔄 Refresh", callback_data="menu_main")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_clients_menu() -> InlineKeyboardMarkup:
        """Create the client management menu"""
        keyboard = [
            [
                InlineKeyboardButton("➕ Add Client", callback_data="client_add"),
                InlineKeyboardButton("📋 List Clients", callback_data="client_list")
            ],
            [
                InlineKeyboardButton("🗑️ Remove Client", callback_data="client_remove"),
                InlineKeyboardButton("📱 Show QR Code", callback_data="client_qr")
            ],
            [
                InlineKeyboardButton("📄 Get Config", callback_data="client_config"),
                InlineKeyboardButton("🔄 Refresh List", callback_data="client_list")
            ],
            [InlineKeyboardButton("⬅️ Back to Main", callback_data="menu_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_client_selection_menu(clients: List[Dict], action: str) -> InlineKeyboardMarkup:
        """Create a menu for selecting clients"""
        keyboard = []
        
        for client in clients:
            status_emoji = "🟢" if client['status']['connected'] else "🔴"
            button_text = f"{status_emoji} {client['name']}"
            callback_data = f"client_{action}_{client['name']}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="menu_clients")])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_user_menu(is_owner: bool) -> InlineKeyboardMarkup:
        """Create user management menu"""
        keyboard = []
        
        if is_owner:
            keyboard.extend([
                [
                    InlineKeyboardButton("👥 List Users", callback_data="users_list"),
                    InlineKeyboardButton("➕ Add User", callback_data="users_add")
                ],
                [
                    InlineKeyboardButton("🗑️ Remove User", callback_data="users_remove"),
                    InlineKeyboardButton("⚙️ Manage Limits", callback_data="users_limits")
                ],
                [
                    InlineKeyboardButton("📊 User Stats", callback_data="users_stats"),
                    InlineKeyboardButton("🔧 Bulk Actions", callback_data="users_bulk")
                ]
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("👤 My Info", callback_data="users_info")
            ])
        
        keyboard.append([InlineKeyboardButton("⬅️ Back to Main", callback_data="menu_main")])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_user_limits_menu() -> InlineKeyboardMarkup:
        """Create user limits management menu"""
        keyboard = [
            [
                InlineKeyboardButton("👤 Set User Limits", callback_data="limits_set_user"),
                InlineKeyboardButton("📋 View All Limits", callback_data="limits_view_all")
            ],
            [
                InlineKeyboardButton("🔧 Default Limits", callback_data="limits_default"),
                InlineKeyboardButton("📊 Limits Report", callback_data="limits_report")
            ],
            [
                InlineKeyboardButton("⬅️ Back", callback_data="menu_users")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

class MessageFormatter:
    """Formats messages for different menu screens"""
    
    @staticmethod
    def format_main_menu(user_name: str) -> str:
        """Format main menu message"""
        server_status = wg_manager.get_server_status()
        
        if not server_status['installed']:
            return (
                f"🤖 *WireBot Dashboard*\n\n"
                f"👋 Welcome, {escape_markdown(user_name)}\\!\n\n"
                f"❌ *WireGuard not installed*\n"
                f"Use /install to set up WireGuard first\\.\n\n"
                f"📱 *Quick Actions:*\n"
                f"• Use the buttons below to navigate\n"
                f"• Type /help for command list\n"
                f"• Type /install to install WireGuard"
            )
        
        wg_status = server_status['wireguard']
        clients = server_status.get('clients', [])
        connected_count = sum(1 for c in clients if c['status']['connected'])
        
        status_emoji = "🟢" if wg_status.get('service_active') else "🔴"
        
        return (
            f"🤖 *WireBot Dashboard*\n\n"
            f"👋 Welcome, {escape_markdown(user_name)}\\!\n\n"
            f"{status_emoji} *WireGuard Status:* "
            f"{'Active' if wg_status.get('service_active') else 'Inactive'}\n"
            f"👥 *Clients:* {len(clients)} total, {connected_count} connected\n"
            f"⏱️ *Uptime:* {server_status['system'].get('uptime', 'Unknown')}\n\n"
            f"📱 *Quick Actions:*\n"
            f"• Manage clients and view statistics\n"
            f"• Monitor server performance\n"
            f"• Backup and restore configurations"
        )
    
    @staticmethod
    def format_server_status() -> str:
        """Format server status message"""
        status = wg_manager.get_server_status()
        
        if not status['installed']:
            return "❌ *WireGuard Status*\n\nWireGuard is not installed on this server\\."
        
        wg_info = status['wireguard']
        sys_info = status['system']
        server_config = status.get('server_config', {})
        
        # System info with proper escaping
        memory = sys_info.get('memory', {})
        memory_percent = memory.get('usage_percent', 0)
        memory_text = f"{memory_percent}% used" if 'usage_percent' in memory else "Unknown"
        
        load_avg = sys_info.get('load_avg', ['?', '?', '?'])
        load_avg_text = escape_markdown(' '.join(str(x) for x in load_avg))
        
        # WireGuard status
        service_status = "🟢 Active" if wg_info.get('service_active') else "🔴 Inactive"
        interface_status = "🟢 Up" if wg_info.get('interface_exists') else "🔴 Down"
        
        # Escape all dynamic content
        uptime = escape_markdown(sys_info.get('uptime', 'Unknown'))
        memory_escaped = escape_markdown(memory_text)
        
        message = (
            f"📊 *Server Status*\n\n"
            f"🖥️ *System Information:*\n"
            f"• Uptime: {uptime}\n"
            f"• Memory: {memory_escaped}\n"
            f"• Load Average: {load_avg_text}\n\n"
            f"🔧 *WireGuard Service:*\n"
            f"• Service: {service_status}\n"
            f"• Interface: {interface_status}\n"
        )
        
        if server_config:
            endpoint = escape_markdown(str(server_config.get('endpoint', 'Unknown')))
            port = escape_markdown(str(server_config.get('port', 'Unknown')))
            client_count = server_config.get('client_count', 0)
            
            message += (
                f"• Endpoint: {endpoint}\n"
                f"• Port: {port}\n"
                f"• Clients: {client_count}\n"
            )
        
        return message
    
    @staticmethod
    def format_client_list(clients: List[Dict]) -> str:
        """Format client list message"""
        if not clients:
            return "👥 *Client List*\n\nNo clients configured\\."
        
        message = f"👥 *Client List* \\({len(clients)} total\\)\n\n"
        
        for i, client in enumerate(clients, 1):
            status_emoji = "🟢" if client['status']['connected'] else "🔴"
            config_emoji = "📄" if client['config_exists'] else "❌"
            
            message += f"{i}\\. {status_emoji} *{escape_markdown(client['name'])}*\n"
            message += f"   📱 Config: {config_emoji}\n"
            
            if client['status']['connected']:
                if client['status']['transfer']:
                    rx = format_file_size(client['status']['transfer']['rx'])
                    tx = format_file_size(client['status']['transfer']['tx'])
                    message += f"   📊 Transfer: ↓{rx} ↑{tx}\n"
                
                if client['status']['last_handshake']:
                    import datetime
                    last_seen = datetime.datetime.fromtimestamp(client['status']['last_handshake'])
                    message += f"   🕐 Last seen: {last_seen.strftime('%H:%M:%S')}\n"
            
            message += "\n"
        
        return message.rstrip()
    
    @staticmethod
    def format_connection_stats() -> str:
        """Format connection statistics message"""
        stats = wg_manager.get_connection_stats()
        
        # Escape dynamic content
        total_rx = escape_markdown(format_file_size(stats['total_transfer']['rx']))
        total_tx = escape_markdown(format_file_size(stats['total_transfer']['tx']))
        
        message = (
            f"📋 *Connection Statistics*\n\n"
            f"👥 *Overview:*\n"
            f"• Total Clients: {stats['total_clients']}\n"
            f"• Connected: {stats['connected_clients']}\n"
            f"• Offline: {stats['total_clients'] - stats['connected_clients']}\n\n"
            f"📊 *Data Transfer:*\n"
            f"• Downloaded: {total_rx}\n"
            f"• Uploaded: {total_tx}\n\n"
        )
        
        if stats['connected_clients'] > 0:
            message += f"🟢 *Active Connections:*\n"
            for client in stats['clients']:
                if client['status']['connected']:
                    message += f"• {escape_markdown(client['name'])}\n"
        
        return message
    
    @staticmethod
    def format_server_config() -> str:
        """Format server configuration message"""
        status = wg_manager.get_server_status()
        
        if not status['installed']:
            return "❌ *Server Configuration*\n\nWireGuard is not installed on this server\\."
        
        wg_info = status['wireguard']
        server_config = status.get('server_config', {})
        
        # Get configuration details
        config_path = "/etc/wireguard/wg0.conf"
        interface_ip = server_config.get('interface_ip', 'Unknown')
        listen_port = server_config.get('listen_port', 'Unknown')
        public_key = server_config.get('public_key', 'Unknown')
        
        # Escape dynamic content
        interface_ip_escaped = escape_markdown(str(interface_ip))
        listen_port_escaped = escape_markdown(str(listen_port))
        public_key_escaped = escape_markdown(str(public_key)[:20] + "..." if len(str(public_key)) > 20 else str(public_key))
        
        # Check if config file exists
        config_exists = os.path.exists(config_path)
        config_size = ""
        if config_exists:
            try:
                size = os.path.getsize(config_path)
                config_size = f" \\({escape_markdown(format_file_size(size))}\\)"
            except:
                config_size = ""
        
        message = (
            f"⚙️ *Server Configuration*\n\n"
            f"📁 *Configuration File:*\n"
            f"• Path: `/etc/wireguard/wg0\\.conf`\n"
            f"• Status: {'✅ Exists' if config_exists else '❌ Missing'}{config_size}\n\n"
            f"🔧 *Interface Settings:*\n"
            f"• Interface IP: {interface_ip_escaped}\n"
            f"• Listen Port: {listen_port_escaped}\n"
            f"• Public Key: {public_key_escaped}\n\n"
            f"🌐 *Service Status:*\n"
            f"• Service: {'🟢 Active' if wg_info.get('service_active') else '🔴 Inactive'}\n"
            f"• Interface: {'🟢 Up' if wg_info.get('interface_up') else '🔴 Down'}\n\n"
            f"📋 *Actions Available:*\n"
            f"• View complete configuration file\n"
            f"• Download configuration as file\n"
            f"• Check service status and logs"
        )
        
        return message
    
    @staticmethod
    def format_help_message() -> str:
        """Format help message"""
        return (
            f"ℹ️ *WireBot Help*\n\n"
            f"🤖 *Commands:*\n"
            f"• `/start` \\- Show main menu\n"
            f"• `/help` \\- Show this help\n"
            f"• `/status` \\- Quick server status\n"
            f"• `/install` \\- Install WireGuard\n\n"
            f"📱 *Navigation:*\n"
            f"• Use inline buttons to navigate\n"
            f"• Most actions have confirmation steps\n"
            f"• Use 'Back' buttons to return\n\n"
            f"👥 *Client Management:*\n"
            f"• Add new VPN clients\n"
            f"• Remove existing clients\n"
            f"• Generate QR codes\n"
            f"• Download config files\n\n"
            f"📊 *Monitoring:*\n"
            f"• View server status\n"
            f"• Check connection statistics\n"
            f"• Monitor data usage\n\n"
            f"💾 *Backup:*\n"
            f"• Create configuration backups\n"
            f"• Download all configs\n\n"
            f"🔒 *Security:*\n"
            f"• Multi\\-user support\n"
            f"• Owner\\-only admin functions\n"
            f"• Audit logging"
        )

async def handle_menu_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text input during menu-driven flows"""
    user_id = update.effective_user.id
    
    # Check authorization
    if not config.is_authorized(user_id):
        await update.message.reply_text("❌ Access denied.")
        return
    
    # Check if user is in a menu state
    menu_state = context.user_data.get('menu_state')
    if not menu_state:
        return  # Not in a menu flow, ignore
    
    try:
        if menu_state == 'waiting_client_name':
            await handle_menu_client_name(update, context)
        elif menu_state == 'waiting_dns_servers':
            await handle_menu_dns_servers(update, context)
        elif menu_state == 'waiting_user_id':
            await handle_menu_user_id(update, context)
        elif menu_state == 'waiting_max_clients':
            await handle_menu_max_clients(update, context)
        elif menu_state == 'waiting_rate_limit':
            await handle_menu_rate_limit(update, context)
    except Exception as e:
        logger.error(f"Error handling menu text input: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")
        context.user_data.clear()

async def handle_menu_client_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle client name input in menu flow"""
    from utils import sanitize_client_name, escape_markdown
    from wireguard_manager import wg_manager
    
    client_name = update.message.text.strip()
    sanitized_name = sanitize_client_name(client_name)
    
    if not sanitized_name:
        await update.message.reply_text(
            "❌ Invalid client name. Please use only letters, numbers, hyphens, and underscores."
        )
        return
    
    # Check if client already exists
    clients = wg_manager.list_clients()
    if any(client['name'] == sanitized_name for client in clients):
        await update.message.reply_text(
            f"❌ Client '{sanitized_name}' already exists. Please choose a different name."
        )
        return
    
    # Store client name and move to DNS step
    context.user_data['client_name'] = sanitized_name
    context.user_data['menu_state'] = 'waiting_dns_servers'
    
    # Send DNS input message
    await update.message.reply_text(
        f"✅ Client name: *{escape_markdown(sanitized_name)}*\n\n"
        f"Now enter DNS servers \\(comma\\-separated IP addresses\\):\n\n"
        f"💡 *Examples:*\n"
        f"• `8\\.8\\.8\\.8` \\(Google DNS\\)\n"
        f"• `1\\.1\\.1\\.1,1\\.0\\.0\\.1` \\(Cloudflare DNS\\)\n"
        f"• `8\\.8\\.8\\.8,8\\.8\\.4\\.4` \\(Google Primary & Secondary\\)\n\n"
        f"Or type 'default' to use Google DNS \\(8\\.8\\.8\\.8, 8\\.8\\.4\\.4\\)",
        parse_mode='MarkdownV2',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Use Default DNS", callback_data="menu_use_default_dns"),
            InlineKeyboardButton("❌ Cancel", callback_data="menu_clients")
        ]])
    )

async def handle_menu_dns_servers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle DNS servers input in menu flow"""
    from utils import validate_dns_servers
    
    dns_input = update.message.text.strip().lower()
    
    # Handle 'default' keyword
    if dns_input == 'default':
        dns_servers = "8.8.8.8,8.8.4.4"
    else:
        if not validate_dns_servers(update.message.text.strip()):
            await update.message.reply_text(
                "❌ Invalid DNS servers format. Please enter valid IP addresses separated by commas.\n\n"
                "Examples:\n"
                "• 8.8.8.8\n"
                "• 1.1.1.1,1.0.0.1\n"
                "• 8.8.8.8,8.8.4.4"
            )
            return
        dns_servers = update.message.text.strip()
    
    # Store DNS and create client
    context.user_data['dns_servers'] = dns_servers
    await create_menu_client(update, context)

async def create_menu_client(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create client from menu flow"""
    from utils import escape_markdown
    from wireguard_manager import wg_manager
    from telegram import InputFile
    
    client_name = context.user_data['client_name']
    dns_servers = context.user_data['dns_servers']
    
    # Send creating message
    creating_msg = await update.message.reply_text("🔧 Creating client configuration...")
    
    try:
        success, message, config_file = wg_manager.add_client(client_name, dns_servers)
        
        if success and config_file:
            # Send config file
            await update.message.reply_document(
                document=InputFile(config_file),
                filename=f"{client_name}.conf",
                caption=f"📄 Configuration file for {client_name}"
            )
            
            # Send config content in code format
            config_success, config_message, config_content = wg_manager.get_client_config(client_name)
            if config_success and config_content:
                # Split long configs to avoid Telegram message limits
                max_length = 3500
                if len(config_content) > max_length:
                    chunks = [config_content[i:i+max_length] for i in range(0, len(config_content), max_length)]
                    for i, chunk in enumerate(chunks):
                        await update.message.reply_text(
                            f"📄 *Config Content \\(Part {i+1}/{len(chunks)}\\)*\n\n```\n{chunk}\n```",
                            parse_mode='MarkdownV2'
                        )
                else:
                    await update.message.reply_text(
                        f"📄 *Config Content*\n\n```\n{config_content}\n```",
                        parse_mode='MarkdownV2'
                    )
            
            # Send QR code as image
            qr_success, qr_message, qr_image_path = wg_manager.get_client_qr(client_name)
            if qr_success and qr_image_path:
                try:
                    # Use robust sending method
                    from telegram_utils import send_qr_image_robust
                    
                    send_success, send_message = await send_qr_image_robust(
                        context.bot, update.message.chat_id, qr_image_path, client_name
                    )
                    
                    if not send_success:
                        await update.message.reply_text(
                            f"⚠️ QR code generated but failed to send: {send_message}\n"
                            f"You can still use the config file and text above to set up your connection."
                        )
                finally:
                    # Clean up temporary file
                    try:
                        import os as os_module
                        os_module.unlink(qr_image_path)
                    except:
                        pass
            else:
                logger.warning(f"QR code generation failed for {client_name}: {qr_message}")
                await update.message.reply_text(
                    f"⚠️ QR code generation failed: {qr_message}\n"
                    f"You can still use the config file and text above to set up your connection."
                )
            
            # Send success message with menu
            await update.message.reply_text(
                f"✅ {escape_markdown(message)}\n\n"
                f"Client *{escape_markdown(client_name)}* has been created successfully\\!",
                parse_mode='MarkdownV2',
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("➕ Add Another Client", callback_data="client_add"),
                        InlineKeyboardButton("📋 View All Clients", callback_data="client_list")
                    ],
                    [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="menu_main")]
                ])
            )
        else:
            await update.message.reply_text(
                f"❌ {escape_markdown(message)}",
                parse_mode='MarkdownV2',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Try Again", callback_data="client_add"),
                    InlineKeyboardButton("⬅️ Back to Clients", callback_data="menu_clients")
                ]])
            )
    
    except Exception as e:
        logger.error(f"Error creating client: {e}")
        await update.message.reply_text(
            "❌ An error occurred while creating the client. Please try again.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Try Again", callback_data="client_add"),
                InlineKeyboardButton("⬅️ Back to Clients", callback_data="menu_clients")
            ]])
        )
    
    finally:
        # Clean up user data
        context.user_data.clear()
        
        # Delete the "creating" message
        try:
            await creating_msg.delete()
        except:
            pass

async def resolve_user_identifier(context, user_input: str):
    """
    Resolve user input (ID or username) to user ID
    Returns: (success: bool, user_id: int, username: str, error_message: str)
    """
    user_input = user_input.strip()
    
    # Try to parse as user ID first
    try:
        user_id = int(user_input)
        return True, user_id, None, ""
    except ValueError:
        pass
    
    # Handle username format
    username = user_input
    if username.startswith('@'):
        username = username[1:]  # Remove @ prefix
    
    # Validate username format
    if not username.replace('_', '').isalnum() or len(username) < 5:
        return False, None, None, "Invalid username format. Usernames must be at least 5 characters and contain only letters, numbers, and underscores."
    
    try:
        # Try to get user info using the bot's get_chat method
        # This works if the user has interacted with the bot or is in a mutual group
        chat = await context.bot.get_chat(f"@{username}")
        if chat.type == 'private' and chat.id:
            return True, chat.id, username, ""
        else:
            return False, None, None, f"Could not resolve username @{username}. The user may need to start the bot first or the username might not exist."
    
    except Exception as e:
        error_msg = str(e)
        if "chat not found" in error_msg.lower() or "username not found" in error_msg.lower():
            return False, None, None, f"Username @{username} not found. Please check the username or ask the user to start the bot first."
        elif "forbidden" in error_msg.lower():
            return False, None, None, f"Cannot access user @{username}. The user needs to start the bot first."
        else:
            return False, None, None, f"Error resolving username @{username}: {error_msg}"

async def handle_menu_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user ID or username input in menu flow"""
    from utils import escape_markdown
    
    user_id = update.effective_user.id
    
    # Check if user is owner
    if not config.is_owner(user_id):
        await update.message.reply_text("❌ Access denied.")
        context.user_data.clear()
        return
    
    user_input = update.message.text.strip()
    
    # Resolve user identifier (ID or username)
    success, new_user_id, username, error_message = await resolve_user_identifier(context, user_input)
    
    if not success:
        await update.message.reply_text(
            f"❌ *Unable to Add User*\n\n"
            f"{escape_markdown(error_message)}\n\n"
            f"💡 *Try:*\n"
            f"• Using the numeric User ID instead\n"
            f"• Asking the user to start the bot first\n"
            f"• Checking the username spelling",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Try Again", callback_data="users_add"),
                InlineKeyboardButton("⬅️ Back", callback_data="menu_users")
            ]]),
            parse_mode='MarkdownV2'
        )
        return  # Don't clear user_data, let them try again
    
    # Check if user is already authorized
    if config.is_authorized(new_user_id):
        display_name = f"@{username}" if username else str(new_user_id)
        await update.message.reply_text(
            f"ℹ️ *User Already Authorized*\n\n"
            f"User {escape_markdown(display_name)} \\(`{new_user_id}`\\) is already in the authorized users list\\.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚙️ Manage Limits", callback_data=f"limits_user_{new_user_id}"),
                InlineKeyboardButton("⬅️ Back", callback_data="menu_users")
            ]]),
            parse_mode='MarkdownV2'
        )
        context.user_data.clear()
        return
    
    # Add the user
    if config.add_authorized_user(new_user_id, username):
        # Set default limits for new user
        default_limits = {
            'max_clients': config.get('limits.max_clients', 100),
            'rate_limit': config.get('limits.rate_limit', 10),
            'can_backup': True,
            'can_view_stats': True,
            'can_manage_clients': True
        }
        config.set_user_limits(new_user_id, default_limits)
        
        display_name = f"@{username}" if username else str(new_user_id)
        
        await update.message.reply_text(
            f"✅ *User Added Successfully*\n\n"
            f"User {escape_markdown(display_name)} \\(`{new_user_id}`\\) has been authorized with default limits\\.\n\n"
            f"📊 *Default Limits:*\n"
            f"• Max Clients: {escape_markdown(str(default_limits['max_clients']))}\n"
            f"• Rate Limit: {escape_markdown(str(default_limits['rate_limit']))}/min\n"
            f"• All permissions enabled\n\n"
            f"💡 You can customize these limits using the Manage Limits option\\.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚙️ Set Custom Limits", callback_data=f"limits_user_{new_user_id}"),
                InlineKeyboardButton("➕ Add Another", callback_data="users_add"),
                InlineKeyboardButton("⬅️ Back", callback_data="menu_users")
            ]]),
            parse_mode='MarkdownV2'
        )
    else:
        display_name = f"@{username}" if username else str(new_user_id)
        await update.message.reply_text(
            f"❌ Failed to add user {escape_markdown(display_name)}\\. Please try again\\.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Try Again", callback_data="users_add"),
                InlineKeyboardButton("⬅️ Back", callback_data="menu_users")
            ]]),
            parse_mode='MarkdownV2'
        )
    
    context.user_data.clear()

async def handle_menu_max_clients(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle max clients input in menu flow"""
    from utils import escape_markdown
    
    user_id = update.effective_user.id
    
    # Check if user is owner
    if not config.is_owner(user_id):
        await update.message.reply_text("❌ Access denied.")
        context.user_data.clear()
        return
    
    target_user_id = context.user_data.get('target_user_id')
    if not target_user_id:
        await update.message.reply_text("❌ Session expired. Please try again.")
        context.user_data.clear()
        return
    
    try:
        max_clients_input = update.message.text.strip().lower()
        
        if max_clients_input in ['unlimited', 'infinite', '-1', '∞']:
            max_clients = -1
        else:
            max_clients = int(max_clients_input)
            if max_clients < 0:
                max_clients = -1
        
        # Update user limits
        current_limits = config.get_user_limits(target_user_id)
        current_limits['max_clients'] = max_clients
        config.set_user_limits(target_user_id, current_limits)
        
        max_display = "Unlimited" if max_clients == -1 else str(max_clients)
        
        await update.message.reply_text(
            f"✅ *Max Clients Updated*\n\n"
            f"User `{target_user_id}` can now create up to {escape_markdown(max_display)} clients\\.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚙️ Configure More", callback_data=f"limits_user_{target_user_id}"),
                InlineKeyboardButton("⬅️ Back", callback_data="limits_set_user")
            ]]),
            parse_mode='MarkdownV2'
        )
    
    except ValueError:
        await update.message.reply_text(
            "❌ *Invalid Input*\n\n"
            "Please enter a number or 'unlimited'\\.\n\n"
            "💡 *Examples:* `5`, `10`, `unlimited`",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Try Again", callback_data=f"set_max_clients_{target_user_id}"),
                InlineKeyboardButton("⬅️ Back", callback_data=f"limits_user_{target_user_id}")
            ]]),
            parse_mode='MarkdownV2'
        )
        return  # Don't clear user_data, let them try again
    
    context.user_data.clear()

async def handle_menu_rate_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle rate limit input in menu flow"""
    from utils import escape_markdown
    
    user_id = update.effective_user.id
    
    # Check if user is owner
    if not config.is_owner(user_id):
        await update.message.reply_text("❌ Access denied.")
        context.user_data.clear()
        return
    
    target_user_id = context.user_data.get('target_user_id')
    if not target_user_id:
        await update.message.reply_text("❌ Session expired. Please try again.")
        context.user_data.clear()
        return
    
    try:
        rate_limit_input = update.message.text.strip().lower()
        
        if rate_limit_input in ['unlimited', 'infinite', '-1', '∞']:
            rate_limit = -1
        else:
            rate_limit = int(rate_limit_input)
            if rate_limit < 0:
                rate_limit = -1
        
        # Update user limits
        current_limits = config.get_user_limits(target_user_id)
        current_limits['rate_limit'] = rate_limit
        config.set_user_limits(target_user_id, current_limits)
        
        rate_display = "Unlimited" if rate_limit == -1 else f"{rate_limit}/min"
        
        await update.message.reply_text(
            f"✅ *Rate Limit Updated*\n\n"
            f"User `{target_user_id}` rate limit set to {escape_markdown(rate_display)}\\.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚙️ Configure More", callback_data=f"limits_user_{target_user_id}"),
                InlineKeyboardButton("⬅️ Back", callback_data="limits_set_user")
            ]]),
            parse_mode='MarkdownV2'
        )
    
    except ValueError:
        await update.message.reply_text(
            "❌ *Invalid Input*\n\n"
            "Please enter a number or 'unlimited'\\.\n\n"
            "💡 *Examples:* `10`, `50`, `unlimited`",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Try Again", callback_data=f"set_rate_limit_{target_user_id}"),
                InlineKeyboardButton("⬅️ Back", callback_data=f"limits_user_{target_user_id}")
            ]]),
            parse_mode='MarkdownV2'
        )
        return  # Don't clear user_data, let them try again
    
    context.user_data.clear()

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all menu callback queries"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "User"
    
    # Check authorization
    if not config.is_authorized(user_id):
        await query.edit_message_text(
            "❌ *Access Denied*\n\nYou are not authorized to use this bot\\.",
            parse_mode='MarkdownV2'
        )
        return
    
    callback_data = query.data
    
    try:
        if callback_data == "menu_main":
            await query.edit_message_text(
                MessageFormatter.format_main_menu(user_name),
                reply_markup=MenuHandler.create_main_menu(),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data == "menu_clients":
            await query.edit_message_text(
                "👥 *Client Management*\n\nChoose an action:",
                reply_markup=MenuHandler.create_clients_menu(),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data == "menu_status":
            await query.edit_message_text(
                MessageFormatter.format_server_status(),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Refresh", callback_data="menu_status"),
                    InlineKeyboardButton("⬅️ Back", callback_data="menu_main")
                ]]),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data == "menu_config":
            await query.edit_message_text(
                MessageFormatter.format_server_config(),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📄 View Config File", callback_data="config_view"),
                    InlineKeyboardButton("🔄 Refresh", callback_data="menu_config")
                ], [
                    InlineKeyboardButton("⬅️ Back", callback_data="menu_main")
                ]]),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data == "config_view":
            # Show server config file content
            try:
                config_path = "/etc/wireguard/wg0.conf"
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        config_content = f.read().strip()
                    
                    if config_content:
                        # Send config content in code format
                        formatted_content = f"```\n{config_content}\n```"
                        
                        # Also send as file
                        with open(config_path, 'rb') as f:
                            await context.bot.send_document(
                                chat_id=query.message.chat_id,
                                document=f,
                                filename="wg0.conf",
                                caption="📄 Server Configuration File"
                            )
                        
                        await query.edit_message_text(
                            f"📄 *Server Configuration*\n\n"
                            f"{formatted_content}\n\n"
                            f"📁 File sent above as download\\.",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("⬅️ Back", callback_data="menu_config")
                            ]]),
                            parse_mode='MarkdownV2'
                        )
                    else:
                        await query.edit_message_text(
                            "❌ Server configuration file is empty\\.",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("⬅️ Back", callback_data="menu_config")
                            ]]),
                            parse_mode='MarkdownV2'
                        )
                else:
                    await query.edit_message_text(
                        "❌ Server configuration file not found\\.\n\n"
                        "WireGuard may not be installed or configured\\.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("⬅️ Back", callback_data="menu_config")
                        ]]),
                        parse_mode='MarkdownV2'
                    )
            except Exception as e:
                logger.error(f"Error viewing config file: {e}")
                await query.edit_message_text(
                    f"❌ Error reading configuration file\\.\n\n"
                    f"Error: {escape_markdown(str(e))}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="menu_config")
                    ]]),
                    parse_mode='MarkdownV2'
                )
        
        elif callback_data == "menu_stats":
            await query.edit_message_text(
                MessageFormatter.format_connection_stats(),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Refresh", callback_data="menu_stats"),
                    InlineKeyboardButton("⬅️ Back", callback_data="menu_main")
                ]]),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data == "client_list":
            clients = wg_manager.list_clients()
            await query.edit_message_text(
                MessageFormatter.format_client_list(clients),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Refresh", callback_data="client_list"),
                    InlineKeyboardButton("⬅️ Back", callback_data="menu_clients")
                ]]),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data in ["client_remove", "client_qr", "client_config"]:
            clients = wg_manager.list_clients()
            if not clients:
                await query.edit_message_text(
                    "❌ No clients found\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="menu_clients")
                    ]]),
                    parse_mode='MarkdownV2'
                )
                return
            
            action = callback_data.split('_')[1]
            action_text = {
                'remove': 'remove',
                'qr': 'show QR code for',
                'config': 'get config for'
            }[action]
            
            await query.edit_message_text(
                f"Select a client to {action_text}:",
                reply_markup=MenuHandler.create_client_selection_menu(clients, action),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data.startswith("client_qr_"):
            client_name = callback_data[10:]  # Remove "client_qr_" prefix
            
            await query.edit_message_text(
                f"📱 Generating QR code for {escape_markdown(client_name)}\\.\\.\\.",
                parse_mode='MarkdownV2'
            )
            
            success, message, qr_image_path = wg_manager.get_client_qr(client_name)
            
            if success and qr_image_path:
                try:
                    # Use robust sending method
                    from telegram_utils import send_qr_image_robust
                    
                    send_success, send_message = await send_qr_image_robust(
                        context.bot, query.message.chat_id, qr_image_path, client_name
                    )
                    
                    if send_success:
                        await query.edit_message_text(
                            f"✅ QR code sent for {escape_markdown(client_name)}\\!\n\n"
                            f"📱 {escape_markdown(send_message)}",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("⬅️ Back", callback_data="menu_clients")
                            ]]),
                            parse_mode='MarkdownV2'
                        )
                    else:
                        await query.edit_message_text(
                            f"⚠️ QR code generated but failed to send\\.\n\n"
                            f"Error: {escape_markdown(send_message)}\n\n"
                            f"You can still get the config file to import manually\\.",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("🔄 Try Again", callback_data=f"client_qr_{client_name}"),
                                InlineKeyboardButton("📄 Get Config Instead", callback_data=f"client_config_{client_name}"),
                                InlineKeyboardButton("⬅️ Back", callback_data="menu_clients")
                            ]]),
                            parse_mode='MarkdownV2'
                        )
                finally:
                    # Clean up temporary file
                    try:
                        import os as os_module
                        os_module.unlink(qr_image_path)
                    except:
                        pass
            else:
                await query.edit_message_text(
                    f"❌ QR Code Error: {escape_markdown(message)}\n\n"
                    f"You can still download the config file and import it manually\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("📄 Get Config File", callback_data=f"client_config_{client_name}"),
                        InlineKeyboardButton("⬅️ Back", callback_data="menu_clients")
                    ]]),
                    parse_mode='MarkdownV2'
                )
        
        elif callback_data.startswith("client_config_"):
            client_name = callback_data[14:]  # Remove "client_config_" prefix
            success, message, config_content = wg_manager.get_client_config(client_name)
            
            if success and config_content:
                # Send config as file
                config_file = f"{client_name}.conf"
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=InputFile(config_content.encode(), filename=config_file),
                    caption=f"📄 Configuration file for {client_name}"
                )
                
                # Also send config content in code format
                # Split long configs to avoid Telegram message limits
                max_length = 3500  # Leave room for formatting
                if len(config_content) > max_length:
                    # Split into chunks
                    chunks = [config_content[i:i+max_length] for i in range(0, len(config_content), max_length)]
                    for i, chunk in enumerate(chunks):
                        await context.bot.send_message(
                            chat_id=query.message.chat_id,
                            text=f"📄 *Config Content for {escape_markdown(client_name)} \\(Part {i+1}/{len(chunks)}\\)*\n\n```\n{chunk}\n```",
                            parse_mode='MarkdownV2'
                        )
                else:
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=f"📄 *Config Content for {escape_markdown(client_name)}*\n\n```\n{config_content}\n```",
                        parse_mode='MarkdownV2'
                    )
                
                await query.edit_message_text(
                    f"✅ Config file and content sent for {escape_markdown(client_name)}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="menu_clients")
                    ]]),
                    parse_mode='MarkdownV2'
                )
            else:
                await query.edit_message_text(
                    f"❌ {escape_markdown(message)}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="menu_clients")
                    ]]),
                    parse_mode='MarkdownV2'
                )
        
        elif callback_data.startswith("client_remove_"):
            client_name = callback_data[14:]  # Remove "client_remove_" prefix
            
            # Show confirmation dialog
            await query.edit_message_text(
                f"🗑️ *Remove Client*\n\n"
                f"Are you sure you want to remove client '{escape_markdown(client_name)}'?\n\n"
                f"⚠️ This action cannot be undone\\!",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Yes, Remove", callback_data=f"confirm_remove_{client_name}"),
                        InlineKeyboardButton("❌ Cancel", callback_data="menu_clients")
                    ]
                ]),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data.startswith("confirm_remove_"):
            client_name = callback_data[15:]  # Remove "confirm_remove_" prefix
            
            await query.edit_message_text(
                f"🗑️ Removing client '{escape_markdown(client_name)}'\\.\\.\\.",
                parse_mode='MarkdownV2'
            )
            
            success, message = wg_manager.remove_client(client_name)
            
            if success:
                await query.edit_message_text(
                    f"✅ {escape_markdown(message)}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back to Clients", callback_data="menu_clients")
                    ]]),
                    parse_mode='MarkdownV2'
                )
            else:
                await query.edit_message_text(
                    f"❌ {escape_markdown(message)}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back to Clients", callback_data="menu_clients")
                    ]]),
                    parse_mode='MarkdownV2'
                )
        
        elif callback_data == "client_add":
            # Check if WireGuard is installed
            if not wg_manager.is_installed():
                await query.edit_message_text(
                    "❌ *WireGuard Not Installed*\n\n"
                    "WireGuard must be installed before adding clients\\.\n"
                    "Use `/install` command to set up WireGuard first\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="menu_clients")
                    ]]),
                    parse_mode='MarkdownV2'
                )
                return
            
            # Start the add client process
            await query.edit_message_text(
                "➕ *Add New Client*\n\n"
                "Please enter a name for the new client:\n"
                "\\(Only letters, numbers, hyphens, and underscores allowed\\)\n\n"
                "💡 *Tip:* Use descriptive names like 'john\\-phone' or 'laptop\\-work'",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Cancel", callback_data="menu_clients")
                ]]),
                parse_mode='MarkdownV2'
            )
            
            # Store the state for this user
            context.user_data['menu_state'] = 'waiting_client_name'
            context.user_data['original_message_id'] = query.message.message_id
        
        elif callback_data == "menu_backup":
            await query.edit_message_text(
                "💾 *Backup & Restore*\n\nChoose an action:",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📦 Create Backup", callback_data="backup_create"),
                        InlineKeyboardButton("📊 Backup Info", callback_data="backup_info")
                    ],
                    [InlineKeyboardButton("⬅️ Back to Main", callback_data="menu_main")]
                ]),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data == "backup_create":
            await query.edit_message_text(
                "📦 Creating backup\\.\\.\\.",
                parse_mode='MarkdownV2'
            )
            
            success, message, backup_file = wg_manager.backup_configs()
            
            if success and backup_file:
                try:
                    # Verify file exists and has content
                    if not os.path.exists(backup_file):
                        raise FileNotFoundError(f"Backup file not found: {backup_file}")
                    
                    file_size = os.path.getsize(backup_file)
                    if file_size == 0:
                        raise ValueError("Backup file is empty")
                    
                    filename = os.path.basename(backup_file)
                    
                    # Send backup file with proper file handling
                    with open(backup_file, 'rb') as f:
                        await context.bot.send_document(
                            chat_id=query.message.chat_id,
                            document=f,
                            filename=filename,
                            caption=f"💾 {escape_markdown(message)}\n\n📏 Size: {format_file_size(file_size)}"
                        )
                    
                    await query.edit_message_text(
                        f"✅ Backup created and sent successfully\\!\n\n"
                        f"📄 File: {escape_markdown(filename)}\n"
                        f"📏 Size: {escape_markdown(format_file_size(file_size))}",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("📦 Create Another", callback_data="backup_create"),
                            InlineKeyboardButton("⬅️ Back", callback_data="menu_backup")
                        ]]),
                        parse_mode='MarkdownV2'
                    )
                    
                    # Clean up backup file after sending
                    try:
                        import os as os_module  # Explicit import to avoid any scoping issues
                        os_module.unlink(backup_file)
                        logger.info(f"Backup file cleaned up: {backup_file}")
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup backup file: {cleanup_error}")
                        
                except Exception as send_error:
                    logger.error(f"Error sending backup file: {send_error}")
                    await query.edit_message_text(
                        f"❌ Backup created but failed to send\\.\n\n"
                        f"Error: {escape_markdown(str(send_error))}\n"
                        f"File location: {escape_markdown(backup_file)}",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔄 Try Again", callback_data="backup_create"),
                            InlineKeyboardButton("⬅️ Back", callback_data="menu_backup")
                        ]]),
                        parse_mode='MarkdownV2'
                    )
            else:
                await query.edit_message_text(
                    f"❌ Backup creation failed\\.\n\n"
                    f"Error: {escape_markdown(message)}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔄 Try Again", callback_data="backup_create"),
                        InlineKeyboardButton("⬅️ Back", callback_data="menu_backup")
                    ]]),
                    parse_mode='MarkdownV2'
                )
        
        elif callback_data == "backup_info":
            # Show backup information
            try:
                # Get system info for backup details
                status = wg_manager.get_server_status()
                clients = wg_manager.list_clients()
                
                # Calculate estimated backup size
                total_configs = 1 + len(clients)  # server config + client configs
                estimated_size = total_configs * 2  # Rough estimate in KB
                
                info_message = (
                    f"📊 *Backup Information*\n\n"
                    f"📄 *What gets backed up:*\n"
                    f"• Server configuration \\(wg0\\.conf\\)\n"
                    f"• All client configurations \\({len(clients)} files\\)\n"
                    f"• Configuration metadata\n\n"
                    f"📦 *Backup Details:*\n"
                    f"• Format: tar\\.gz compressed archive\n"
                    f"• Total files: {total_configs}\n"
                    f"• Estimated size: ~{estimated_size}KB\n\n"
                    f"🔒 *Security:*\n"
                    f"• Contains private keys and sensitive data\n"
                    f"• Store backup files securely\n"
                    f"• Delete after downloading if not needed\n\n"
                    f"💡 *Usage:*\n"
                    f"• Extract with: `tar -xzf backup_file.tar.gz`\n"
                    f"• Server config in root, clients in /clients/ folder"
                )
                
                await query.edit_message_text(
                    info_message,
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("📦 Create Backup", callback_data="backup_create"),
                            InlineKeyboardButton("⬅️ Back", callback_data="menu_backup")
                        ]
                    ]),
                    parse_mode='MarkdownV2'
                )
            except Exception as e:
                logger.error(f"Error showing backup info: {e}")
                await query.edit_message_text(
                    f"❌ Error loading backup information\\.\n\n"
                    f"Error: {escape_markdown(str(e))}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="menu_backup")
                    ]]),
                    parse_mode='MarkdownV2'
                )
        
        elif callback_data == "users_list":
            is_owner = config.is_owner(user_id)
            if not is_owner:
                await query.edit_message_text(
                    "❌ Access denied\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="menu_users")
                    ]]),
                    parse_mode='MarkdownV2'
                )
                return
            
            authorized_users = config.get('authorized_users', [])
            owner_id = config.get('owner_id')
            
            message = "👥 *Authorized Users*\n\n"
            for i, uid in enumerate(authorized_users, 1):
                role = " \\(Owner\\)" if uid == owner_id else ""
                username = config.get_user_username(uid)
                
                if username:
                    display_name = f"@{escape_markdown(username)} \\(`{uid}`\\)"
                else:
                    display_name = f"`{uid}`"
                
                message += f"{i}\\. {display_name}{role}\n"
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back", callback_data="menu_users")
                ]]),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data == "users_add":
            is_owner = config.is_owner(user_id)
            if not is_owner:
                await query.edit_message_text(
                    "❌ Access denied\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="menu_users")
                    ]]),
                    parse_mode='MarkdownV2'
                )
                return
            
            # Start menu-driven user addition
            context.user_data['menu_state'] = 'waiting_user_id'
            context.user_data['user_action'] = 'add'
            
            await query.edit_message_text(
                "➕ *Add New User*\n\n"
                "Please send the Telegram User ID or Username of the user you want to authorize\\.\n\n"
                "💡 *Accepted Formats:*\n"
                "• User ID: `your_user_id`\n"
                "• Username: `@username` or `username`\n\n"
                "🔍 *How to find User ID:*\n"
                "• Forward a message from the user to @userinfobot\n"
                "• Or ask the user to send `/start` to @userinfobot\n\n"
                "📝 *Send either format:*",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Cancel", callback_data="menu_users")
                ]]),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data == "users_limits":
            is_owner = config.is_owner(user_id)
            if not is_owner:
                await query.edit_message_text(
                    "❌ Access denied\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="menu_users")
                    ]]),
                    parse_mode='MarkdownV2'
                )
                return
            
            await query.edit_message_text(
                "⚙️ *User Limits Management*\n\n"
                "Configure user permissions and limits:",
                reply_markup=MenuHandler.create_user_limits_menu(),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data == "limits_set_user":
            is_owner = config.is_owner(user_id)
            if not is_owner:
                await query.edit_message_text(
                    "❌ Access denied\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="users_limits")
                    ]]),
                    parse_mode='MarkdownV2'
                )
                return
            
            # Show list of users to select for limit setting
            users_info = config.get_all_users_with_limits()
            non_owner_users = [u for u in users_info if not u['is_owner']]
            
            if not non_owner_users:
                await query.edit_message_text(
                    "ℹ️ *No Users to Configure*\n\n"
                    "There are no non\\-owner users to set limits for\\.\n"
                    "Add some users first\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("➕ Add User", callback_data="users_add"),
                        InlineKeyboardButton("⬅️ Back", callback_data="users_limits")
                    ]]),
                    parse_mode='MarkdownV2'
                )
                return
            
            keyboard = []
            for user_info in non_owner_users[:10]:  # Limit to 10 users for UI
                uid = user_info['user_id']
                user_id_str = str(uid)
                username = config.get_user_username(uid)
                
                if username:
                    button_text = f"👤 @{username}"
                else:
                    button_text = f"👤 {user_id_str}"
                
                keyboard.append([
                    InlineKeyboardButton(button_text, callback_data=f"limits_user_{user_id_str}")
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back", callback_data="users_limits")
            ])
            
            await query.edit_message_text(
                "👤 *Select User to Configure*\n\n"
                "Choose a user to set limits for:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data.startswith("limits_user_"):
            is_owner = config.is_owner(user_id)
            if not is_owner:
                await query.edit_message_text(
                    "❌ Access denied\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="users_limits")
                    ]]),
                    parse_mode='MarkdownV2'
                )
                return
            
            target_user_id = int(callback_data[12:])  # Remove "limits_user_" prefix
            limits = config.get_user_limits(target_user_id)
            
            # Format current limits
            max_clients = "Unlimited" if limits['max_clients'] == -1 else str(limits['max_clients'])
            rate_limit = "Unlimited" if limits['rate_limit'] == -1 else str(limits['rate_limit'])
            
            message = (
                f"⚙️ *User Limits: {escape_markdown(str(target_user_id))}*\n\n"
                f"📊 *Current Limits:*\n"
                f"• Max Clients: {escape_markdown(max_clients)}\n"
                f"• Rate Limit: {escape_markdown(rate_limit)}/min\n"
                f"• Can Backup: {'✅' if limits['can_backup'] else '❌'}\n"
                f"• Can View Stats: {'✅' if limits['can_view_stats'] else '❌'}\n"
                f"• Can Manage Clients: {'✅' if limits['can_manage_clients'] else '❌'}\n\n"
                f"🔧 *Configure:*"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("📊 Max Clients", callback_data=f"set_max_clients_{target_user_id}"),
                    InlineKeyboardButton("⏱️ Rate Limit", callback_data=f"set_rate_limit_{target_user_id}")
                ],
                [
                    InlineKeyboardButton("💾 Backup Access", callback_data=f"toggle_backup_{target_user_id}"),
                    InlineKeyboardButton("📈 Stats Access", callback_data=f"toggle_stats_{target_user_id}")
                ],
                [
                    InlineKeyboardButton("👥 Client Management", callback_data=f"toggle_clients_{target_user_id}")
                ],
                [
                    InlineKeyboardButton("🔄 Reset to Default", callback_data=f"reset_limits_{target_user_id}"),
                    InlineKeyboardButton("⬅️ Back", callback_data="limits_set_user")
                ]
            ]
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data == "limits_view_all":
            is_owner = config.is_owner(user_id)
            if not is_owner:
                await query.edit_message_text(
                    "❌ Access denied\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="users_limits")
                    ]]),
                    parse_mode='MarkdownV2'
                )
                return
            
            users_info = config.get_all_users_with_limits()
            
            message = "📋 *All User Limits*\n\n"
            
            for user_info in users_info:
                uid = user_info['user_id']
                limits = user_info['limits']
                is_owner_user = user_info['is_owner']
                
                role = " \\(Owner\\)" if is_owner_user else ""
                username = config.get_user_username(uid)
                
                if username:
                    display_name = f"@{escape_markdown(username)} \\(`{uid}`\\)"
                else:
                    display_name = f"`{uid}`"
                
                max_clients = "∞" if limits['max_clients'] == -1 else str(limits['max_clients'])
                rate_limit = "∞" if limits['rate_limit'] == -1 else str(limits['rate_limit'])
                
                message += (
                    f"👤 {display_name}{role}\n"
                    f"  • Clients: {escape_markdown(max_clients)}\n"
                    f"  • Rate: {escape_markdown(rate_limit)}/min\n"
                    f"  • Backup: {'✅' if limits['can_backup'] else '❌'}\n\n"
                )
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⚙️ Manage Limits", callback_data="limits_set_user"),
                    InlineKeyboardButton("⬅️ Back", callback_data="users_limits")
                ]]),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data.startswith("set_max_clients_"):
            is_owner = config.is_owner(user_id)
            if not is_owner:
                await query.edit_message_text(
                    "❌ Access denied\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="users_limits")
                    ]]),
                    parse_mode='MarkdownV2'
                )
                return
            
            target_user_id = int(callback_data[16:])  # Remove "set_max_clients_" prefix
            context.user_data['menu_state'] = 'waiting_max_clients'
            context.user_data['target_user_id'] = target_user_id
            
            await query.edit_message_text(
                f"📊 *Set Max Clients for User {escape_markdown(str(target_user_id))}*\n\n"
                f"Enter the maximum number of clients this user can create\\.\n\n"
                f"💡 *Options:*\n"
                f"• Enter a number \\(e\\.g\\. `5`, `10`, `50`\\)\n"
                f"• Enter `unlimited` for no limit\n\n"
                f"📝 *Send your choice:*",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Cancel", callback_data=f"limits_user_{target_user_id}")
                ]]),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data.startswith("set_rate_limit_"):
            is_owner = config.is_owner(user_id)
            if not is_owner:
                await query.edit_message_text(
                    "❌ Access denied\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="users_limits")
                    ]]),
                    parse_mode='MarkdownV2'
                )
                return
            
            target_user_id = int(callback_data[15:])  # Remove "set_rate_limit_" prefix
            context.user_data['menu_state'] = 'waiting_rate_limit'
            context.user_data['target_user_id'] = target_user_id
            
            await query.edit_message_text(
                f"⏱️ *Set Rate Limit for User {escape_markdown(str(target_user_id))}*\n\n"
                f"Enter the maximum requests per minute for this user\\.\n\n"
                f"💡 *Options:*\n"
                f"• Enter a number \\(e\\.g\\. `10`, `50`, `100`\\)\n"
                f"• Enter `unlimited` for no limit\n\n"
                f"📝 *Send your choice:*",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Cancel", callback_data=f"limits_user_{target_user_id}")
                ]]),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data.startswith("toggle_backup_"):
            is_owner = config.is_owner(user_id)
            if not is_owner:
                await query.edit_message_text(
                    "❌ Access denied\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="users_limits")
                    ]]),
                    parse_mode='MarkdownV2'
                )
                return
            
            target_user_id = int(callback_data[14:])  # Remove "toggle_backup_" prefix
            current_limits = config.get_user_limits(target_user_id)
            current_limits['can_backup'] = not current_limits['can_backup']
            config.set_user_limits(target_user_id, current_limits)
            
            status = "enabled" if current_limits['can_backup'] else "disabled"
            
            await query.edit_message_text(
                f"✅ *Backup Access Updated*\n\n"
                f"Backup access for user `{target_user_id}` is now {escape_markdown(status)}\\.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⚙️ Configure More", callback_data=f"limits_user_{target_user_id}"),
                    InlineKeyboardButton("⬅️ Back", callback_data="limits_set_user")
                ]]),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data.startswith("toggle_stats_"):
            is_owner = config.is_owner(user_id)
            if not is_owner:
                await query.edit_message_text(
                    "❌ Access denied\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="users_limits")
                    ]]),
                    parse_mode='MarkdownV2'
                )
                return
            
            target_user_id = int(callback_data[13:])  # Remove "toggle_stats_" prefix
            current_limits = config.get_user_limits(target_user_id)
            current_limits['can_view_stats'] = not current_limits['can_view_stats']
            config.set_user_limits(target_user_id, current_limits)
            
            status = "enabled" if current_limits['can_view_stats'] else "disabled"
            
            await query.edit_message_text(
                f"✅ *Stats Access Updated*\n\n"
                f"Stats access for user `{target_user_id}` is now {escape_markdown(status)}\\.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⚙️ Configure More", callback_data=f"limits_user_{target_user_id}"),
                    InlineKeyboardButton("⬅️ Back", callback_data="limits_set_user")
                ]]),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data.startswith("toggle_clients_"):
            is_owner = config.is_owner(user_id)
            if not is_owner:
                await query.edit_message_text(
                    "❌ Access denied\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="users_limits")
                    ]]),
                    parse_mode='MarkdownV2'
                )
                return
            
            target_user_id = int(callback_data[15:])  # Remove "toggle_clients_" prefix
            current_limits = config.get_user_limits(target_user_id)
            current_limits['can_manage_clients'] = not current_limits['can_manage_clients']
            config.set_user_limits(target_user_id, current_limits)
            
            status = "enabled" if current_limits['can_manage_clients'] else "disabled"
            
            await query.edit_message_text(
                f"✅ *Client Management Updated*\n\n"
                f"Client management for user `{target_user_id}` is now {escape_markdown(status)}\\.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⚙️ Configure More", callback_data=f"limits_user_{target_user_id}"),
                    InlineKeyboardButton("⬅️ Back", callback_data="limits_set_user")
                ]]),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data.startswith("reset_limits_"):
            is_owner = config.is_owner(user_id)
            if not is_owner:
                await query.edit_message_text(
                    "❌ Access denied\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="users_limits")
                    ]]),
                    parse_mode='MarkdownV2'
                )
                return
            
            target_user_id = int(callback_data[13:])  # Remove "reset_limits_" prefix
            
            # Reset to default limits
            default_limits = {
                'max_clients': config.get('limits.max_clients', 100),
                'rate_limit': config.get('limits.rate_limit', 10),
                'can_backup': True,
                'can_view_stats': True,
                'can_manage_clients': True
            }
            config.set_user_limits(target_user_id, default_limits)
            
            await query.edit_message_text(
                f"✅ *Limits Reset to Default*\n\n"
                f"User `{target_user_id}` limits have been reset to default values\\.\n\n"
                f"📊 *Default Limits:*\n"
                f"• Max Clients: {escape_markdown(str(default_limits['max_clients']))}\n"
                f"• Rate Limit: {escape_markdown(str(default_limits['rate_limit']))}/min\n"
                f"• All permissions enabled",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⚙️ Configure More", callback_data=f"limits_user_{target_user_id}"),
                    InlineKeyboardButton("⬅️ Back", callback_data="limits_set_user")
                ]]),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data == "menu_use_default_dns":
            # Handle default DNS selection in menu flow
            if context.user_data.get('menu_state') == 'waiting_dns_servers':
                context.user_data['dns_servers'] = "8.8.8.8,8.8.4.4"
                
                # Create a fake update object for the create_menu_client function
                class FakeMessage:
                    def __init__(self, chat_id):
                        self.chat_id = chat_id
                        self.message_id = query.message.message_id
                    
                    async def reply_text(self, *args, **kwargs):
                        return await context.bot.send_message(self.chat_id, *args, **kwargs)
                    
                    async def reply_document(self, *args, **kwargs):
                        return await context.bot.send_document(self.chat_id, *args, **kwargs)
                    
                    async def reply_photo(self, *args, **kwargs):
                        return await context.bot.send_photo(self.chat_id, *args, **kwargs)
                
                fake_update = type('FakeUpdate', (), {})()
                fake_update.message = FakeMessage(query.message.chat_id)
                
                await create_menu_client(fake_update, context)
            else:
                await query.edit_message_text(
                    "❌ Invalid operation\\.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data="menu_clients")
                    ]]),
                    parse_mode='MarkdownV2'
                )
        
        elif callback_data == "menu_help":
            await query.edit_message_text(
                MessageFormatter.format_help_message(),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back to Main", callback_data="menu_main")
                ]]),
                parse_mode='MarkdownV2'
            )
        
        elif callback_data == "menu_users":
            is_owner = config.is_owner(user_id)
            await query.edit_message_text(
                "🔒 *User Management*\n\nChoose an action:",
                reply_markup=MenuHandler.create_user_menu(is_owner),
                parse_mode='MarkdownV2'
            )
        
        else:
            # Handle other callbacks or show error
            await query.edit_message_text(
                "❌ Unknown action\\. Please try again\\.",
                reply_markup=MenuHandler.create_main_menu(),
                parse_mode='MarkdownV2'
            )
    
    except Exception as e:
        logger.error(f"Error handling callback {callback_data}: {e}")
        await query.edit_message_text(
            "❌ An error occurred\\. Please try again\\.",
            reply_markup=MenuHandler.create_main_menu(),
            parse_mode='MarkdownV2'
        )
