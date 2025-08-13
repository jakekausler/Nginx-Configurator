"""
Permission checking utilities for nginx configuration management.

This module provides functions to check for required system permissions
before performing operations that require elevated privileges.
"""

import os
import subprocess
from pathlib import Path
from typing import List, Tuple


class InsufficientPermissionsError(Exception):
    """Raised when insufficient permissions are detected for required operations."""
    pass


def check_sudo_privileges() -> None:
    """
    Check if the current process has sudo privileges.
    
    Raises:
        InsufficientPermissionsError: If sudo privileges are not available
    """
    # Method 1: Check if running as root
    if os.getuid() == 0:
        return
    
    # Method 2: Check if sudo is available and working
    try:
        result = subprocess.run(
            ['sudo', '-n', 'true'],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            return
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    raise InsufficientPermissionsError(
        "This command requires sudo privileges. Please run with 'sudo' or as root."
    )


def check_nginx_permissions() -> List[str]:
    """
    Check permissions for nginx-related directories and files.
    
    Returns:
        List of permission issues found (empty if no issues)
    """
    issues = []
    
    # Check nginx directories
    nginx_dirs = [
        '/etc/nginx',
        '/etc/nginx/sites-available',
        '/etc/nginx/sites-enabled',
        '/var/log/nginx'
    ]
    
    for dir_path in nginx_dirs:
        path = Path(dir_path)
        if not path.exists():
            issues.append(f"Directory does not exist: {dir_path}")
        elif not os.access(path, os.R_OK | os.W_OK):
            issues.append(f"No read/write access to: {dir_path}")
    
    # Check nginx configuration file
    nginx_conf = Path('/etc/nginx/nginx.conf')
    if nginx_conf.exists() and not os.access(nginx_conf, os.R_OK):
        issues.append(f"No read access to: {nginx_conf}")
    
    return issues


def check_letsencrypt_permissions() -> List[str]:
    """
    Check permissions for Let's Encrypt directories.
    
    Returns:
        List of permission issues found (empty if no issues)
    """
    issues = []
    
    letsencrypt_dirs = [
        '/etc/letsencrypt',
        '/etc/letsencrypt/live',
        '/etc/letsencrypt/archive'
    ]
    
    for dir_path in letsencrypt_dirs:
        path = Path(dir_path)
        if path.exists() and not os.access(path, os.R_OK):
            issues.append(f"No read access to: {dir_path}")
    
    return issues


def check_systemctl_permissions() -> bool:
    """
    Check if systemctl can be used to manage nginx service.
    
    Returns:
        True if systemctl can be used, False otherwise
    """
    try:
        result = subprocess.run(
            ['sudo', '-n', 'systemctl', 'status', 'nginx'],
            capture_output=True,
            timeout=10
        )
        return result.returncode in [0, 3]  # 0 = running, 3 = stopped
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def validate_all_permissions() -> Tuple[bool, List[str]]:
    """
    Validate all required permissions for nginx configuration management.
    
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    
    # Check sudo privileges
    try:
        check_sudo_privileges()
    except InsufficientPermissionsError as e:
        issues.append(str(e))
    
    # Check nginx permissions
    issues.extend(check_nginx_permissions())
    
    # Check Let's Encrypt permissions
    issues.extend(check_letsencrypt_permissions())
    
    # Check systemctl permissions
    if not check_systemctl_permissions():
        issues.append("Cannot manage nginx service with systemctl")
    
    return len(issues) == 0, issues


def require_sudo_privileges() -> None:
    """
    Require sudo privileges and exit gracefully if not available.
    
    This is the main function to call at the beginning of commands
    that require elevated privileges.
    
    Raises:
        SystemExit: If insufficient privileges are detected
    """
    try:
        check_sudo_privileges()
    except InsufficientPermissionsError as e:
        print(f"Error: {e}")
        print("\nTo run this command, you need to:")
        print("1. Run with sudo: sudo ./nginx-sites <command>")
        print("2. Or run as root user")
        print("3. Or configure passwordless sudo for your user")
        raise SystemExit(1)