"""
Tests for Route 53 DNS manager
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError, NoCredentialsError

from lib.route53_manager import Route53Manager


class TestRoute53Manager:
    """Test cases for Route53Manager"""

    @pytest.fixture
    def mock_boto3_session(self):
        """Mock boto3.Session for testing"""
        with patch('boto3.Session') as mock_session:
            mock_client = Mock()
            mock_session.return_value.client.return_value = mock_client
            yield mock_session, mock_client

    @pytest.fixture
    def sample_hosted_zones(self):
        """Sample hosted zones response from AWS"""
        return {
            'HostedZones': [
                {
                    'Id': '/hostedzone/Z123456789ABCDEF',
                    'Name': 'jakekausler.com.',
                    'CallerReference': 'test-ref'
                }
            ]
        }

    @pytest.fixture
    def sample_record_sets(self):
        """Sample DNS record sets"""
        return [{
            'ResourceRecordSets': [
                {
                    'Name': 'jakekausler.com.',
                    'Type': 'A',
                    'TTL': 300,
                    'ResourceRecords': [{'Value': '1.2.3.4'}]
                },
                {
                    'Name': 'test.jakekausler.com.',
                    'Type': 'A',
                    'TTL': 300,
                    'ResourceRecords': [{'Value': '1.2.3.4'}]
                },
                {
                    'Name': 'jakekausler.com.',
                    'Type': 'NS',
                    'TTL': 172800,
                    'ResourceRecords': [{'Value': 'ns1.example.com'}]
                }
            ]
        }]

    def test_init_with_custom_profile(self, mock_boto3_session, sample_hosted_zones):
        """Test initialization with custom profile"""
        mock_session, mock_client = mock_boto3_session
        mock_client.list_hosted_zones.return_value = sample_hosted_zones
        
        manager = Route53Manager(profile_name='custom-profile')
        
        assert manager.profile_name == 'custom-profile'
        assert manager.hosted_zone_id == 'Z123456789ABCDEF'

    def test_init_with_default_profile(self, mock_boto3_session, sample_hosted_zones):
        """Test initialization with default route53 profile"""
        mock_session, mock_client = mock_boto3_session
        mock_client.list_hosted_zones.return_value = sample_hosted_zones
        
        manager = Route53Manager()
        
        assert manager.profile_name == 'route53'
        mock_session.assert_called_with(profile_name='route53')

    def test_init_with_explicit_zone_id(self):
        """Test initialization with explicit hosted zone ID"""
        manager = Route53Manager(hosted_zone_id='Z987654321', profile_name='test')
        
        assert manager.hosted_zone_id == 'Z987654321'
        assert manager.profile_name == 'test'

    def test_find_hosted_zone_success(self, mock_boto3_session, sample_hosted_zones):
        """Test finding hosted zone successfully"""
        mock_session, mock_client = mock_boto3_session
        mock_client.list_hosted_zones.return_value = sample_hosted_zones
        
        manager = Route53Manager()
        
        assert manager.hosted_zone_id == 'Z123456789ABCDEF'

    def test_find_hosted_zone_not_found(self, mock_boto3_session):
        """Test hosted zone not found"""
        mock_session, mock_client = mock_boto3_session
        mock_client.list_hosted_zones.return_value = {'HostedZones': []}
        
        with pytest.raises(Exception, match="Hosted zone for jakekausler.com not found"):
            Route53Manager()

    def test_credentials_error(self):
        """Test handling of missing AWS credentials"""
        with patch('boto3.Session') as mock_session:
            mock_session.side_effect = NoCredentialsError()
            
            with pytest.raises(Exception, match="AWS credentials not configured for profile 'route53'"):
                Route53Manager()  # This will call _find_hosted_zone

    def test_profile_not_found(self):
        """Test handling of missing AWS profile"""
        with patch('boto3.Session') as mock_session:
            mock_session.side_effect = Exception("The config profile (route53) could not be found")
            
            with pytest.raises(Exception, match="AWS profile 'route53' not found"):
                Route53Manager()  # This will call _find_hosted_zone

    def test_get_existing_records(self, mock_boto3_session, sample_hosted_zones, sample_record_sets):
        """Test retrieving existing DNS records"""
        mock_session, mock_client = mock_boto3_session
        mock_client.list_hosted_zones.return_value = sample_hosted_zones
        
        # Mock paginator for record sets
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = sample_record_sets
        mock_client.get_paginator.return_value = mock_paginator
        
        manager = Route53Manager()
        records = manager.get_existing_records()
        
        expected_records = {
            'jakekausler.com': '1.2.3.4',
            'test.jakekausler.com': '1.2.3.4'
        }
        assert records == expected_records

    def test_get_main_domain_ip(self, mock_boto3_session, sample_hosted_zones, sample_record_sets):
        """Test getting main domain IP address"""
        mock_session, mock_client = mock_boto3_session
        mock_client.list_hosted_zones.return_value = sample_hosted_zones
        
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = sample_record_sets
        mock_client.get_paginator.return_value = mock_paginator
        
        manager = Route53Manager()
        ip = manager.get_main_domain_ip()
        
        assert ip == '1.2.3.4'

    def test_get_main_domain_ip_not_found(self, mock_boto3_session, sample_hosted_zones):
        """Test error when main domain IP not found"""
        mock_session, mock_client = mock_boto3_session
        mock_client.list_hosted_zones.return_value = sample_hosted_zones
        
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{'ResourceRecordSets': []}]
        mock_client.get_paginator.return_value = mock_paginator
        
        manager = Route53Manager()
        
        with pytest.raises(Exception, match="jakekausler.com A record not found"):
            manager.get_main_domain_ip()

    def test_sync_dns_records_create_only(self, mock_boto3_session, sample_hosted_zones, sample_record_sets):
        """Test syncing DNS records - create new records only"""
        mock_session, mock_client = mock_boto3_session
        mock_client.list_hosted_zones.return_value = sample_hosted_zones
        
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = sample_record_sets
        mock_client.get_paginator.return_value = mock_paginator
        
        # Mock successful record creation
        mock_client.change_resource_record_sets.return_value = {
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        
        manager = Route53Manager()
        enabled_domains = ['jakekausler.com', 'new.jakekausler.com', 'another.jakekausler.com']
        
        created, deleted = manager.sync_dns_records(enabled_domains)
        
        assert created == 2  # new.jakekausler.com and another.jakekausler.com
        assert deleted == 1  # test.jakekausler.com should be deleted
        assert mock_client.change_resource_record_sets.call_count == 3

    def test_sync_dns_records_delete_only(self, mock_boto3_session, sample_hosted_zones, sample_record_sets):
        """Test syncing DNS records - delete obsolete records only"""
        mock_session, mock_client = mock_boto3_session
        mock_client.list_hosted_zones.return_value = sample_hosted_zones
        
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = sample_record_sets
        mock_client.get_paginator.return_value = mock_paginator
        
        # Mock successful record deletion
        mock_client.change_resource_record_sets.return_value = {
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        
        manager = Route53Manager()
        enabled_domains = ['jakekausler.com']  # Only keep main domain
        
        created, deleted = manager.sync_dns_records(enabled_domains)
        
        assert created == 0
        assert deleted == 1  # test.jakekausler.com should be deleted
        assert mock_client.change_resource_record_sets.call_count == 1

    def test_sync_dns_records_no_changes(self, mock_boto3_session, sample_hosted_zones, sample_record_sets):
        """Test syncing DNS records when no changes needed"""
        mock_session, mock_client = mock_boto3_session
        mock_client.list_hosted_zones.return_value = sample_hosted_zones
        
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = sample_record_sets
        mock_client.get_paginator.return_value = mock_paginator
        
        manager = Route53Manager()
        enabled_domains = ['jakekausler.com', 'test.jakekausler.com']
        
        created, deleted = manager.sync_dns_records(enabled_domains)
        
        assert created == 0
        assert deleted == 0
        assert mock_client.change_resource_record_sets.call_count == 0

    def test_create_a_record_success(self, mock_boto3_session, sample_hosted_zones):
        """Test successful A record creation"""
        mock_session, mock_client = mock_boto3_session
        mock_client.list_hosted_zones.return_value = sample_hosted_zones
        mock_client.change_resource_record_sets.return_value = {
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        
        manager = Route53Manager()
        result = manager._create_a_record('new.jakekausler.com', '1.2.3.4')
        
        assert result is True
        mock_client.change_resource_record_sets.assert_called_once()

    def test_create_a_record_failure(self, mock_boto3_session, sample_hosted_zones):
        """Test A record creation failure"""
        mock_session, mock_client = mock_boto3_session
        mock_client.list_hosted_zones.return_value = sample_hosted_zones
        mock_client.change_resource_record_sets.side_effect = ClientError(
            {'Error': {'Code': 'InvalidInput', 'Message': 'Test error'}}, 
            'ChangeResourceRecordSets'
        )
        
        manager = Route53Manager()
        result = manager._create_a_record('new.jakekausler.com', '1.2.3.4')
        
        assert result is False

    def test_delete_a_record_success(self, mock_boto3_session, sample_hosted_zones):
        """Test successful A record deletion"""
        mock_session, mock_client = mock_boto3_session
        mock_client.list_hosted_zones.return_value = sample_hosted_zones
        mock_client.change_resource_record_sets.return_value = {
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        
        manager = Route53Manager()
        result = manager._delete_a_record('old.jakekausler.com', '1.2.3.4')
        
        assert result is True
        mock_client.change_resource_record_sets.assert_called_once()

    def test_delete_a_record_failure(self, mock_boto3_session, sample_hosted_zones):
        """Test A record deletion failure"""
        mock_session, mock_client = mock_boto3_session
        mock_client.list_hosted_zones.return_value = sample_hosted_zones
        mock_client.change_resource_record_sets.side_effect = ClientError(
            {'Error': {'Code': 'InvalidInput', 'Message': 'Test error'}}, 
            'ChangeResourceRecordSets'
        )
        
        manager = Route53Manager()
        result = manager._delete_a_record('old.jakekausler.com', '1.2.3.4')
        
        assert result is False

    def test_sync_preserves_essential_records(self, mock_boto3_session, sample_hosted_zones):
        """Test that essential records are preserved during sync"""
        mock_session, mock_client = mock_boto3_session
        mock_client.list_hosted_zones.return_value = sample_hosted_zones
        
        # Mock records with main domain only
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{
            'ResourceRecordSets': [
                {
                    'Name': 'jakekausler.com.',
                    'Type': 'A',
                    'TTL': 300,
                    'ResourceRecords': [{'Value': '1.2.3.4'}]
                }
            ]
        }]
        mock_client.get_paginator.return_value = mock_paginator
        
        manager = Route53Manager()
        enabled_domains = []  # No enabled domains
        
        created, deleted = manager.sync_dns_records(enabled_domains)
        
        # Main domain should not be deleted
        assert created == 0
        assert deleted == 0

    def test_sync_ignores_non_jakekausler_domains(self, mock_boto3_session, sample_hosted_zones, sample_record_sets):
        """Test that non-jakekausler.com domains are ignored"""
        mock_session, mock_client = mock_boto3_session
        mock_client.list_hosted_zones.return_value = sample_hosted_zones
        
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = sample_record_sets
        mock_client.get_paginator.return_value = mock_paginator
        
        # Mock successful record deletion
        mock_client.change_resource_record_sets.return_value = {
            'ResponseMetadata': {'HTTPStatusCode': 200}
        }
        
        manager = Route53Manager()
        enabled_domains = ['jakekausler.com', 'external.com', 'test.example.com']
        
        created, deleted = manager.sync_dns_records(enabled_domains)
        
        # Only jakekausler.com subdomains should be processed
        assert created == 0  # external.com and test.example.com ignored
        assert deleted == 1   # test.jakekausler.com deleted

    def test_list_dns_records(self, mock_boto3_session, sample_hosted_zones, sample_record_sets):
        """Test listing DNS records"""
        mock_session, mock_client = mock_boto3_session
        mock_client.list_hosted_zones.return_value = sample_hosted_zones
        
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = sample_record_sets
        mock_client.get_paginator.return_value = mock_paginator
        
        manager = Route53Manager()
        records = manager.list_dns_records()
        
        expected_records = {
            'jakekausler.com': '1.2.3.4',
            'test.jakekausler.com': '1.2.3.4'
        }
        assert records == expected_records