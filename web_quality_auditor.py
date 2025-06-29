#!/usr/bin/env python3
"""
AI-Powered Web Quality Auditor Agent

A comprehensive web quality auditing tool that analyzes websites for:
- Performance metrics
- SEO optimization
- Accessibility compliance
- Security vulnerabilities
- Code quality
- User experience factors
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import aiohttp
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
import validators
import psutil
from pydantic import BaseModel, HttpUrl
from tabulate import tabulate
import colorlog


class AuditConfig(BaseModel):
    """Configuration for web audit"""
    url: HttpUrl
    timeout: int = 30
    user_agent: str = "WebQualityAuditor/1.0"
    check_performance: bool = True
    check_seo: bool = True
    check_accessibility: bool = True
    check_security: bool = True
    check_mobile: bool = True
    check_fraud: bool = True
    max_pages: int = 10
    output_format: str = "json"  # json, html, markdown
    # Fraud detection specific settings
    fraud_scam_keywords: List[str] = [
        "FREE", "URGENT", "WINNER", "GIVEAWAY", "ACT NOW", "LIMITED TIME",
        "CONGRATULATIONS", "CLAIM NOW", "INSTANT", "GUARANTEED", "RISK FREE",
        "AMAZING DEAL", "ONCE IN A LIFETIME", "EXCLUSIVE OFFER", "CLICK HERE"
    ]
    fraud_allowed_brands: List[str] = []  # Brands that are legitimately referenced
    fraud_max_redirects: int = 3
    fraud_scam_keyword_threshold: float = 0.05  # 5% of total words


class AuditResult(BaseModel):
    """Result of web audit"""
    url: str
    timestamp: datetime
    performance_score: float
    seo_score: float
    accessibility_score: float
    security_score: float
    fraud_score: float
    overall_score: float
    issues: List[Dict]
    recommendations: List[str]
    metrics: Dict


class WebQualityAuditor:
    """Main auditor class"""
    
    def __init__(self, config: AuditConfig):
        self.config = config
        self.logger = self._setup_logger()
        self.session = None
        self.driver = None
        
    def _setup_logger(self) -> logging.Logger:
        """Setup colored logging"""
        handler = colorlog.StreamHandler()
        handler.setFormatter(colorlog.ColoredFormatter(
            '%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(message)s',
            datefmt=None,
            reset=True,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        ))
        
        logger = colorlog.getLogger('WebQualityAuditor')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            headers={'User-Agent': self.config.user_agent}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
        if self.driver:
            self.driver.quit()
    
    def _setup_selenium(self) -> webdriver.Chrome:
        """Setup Selenium WebDriver"""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument(f'--user-agent={self.config.user_agent}')
        
        try:
            driver = webdriver.Chrome(
                service=webdriver.chrome.service.Service(ChromeDriverManager().install()),
                options=options
            )
            return driver
        except Exception as e:
            self.logger.error(f"Failed to setup Selenium: {e}")
            return None
    
    async def audit_website(self) -> AuditResult:
        """Main audit function"""
        self.logger.info(f"Starting audit for: {self.config.url}")
        
        # Initialize results
        issues = []
        recommendations = []
        metrics = {}
        
        # Fetch page content
        try:
            async with self.session.get(str(self.config.url)) as response:
                content = await response.text()
                status_code = response.status
                headers = dict(response.headers)
                
        except Exception as e:
            self.logger.error(f"Failed to fetch URL: {e}")
            return self._create_error_result(str(e))
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # Performance Analysis
        performance_score = 0
        if self.config.check_performance:
            performance_score, perf_issues, perf_metrics = await self._analyze_performance(
                soup, headers, content
            )
            issues.extend(perf_issues)
            metrics.update(perf_metrics)
        
        # SEO Analysis
        seo_score = 0
        if self.config.check_seo:
            seo_score, seo_issues, seo_metrics = self._analyze_seo(soup)
            issues.extend(seo_issues)
            metrics.update(seo_metrics)
        
        # Accessibility Analysis
        accessibility_score = 0
        if self.config.check_accessibility:
            accessibility_score, acc_issues = self._analyze_accessibility(soup)
            issues.extend(acc_issues)
        
        # Security Analysis
        security_score = 0
        if self.config.check_security:
            security_score, sec_issues = self._analyze_security(headers, soup)
            issues.extend(sec_issues)
        
        # Fraud Detection Analysis
        fraud_score = 0
        if self.config.check_fraud:
            fraud_score, fraud_issues, fraud_metrics = await self._analyze_fraud_detection(
                soup, headers, content, response
            )
            issues.extend(fraud_issues)
            metrics.update(fraud_metrics)
        
        # Mobile Responsiveness
        if self.config.check_mobile:
            mobile_issues = await self._analyze_mobile_responsiveness()
            issues.extend(mobile_issues)
        
        # Calculate overall score
        scores = [performance_score, seo_score, accessibility_score, security_score, fraud_score]
        overall_score = sum(scores) / len([s for s in scores if s > 0])
        
        # Generate recommendations
        recommendations = self._generate_recommendations(issues)
        
        return AuditResult(
            url=str(self.config.url),
            timestamp=datetime.now(),
            performance_score=performance_score,
            seo_score=seo_score,
            accessibility_score=accessibility_score,
            security_score=security_score,
            fraud_score=fraud_score,
            overall_score=overall_score,
            issues=issues,
            recommendations=recommendations,
            metrics=metrics
        )
    
    async def _analyze_performance(self, soup: BeautifulSoup, headers: Dict, content: str) -> Tuple[float, List[Dict], Dict]:
        """Analyze website performance"""
        issues = []
        metrics = {}
        score = 100
        
        # Page size analysis
        page_size = len(content.encode('utf-8'))
        metrics['page_size_bytes'] = page_size
        metrics['page_size_kb'] = round(page_size / 1024, 2)
        
        if page_size > 1024 * 1024:  # 1MB
            issues.append({
                'type': 'performance',
                'severity': 'high',
                'message': f'Large page size: {metrics["page_size_kb"]}KB',
                'recommendation': 'Optimize images and minify CSS/JS'
            })
            score -= 20
        
        # Image optimization
        images = soup.find_all('img')
        metrics['total_images'] = len(images)
        
        images_without_alt = [img for img in images if not img.get('alt')]
        if images_without_alt:
            issues.append({
                'type': 'performance',
                'severity': 'medium',
                'message': f'{len(images_without_alt)} images without alt text',
                'recommendation': 'Add alt text to all images'
            })
            score -= 10
        
        # CSS and JS resources
        css_links = soup.find_all('link', rel='stylesheet')
        js_scripts = soup.find_all('script', src=True)
        
        metrics['css_files'] = len(css_links)
        metrics['js_files'] = len(js_scripts)
        
        if len(css_links) > 5:
            issues.append({
                'type': 'performance',
                'severity': 'medium',
                'message': f'Too many CSS files: {len(css_links)}',
                'recommendation': 'Combine CSS files to reduce HTTP requests'
            })
            score -= 10
        
        if len(js_scripts) > 10:
            issues.append({
                'type': 'performance',
                'severity': 'medium',
                'message': f'Too many JS files: {len(js_scripts)}',
                'recommendation': 'Combine and minify JavaScript files'
            })
            score -= 10
        
        # Compression check
        if 'content-encoding' not in headers:
            issues.append({
                'type': 'performance',
                'severity': 'high',
                'message': 'No compression detected',
                'recommendation': 'Enable gzip/brotli compression'
            })
            score -= 15
        
        # Caching headers
        cache_headers = ['cache-control', 'expires', 'etag', 'last-modified']
        if not any(header in headers for header in cache_headers):
            issues.append({
                'type': 'performance',
                'severity': 'medium',
                'message': 'No caching headers found',
                'recommendation': 'Implement proper caching headers'
            })
            score -= 10
        
        return max(0, score), issues, metrics
    
    def _analyze_seo(self, soup: BeautifulSoup) -> Tuple[float, List[Dict], Dict]:
        """Analyze SEO factors"""
        issues = []
        metrics = {}
        score = 100
        
        # Title tag
        title = soup.find('title')
        if not title:
            issues.append({
                'type': 'seo',
                'severity': 'high',
                'message': 'Missing title tag',
                'recommendation': 'Add a descriptive title tag'
            })
            score -= 20
        else:
            title_text = title.get_text().strip()
            metrics['title_length'] = len(title_text)
            if len(title_text) < 30 or len(title_text) > 60:
                issues.append({
                    'type': 'seo',
                    'severity': 'medium',
                    'message': f'Title length not optimal: {len(title_text)} chars',
                    'recommendation': 'Keep title between 30-60 characters'
                })
                score -= 10
        
        # Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if not meta_desc:
            issues.append({
                'type': 'seo',
                'severity': 'high',
                'message': 'Missing meta description',
                'recommendation': 'Add a meta description tag'
            })
            score -= 15
        else:
            desc_content = meta_desc.get('content', '')
            metrics['meta_description_length'] = len(desc_content)
            if len(desc_content) < 120 or len(desc_content) > 160:
                issues.append({
                    'type': 'seo',
                    'severity': 'medium',
                    'message': f'Meta description length not optimal: {len(desc_content)} chars',
                    'recommendation': 'Keep meta description between 120-160 characters'
                })
                score -= 10
        
        # Heading structure
        h1_tags = soup.find_all('h1')
        metrics['h1_count'] = len(h1_tags)
        
        if len(h1_tags) == 0:
            issues.append({
                'type': 'seo',
                'severity': 'high',
                'message': 'No H1 tag found',
                'recommendation': 'Add an H1 tag for the main heading'
            })
            score -= 15
        elif len(h1_tags) > 1:
            issues.append({
                'type': 'seo',
                'severity': 'medium',
                'message': f'Multiple H1 tags found: {len(h1_tags)}',
                'recommendation': 'Use only one H1 tag per page'
            })
            score -= 10
        
        # Internal links
        internal_links = soup.find_all('a', href=True)
        metrics['internal_links'] = len([link for link in internal_links 
                                       if not link['href'].startswith(('http', 'mailto', 'tel'))])
        
        # Canonical URL
        canonical = soup.find('link', rel='canonical')
        if not canonical:
            issues.append({
                'type': 'seo',
                'severity': 'medium',
                'message': 'Missing canonical URL',
                'recommendation': 'Add canonical URL to prevent duplicate content'
            })
            score -= 10
        
        return max(0, score), issues, metrics
    
    def _analyze_accessibility(self, soup: BeautifulSoup) -> Tuple[float, List[Dict]]:
        """Analyze accessibility compliance"""
        issues = []
        score = 100
        
        # Images without alt text
        images = soup.find_all('img')
        images_without_alt = [img for img in images if not img.get('alt')]
        if images_without_alt:
            issues.append({
                'type': 'accessibility',
                'severity': 'high',
                'message': f'{len(images_without_alt)} images missing alt text',
                'recommendation': 'Add descriptive alt text to all images'
            })
            score -= 20
        
        # Form labels
        inputs = soup.find_all('input', type=['text', 'email', 'password', 'tel'])
        inputs_without_labels = []
        for inp in inputs:
            inp_id = inp.get('id')
            if not inp_id or not soup.find('label', attrs={'for': inp_id}):
                inputs_without_labels.append(inp)
        
        if inputs_without_labels:
            issues.append({
                'type': 'accessibility',
                'severity': 'high',
                'message': f'{len(inputs_without_labels)} form inputs without labels',
                'recommendation': 'Associate labels with form inputs'
            })
            score -= 15
        
        # Color contrast (basic check)
        # This is a simplified check - real implementation would need more sophisticated analysis
        style_tags = soup.find_all('style')
        inline_styles = soup.find_all(attrs={'style': True})
        
        # ARIA attributes
        aria_elements = soup.find_all(attrs={'aria-label': True})
        if len(aria_elements) == 0 and len(inputs) > 0:
            issues.append({
                'type': 'accessibility',
                'severity': 'medium',
                'message': 'No ARIA labels found',
                'recommendation': 'Consider adding ARIA labels for better accessibility'
            })
            score -= 10
        
        # Skip links
        skip_links = soup.find_all('a', href='#main') or soup.find_all('a', href='#content')
        if not skip_links:
            issues.append({
                'type': 'accessibility',
                'severity': 'medium',
                'message': 'No skip links found',
                'recommendation': 'Add skip links for keyboard navigation'
            })
            score -= 10
        
        return max(0, score), issues
    
    def _analyze_security(self, headers: Dict, soup: BeautifulSoup) -> Tuple[float, List[Dict]]:
        """Analyze security headers and practices"""
        issues = []
        score = 100
        
        # Security headers
        security_headers = {
            'strict-transport-security': 'HSTS header missing',
            'x-content-type-options': 'X-Content-Type-Options header missing',
            'x-frame-options': 'X-Frame-Options header missing',
            'x-xss-protection': 'X-XSS-Protection header missing',
            'content-security-policy': 'Content Security Policy header missing'
        }
        
        for header, message in security_headers.items():
            if header not in headers:
                issues.append({
                    'type': 'security',
                    'severity': 'medium',
                    'message': message,
                    'recommendation': f'Add {header} header for better security'
                })
                score -= 10
        
        # HTTPS check
        if not str(self.config.url).startswith('https://'):
            issues.append({
                'type': 'security',
                'severity': 'high',
                'message': 'Site not using HTTPS',
                'recommendation': 'Implement SSL/TLS encryption'
            })
            score -= 25
        
        # Mixed content
        http_resources = []
        for tag in soup.find_all(['img', 'script', 'link']):
            src = tag.get('src') or tag.get('href')
            if src and src.startswith('http://'):
                http_resources.append(src)
        
        if http_resources:
            issues.append({
                'type': 'security',
                'severity': 'high',
                'message': f'{len(http_resources)} HTTP resources on HTTPS page',
                'recommendation': 'Use HTTPS for all resources to prevent mixed content'
            })
            score -= 20
        
        return max(0, score), issues
    
    async def _analyze_mobile_responsiveness(self) -> List[Dict]:
        """Analyze mobile responsiveness using Selenium"""
        issues = []
        
        if not self.driver:
            self.driver = self._setup_selenium()
        
        if not self.driver:
            return issues
        
        try:
            self.driver.get(str(self.config.url))
            
            # Test different viewport sizes
            viewports = [
                (375, 667),  # iPhone
                (768, 1024), # iPad
                (1920, 1080) # Desktop
            ]
            
            for width, height in viewports:
                self.driver.set_window_size(width, height)
                time.sleep(1)
                
                # Check for horizontal scrollbar
                body_width = self.driver.execute_script("return document.body.scrollWidth")
                if body_width > width:
                    issues.append({
                        'type': 'mobile',
                        'severity': 'medium',
                        'message': f'Horizontal scroll at {width}x{height}',
                        'recommendation': 'Ensure content fits viewport width'
                    })
                    break
        
        except Exception as e:
            self.logger.error(f"Mobile analysis failed: {e}")
        
        return issues
    
    def _generate_recommendations(self, issues: List[Dict]) -> List[str]:
        """Generate prioritized recommendations"""
        recommendations = []
        
        # Group by severity
        high_issues = [i for i in issues if i.get('severity') == 'high']
        medium_issues = [i for i in issues if i.get('severity') == 'medium']
        
        if high_issues:
            recommendations.append("🔴 High Priority Issues:")
            for issue in high_issues[:5]:  # Top 5 high priority
                recommendations.append(f"  • {issue['recommendation']}")
        
        if medium_issues:
            recommendations.append("🟡 Medium Priority Issues:")
            for issue in medium_issues[:5]:  # Top 5 medium priority
                recommendations.append(f"  • {issue['recommendation']}")
        
        return recommendations
    
    async def _analyze_fraud_detection(self, soup: BeautifulSoup, headers: Dict, content: str, response) -> Tuple[float, List[Dict], Dict]:
        """Comprehensive fraud detection analysis"""
        issues = []
        metrics = {}
        score = 100
        fraud_points = 0
        
        # 1. Suspicious Redirect Pattern Analysis
        redirect_issues, redirect_points = await self._check_suspicious_redirects(response)
        issues.extend(redirect_issues)
        fraud_points += redirect_points
        
        # 2. Keyword & Content Scam Detection
        scam_issues, scam_points, scam_metrics = self._check_scam_keywords(soup, content)
        issues.extend(scam_issues)
        fraud_points += scam_points
        metrics.update(scam_metrics)
        
        # 3. Brand Spoofing Detection
        brand_issues, brand_points = self._check_brand_spoofing(soup, content)
        issues.extend(brand_issues)
        fraud_points += brand_points
        
        # 4. Outbound Link Analysis
        link_issues, link_points, link_metrics = await self._analyze_outbound_links(soup)
        issues.extend(link_issues)
        fraud_points += link_points
        metrics.update(link_metrics)
        
        # 5. Cloaking Detection
        cloaking_issues, cloaking_points = await self._detect_cloaking()
        issues.extend(cloaking_issues)
        fraud_points += cloaking_points
        
        # 6. Script and iFrame Analysis
        script_issues, script_points = self._analyze_suspicious_scripts(soup)
        issues.extend(script_issues)
        fraud_points += script_points
        
        # Calculate fraud score (inverse of fraud points)
        fraud_score = max(0, 100 - fraud_points)
        metrics['fraud_score'] = fraud_score
        metrics['fraud_risk_level'] = self._get_fraud_risk_level(fraud_score)
        
        return fraud_score, issues, metrics
    
    async def _check_suspicious_redirects(self, response) -> Tuple[List[Dict], int]:
        """Check for suspicious redirect patterns"""
        issues = []
        points = 0
        
        try:
            # Check redirect history
            redirect_count = len(response.history)
            
            if redirect_count > self.config.fraud_max_redirects:
                issues.append({
                    'type': 'fraud',
                    'severity': 'high',
                    'message': f'Excessive redirects detected: {redirect_count} hops',
                    'recommendation': 'Review redirect chain for potential malicious behavior'
                })
                points += 25
            
            # Check for off-domain redirects
            original_domain = urlparse(str(self.config.url)).netloc
            for redirect in response.history:
                redirect_domain = urlparse(str(redirect.url)).netloc
                if redirect_domain != original_domain:
                    issues.append({
                        'type': 'fraud',
                        'severity': 'medium',
                        'message': f'Off-domain redirect detected: {redirect_domain}',
                        'recommendation': 'Verify legitimacy of external redirects'
                    })
                    points += 15
                    break
                    
        except Exception as e:
            self.logger.error(f"Redirect analysis failed: {e}")
        
        return issues, points
    
    def _check_scam_keywords(self, soup: BeautifulSoup, content: str) -> Tuple[List[Dict], int, Dict]:
        """Check for scam-related keywords"""
        issues = []
        points = 0
        metrics = {}
        
        # Extract text content
        text_content = soup.get_text().upper()
        words = text_content.split()
        total_words = len(words)
        
        if total_words == 0:
            return issues, points, metrics
        
        # Count scam keywords
        scam_keyword_count = 0
        found_keywords = []
        
        for keyword in self.config.fraud_scam_keywords:
            count = text_content.count(keyword.upper())
            if count > 0:
                scam_keyword_count += count
                found_keywords.append(f"{keyword}({count})")
        
        scam_density = scam_keyword_count / total_words
        metrics['scam_keyword_count'] = scam_keyword_count
        metrics['scam_keyword_density'] = round(scam_density, 4)
        metrics['total_words'] = total_words
        
        if scam_density > self.config.fraud_scam_keyword_threshold:
            severity = 'high' if scam_density > 0.1 else 'medium'
            issues.append({
                'type': 'fraud',
                'severity': severity,
                'message': f'High scam keyword density: {scam_density:.2%} ({scam_keyword_count}/{total_words})',
                'recommendation': f'Review content for suspicious keywords: {', '.join(found_keywords[:5])}'
            })
            points += 30 if severity == 'high' else 20
        
        return issues, points, metrics
    
    def _check_brand_spoofing(self, soup: BeautifulSoup, content: str) -> Tuple[List[Dict], int]:
        """Check for brand spoofing"""
        issues = []
        points = 0
        
        # Common brands that are often spoofed
        common_brands = [
            'AMAZON', 'APPLE', 'GOOGLE', 'MICROSOFT', 'PAYPAL', 'FACEBOOK',
            'NETFLIX', 'EBAY', 'WALMART', 'TARGET', 'VISA', 'MASTERCARD',
            'AMERICAN EXPRESS', 'BANK OF AMERICA', 'WELLS FARGO', 'CHASE'
        ]
        
        text_content = soup.get_text().upper()
        title = soup.find('title')
        title_text = title.get_text().upper() if title else ''
        
        found_brands = []
        for brand in common_brands:
            if brand not in [b.upper() for b in self.config.fraud_allowed_brands]:
                brand_count = text_content.count(brand) + title_text.count(brand)
                if brand_count >= 3:  # Mentioned 3+ times
                    found_brands.append(f"{brand}({brand_count})")
        
        if found_brands:
            issues.append({
                'type': 'fraud',
                'severity': 'high',
                'message': f'Potential brand spoofing detected: {', '.join(found_brands)}',
                'recommendation': 'Verify authorization to use these brand names'
            })
            points += 35
        
        return issues, points
    
    async def _analyze_outbound_links(self, soup: BeautifulSoup) -> Tuple[List[Dict], int, Dict]:
        """Analyze outbound links for suspicious patterns"""
        issues = []
        points = 0
        metrics = {}
        
        # Extract all links
        links = soup.find_all('a', href=True)
        external_links = []
        suspicious_anchors = []
        
        current_domain = urlparse(str(self.config.url)).netloc
        
        for link in links:
            href = link.get('href', '')
            anchor_text = link.get_text().strip().upper()
            
            # Parse URL
            try:
                parsed = urlparse(href)
                if parsed.netloc and parsed.netloc != current_domain:
                    external_links.append(href)
                    
                    # Check for suspicious anchor text
                    suspicious_phrases = [
                        'CLICK HERE', 'FREE MONEY', 'CLAIM NOW', 'WIN NOW',
                        'URGENT', 'LIMITED TIME', 'ACT NOW'
                    ]
                    
                    for phrase in suspicious_phrases:
                        if phrase in anchor_text:
                            suspicious_anchors.append(anchor_text)
                            break
            except Exception:
                continue
        
        metrics['total_links'] = len(links)
        metrics['external_links'] = len(external_links)
        metrics['suspicious_anchor_count'] = len(suspicious_anchors)
        
        # Flag excessive external links
        if len(external_links) > 20:
            issues.append({
                'type': 'fraud',
                'severity': 'medium',
                'message': f'Excessive external links: {len(external_links)}',
                'recommendation': 'Review external links for legitimacy'
            })
            points += 15
        
        # Flag suspicious anchor text
        if suspicious_anchors:
            issues.append({
                'type': 'fraud',
                'severity': 'medium',
                'message': f'Suspicious link text detected: {len(suspicious_anchors)} instances',
                'recommendation': f'Review links with suspicious text: {', '.join(suspicious_anchors[:3])}'
            })
            points += 20
        
        return issues, points, metrics
    
    async def _detect_cloaking(self) -> Tuple[List[Dict], int]:
        """Detect cloaking by comparing bot vs browser content"""
        issues = []
        points = 0
        
        try:
            # Fetch as bot
            bot_headers = {'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'}
            async with self.session.get(str(self.config.url), headers=bot_headers) as bot_response:
                bot_content = await bot_response.text()
            
            # Fetch as browser (already done in main audit)
            browser_headers = {'User-Agent': self.config.user_agent}
            async with self.session.get(str(self.config.url), headers=browser_headers) as browser_response:
                browser_content = await browser_response.text()
            
            # Simple similarity check
            bot_length = len(bot_content)
            browser_length = len(browser_content)
            
            if bot_length > 0 and browser_length > 0:
                size_diff = abs(bot_length - browser_length) / max(bot_length, browser_length)
                
                if size_diff > 0.4:  # 40% difference
                    issues.append({
                        'type': 'fraud',
                        'severity': 'high',
                        'message': f'Potential cloaking detected: {size_diff:.1%} content difference',
                        'recommendation': 'Ensure same content is served to all user agents'
                    })
                    points += 40
                    
        except Exception as e:
            self.logger.error(f"Cloaking detection failed: {e}")
        
        return issues, points
    
    def _analyze_suspicious_scripts(self, soup: BeautifulSoup) -> Tuple[List[Dict], int]:
        """Analyze scripts and iframes for suspicious patterns"""
        issues = []
        points = 0
        
        # Check for suspicious scripts
        scripts = soup.find_all('script')
        for script in scripts:
            script_content = script.get_text() if script.string else ''
            src = script.get('src', '')
            
            # Check for auto-redirect scripts
            if any(pattern in script_content.lower() for pattern in [
                'window.location', 'document.location', 'location.href',
                'location.replace', 'location.assign'
            ]):
                issues.append({
                    'type': 'fraud',
                    'severity': 'medium',
                    'message': 'Auto-redirect JavaScript detected',
                    'recommendation': 'Review JavaScript for malicious redirects'
                })
                points += 15
                break
        
        # Check for suspicious iframes
        iframes = soup.find_all('iframe')
        hidden_iframes = []
        
        for iframe in iframes:
            style = iframe.get('style', '').lower()
            width = iframe.get('width', '')
            height = iframe.get('height', '')
            
            # Check for hidden iframes
            if ('display:none' in style or 'visibility:hidden' in style or
                width in ['0', '1'] or height in ['0', '1']):
                hidden_iframes.append(iframe.get('src', 'unknown'))
        
        if hidden_iframes:
            issues.append({
                'type': 'fraud',
                'severity': 'high',
                'message': f'Hidden iframes detected: {len(hidden_iframes)}',
                'recommendation': 'Review hidden iframes for malicious content'
            })
            points += 25
        
        return issues, points
    
    def _get_fraud_risk_level(self, fraud_score: float) -> str:
        """Get fraud risk level based on score"""
        if fraud_score >= 70:
            return 'Low'
        elif fraud_score >= 30:
            return 'Medium'
        else:
            return 'High'
    
    def _create_error_result(self, error_message: str) -> AuditResult:
        """Create error result"""
        return AuditResult(
            url=str(self.config.url),
            timestamp=datetime.now(),
            performance_score=0,
            seo_score=0,
            accessibility_score=0,
            security_score=0,
            fraud_score=0,
            overall_score=0,
            issues=[{
                'type': 'error',
                'severity': 'high',
                'message': error_message,
                'recommendation': 'Fix the error and try again'
            }],
            recommendations=[f"Fix error: {error_message}"],
            metrics={}
        )


class ReportGenerator:
    """Generate audit reports in different formats"""
    
    @staticmethod
    def generate_json_report(result: AuditResult) -> str:
        """Generate JSON report"""
        return result.model_dump_json(indent=2)
    
    @staticmethod
    def generate_markdown_report(result: AuditResult) -> str:
        """Generate Markdown report"""
        report = f"""# Web Quality Audit Report

**URL:** {result.url}  
**Date:** {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

## Overall Score: {result.overall_score:.1f}/100

### Scores by Category
- 🚀 **Performance:** {result.performance_score:.1f}/100
- 🔍 **SEO:** {result.seo_score:.1f}/100
- ♿ **Accessibility:** {result.accessibility_score:.1f}/100
- 🔒 **Security:** {result.security_score:.1f}/100
- 🛡️ **Fraud Detection:** {result.fraud_score:.1f}/100

### Issues Found ({len(result.issues)})
"""
        
        for issue in result.issues:
            severity_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(issue['severity'], '⚪')
            report += f"\n{severity_emoji} **{issue['type'].title()}** - {issue['message']}\n"
            report += f"   *Recommendation: {issue['recommendation']}*\n"
        
        if result.recommendations:
            report += "\n### Recommendations\n\n"
            for rec in result.recommendations:
                report += f"{rec}\n"
        
        if result.metrics:
            report += "\n### Metrics\n\n"
            for key, value in result.metrics.items():
                report += f"- **{key.replace('_', ' ').title()}:** {value}\n"
        
        return report
    
    @staticmethod
    def generate_html_report(result: AuditResult) -> str:
        """Generate HTML report"""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Web Quality Audit Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ background: #f8f9fa; padding: 20px; border-radius: 8px; }}
        .score {{ font-size: 2em; font-weight: bold; color: #28a745; }}
        .category {{ margin: 20px 0; }}
        .issue {{ margin: 10px 0; padding: 10px; border-left: 4px solid #dc3545; background: #f8f9fa; }}
        .issue.medium {{ border-color: #ffc107; }}
        .issue.low {{ border-color: #28a745; }}
        .metrics {{ background: #e9ecef; padding: 15px; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Web Quality Audit Report</h1>
        <p><strong>URL:</strong> {result.url}</p>
        <p><strong>Date:</strong> {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <div class="score">Overall Score: {result.overall_score:.1f}/100</div>
    </div>
    
    <div class="category">
        <h2>Scores by Category</h2>
        <ul>
            <li>🚀 Performance: {result.performance_score:.1f}/100</li>
            <li>🔍 SEO: {result.seo_score:.1f}/100</li>
            <li>♿ Accessibility: {result.accessibility_score:.1f}/100</li>
            <li>🔒 Security: {result.security_score:.1f}/100</li>
            <li>🛡️ Fraud Detection: {result.fraud_score:.1f}/100</li>
        </ul>
    </div>
    
    <div class="category">
        <h2>Issues Found ({len(result.issues)})</h2>"""
        
        for issue in result.issues:
            html += f"""<div class="issue {issue['severity']}">
            <strong>{issue['type'].title()}</strong> - {issue['message']}<br>
            <em>Recommendation: {issue['recommendation']}</em>
        </div>"""
        
        if result.metrics:
            html += "<div class='metrics'><h3>Metrics</h3><ul>"
            for key, value in result.metrics.items():
                html += f"<li><strong>{key.replace('_', ' ').title()}:</strong> {value}</li>"
            html += "</ul></div>"
        
        html += "</div></body></html>"
        return html


async def main():
    """Main function for CLI usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='AI-Powered Web Quality Auditor')
    parser.add_argument('url', help='URL to audit')
    parser.add_argument('--output', '-o', choices=['json', 'markdown', 'html'], 
                       default='markdown', help='Output format')
    parser.add_argument('--file', '-f', help='Output file path')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout')
    
    args = parser.parse_args()
    
    # Validate URL
    if not validators.url(args.url):
        print(f"❌ Invalid URL: {args.url}")
        return
    
    # Create config
    config = AuditConfig(url=args.url, timeout=args.timeout, output_format=args.output)
    
    # Run audit
    async with WebQualityAuditor(config) as auditor:
        print(f"🔍 Auditing {args.url}...")
        result = await auditor.audit_website()
        
        # Generate report
        if args.output == 'json':
            report = ReportGenerator.generate_json_report(result)
        elif args.output == 'html':
            report = ReportGenerator.generate_html_report(result)
        else:
            report = ReportGenerator.generate_markdown_report(result)
        
        # Output report
        if args.file:
            Path(args.file).write_text(report, encoding='utf-8')
            print(f"📄 Report saved to: {args.file}")
        else:
            print("\n" + "="*80)
            print(report)
            print("="*80)
        
        # Summary
        print(f"\n✅ Audit completed!")
        print(f"📊 Overall Score: {result.overall_score:.1f}/100")
        print(f"🐛 Issues Found: {len(result.issues)}")
        
        if result.overall_score >= 80:
            print("🎉 Excellent! Your website has great quality.")
        elif result.overall_score >= 60:
            print("👍 Good! Some improvements recommended.")
        else:
            print("⚠️  Needs improvement. Please address the issues found.")


if __name__ == '__main__':
    asyncio.run(main())