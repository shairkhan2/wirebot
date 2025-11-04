"""
Enhanced WireBot - Comprehensive WireGuard Management Bot
Features: Menu-driven interface, full client management, server monitoring, multi-user support
"""
import logging
import asyncio
from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

# Import our modules
from config import config
from wireguard_manager import wg_manager
from menu_handlers import handle_menu_callback, handle_menu_text_input, MenuHandler, MessageFormatter
from utils import sanitize_client_name, validate_dns_servers, escape_markdown

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_CLIENT_NAME, WAITING_DNS_SERVERS, WAITING_USER_ID, WAITING_CONFIRM_REMOVE = range(4)

class WireBot:
    """Main WireBot class"""
    
    def __init__(self):
        self.application = None
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "User"
        
        # Check authorization
        if not config.is_authorized(user_id):
            await update.message.reply_text(
                "❌ *Access Denied*\n\n"
                "You are not authorized to use this bot\\.\n"
                "Please contact the bot owner for access\\.",
                parse_mode='MarkdownV2'
            )
            return
        
        # Send welcome message with main menu
        await update.message.reply_text(
            MessageFormatter.format_main_menu(user_name),
            reply_markup=MenuHandler.create_main_menu(),
            parse_mode='MarkdownV2'
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        user_id = update.effective_user.id
        
        if not config.is_authorized(user_id):
            await update.message.reply_text("❌ Access denied.")
            return
        
        await update.message.reply_text(
            MessageFormatter.format_help_message(),
            parse_mode='MarkdownV2'
        )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command"""
        user_id = update.effective_user.id
        
        if not config.is_authorized(user_id):
            await update.message.reply_text("❌ Access denied.")
            return
        
        await update.message.reply_text(
            MessageFormatter.format_server_status(),
            parse_mode='MarkdownV2'
        )
    
    async def install_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /install command"""
        user_id = update.effective_user.id
        
        if not config.is_owner(user_id):
            await update.message.reply_text("❌ Only the bot owner can install WireGuard.")
            return
        
        if wg_manager.is_installed():
            await update.message.reply_text("✅ WireGuard is already installed.")
            return
        
        await update.message.reply_text("🔧 Installing WireGuard... This may take a few minutes.")
        
        success, message = wg_manager.install_wireguard()
        
        if success:
            await update.message.reply_text(f"✅ {message}")
        else:
            await update.message.reply_text(f"❌ {message}")
    
    # Conversation handlers for adding clients
    async def add_client_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start add client conversation"""
        user_id = update.effective_user.id
        
        if not config.is_authorized(user_id):
            await update.message.reply_text("❌ Access denied.")
            return ConversationHandler.END
        
        if not wg_manager.is_installed():
            await update.message.reply_text("❌ WireGuard is not installed. Use /install first.")
            return ConversationHandler.END
        
        await update.message.reply_text(
            "➕ *Add New Client*\n\n"
            "Please enter a name for the new client:\n"
            "\\(Only letters, numbers, hyphens, and underscores allowed\\)",
            parse_mode='MarkdownV2'
        )
        return WAITING_CLIENT_NAME
    
    async def add_client_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle client name input"""
        client_name = update.message.text.strip()
        sanitized_name = sanitize_client_name(client_name)
        
        if not sanitized_name:
            await update.message.reply_text(
                "❌ Invalid client name. Please use only letters, numbers, hyphens, and underscores."
            )
            return WAITING_CLIENT_NAME
        
        # Check if client already exists
        clients = wg_manager.list_clients()
        if any(client['name'] == sanitized_name for client in clients):
            await update.message.reply_text(
                f"❌ Client '{sanitized_name}' already exists. Please choose a different name."
            )
            return WAITING_CLIENT_NAME
        
        context.user_data['client_name'] = sanitized_name
        
        await update.message.reply_text(
            f"✅ Client name: *{escape_markdown(sanitized_name)}*\n\n"
            f"Now enter DNS servers \\(comma\\-separated IP addresses\\):\n"
            f"Or send /skip to use default \\(8\\.8\\.8\\.8, 8\\.8\\.4\\.4\\)",
            parse_mode='MarkdownV2'
        )
        return WAITING_DNS_SERVERS
    
    async def add_client_dns(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle DNS servers input"""
        dns_input = update.message.text.strip()
        
        if not validate_dns_servers(dns_input):
            await update.message.reply_text(
                "❌ Invalid DNS servers format. Please enter valid IP addresses separated by commas."
            )
            return WAITING_DNS_SERVERS
        
        context.user_data['dns_servers'] = dns_input
        return await self.create_client(update, context)
    
    async def skip_dns(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Skip DNS configuration"""
        context.user_data['dns_servers'] = "8.8.8.8,8.8.4.4"
        return await self.create_client(update, context)
    
    async def create_client(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Create the client configuration"""
        client_name = context.user_data['client_name']
        dns_servers = context.user_data['dns_servers']
        
        await update.message.reply_text("🔧 Creating client configuration...")
        
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
                max_length = 3500  # Leave room for formatting
                if len(config_content) > max_length:
                    # Split into chunks
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
            
            # Get and send QR code as image
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
                    import os
                    try:
                        os.unlink(qr_image_path)
                    except:
                        pass
            else:
                logger.warning(f"QR code generation failed for {client_name}: {qr_message}")
                await update.message.reply_text(
                    f"⚠️ QR code generation failed: {qr_message}\n"
                    f"You can still use the config file and text above to set up your connection."
                )
            
            await update.message.reply_text(f"✅ {message}")
        else:
            await update.message.reply_text(f"❌ {message}")
        
        return ConversationHandler.END
    
    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel any ongoing conversation"""
        await update.message.reply_text("❌ Operation cancelled.")
        return ConversationHandler.END
    
    # User management (owner only)
    async def add_user_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start add user conversation"""
        user_id = update.effective_user.id
        
        if not config.is_owner(user_id):
            await update.message.reply_text("❌ Only the bot owner can add users.")
            return ConversationHandler.END
        
        await update.message.reply_text(
            "👤 *Add New User*\n\n"
            "Please enter the Telegram user ID of the user to authorize:",
            parse_mode='MarkdownV2'
        )
        return WAITING_USER_ID
    
    async def add_user_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle user ID input"""
        try:
            new_user_id = int(update.message.text.strip())
            
            if config.add_authorized_user(new_user_id):
                await update.message.reply_text(f"✅ User {new_user_id} has been authorized.")
            else:
                await update.message.reply_text(f"ℹ️ User {new_user_id} is already authorized.")
        
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID. Please enter a valid number.")
            return WAITING_USER_ID
        
        return ConversationHandler.END
    
    async def list_users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List authorized users"""
        user_id = update.effective_user.id
        
        if not config.is_owner(user_id):
            await update.message.reply_text("❌ Only the bot owner can view user list.")
            return
        
        authorized_users = config.get('authorized_users', [])
        owner_id = config.get('owner_id')
        
        message = "👥 *Authorized Users*\n\n"
        for i, uid in enumerate(authorized_users, 1):
            role = " \\(Owner\\)" if uid == owner_id else ""
            message += f"{i}\\. `{uid}`{role}\n"
        
        await update.message.reply_text(message, parse_mode='MarkdownV2')
    
    def setup_handlers(self):
        """Setup all command and callback handlers"""
        # Basic commands
        self.application.add_handler(CommandHandler('start', self.start_command))
        self.application.add_handler(CommandHandler('help', self.help_command))
        self.application.add_handler(CommandHandler('status', self.status_command))
        self.application.add_handler(CommandHandler('install', self.install_command))
        self.application.add_handler(CommandHandler('users', self.list_users_command))
        
        # Callback query handler for menu interactions
        self.application.add_handler(CallbackQueryHandler(handle_menu_callback))
        
        # Text message handler for menu-driven flows (must be after conversation handlers)
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_text_input))
        
        # Conversation handler for adding clients
        add_client_conv = ConversationHandler(
            entry_points=[CommandHandler('add_client', self.add_client_start)],
            states={
                WAITING_CLIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_client_name)],
                WAITING_DNS_SERVERS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_client_dns),
                    CommandHandler('skip', self.skip_dns)
                ],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_conversation)],
        )
        self.application.add_handler(add_client_conv)
        
        # Conversation handler for adding users
        add_user_conv = ConversationHandler(
            entry_points=[CommandHandler('add_user', self.add_user_start)],
            states={
                WAITING_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_user_id)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_conversation)],
        )
        self.application.add_handler(add_user_conv)
    
    def run(self):
        """Start the bot"""
        # Create application
        self.application = Application.builder().token(config.get('bot_token')).build()
        
        # Setup handlers
        self.setup_handlers()
        
        logger.info("WireBot started successfully!")
        logger.info(f"Owner ID: {config.get('owner_id')}")
        logger.info(f"Authorized users: {len(config.get('authorized_users', []))}")
        
        # Run the bot
        self.application.run_polling()

if __name__ == '__main__':
    bot = WireBot()
    bot.run()
