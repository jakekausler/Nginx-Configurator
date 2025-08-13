"""
AWS Route 53 DNS Management for Nginx Sites

This module provides functionality to automatically manage DNS records in AWS Route 53
based on the enabled sites in the nginx configuration.
"""

import boto3
from typing import Dict, List, Optional, Tuple
import logging
from botocore.exceptions import ClientError, NoCredentialsError


class Route53Manager:
    """Manage DNS records in AWS Route 53"""
    
    def __init__(self, hosted_zone_id: Optional[str] = None, profile_name: str = 'route53'):
        self.hosted_zone_id = hosted_zone_id or self._find_hosted_zone(profile_name)
        self.profile_name = profile_name
        self.route53 = None
        self.logger = logging.getLogger(__name__)
        
    def _get_client(self):
        """Get Route 53 client with error handling"""
        if not self.route53:
            try:
                session = boto3.Session(profile_name=self.profile_name)
                self.route53 = session.client('route53')
            except NoCredentialsError:
                raise Exception(f"AWS credentials not configured for profile '{self.profile_name}'. Run 'aws configure --profile {self.profile_name}' first.")
            except Exception as e:
                if 'could not be found' in str(e):
                    raise Exception(f"AWS profile '{self.profile_name}' not found. Run 'aws configure --profile {self.profile_name}' first.")
                raise Exception(f"Failed to create AWS client: {e}")
        return self.route53
        
    def _find_hosted_zone(self, profile_name: str) -> Optional[str]:
        """Find hosted zone ID for jakekausler.com"""
        try:
            session = boto3.Session(profile_name=profile_name)
            client = session.client('route53')
            response = client.list_hosted_zones()
            for zone in response['HostedZones']:
                if zone['Name'] == 'jakekausler.com.':
                    return zone['Id'].split('/')[-1]  # Remove /hostedzone/ prefix
            raise Exception("Hosted zone for jakekausler.com not found")
        except NoCredentialsError:
            raise Exception(f"AWS credentials not configured for profile '{profile_name}'. Run 'aws configure --profile {profile_name}' first.")
        except ClientError as e:
            raise Exception(f"Failed to find hosted zone: {e}")
        except Exception as e:
            if 'could not be found' in str(e):
                raise Exception(f"AWS profile '{profile_name}' not found. Run 'aws configure --profile {profile_name}' first.")
            raise Exception(f"Failed to create AWS client: {e}")

    def get_existing_records(self) -> Dict[str, str]:
        """Get existing A records from Route 53"""
        client = self._get_client()
        records = {}
        
        try:
            paginator = client.get_paginator('list_resource_record_sets')
            for page in paginator.paginate(HostedZoneId=self.hosted_zone_id):
                for record in page['ResourceRecordSets']:
                    if record['Type'] == 'A' and len(record.get('ResourceRecords', [])) > 0:
                        name = record['Name'].rstrip('.')
                        ip = record['ResourceRecords'][0]['Value']
                        records[name] = ip
            return records
        except ClientError as e:
            raise Exception(f"Failed to get existing records: {e}")

    def get_main_domain_ip(self) -> str:
        """Get current IP of jakekausler.com A record"""
        records = self.get_existing_records()
        if 'jakekausler.com' not in records:
            raise Exception("jakekausler.com A record not found")
        return records['jakekausler.com']

    def sync_dns_records(self, enabled_domains: List[str]) -> Tuple[int, int]:
        """Sync DNS records with enabled sites
        
        Returns: (created_count, deleted_count)
        """
        current_records = self.get_existing_records()
        main_ip = self.get_main_domain_ip()
        
        # Preserve essential records
        essential_records = {'jakekausler.com'}
        
        # Determine what should exist
        target_records = essential_records.copy()
        for domain in enabled_domains:
            if domain.endswith('.jakekausler.com'):
                target_records.add(domain)
        
        # Find records to create and delete
        to_create = target_records - set(current_records.keys())
        to_delete = set(current_records.keys()) - target_records - essential_records
        
        created_count = 0
        deleted_count = 0
        
        # Create missing records
        for domain in to_create:
            if self._create_a_record(domain, main_ip):
                created_count += 1
                self.logger.info(f"Created A record for {domain}")
        
        # Delete obsolete records  
        for domain in to_delete:
            if self._delete_a_record(domain, current_records[domain]):
                deleted_count += 1
                self.logger.info(f"Deleted A record for {domain}")
        
        return created_count, deleted_count

    def _create_a_record(self, domain: str, ip: str) -> bool:
        """Create A record for domain"""
        client = self._get_client()
        
        try:
            response = client.change_resource_record_sets(
                HostedZoneId=self.hosted_zone_id,
                ChangeBatch={
                    'Changes': [{
                        'Action': 'CREATE',
                        'ResourceRecordSet': {
                            'Name': domain,
                            'Type': 'A',
                            'TTL': 300,
                            'ResourceRecords': [{'Value': ip}]
                        }
                    }]
                }
            )
            return response['ResponseMetadata']['HTTPStatusCode'] == 200
        except ClientError as e:
            self.logger.error(f"Failed to create A record for {domain}: {e}")
            return False

    def _delete_a_record(self, domain: str, ip: str) -> bool:
        """Delete A record for domain"""
        client = self._get_client()
        
        try:
            response = client.change_resource_record_sets(
                HostedZoneId=self.hosted_zone_id,
                ChangeBatch={
                    'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': {
                            'Name': domain,
                            'Type': 'A',
                            'TTL': 300,
                            'ResourceRecords': [{'Value': ip}]
                        }
                    }]
                }
            )
            return response['ResponseMetadata']['HTTPStatusCode'] == 200
        except ClientError as e:
            self.logger.error(f"Failed to delete A record for {domain}: {e}")
            return False

    def list_dns_records(self) -> Dict[str, str]:
        """List all DNS records for debugging purposes"""
        return self.get_existing_records()