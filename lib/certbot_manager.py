import subprocess
import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import logging
from datetime import datetime

from .permissions import check_sudo_privileges, InsufficientPermissionsError


class CertbotManager:
    """Manage SSL certificates with certbot"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)
    
    def check_certificate_exists(self, domain: str) -> bool:
        """Check if certificate exists for domain"""
        cert_path = Path(f'/etc/letsencrypt/live/{domain}/fullchain.pem')
        return cert_path.exists()
    
    def request_certificate(self, domain: str, email: Optional[str] = None, include_www: bool = False) -> Tuple[bool, str]:
        """Request certificate for domain"""
        # Check permissions first (unless dry-run)
        if not self.dry_run:
            try:
                check_sudo_privileges()
            except InsufficientPermissionsError as e:
                return False, str(e)
        
        if self.check_certificate_exists(domain):
            return True, f"Certificate already exists for {domain}"
        
        # Build certbot command
        cmd = ['certbot', '--nginx', '-d', domain]
        
        # Add www subdomain if requested
        if include_www:
            cmd.extend(['-d', f'www.{domain}'])
        
        # Non-interactive mode
        cmd.append('--non-interactive')
        cmd.append('--agree-tos')
        
        if email:
            cmd.extend(['--email', email])
        else:
            cmd.append('--register-unsafely-without-email')
        
        if self.dry_run:
            cmd.append('--dry-run')
        
        # Execute certbot
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self.logger.info(f"Certificate obtained for {domain}")
                return True, result.stdout
            else:
                self.logger.error(f"Failed to obtain certificate for {domain}: {result.stderr}")
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            return False, "Certbot command timed out"
        except Exception as e:
            return False, str(e)
    
    def get_certificate_info(self, domain: str) -> Optional[Dict]:
        """Get certificate information"""
        if not self.check_certificate_exists(domain):
            return None
        
        try:
            result = subprocess.run(
                ['certbot', 'certificates', '-d', domain],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self.logger.error(f"Failed to get certificate info: {result.stderr}")
                return None
            
            # Parse output for certificate info
            output = result.stdout
            info = {}
            
            # Extract expiry date
            expiry_match = re.search(r'Expiry Date:\s*(\S+\s+\S+)', output)
            if expiry_match:
                info['expiry'] = expiry_match.group(1)
            
            # Extract certificate path
            cert_match = re.search(r'Certificate Path:\s*(\S+)', output)
            if cert_match:
                info['cert_path'] = cert_match.group(1)
            
            # Extract domains
            domains_match = re.search(r'Domains:\s*(.+)', output)
            if domains_match:
                domains_str = domains_match.group(1).strip()
                info['domains'] = [d.strip() for d in domains_str.split()]
            
            # Extract validity status
            if 'VALID' in output:
                info['valid'] = True
            elif 'INVALID' in output or 'EXPIRED' in output:
                info['valid'] = False
            
            return info if info else None
            
        except Exception as e:
            self.logger.error(f"Failed to get certificate info: {e}")
            return None
    
    def renew_certificates(self) -> Tuple[bool, str]:
        """Renew all certificates"""
        # Check permissions first (unless dry-run)
        if not self.dry_run:
            try:
                check_sudo_privileges()
            except InsufficientPermissionsError as e:
                return False, str(e)
        
        cmd = ['certbot', 'renew']
        
        if self.dry_run:
            cmd.append('--dry-run')
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                self.logger.info("Certificate renewal completed successfully")
                return True, result.stdout
            else:
                self.logger.error(f"Certificate renewal failed: {result.stderr}")
                return False, result.stderr
        except subprocess.TimeoutExpired:
            return False, "Certificate renewal timed out"
        except Exception as e:
            return False, str(e)
    
    def list_certificates(self) -> List[Dict]:
        """List all managed certificates"""
        try:
            result = subprocess.run(
                ['certbot', 'certificates'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self.logger.error(f"Failed to list certificates: {result.stderr}")
                return []
            
            output = result.stdout
            certificates = []
            
            # Split output by certificate entries
            # Look for lines that are mostly dashes (at least 20 dashes)
            cert_blocks = re.split(r'[\s\-]{20,}', output)
            
            for block in cert_blocks:
                block = block.strip()
                if not block or 'Certificate Name:' not in block:
                    continue
                
                cert_info = {}
                
                # Extract certificate name
                name_match = re.search(r'Certificate Name:\s*(\S+)', block)
                if name_match:
                    cert_info['name'] = name_match.group(1)
                
                # Extract domains
                domains_match = re.search(r'Domains:\s*(.+)', block)
                if domains_match:
                    domains_str = domains_match.group(1).strip()
                    cert_info['domains'] = [d.strip() for d in domains_str.split()]
                
                # Extract expiry date
                expiry_match = re.search(r'Expiry Date:\s*([^\(]+)', block)
                if expiry_match:
                    cert_info['expiry'] = expiry_match.group(1).strip()
                
                # Check if valid
                if 'VALID' in block:
                    cert_info['valid'] = True
                elif 'INVALID' in block or 'EXPIRED' in block:
                    cert_info['valid'] = False
                
                if cert_info and 'name' in cert_info:
                    certificates.append(cert_info)
            
            return certificates
            
        except Exception as e:
            self.logger.error(f"Failed to list certificates: {e}")
            return []
    
    def revoke_certificate(self, domain: str, reason: str = "unspecified") -> Tuple[bool, str]:
        """Revoke a certificate"""
        # Check permissions first (unless dry-run)
        if not self.dry_run:
            try:
                check_sudo_privileges()
            except InsufficientPermissionsError as e:
                return False, str(e)
        
        cert_path = Path(f'/etc/letsencrypt/live/{domain}/cert.pem')
        
        if not cert_path.exists():
            return False, f"Certificate not found for {domain}"
        
        cmd = [
            'certbot', 'revoke',
            '--cert-path', str(cert_path),
            '--reason', reason,
            '--non-interactive'
        ]
        
        if self.dry_run:
            cmd.append('--dry-run')
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self.logger.info(f"Certificate revoked for {domain}")
                return True, result.stdout
            else:
                self.logger.error(f"Failed to revoke certificate: {result.stderr}")
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            return False, "Certificate revocation timed out"
        except Exception as e:
            return False, str(e)
    
    def delete_certificate(self, domain: str) -> Tuple[bool, str]:
        """Delete a certificate and its renewal configuration"""
        # Check permissions first (unless dry-run)
        if not self.dry_run:
            try:
                check_sudo_privileges()
            except InsufficientPermissionsError as e:
                return False, str(e)
        
        cmd = [
            'certbot', 'delete',
            '--cert-name', domain,
            '--non-interactive'
        ]
        
        if self.dry_run:
            cmd.append('--dry-run')
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self.logger.info(f"Certificate deleted for {domain}")
                return True, result.stdout
            else:
                self.logger.error(f"Failed to delete certificate: {result.stderr}")
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            return False, "Certificate deletion timed out"
        except Exception as e:
            return False, str(e)