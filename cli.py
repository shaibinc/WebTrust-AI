#!/usr/bin/env python3
"""
Command Line Interface for AI-Powered Web Quality Auditor
"""

import asyncio
import sys
import json
from pathlib import Path
from typing import Optional

import click
import validators
from tabulate import tabulate
from colorama import init, Fore, Style

from web_quality_auditor import WebQualityAuditor, AuditConfig, ReportGenerator

# Initialize colorama for cross-platform colored output
init(autoreset=True)


def print_banner():
    """Print application banner"""
    banner = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           🔍 AI-Powered Web Quality Auditor v1.0            ║
║                                                              ║
║              Comprehensive Website Analysis Tool            ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
    """
    click.echo(banner)


def print_score_bar(score: float, label: str, width: int = 40) -> None:
    """Print a colored score bar"""
    filled = int(score / 100 * width)
    bar = '█' * filled + '░' * (width - filled)
    
    if score >= 80:
        color = Fore.GREEN
    elif score >= 60:
        color = Fore.YELLOW
    else:
        color = Fore.RED
    
    click.echo(f"{label:15} {color}{bar}{Style.RESET_ALL} {score:5.1f}/100")


def print_issues_summary(issues: list) -> None:
    """Print issues summary"""
    if not issues:
        click.echo(f"\n{Fore.GREEN}✅ No issues found! Your website looks great!{Style.RESET_ALL}")
        return
    
    # Count issues by severity
    high = len([i for i in issues if i.get('severity') == 'high'])
    medium = len([i for i in issues if i.get('severity') == 'medium'])
    low = len([i for i in issues if i.get('severity') == 'low'])
    
    click.echo(f"\n📊 Issues Summary:")
    if high > 0:
        click.echo(f"   {Fore.RED}🔴 High Priority: {high}{Style.RESET_ALL}")
    if medium > 0:
        click.echo(f"   {Fore.YELLOW}🟡 Medium Priority: {medium}{Style.RESET_ALL}")
    if low > 0:
        click.echo(f"   {Fore.GREEN}🟢 Low Priority: {low}{Style.RESET_ALL}")


def print_detailed_issues(issues: list, show_all: bool = False) -> None:
    """Print detailed issues"""
    if not issues:
        return
    
    click.echo(f"\n🐛 Detailed Issues:")
    click.echo("─" * 80)
    
    # Group by severity
    high_issues = [i for i in issues if i.get('severity') == 'high']
    medium_issues = [i for i in issues if i.get('severity') == 'medium']
    low_issues = [i for i in issues if i.get('severity') == 'low']
    
    def print_issue_group(issue_list, title, color, emoji):
        if not issue_list:
            return
        
        click.echo(f"\n{color}{emoji} {title} ({len(issue_list)}){Style.RESET_ALL}")
        
        for i, issue in enumerate(issue_list, 1):
            if not show_all and i > 5:  # Limit to 5 issues per category
                click.echo(f"   ... and {len(issue_list) - 5} more (use --verbose to see all)")
                break
            
            click.echo(f"\n   {i}. {issue['type'].title()}: {issue['message']}")
            click.echo(f"      💡 {issue['recommendation']}")
    
    print_issue_group(high_issues, "High Priority Issues", Fore.RED, "🔴")
    print_issue_group(medium_issues, "Medium Priority Issues", Fore.YELLOW, "🟡")
    print_issue_group(low_issues, "Low Priority Issues", Fore.GREEN, "🟢")


def print_metrics_table(metrics: dict) -> None:
    """Print metrics in a table format"""
    if not metrics:
        return
    
    click.echo(f"\n📈 Performance Metrics:")
    click.echo("─" * 50)
    
    # Prepare table data
    table_data = []
    for key, value in metrics.items():
        display_key = key.replace('_', ' ').title()
        
        # Format value based on type
        if isinstance(value, float):
            display_value = f"{value:.2f}"
        elif isinstance(value, int):
            display_value = f"{value:,}"
        else:
            display_value = str(value)
        
        table_data.append([display_key, display_value])
    
    # Print table
    table = tabulate(table_data, headers=["Metric", "Value"], tablefmt="grid")
    click.echo(table)


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """AI-Powered Web Quality Auditor - Comprehensive website analysis tool"""
    pass


@cli.command()
@click.argument('url')
@click.option('--output', '-o', type=click.Choice(['json', 'markdown', 'html', 'console']), 
              default='console', help='Output format')
@click.option('--file', '-f', type=click.Path(), help='Output file path')
@click.option('--timeout', '-t', default=30, help='Request timeout in seconds')
@click.option('--user-agent', '-u', default='WebQualityAuditor-CLI/1.0', help='User agent string')
@click.option('--no-performance', is_flag=True, help='Skip performance checks')
@click.option('--no-seo', is_flag=True, help='Skip SEO checks')
@click.option('--no-accessibility', is_flag=True, help='Skip accessibility checks')
@click.option('--no-security', is_flag=True, help='Skip security checks')
@click.option('--no-mobile', is_flag=True, help='Skip mobile responsiveness checks')
@click.option('--no-fraud', is_flag=True, help='Skip fraud detection checks')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed output')
@click.option('--quiet', '-q', is_flag=True, help='Minimal output')
def audit(url: str, output: str, file: Optional[str], timeout: int, user_agent: str,
               no_performance: bool, no_seo: bool, no_accessibility: bool, 
               no_security: bool, no_mobile: bool, no_fraud: bool, verbose: bool, quiet: bool):
    """Audit a website for quality issues"""
    asyncio.run(_audit_async(url, output, file, timeout, user_agent,
                            no_performance, no_seo, no_accessibility,
                            no_security, no_mobile, no_fraud, verbose, quiet))


async def _audit_async(url: str, output: str, file: Optional[str], timeout: int, user_agent: str,
                      no_performance: bool, no_seo: bool, no_accessibility: bool, 
                      no_security: bool, no_mobile: bool, no_fraud: bool, verbose: bool, quiet: bool):
    """Audit a website for quality issues"""
    
    if not quiet:
        print_banner()
    
    # Validate URL
    if not validators.url(url):
        click.echo(f"{Fore.RED}❌ Invalid URL: {url}{Style.RESET_ALL}", err=True)
        sys.exit(1)
    
    # Create configuration
    config = AuditConfig(
        url=url,
        timeout=timeout,
        user_agent=user_agent,
        check_performance=not no_performance,
        check_seo=not no_seo,
        check_accessibility=not no_accessibility,
        check_security=not no_security,
        check_mobile=not no_mobile,
        check_fraud=not no_fraud,
        output_format=output
    )
    
    if not quiet:
        click.echo(f"🔍 Auditing: {Fore.CYAN}{url}{Style.RESET_ALL}")
        click.echo(f"⏱️  Timeout: {timeout}s")
        
        # Show enabled checks
        checks = []
        if config.check_performance:
            checks.append("🚀 Performance")
        if config.check_seo:
            checks.append("🔍 SEO")
        if config.check_accessibility:
            checks.append("♿ Accessibility")
        if config.check_security:
            checks.append("🔒 Security")
        if config.check_mobile:
            checks.append("📱 Mobile")
        if config.check_fraud:
            checks.append("🛡️ Fraud Detection")
        
        click.echo(f"📋 Checks: {', '.join(checks)}")
        click.echo("\n" + "─" * 80)
    
    # Run audit
    try:
        with click.progressbar(length=100, label='Running audit') as bar:
            async with WebQualityAuditor(config) as auditor:
                bar.update(20)
                result = await auditor.audit_website()
                bar.update(80)
        
        if not quiet:
            click.echo(f"\n{Fore.GREEN}✅ Audit completed successfully!{Style.RESET_ALL}")
    
    except Exception as e:
        click.echo(f"\n{Fore.RED}❌ Audit failed: {str(e)}{Style.RESET_ALL}", err=True)
        sys.exit(1)
    
    # Generate and output report
    if output == 'console':
        # Console output
        if not quiet:
            click.echo(f"\n📊 Overall Score: {Fore.CYAN}{result.overall_score:.1f}/100{Style.RESET_ALL}")
            click.echo("\n📈 Category Scores:")
            
            if result.performance_score > 0:
                print_score_bar(result.performance_score, "🚀 Performance")
            if result.seo_score > 0:
                print_score_bar(result.seo_score, "🔍 SEO")
            if result.accessibility_score > 0:
                print_score_bar(result.accessibility_score, "♿ Accessibility")
            if result.security_score > 0:
                print_score_bar(result.security_score, "🔒 Security")
            if result.fraud_score > 0:
                print_score_bar(result.fraud_score, "🛡️ Fraud Detection")
            
            print_issues_summary(result.issues)
            
            if verbose:
                print_detailed_issues(result.issues, show_all=True)
                print_metrics_table(result.metrics)
            else:
                print_detailed_issues(result.issues, show_all=False)
            
            # Recommendations
            if result.recommendations:
                click.echo(f"\n💡 Top Recommendations:")
                for rec in result.recommendations[:5]:
                    click.echo(f"   • {rec}")
        else:
            # Quiet mode - just the score
            click.echo(f"{result.overall_score:.1f}")
    
    else:
        # Generate report in specified format
        if output == 'json':
            report = ReportGenerator.generate_json_report(result)
        elif output == 'markdown':
            report = ReportGenerator.generate_markdown_report(result)
        elif output == 'html':
            report = ReportGenerator.generate_html_report(result)
        
        # Output to file or stdout
        if file:
            Path(file).write_text(report, encoding='utf-8')
            if not quiet:
                click.echo(f"\n📄 Report saved to: {Fore.GREEN}{file}{Style.RESET_ALL}")
        else:
            click.echo(report)


@cli.command()
@click.argument('urls', nargs=-1, required=True)
@click.option('--output-dir', '-d', type=click.Path(exists=True), default='.', 
              help='Output directory for reports')
@click.option('--format', '-f', type=click.Choice(['json', 'markdown', 'html']), 
              default='json', help='Report format')
@click.option('--concurrent', '-c', default=3, help='Number of concurrent audits')
@click.option('--timeout', '-t', default=30, help='Request timeout in seconds')
def batch(urls: tuple, output_dir: str, format: str, concurrent: int, timeout: int):
    """Audit multiple websites in batch"""
    asyncio.run(_batch_async(urls, output_dir, format, concurrent, timeout))


async def _batch_async(urls: tuple, output_dir: str, format: str, concurrent: int, timeout: int):
    """Audit multiple websites in batch"""
    print_banner()
    
    click.echo(f"🔄 Batch auditing {len(urls)} websites")
    click.echo(f"📁 Output directory: {output_dir}")
    click.echo(f"📄 Format: {format}")
    click.echo(f"⚡ Concurrent jobs: {concurrent}")
    click.echo("\n" + "─" * 80)
    
    # Validate URLs
    valid_urls = []
    for url in urls:
        if validators.url(url):
            valid_urls.append(url)
        else:
            click.echo(f"{Fore.YELLOW}⚠️  Skipping invalid URL: {url}{Style.RESET_ALL}")
    
    if not valid_urls:
        click.echo(f"{Fore.RED}❌ No valid URLs to audit{Style.RESET_ALL}")
        sys.exit(1)
    
    # Semaphore to limit concurrent audits
    semaphore = asyncio.Semaphore(concurrent)
    
    async def audit_single(url: str) -> tuple:
        """Audit a single URL"""
        async with semaphore:
            try:
                config = AuditConfig(
                    url=url, 
                    timeout=timeout,
                    check_fraud=True  # Enable fraud detection by default in batch mode
                )
                async with WebQualityAuditor(config) as auditor:
                    result = await auditor.audit_website()
                return url, result, None
            except Exception as e:
                return url, None, str(e)
    
    # Run audits
    with click.progressbar(valid_urls, label='Auditing websites') as urls_progress:
        tasks = [audit_single(url) for url in valid_urls]
        results = await asyncio.gather(*tasks)
        
        # Process results
        successful = 0
        failed = 0
        
        for url, result, error in results:
            urls_progress.update(1)
            
            if error:
                click.echo(f"\n{Fore.RED}❌ Failed: {url} - {error}{Style.RESET_ALL}")
                failed += 1
                continue
            
            # Generate report
            if format == 'json':
                report = ReportGenerator.generate_json_report(result)
                ext = 'json'
            elif format == 'markdown':
                report = ReportGenerator.generate_markdown_report(result)
                ext = 'md'
            elif format == 'html':
                report = ReportGenerator.generate_html_report(result)
                ext = 'html'
            
            # Save report
            filename = f"audit_{url.replace('://', '_').replace('/', '_')}.{ext}"
            filepath = Path(output_dir) / filename
            filepath.write_text(report, encoding='utf-8')
            
            click.echo(f"\n{Fore.GREEN}✅ {url} - Score: {result.overall_score:.1f}/100{Style.RESET_ALL}")
            successful += 1
    
    # Summary
    click.echo(f"\n📊 Batch Audit Summary:")
    click.echo(f"   {Fore.GREEN}✅ Successful: {successful}{Style.RESET_ALL}")
    click.echo(f"   {Fore.RED}❌ Failed: {failed}{Style.RESET_ALL}")
    click.echo(f"   📁 Reports saved to: {output_dir}")


@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', default=8000, help='Port to bind to')
@click.option('--reload', is_flag=True, help='Enable auto-reload')
def serve(host: str, port: int, reload: bool):
    """Start the API server"""
    print_banner()
    
    click.echo(f"🚀 Starting API server...")
    click.echo(f"🌐 Host: {host}")
    click.echo(f"🔌 Port: {port}")
    click.echo(f"🔄 Reload: {reload}")
    click.echo(f"\n📖 API Documentation: http://{host}:{port}/docs")
    click.echo("\n" + "─" * 80)
    
    import uvicorn
    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


@cli.command()
def streamlit():
    """Start the Streamlit web interface"""
    print_banner()
    
    click.echo(f"🎨 Starting Streamlit web interface...")
    click.echo(f"🌐 URL: http://localhost:8501")
    click.echo("\n" + "─" * 80)
    
    import subprocess
    subprocess.run(["streamlit", "run", "streamlit_app.py"])


if __name__ == '__main__':
    # Handle async commands
    import inspect
    
    def async_command(f):
        """Decorator to handle async click commands"""
        def wrapper(*args, **kwargs):
            return asyncio.run(f(*args, **kwargs))
        return wrapper
    
    # Apply async wrapper to async commands
    for name, obj in list(globals().items()):
        if hasattr(obj, '__call__') and inspect.iscoroutinefunction(obj):
            if hasattr(obj, 'callback') and obj.callback:
                obj.callback = async_command(obj.callback)
    
    cli()