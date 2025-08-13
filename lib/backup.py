#!/usr/bin/env python3
"""
Backup and restore functionality for nginx configurations.

Provides automated backup creation, restoration, and cleanup of nginx configuration files.
"""

import tarfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class BackupManager:
    """Manage configuration backups for nginx sites."""
    
    def __init__(self, backup_dir: Path):
        """
        Initialize backup manager.
        
        Args:
            backup_dir: Directory to store backup files
        """
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, description: str = "") -> Path:
        """
        Create timestamped backup of nginx configs.
        
        Args:
            description: Optional description to include in backup name
            
        Returns:
            Path to created backup file
            
        Raises:
            IOError: If backup creation fails
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"nginx_backup_{timestamp}"
        if description:
            # Sanitize description for filename
            safe_description = description.replace(' ', '_').replace('/', '_')
            backup_name += f"_{safe_description}"
        
        backup_path = self.backup_dir / f"{backup_name}.tar.gz"
        
        try:
            with tarfile.open(backup_path, 'w:gz') as tar:
                # Backup sites-available
                sites_available = Path('/etc/nginx/sites-available')
                if sites_available.exists():
                    tar.add(sites_available, arcname='sites-available')
                    logger.info(f"Backed up {sites_available}")
                
                # Backup sites-enabled (preserving symlinks)
                sites_enabled = Path('/etc/nginx/sites-enabled')
                if sites_enabled.exists():
                    tar.add(sites_enabled, arcname='sites-enabled')
                    logger.info(f"Backed up {sites_enabled}")
                
                # Backup main nginx.conf
                nginx_conf = Path('/etc/nginx/nginx.conf')
                if nginx_conf.exists():
                    tar.add(nginx_conf, arcname='nginx.conf')
                    logger.info(f"Backed up {nginx_conf}")
            
            logger.info(f"Created backup: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            if backup_path.exists():
                backup_path.unlink()
            raise IOError(f"Backup creation failed: {e}")
    
    def restore_backup(self, backup_path: Path) -> bool:
        """
        Restore configuration from backup.
        
        Args:
            backup_path: Path to backup file to restore
            
        Returns:
            True if restore successful, False otherwise
            
        Raises:
            FileNotFoundError: If backup file doesn't exist
            IOError: If restore operation fails
        """
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")
        
        # Extract to temporary directory first for safety
        temp_dir = Path('/tmp/nginx_restore')
        temp_dir.mkdir(exist_ok=True)
        
        try:
            # Extract backup
            with tarfile.open(backup_path, 'r:gz') as tar:
                tar.extractall(temp_dir)
            
            logger.info(f"Extracted backup to temporary directory: {temp_dir}")
            
            # Create safety backup of current config before restore
            safety_backup = self.create_backup('pre_restore_safety')
            logger.info(f"Created safety backup before restore: {safety_backup}")
            
            # Restore sites-available
            sites_available_backup = temp_dir / 'sites-available'
            if sites_available_backup.exists():
                sites_available = Path('/etc/nginx/sites-available')
                if sites_available.exists():
                    shutil.rmtree(sites_available)
                shutil.copytree(sites_available_backup, sites_available)
                logger.info(f"Restored {sites_available}")
            
            # Restore sites-enabled
            sites_enabled_backup = temp_dir / 'sites-enabled'
            if sites_enabled_backup.exists():
                sites_enabled = Path('/etc/nginx/sites-enabled')
                if sites_enabled.exists():
                    shutil.rmtree(sites_enabled)
                shutil.copytree(sites_enabled_backup, sites_enabled, symlinks=True)
                logger.info(f"Restored {sites_enabled}")
            
            # Restore nginx.conf if present
            nginx_conf_backup = temp_dir / 'nginx.conf'
            if nginx_conf_backup.exists():
                nginx_conf = Path('/etc/nginx/nginx.conf')
                shutil.copy2(nginx_conf_backup, nginx_conf)
                logger.info(f"Restored {nginx_conf}")
            
            logger.info(f"Successfully restored from backup: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            raise IOError(f"Restore operation failed: {e}")
            
        finally:
            # Clean up temporary directory
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def list_backups(self) -> List[Path]:
        """
        List available backups sorted by date (newest first).
        
        Returns:
            List of Path objects for backup files
        """
        backups = sorted(
            self.backup_dir.glob('nginx_backup_*.tar.gz'),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        return backups
    
    def cleanup_old_backups(self, keep: int = 10):
        """
        Remove old backups, keeping most recent N.
        
        Args:
            keep: Number of recent backups to keep
        """
        if keep < 1:
            logger.warning(f"Invalid keep value {keep}, using minimum of 1")
            keep = 1
        
        backups = self.list_backups()
        
        if len(backups) <= keep:
            logger.info(f"No cleanup needed: {len(backups)} backups, keeping {keep}")
            return
        
        # Remove old backups
        for backup in backups[keep:]:
            try:
                backup.unlink()
                logger.info(f"Removed old backup: {backup.name}")
            except Exception as e:
                logger.error(f"Failed to remove backup {backup.name}: {e}")
    
    def get_backup_info(self, backup_path: Path) -> dict:
        """
        Get information about a backup file.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            Dictionary with backup information
        """
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")
        
        stat = backup_path.stat()
        
        # Extract timestamp from filename
        name_parts = backup_path.stem.replace('.tar', '').split('_')
        timestamp_str = None
        description = None
        
        if len(name_parts) >= 3:
            timestamp_str = f"{name_parts[2]}_{name_parts[3]}"
            if len(name_parts) > 4:
                description = '_'.join(name_parts[4:])
        
        info = {
            'path': backup_path,
            'name': backup_path.name,
            'size': stat.st_size,
            'created': datetime.fromtimestamp(stat.st_mtime),
            'timestamp_str': timestamp_str,
            'description': description
        }
        
        # List contents
        try:
            with tarfile.open(backup_path, 'r:gz') as tar:
                info['contents'] = tar.getnames()
        except Exception as e:
            logger.error(f"Failed to read backup contents: {e}")
            info['contents'] = []
        
        return info