#!/usr/bin/env python3
"""
Test suite for AI-Powered Web Quality Auditor
"""

import asyncio
import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from web_quality_auditor import WebQualityAuditor, AuditConfig, AuditResult, ReportGenerator
from api_server import app
from fastapi.testclient import TestClient


class TestAuditConfig:
    """Test AuditConfig model"""
    
    def test_valid_config(self):
        """Test valid configuration"""
        config = AuditConfig(url="https://example.com")
        assert str(config.url) == "https://example.com"
        assert config.timeout == 30
        assert config.check_performance is True
    
    def test_invalid_url(self):
        """Test invalid URL"""
        with pytest.raises(ValueError):
            AuditConfig(url="not-a-url")


class TestWebQualityAuditor:
    """Test WebQualityAuditor class"""
    
    @pytest.fixture
    def config(self):
        """Test configuration"""
        return AuditConfig(url="https://httpbin.org/html")
    
    @pytest.fixture
    def mock_html(self):
        """Mock HTML content for testing"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="This is a test page for auditing">
            <link rel="stylesheet" href="style.css">
        </head>
        <body>
            <h1>Main Heading</h1>
            <img src="image.jpg" alt="Test image">
            <img src="image2.jpg">
            <a href="/page1">Internal link</a>
            <script src="script.js"></script>
        </body>
        </html>
        """
    
    @pytest.mark.asyncio
    async def test_auditor_initialization(self, config):
        """Test auditor initialization"""
        async with WebQualityAuditor(config) as auditor:
            assert auditor.config == config
            assert auditor.session is not None
    
    @pytest.mark.asyncio
    async def test_seo_analysis(self, config, mock_html):
        """Test SEO analysis"""
        from bs4 import BeautifulSoup
        
        auditor = WebQualityAuditor(config)
        soup = BeautifulSoup(mock_html, 'html.parser')
        
        score, issues, metrics = auditor._analyze_seo(soup)
        
        assert score > 0
        assert 'title_length' in metrics
        assert 'meta_description_length' in metrics
        assert 'h1_count' in metrics
        assert metrics['h1_count'] == 1
    
    @pytest.mark.asyncio
    async def test_accessibility_analysis(self, config, mock_html):
        """Test accessibility analysis"""
        from bs4 import BeautifulSoup
        
        auditor = WebQualityAuditor(config)
        soup = BeautifulSoup(mock_html, 'html.parser')
        
        score, issues = auditor._analyze_accessibility(soup)
        
        assert score > 0
        # Should find one image without alt text
        alt_issues = [i for i in issues if 'alt text' in i['message']]
        assert len(alt_issues) > 0
    
    @pytest.mark.asyncio
    async def test_performance_analysis(self, config, mock_html):
        """Test performance analysis"""
        from bs4 import BeautifulSoup
        
        auditor = WebQualityAuditor(config)
        soup = BeautifulSoup(mock_html, 'html.parser')
        headers = {'content-type': 'text/html'}
        
        score, issues, metrics = await auditor._analyze_performance(soup, headers, mock_html)
        
        assert score > 0
        assert 'page_size_bytes' in metrics
        assert 'total_images' in metrics
        assert 'css_files' in metrics
        assert 'js_files' in metrics
    
    @pytest.mark.asyncio
    async def test_security_analysis(self, config, mock_html):
        """Test security analysis"""
        from bs4 import BeautifulSoup
        
        auditor = WebQualityAuditor(config)
        soup = BeautifulSoup(mock_html, 'html.parser')
        headers = {}
        
        score, issues = auditor._analyze_security(headers, soup)
        
        # Should find missing security headers
        assert len(issues) > 0
        security_issues = [i for i in issues if i['type'] == 'security']
        assert len(security_issues) > 0
    
    def test_recommendations_generation(self, config):
        """Test recommendations generation"""
        auditor = WebQualityAuditor(config)
        
        issues = [
            {'type': 'seo', 'severity': 'high', 'message': 'Missing title', 'recommendation': 'Add title'},
            {'type': 'performance', 'severity': 'medium', 'message': 'Large image', 'recommendation': 'Optimize image'}
        ]
        
        recommendations = auditor._generate_recommendations(issues)
        
        assert len(recommendations) > 0
        assert any('High Priority' in rec for rec in recommendations)


class TestReportGenerator:
    """Test ReportGenerator class"""
    
    @pytest.fixture
    def sample_result(self):
        """Sample audit result for testing"""
        return AuditResult(
            url="https://example.com",
            timestamp=datetime.now(),
            performance_score=85.0,
            seo_score=90.0,
            accessibility_score=75.0,
            security_score=80.0,
            overall_score=82.5,
            issues=[
                {
                    'type': 'performance',
                    'severity': 'medium',
                    'message': 'Large page size',
                    'recommendation': 'Optimize images'
                }
            ],
            recommendations=['Optimize images for better performance'],
            metrics={'page_size_kb': 1024, 'total_images': 5}
        )
    
    def test_json_report(self, sample_result):
        """Test JSON report generation"""
        report = ReportGenerator.generate_json_report(sample_result)
        
        # Should be valid JSON
        data = json.loads(report)
        assert data['url'] == 'https://example.com'
        assert data['overall_score'] == 82.5
    
    def test_markdown_report(self, sample_result):
        """Test Markdown report generation"""
        report = ReportGenerator.generate_markdown_report(sample_result)
        
        assert '# Web Quality Audit Report' in report
        assert 'https://example.com' in report
        assert '82.5/100' in report
        assert 'Performance' in report
    
    def test_html_report(self, sample_result):
        """Test HTML report generation"""
        report = ReportGenerator.generate_html_report(sample_result)
        
        assert '<!DOCTYPE html>' in report
        assert 'Web Quality Audit Report' in report
        assert 'https://example.com' in report
        assert '82.5/100' in report


class TestAPIServer:
    """Test FastAPI server"""
    
    @pytest.fixture
    def client(self):
        """Test client"""
        return TestClient(app)
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        assert "AI-Powered Web Quality Auditor API" in response.text
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert 'timestamp' in data
    
    def test_audit_endpoint(self, client):
        """Test audit endpoint"""
        payload = {
            "url": "https://httpbin.org/html",
            "check_performance": True,
            "check_seo": True
        }
        
        response = client.post("/audit", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert 'job_id' in data
        assert data['status'] == 'pending'
        assert data['url'] == 'https://httpbin.org/html'
    
    def test_invalid_url_audit(self, client):
        """Test audit with invalid URL"""
        payload = {
            "url": "not-a-url"
        }
        
        response = client.post("/audit", json=payload)
        assert response.status_code == 422  # Validation error
    
    def test_jobs_endpoint(self, client):
        """Test jobs listing endpoint"""
        response = client.get("/jobs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_stats_endpoint(self, client):
        """Test stats endpoint"""
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert 'total_jobs' in data
        assert 'completed_jobs' in data
        assert 'success_rate' in data
    
    def test_nonexistent_job(self, client):
        """Test getting nonexistent job"""
        response = client.get("/audit/nonexistent-job-id")
        assert response.status_code == 404


class TestIntegration:
    """Integration tests"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_full_audit_flow(self):
        """Test complete audit flow with real website"""
        config = AuditConfig(
            url="https://httpbin.org/html",
            timeout=30,
            check_mobile=False  # Skip mobile test for speed
        )
        
        async with WebQualityAuditor(config) as auditor:
            result = await auditor.audit_website()
            
            assert result.url == "https://httpbin.org/html"
            assert result.overall_score >= 0
            assert isinstance(result.issues, list)
            assert isinstance(result.recommendations, list)
            assert isinstance(result.metrics, dict)
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling with invalid URL"""
        config = AuditConfig(url="https://nonexistent-domain-12345.com")
        
        async with WebQualityAuditor(config) as auditor:
            result = await auditor.audit_website()
            
            assert result.overall_score == 0
            assert len(result.issues) > 0
            assert result.issues[0]['type'] == 'error'


if __name__ == "__main__":
    # Run tests
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-x"  # Stop on first failure
    ])