"""
Utility functions for WireBot
"""
import os
import re
import pwd
import subprocess
import logging
from typing import Optional, List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

def get_export_directory() -> str:
    """
    Get the correct export directory for WireGuard configs
    Mimics the get_export_dir() function from wireguard.sh
    """
    export_dir = os.path.expanduser("~/")
    
    # Check if running with sudo
    sudo_user = os.environ.get('SUDO_USER')
    if sudo_user:
        try:
            user_info = pwd.getpwnam(sudo_user)
            user_home = user_info.pw_dir
            if user_home and user_home != "/" and os.path.isdir(user_home):
                export_dir = f"{user_home}/"
        except KeyError:
            pass
    
    return export_dir

def find_config_file(client_name: str, search_paths: Optional[List[str]] = None) -> Optional[str]:
    """
    Find a WireGuard config file in multiple possible locations
    """
    if search_paths is None:
        search_paths = [
            get_export_directory(),
            "/root/",
            "/home/shair/",
            os.path.expanduser("~/"),
            "/tmp/",
            "/etc/wireguard/clients/"
        ]
    
    filename = f"{client_name}.conf"
    
    for path in search_paths:
        full_path = os.path.join(path, filename)
        if os.path.exists(full_path):
            logger.info(f"Found config file: {full_path}")
            return full_path
    
    logger.warning(f"Config file {filename} not found in any search paths")
    return None

def sanitize_client_name(name: str) -> str:
    """
    Sanitize client name according to WireGuard requirements
    """
    # Allow only alphanumeric, underscore, and hyphen
    sanitized = re.sub(r'[^0-9a-zA-Z_-]', '_', name)
    # Limit to 15 characters
    return sanitized[:15]

def validate_ip_address(ip: str) -> bool:
    """
    Validate IPv4 address format
    """
    pattern = r'^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$'
    return bool(re.match(pattern, ip))

def validate_dns_servers(dns_string: str) -> bool:
    """
    Validate DNS servers string (comma-separated IPs)
    """
    if not dns_string or not dns_string.strip():
        return False
    
    dns_servers = [ip.strip() for ip in dns_string.split(',')]
    return all(validate_ip_address(ip) for ip in dns_servers if ip.strip())

def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human readable format
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def run_command(command: List[str], capture_output: bool = True, timeout: int = 30) -> Tuple[int, str, str]:
    """
    Run a system command safely with timeout
    """
    try:
        result = subprocess.run(
            command,
            capture_output=capture_output,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out: {' '.join(command)}")
        return -1, "", "Command timed out"
    except Exception as e:
        logger.error(f"Command failed: {' '.join(command)}, Error: {e}")
        return -1, "", str(e)

def escape_markdown(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2
    """
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

def format_duration(seconds: int) -> str:
    """
    Format duration in human readable format
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d {hours}h"

def get_system_info() -> dict:
    """
    Get basic system information
    """
    info = {}
    
    try:
        # Get system uptime
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
            info['uptime'] = format_duration(int(uptime_seconds))
    except:
        info['uptime'] = "Unknown"
    
    try:
        # Get memory info
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
            total_match = re.search(r'MemTotal:\s+(\d+)', meminfo)
            available_match = re.search(r'MemAvailable:\s+(\d+)', meminfo)
            
            if total_match and available_match:
                total_kb = int(total_match.group(1))
                available_kb = int(available_match.group(1))
                used_kb = total_kb - available_kb
                
                info['memory'] = {
                    'total': format_file_size(total_kb * 1024),
                    'used': format_file_size(used_kb * 1024),
                    'available': format_file_size(available_kb * 1024),
                    'usage_percent': round((used_kb / total_kb) * 100, 1)
                }
    except:
        info['memory'] = {"error": "Unable to read memory info"}
    
    try:
        # Get load average
        with open('/proc/loadavg', 'r') as f:
            load_avg = f.readline().split()[:3]
            info['load_avg'] = load_avg
    except:
        info['load_avg'] = ["Unknown", "Unknown", "Unknown"]
    
    return info

def check_wireguard_status() -> dict:
    """
    Check WireGuard service status
    """
    status = {}
    
    # Check if WireGuard is installed
    returncode, _, _ = run_command(['which', 'wg'])
    status['installed'] = returncode == 0
    
    if not status['installed']:
        return status
    
    # Check if wg0 interface exists
    returncode, output, _ = run_command(['wg', 'show', 'wg0'])
    status['interface_exists'] = returncode == 0
    
    if status['interface_exists']:
        status['interface_info'] = output.strip()
    
    # Check systemd service status
    returncode, output, _ = run_command(['systemctl', 'is-active', 'wg-quick@wg0'])
    status['service_active'] = output.strip() == 'active'
    
    returncode, output, _ = run_command(['systemctl', 'is-enabled', 'wg-quick@wg0'])
    status['service_enabled'] = 'enabled' in output
    
    return status
