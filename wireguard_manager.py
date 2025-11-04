"""
WireGuard management wrapper for WireBot
"""
import os
import re
import subprocess
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from config import config
from utils import (
    get_export_directory, find_config_file, sanitize_client_name,
    validate_ip_address, run_command, get_system_info, check_wireguard_status
)

logger = logging.getLogger(__name__)

class WireGuardManager:
    """Manages WireGuard server and client operations"""
    
    def __init__(self):
        self.script_path = config.get('wireguard.script_path')
        self.wg_conf = config.get('wireguard.config_path')
        self.export_dir = get_export_directory()
    
    def is_installed(self) -> bool:
        """Check if WireGuard is installed and configured"""
        return os.path.exists(self.wg_conf) and os.path.exists(self.script_path)
    
    def get_server_status(self) -> Dict:
        """Get comprehensive server status"""
        status = {
            'installed': self.is_installed(),
            'system': get_system_info(),
            'wireguard': check_wireguard_status()
        }
        
        if status['installed']:
            status['clients'] = self.list_clients()
            status['server_config'] = self._get_server_config()
        
        return status
    
    def _get_server_config(self) -> Dict:
        """Get server configuration details"""
        config_info = {}
        
        if not os.path.exists(self.wg_conf):
            return config_info
        
        try:
            with open(self.wg_conf, 'r') as f:
                content = f.read()
            
            # Extract server info
            endpoint_match = re.search(r'# ENDPOINT (.+)', content)
            if endpoint_match:
                config_info['endpoint'] = endpoint_match.group(1)
            
            listen_port_match = re.search(r'ListenPort = (\d+)', content)
            if listen_port_match:
                config_info['port'] = listen_port_match.group(1)
            
            address_match = re.search(r'Address = ([^\n]+)', content)
            if address_match:
                config_info['address'] = address_match.group(1)
            
            # Count clients
            client_count = len(re.findall(r'# BEGIN_PEER', content))
            config_info['client_count'] = client_count
            
        except Exception as e:
            logger.error(f"Error reading server config: {e}")
        
        return config_info
    
    def list_clients(self) -> List[Dict]:
        """List all configured clients"""
        clients = []
        
        if not os.path.exists(self.wg_conf):
            return clients
        
        try:
            with open(self.wg_conf, 'r') as f:
                content = f.read()
            
            # Find all client sections
            client_sections = re.findall(
                r'# BEGIN_PEER (.+?)\n\[Peer\]\nPublicKey = (.+?)\n.*?AllowedIPs = ([^\n]+)',
                content,
                re.DOTALL
            )
            
            for client_name, public_key, allowed_ips in client_sections:
                client_info = {
                    'name': client_name,
                    'public_key': public_key,
                    'allowed_ips': allowed_ips,
                    'config_exists': find_config_file(client_name) is not None
                }
                
                # Get connection status if possible
                client_info['status'] = self._get_client_status(public_key)
                clients.append(client_info)
        
        except Exception as e:
            logger.error(f"Error listing clients: {e}")
        
        return clients
    
    def _get_client_status(self, public_key: str) -> Dict:
        """Get client connection status"""
        status = {'connected': False, 'last_handshake': None, 'transfer': None}
        
        try:
            returncode, output, _ = run_command(['wg', 'show', 'wg0', 'dump'])
            if returncode == 0:
                for line in output.strip().split('\n')[1:]:  # Skip header
                    parts = line.split('\t')
                    if len(parts) >= 6 and parts[0] == public_key:
                        status['connected'] = True
                        if parts[4] != '0':
                            status['last_handshake'] = int(parts[4])
                        if parts[5] != '0' or parts[6] != '0':
                            status['transfer'] = {
                                'rx': int(parts[5]),
                                'tx': int(parts[6])
                            }
                        break
        except Exception as e:
            logger.error(f"Error getting client status: {e}")
        
        return status
    
    def add_client(self, client_name: str, dns_servers: str = "8.8.8.8") -> Tuple[bool, str, Optional[str]]:
        """
        Add a new WireGuard client
        Returns: (success, message, config_file_path)
        """
        # Sanitize client name
        sanitized_name = sanitize_client_name(client_name)
        if not sanitized_name:
            return False, "Invalid client name", None
        
        # Check if client already exists
        clients = self.list_clients()
        if any(client['name'] == sanitized_name for client in clients):
            return False, f"Client '{sanitized_name}' already exists", None
        
        # Validate DNS servers
        dns_list = [ip.strip() for ip in dns_servers.split(',')]
        if not all(validate_ip_address(ip) for ip in dns_list):
            return False, "Invalid DNS server format", None
        
        # Run WireGuard script to add client
        try:
            command = [
                'sudo', 'bash', self.script_path,
                '--addclient', sanitized_name,
                '--dns1', dns_list[0]
            ]
            
            if len(dns_list) > 1:
                command.extend(['--dns2', dns_list[1]])
            
            returncode, stdout, stderr = run_command(command, timeout=60)
            
            if returncode != 0:
                error_msg = stderr or stdout or "Unknown error occurred"
                return False, f"Failed to create client: {error_msg}", None
            
            # Find the created config file
            config_file = find_config_file(sanitized_name)
            if not config_file:
                return False, "Client created but config file not found", None
            
            return True, f"Client '{sanitized_name}' created successfully", config_file
            
        except Exception as e:
            logger.error(f"Error adding client: {e}")
            return False, f"Error adding client: {str(e)}", None
    
    def remove_client(self, client_name: str) -> Tuple[bool, str]:
        """
        Remove a WireGuard client
        Returns: (success, message)
        """
        # Check if client exists
        clients = self.list_clients()
        if not any(client['name'] == client_name for client in clients):
            return False, f"Client '{client_name}' not found"
        
        try:
            # Run WireGuard script to remove client
            command = [
                'sudo', 'bash', self.script_path,
                '--removeclient', client_name,
                '--yes'
            ]
            
            returncode, stdout, stderr = run_command(command, timeout=30)
            
            if returncode != 0:
                error_msg = stderr or stdout or "Unknown error occurred"
                return False, f"Failed to remove client: {error_msg}"
            
            return True, f"Client '{client_name}' removed successfully"
            
        except Exception as e:
            logger.error(f"Error removing client: {e}")
            return False, f"Error removing client: {str(e)}"
    
    def get_client_qr(self, client_name: str) -> Tuple[bool, str, Optional[str]]:
        """
        Generate QR code image for a client
        Returns: (success, message, qr_image_path)
        """
        # Find client config file
        config_file = find_config_file(client_name)
        if not config_file:
            return False, f"Config file for '{client_name}' not found", None
        
        try:
            import qrcode
            from PIL import Image
            import tempfile
            import os
            
            # Read config content
            with open(config_file, 'r') as f:
                config_content = f.read().strip()
            
            if not config_content:
                return False, "Config file is empty", None
            
            # Generate QR code with better settings
            qr = qrcode.QRCode(
                version=None,  # Auto-determine version
                error_correction=qrcode.constants.ERROR_CORRECT_M,  # Better error correction
                box_size=8,    # Smaller box size for better compatibility
                border=2,      # Smaller border
            )
            
            qr.add_data(config_content)
            qr.make(fit=True)
            
            # Create QR code image with explicit format
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            # Ensure it's a PIL Image
            if not isinstance(qr_img, Image.Image):
                qr_img = qr_img.convert('RGB')
            
            # Create temporary file with proper permissions
            temp_fd, temp_path = tempfile.mkstemp(suffix='.png', prefix='wirebot_qr_')
            
            try:
                # Save image to temporary file
                with os.fdopen(temp_fd, 'wb') as temp_file:
                    qr_img.save(temp_file, 'PNG', optimize=True)
                
                # Verify file was created and has content
                if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                    logger.info(f"QR code generated successfully: {temp_path}")
                    return True, f"QR code for '{client_name}'", temp_path
                else:
                    logger.error("QR code file was not created properly")
                    return False, "Failed to create QR code file", None
                    
            except Exception as save_error:
                logger.error(f"Error saving QR code image: {save_error}")
                # Clean up failed file
                try:
                    os.unlink(temp_path)
                except:
                    pass
                return False, f"Failed to save QR code: {str(save_error)}", None
            
        except ImportError as e:
            logger.error(f"QR code libraries not available: {e}")
            return False, "QR code generation requires 'qrcode' and 'pillow' packages", None
        except Exception as e:
            logger.error(f"Error generating QR code: {e}")
            return False, f"QR code generation failed: {str(e)}", None
    
    def get_client_config(self, client_name: str) -> Tuple[bool, str, Optional[str]]:
        """
        Get client configuration content
        Returns: (success, message, config_content)
        """
        config_file = find_config_file(client_name)
        if not config_file:
            return False, f"Config file for '{client_name}' not found", None
        
        try:
            with open(config_file, 'r') as f:
                config_content = f.read()
            return True, f"Configuration for '{client_name}'", config_content
        except Exception as e:
            logger.error(f"Error reading config file: {e}")
            return False, f"Error reading config: {str(e)}", None
    
    def backup_configs(self) -> Tuple[bool, str, Optional[str]]:
        """
        Create backup of all configurations
        Returns: (success, message, backup_file_path)
        """
        try:
            import tarfile
            import datetime
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"wireguard_backup_{timestamp}.tar.gz"
            backup_path = os.path.join(self.export_dir, backup_filename)
            
            with tarfile.open(backup_path, "w:gz") as tar:
                # Add server config
                if os.path.exists(self.wg_conf):
                    tar.add(self.wg_conf, arcname="wg0.conf")
                
                # Add client configs
                clients = self.list_clients()
                for client in clients:
                    config_file = find_config_file(client['name'])
                    if config_file:
                        tar.add(config_file, arcname=f"clients/{client['name']}.conf")
            
            return True, f"Backup created: {backup_filename}", backup_path
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return False, f"Error creating backup: {str(e)}", None
    
    def install_wireguard(self) -> Tuple[bool, str]:
        """
        Install WireGuard using the script
        Returns: (success, message)
        """
        if self.is_installed():
            return False, "WireGuard is already installed"
        
        try:
            command = ['sudo', 'bash', self.script_path, '--auto']
            returncode, stdout, stderr = run_command(command, timeout=300)  # 5 minutes timeout
            
            if returncode != 0:
                error_msg = stderr or stdout or "Unknown error occurred"
                return False, f"Installation failed: {error_msg}"
            
            return True, "WireGuard installed successfully"
            
        except Exception as e:
            logger.error(f"Error installing WireGuard: {e}")
            return False, f"Installation error: {str(e)}"
    
    def get_connection_stats(self) -> Dict:
        """Get detailed connection statistics"""
        stats = {
            'total_clients': 0,
            'connected_clients': 0,
            'total_transfer': {'rx': 0, 'tx': 0},
            'clients': []
        }
        
        clients = self.list_clients()
        stats['total_clients'] = len(clients)
        
        for client in clients:
            if client['status']['connected']:
                stats['connected_clients'] += 1
                if client['status']['transfer']:
                    stats['total_transfer']['rx'] += client['status']['transfer']['rx']
                    stats['total_transfer']['tx'] += client['status']['transfer']['tx']
        
        stats['clients'] = clients
        return stats

# Global manager instance
wg_manager = WireGuardManager()
