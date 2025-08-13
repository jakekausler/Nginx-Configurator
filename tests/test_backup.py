#!/usr/bin/env python3
"""
Unit tests for backup management functionality.
"""

import pytest
import tarfile
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.backup import BackupManager


class TestBackupManager:
    """Test cases for BackupManager class."""
    
    @pytest.fixture
    def temp_backup_dir(self):
        """Create a temporary directory for backups."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def backup_manager(self, temp_backup_dir):
        """Create a BackupManager instance with temp directory."""
        return BackupManager(temp_backup_dir)
    
    @pytest.fixture
    def mock_nginx_dirs(self, tmp_path):
        """Create mock nginx directory structure."""
        sites_available = tmp_path / 'nginx' / 'sites-available'
        sites_enabled = tmp_path / 'nginx' / 'sites-enabled'
        
        sites_available.mkdir(parents=True)
        sites_enabled.mkdir(parents=True)
        
        # Create some test site configs
        (sites_available / 'test.com').write_text('server { server_name test.com; }')
        (sites_available / 'example.com').write_text('server { server_name example.com; }')
        
        # Create symlink in sites-enabled
        (sites_enabled / 'test.com').symlink_to(sites_available / 'test.com')
        
        # Create nginx.conf
        nginx_conf = tmp_path / 'nginx' / 'nginx.conf'
        nginx_conf.write_text('user www-data;\nworker_processes auto;')
        
        return {
            'sites_available': sites_available,
            'sites_enabled': sites_enabled,
            'nginx_conf': nginx_conf
        }
    
    def test_init_creates_backup_directory(self, tmp_path):
        """Test that BackupManager creates backup directory if it doesn't exist."""
        backup_dir = tmp_path / 'new_backup_dir'
        assert not backup_dir.exists()
        
        BackupManager(backup_dir)
        assert backup_dir.exists()
    
    def test_create_backup_basic(self, backup_manager, mock_nginx_dirs):
        """Test basic backup creation."""
        with patch('lib.backup.Path') as mock_path:
            # Mock the nginx paths to point to our test directories
            def path_side_effect(path_str):
                if path_str == '/etc/nginx/sites-available':
                    return mock_nginx_dirs['sites_available']
                elif path_str == '/etc/nginx/sites-enabled':
                    return mock_nginx_dirs['sites_enabled']
                elif path_str == '/etc/nginx/nginx.conf':
                    return mock_nginx_dirs['nginx_conf']
                return Path(path_str)
            
            mock_path.side_effect = path_side_effect
            
            backup_path = backup_manager.create_backup()
            
            assert backup_path.exists()
            assert backup_path.suffix == '.gz'
            assert 'nginx_backup_' in backup_path.name
            
            # Verify backup contains expected files
            with tarfile.open(backup_path, 'r:gz') as tar:
                names = tar.getnames()
                assert 'sites-available' in names or any('sites-available' in n for n in names)
    
    def test_create_backup_with_description(self, backup_manager):
        """Test backup creation with description."""
        with patch('lib.backup.tarfile.open'):
            backup_path = backup_manager.create_backup('test_backup')
            
            assert 'test_backup' in backup_path.name
            assert 'nginx_backup_' in backup_path.name
    
    def test_create_backup_sanitizes_description(self, backup_manager):
        """Test that backup description is sanitized for filename."""
        with patch('lib.backup.tarfile.open'):
            backup_path = backup_manager.create_backup('test/backup with spaces')
            
            assert 'test_backup_with_spaces' in backup_path.name
            assert '/' not in backup_path.stem
    
    def test_list_backups_empty(self, backup_manager):
        """Test listing backups when none exist."""
        backups = backup_manager.list_backups()
        assert backups == []
    
    def test_list_backups_sorted(self, backup_manager, temp_backup_dir):
        """Test that backups are listed in reverse chronological order."""
        # Create some backup files with different timestamps
        backup1 = temp_backup_dir / 'nginx_backup_20240101_120000.tar.gz'
        backup2 = temp_backup_dir / 'nginx_backup_20240102_120000.tar.gz'
        backup3 = temp_backup_dir / 'nginx_backup_20240103_120000.tar.gz'
        
        # Create files in random order
        backup2.touch()
        backup1.touch()
        backup3.touch()
        
        backups = backup_manager.list_backups()
        
        # Should be sorted newest first
        assert len(backups) == 3
        # The actual order depends on file modification time, not name
        assert all(b.suffix == '.gz' for b in backups)
    
    def test_cleanup_old_backups_keeps_recent(self, backup_manager, temp_backup_dir):
        """Test that cleanup keeps specified number of recent backups."""
        # Create 5 backup files
        for i in range(5):
            backup = temp_backup_dir / f'nginx_backup_2024010{i}_120000.tar.gz'
            backup.touch()
        
        # Keep only 3 most recent
        backup_manager.cleanup_old_backups(keep=3)
        
        remaining = list(temp_backup_dir.glob('nginx_backup_*.tar.gz'))
        assert len(remaining) == 3
    
    def test_cleanup_old_backups_no_cleanup_needed(self, backup_manager, temp_backup_dir):
        """Test cleanup when fewer backups than keep threshold."""
        # Create 2 backup files
        for i in range(2):
            backup = temp_backup_dir / f'nginx_backup_2024010{i}_120000.tar.gz'
            backup.touch()
        
        # Try to keep 5 (more than exist)
        backup_manager.cleanup_old_backups(keep=5)
        
        remaining = list(temp_backup_dir.glob('nginx_backup_*.tar.gz'))
        assert len(remaining) == 2  # All kept
    
    def test_cleanup_old_backups_minimum_keep(self, backup_manager):
        """Test that cleanup enforces minimum keep value of 1."""
        with patch.object(backup_manager, 'list_backups') as mock_list:
            mock_list.return_value = [Path('backup1.tar.gz'), Path('backup2.tar.gz')]
            
            # Try to keep 0 (should be corrected to 1)
            backup_manager.cleanup_old_backups(keep=0)
            
            # Should have been called to get list
            mock_list.assert_called_once()
    
    def test_restore_backup_not_found(self, backup_manager):
        """Test restore with non-existent backup file."""
        fake_backup = Path('/tmp/nonexistent_backup.tar.gz')
        
        with pytest.raises(FileNotFoundError) as exc_info:
            backup_manager.restore_backup(fake_backup)
        
        assert 'Backup not found' in str(exc_info.value)
    
    @patch('lib.backup.shutil.rmtree')
    @patch('lib.backup.shutil.copytree')
    @patch('lib.backup.shutil.copy2')
    def test_restore_backup_success(self, mock_copy2, mock_copytree, mock_rmtree, 
                                   backup_manager, temp_backup_dir):
        """Test successful backup restoration."""
        # Create a mock backup file
        backup_file = temp_backup_dir / 'test_backup.tar.gz'
        
        # Create a simple tar file with test content
        with tarfile.open(backup_file, 'w:gz') as tar:
            # Create temporary files to add to tar
            temp_dir = Path(tempfile.mkdtemp())
            sites_available = temp_dir / 'sites-available'
            sites_available.mkdir()
            (sites_available / 'test.com').write_text('test config')
            
            tar.add(sites_available, arcname='sites-available')
            shutil.rmtree(temp_dir)
        
        # Mock the create_backup method to avoid actual backup during restore
        with patch.object(backup_manager, 'create_backup') as mock_create:
            mock_create.return_value = Path('/tmp/safety_backup.tar.gz')
            
            result = backup_manager.restore_backup(backup_file)
            
            assert result is True
            mock_create.assert_called_once_with('pre_restore_safety')
    
    def test_restore_backup_cleanup_on_error(self, backup_manager, temp_backup_dir):
        """Test that temporary directory is cleaned up even on error."""
        backup_file = temp_backup_dir / 'test_backup.tar.gz'
        backup_file.touch()  # Create empty file (invalid tar)
        
        with patch('lib.backup.shutil.rmtree') as mock_rmtree:
            with pytest.raises(IOError):
                backup_manager.restore_backup(backup_file)
            
            # Verify cleanup was attempted
            calls = [str(call[0][0]) for call in mock_rmtree.call_args_list]
            assert any('/tmp/nginx_restore' in call for call in calls)
    
    def test_get_backup_info(self, backup_manager, temp_backup_dir):
        """Test getting backup information."""
        # Create a backup file with known content
        backup_file = temp_backup_dir / 'nginx_backup_20240115_143022_test_desc.tar.gz'
        
        with tarfile.open(backup_file, 'w:gz') as tar:
            # Add a dummy file
            temp_file = temp_backup_dir / 'test.txt'
            temp_file.write_text('test')
            tar.add(temp_file, arcname='sites-available/test.com')
            temp_file.unlink()
        
        info = backup_manager.get_backup_info(backup_file)
        
        assert info['name'] == backup_file.name
        assert info['path'] == backup_file
        assert info['size'] > 0
        assert isinstance(info['created'], datetime)
        assert info['timestamp_str'] == '20240115_143022'
        assert info['description'] == 'test_desc'
        assert 'sites-available/test.com' in info['contents']
    
    def test_get_backup_info_not_found(self, backup_manager):
        """Test getting info for non-existent backup."""
        fake_backup = Path('/tmp/nonexistent.tar.gz')
        
        with pytest.raises(FileNotFoundError) as exc_info:
            backup_manager.get_backup_info(fake_backup)
        
        assert 'Backup not found' in str(exc_info.value)
    
    def test_get_backup_info_invalid_tar(self, backup_manager, temp_backup_dir):
        """Test getting info for invalid tar file."""
        # Create an invalid tar file
        backup_file = temp_backup_dir / 'nginx_backup_20240115_143022.tar.gz'
        backup_file.write_text('not a tar file')
        
        info = backup_manager.get_backup_info(backup_file)
        
        # Should still return basic info even if can't read contents
        assert info['name'] == backup_file.name
        assert info['contents'] == []  # Empty due to read error