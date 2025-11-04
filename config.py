"""
Configuration management for WireBot
"""
import os
import json
import logging
from typing import Dict, List, Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class Config:
    """Configuration manager for WireBot"""
    
    def __init__(self, config_file: str = "wirebot_config.json"):
        self.config_file = Path(config_file)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from file or create default"""
        # Get configuration from environment variables
        bot_token = os.getenv('BOT_TOKEN')
        owner_id = os.getenv('OWNER_ID')
        
        if not bot_token:
            raise ValueError("BOT_TOKEN environment variable is required. Please set it in your .env file.")
        
        if not owner_id:
            raise ValueError("OWNER_ID environment variable is required. Please set it in your .env file.")
        
        try:
            owner_id = int(owner_id)
        except ValueError:
            raise ValueError("OWNER_ID must be a valid integer (Telegram User ID).")
        
        # Parse additional authorized users if provided
        authorized_users = [owner_id]  # Owner is always authorized
        additional_users = os.getenv('AUTHORIZED_USERS', '')
        if additional_users:
            try:
                additional_ids = [int(uid.strip()) for uid in additional_users.split(',') if uid.strip()]
                authorized_users.extend(additional_ids)
            except ValueError:
                logger.warning("Invalid AUTHORIZED_USERS format. Should be comma-separated user IDs.")
        
        default_config = {
            "bot_token": bot_token,
            "owner_id": owner_id,
            "authorized_users": authorized_users,
            "wireguard": {
                "script_path": os.getenv('WIREGUARD_SCRIPT_PATH', './wireguard.sh'),
                "config_path": os.getenv('WIREGUARD_CONFIG_PATH', '/etc/wireguard/wg0.conf'),
                "export_paths": [
                    "/root/",
                    "/home/",
                    "~/",
                    "/tmp/"
                ]
            },
            "features": {
                "multi_user": True,
                "monitoring": True,
                "backup": True,
                "audit_log": True
            },
            "limits": {
                "max_clients": int(os.getenv('MAX_CLIENTS_PER_USER', '100')),
                "rate_limit": int(os.getenv('RATE_LIMIT_PER_USER', '10'))
            }
        }
        
        # Load additional config from file if it exists (for user limits, usernames, etc.)
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                
                # Merge file config with environment-based config
                # Environment variables take precedence for sensitive data
                merged_config = {**loaded_config, **default_config}
                
                # Preserve user-specific data from file
                if 'user_limits' in loaded_config:
                    merged_config['user_limits'] = loaded_config['user_limits']
                if 'user_usernames' in loaded_config:
                    merged_config['user_usernames'] = loaded_config['user_usernames']
                
                return merged_config
            except Exception as e:
                logger.error(f"Error loading config file: {e}")
                logger.info("Using environment-based configuration")
                return default_config
        else:
            # Create initial config file for user data storage
            self.save_config(default_config)
            return default_config
    
    def save_config(self, config: Optional[Dict] = None) -> None:
        """Save configuration to file"""
        config_to_save = config or self.config
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_to_save, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def get(self, key: str, default=None):
        """Get configuration value with dot notation support"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value) -> None:
        """Set configuration value with dot notation support"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save_config()
    
    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized"""
        return user_id in self.get('authorized_users', [])
    
    def is_owner(self, user_id: int) -> bool:
        """Check if user is the owner"""
        return user_id == self.get('owner_id')
    
    def add_authorized_user(self, user_id: int, username: str = None) -> bool:
        """Add user to authorized list"""
        authorized = self.get('authorized_users', [])
        if user_id not in authorized:
            authorized.append(user_id)
            self.set('authorized_users', authorized)
            
            # Store username if provided
            if username:
                self.set_user_username(user_id, username)
            
            return True
        return False
    
    def set_user_username(self, user_id: int, username: str) -> None:
        """Store username for a user ID"""
        usernames = self.get('user_usernames', {})
        usernames[str(user_id)] = username
        self.set('user_usernames', usernames)
    
    def get_user_username(self, user_id: int) -> Optional[str]:
        """Get stored username for a user ID"""
        usernames = self.get('user_usernames', {})
        return usernames.get(str(user_id))
    
    def remove_authorized_user(self, user_id: int) -> bool:
        """Remove user from authorized list"""
        authorized = self.get('authorized_users', [])
        if user_id in authorized and user_id != self.get('owner_id'):
            authorized.remove(user_id)
            self.set('authorized_users', authorized)
            # Also remove user limits if they exist
            self.remove_user_limits(user_id)
            return True
        return False
    
    def get_user_limits(self, user_id: int) -> Dict:
        """Get limits for a specific user"""
        user_limits = self.get('user_limits', {})
        default_limits = {
            'max_clients': self.get('limits.max_clients', 100),
            'rate_limit': self.get('limits.rate_limit', 10),
            'can_backup': True,
            'can_view_stats': True,
            'can_manage_clients': True
        }
        
        # Owner has no limits
        if self.is_owner(user_id):
            return {
                'max_clients': -1,  # -1 means unlimited
                'rate_limit': -1,
                'can_backup': True,
                'can_view_stats': True,
                'can_manage_clients': True
            }
        
        return user_limits.get(str(user_id), default_limits)
    
    def set_user_limits(self, user_id: int, limits: Dict) -> None:
        """Set limits for a specific user"""
        if self.is_owner(user_id):
            return  # Cannot set limits on owner
        
        user_limits = self.get('user_limits', {})
        user_limits[str(user_id)] = limits
        self.set('user_limits', user_limits)
    
    def remove_user_limits(self, user_id: int) -> None:
        """Remove limits for a specific user"""
        user_limits = self.get('user_limits', {})
        if str(user_id) in user_limits:
            del user_limits[str(user_id)]
            self.set('user_limits', user_limits)
    
    def get_all_users_with_limits(self) -> List[Dict]:
        """Get all authorized users with their limits"""
        authorized = self.get('authorized_users', [])
        users_info = []
        
        for user_id in authorized:
            limits = self.get_user_limits(user_id)
            users_info.append({
                'user_id': user_id,
                'is_owner': self.is_owner(user_id),
                'limits': limits
            })
        
        return users_info
    
    def can_user_perform_action(self, user_id: int, action: str) -> bool:
        """Check if user can perform a specific action"""
        limits = self.get_user_limits(user_id)
        
        action_map = {
            'backup': 'can_backup',
            'view_stats': 'can_view_stats',
            'manage_clients': 'can_manage_clients'
        }
        
        return limits.get(action_map.get(action, action), True)
    
    def get_user_client_count(self, user_id: int) -> int:
        """Get current client count for user (placeholder - would need tracking)"""
        # This would need to be implemented with actual client tracking
        # For now, return 0 as placeholder
        return 0
    
    def can_user_add_client(self, user_id: int) -> bool:
        """Check if user can add more clients"""
        if not self.can_user_perform_action(user_id, 'manage_clients'):
            return False
        
        limits = self.get_user_limits(user_id)
        max_clients = limits.get('max_clients', 100)
        
        if max_clients == -1:  # Unlimited
            return True
        
        current_count = self.get_user_client_count(user_id)
        return current_count < max_clients

# Global config instance
config = Config()
