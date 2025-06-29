#!/usr/bin/env python3
"""
Streamlit Web Interface for AI-Powered Web Quality Auditor
"""

import asyncio
import json
import time
from datetime import datetime
from io import BytesIO

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import validators

from web_quality_auditor import WebQualityAuditor, AuditConfig, ReportGenerator


def create_score_gauge(score: float, title: str) -> go.Figure:
    """Create a gauge chart for scores"""
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title},
        delta={'reference': 80},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 50], 'color': "lightgray"},
                {'range': [50, 80], 'color': "gray"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))
    
    fig.update_layout(height=300)
    return fig


def create_issues_chart(issues: list) -> go.Figure:
    """Create a chart showing issues by type and severity"""
    if not issues:
        return None
    
    df = pd.DataFrame(issues)
    
    # Count issues by type and severity
    issue_counts = df.groupby(['type', 'severity']).size().reset_index(name='count')
    
    fig = px.bar(
        issue_counts,
        x='type',
        y='count',
        color='severity',
        title='Issues by Type and Severity',
        color_discrete_map={
            'high': '#dc3545',
            'medium': '#ffc107',
            'low': '#28a745'
        }
    )
    
    fig.update_layout(height=400)
    return fig


def display_metrics(metrics: dict):
    """Display metrics in a nice format"""
    if not metrics:
        return
    
    st.subheader("📊 Detailed Metrics")
    
    # Create columns for metrics
    cols = st.columns(3)
    
    metric_items = list(metrics.items())
    for i, (key, value) in enumerate(metric_items):
        col_idx = i % 3
        with cols[col_idx]:
            # Format the key for display
            display_key = key.replace('_', ' ').title()
            
            # Format the value based on type
            if isinstance(value, float):
                display_value = f"{value:.2f}"
            elif isinstance(value, int):
                display_value = f"{value:,}"
            else:
                display_value = str(value)
            
            st.metric(display_key, display_value)


def display_issues(issues: list):
    """Display issues in an organized way"""
    if not issues:
        st.success("🎉 No issues found!")
        return
    
    st.subheader(f"🐛 Issues Found ({len(issues)})")
    
    # Group issues by severity
    high_issues = [i for i in issues if i.get('severity') == 'high']
    medium_issues = [i for i in issues if i.get('severity') == 'medium']
    low_issues = [i for i in issues if i.get('severity') == 'low']
    
    # Display high priority issues
    if high_issues:
        st.error(f"🔴 High Priority Issues ({len(high_issues)})")
        for issue in high_issues:
            with st.expander(f"{issue['type'].title()}: {issue['message']}"):
                st.write(f"**Recommendation:** {issue['recommendation']}")
    
    # Display medium priority issues
    if medium_issues:
        st.warning(f"🟡 Medium Priority Issues ({len(medium_issues)})")
        for issue in medium_issues:
            with st.expander(f"{issue['type'].title()}: {issue['message']}"):
                st.write(f"**Recommendation:** {issue['recommendation']}")
    
    # Display low priority issues
    if low_issues:
        st.info(f"🟢 Low Priority Issues ({len(low_issues)})")
        for issue in low_issues:
            with st.expander(f"{issue['type'].title()}: {issue['message']}"):
                st.write(f"**Recommendation:** {issue['recommendation']}")


async def run_audit(config: AuditConfig):
    """Run the audit asynchronously"""
    async with WebQualityAuditor(config) as auditor:
        return await auditor.audit_website()


def main():
    """Main Streamlit app"""
    st.set_page_config(
        page_title="AI-Powered Web Quality Auditor",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🔍 AI-Powered Web Quality Auditor")
    st.markdown("""
    Comprehensive website analysis tool that evaluates:
    - 🚀 **Performance** - Page speed, optimization
    - 🔍 **SEO** - Search engine optimization
    - ♿ **Accessibility** - WCAG compliance
    - 🔒 **Security** - Security headers, HTTPS
    - 📱 **Mobile** - Responsive design
    - 🛡️ **Fraud Detection** - Malicious content, scams, phishing
    """)
    
    # Sidebar configuration
    st.sidebar.header("⚙️ Configuration")
    
    # URL input
    url = st.sidebar.text_input(
        "Website URL",
        placeholder="https://example.com",
        help="Enter the full URL including https://"
    )
    
    # Audit options
    st.sidebar.subheader("Audit Options")
    check_performance = st.sidebar.checkbox("🚀 Performance", value=True)
    check_seo = st.sidebar.checkbox("🔍 SEO", value=True)
    check_accessibility = st.sidebar.checkbox("♿ Accessibility", value=True)
    check_security = st.sidebar.checkbox("🔒 Security", value=True)
    check_mobile = st.sidebar.checkbox("📱 Mobile", value=True)
    check_fraud = st.sidebar.checkbox("🛡️ Fraud Detection", value=True)
    
    # Advanced options
    with st.sidebar.expander("Advanced Options"):
        timeout = st.slider("Timeout (seconds)", 10, 60, 30)
        user_agent = st.text_input(
            "User Agent",
            value="WebQualityAuditor/1.0",
            help="Custom user agent string"
        )
    
    # Output format
    output_format = st.sidebar.selectbox(
        "Report Format",
        ["Interactive", "JSON", "Markdown", "HTML"]
    )
    
    # Run audit button
    if st.sidebar.button("🚀 Run Audit", type="primary"):
        if not url:
            st.error("Please enter a URL to audit")
            return
        
        if not validators.url(url):
            st.error("Please enter a valid URL (including https://)")
            return
        
        # Create config
        config = AuditConfig(
            url=url,
            timeout=timeout,
            user_agent=user_agent,
            check_performance=check_performance,
            check_seo=check_seo,
            check_accessibility=check_accessibility,
            check_security=check_security,
            check_mobile=check_mobile,
            check_fraud=check_fraud,
            output_format=output_format.lower()
        )
        
        # Run audit with progress
        with st.spinner(f"🔍 Auditing {url}..."):
            try:
                # Run the async audit
                result = asyncio.run(run_audit(config))
                
                # Store result in session state
                st.session_state.audit_result = result
                st.session_state.audit_config = config
                
            except Exception as e:
                st.error(f"Audit failed: {str(e)}")
                return
    
    # Display results if available
    if hasattr(st.session_state, 'audit_result'):
        result = st.session_state.audit_result
        config = st.session_state.audit_config
        
        st.success(f"✅ Audit completed for {result.url}")
        
        # Overall score
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.metric(
                "Overall Score",
                f"{result.overall_score:.1f}/100",
                delta=f"{result.overall_score - 70:.1f}" if result.overall_score != 0 else None
            )
        
        with col2:
            if result.overall_score >= 80:
                st.success("🎉 Excellent!")
            elif result.overall_score >= 60:
                st.warning("👍 Good")
            else:
                st.error("⚠️ Needs Work")
        
        with col3:
            st.metric("Issues Found", len(result.issues))
        
        # Score gauges
        scores_to_show = []
        if result.performance_score > 0:
            scores_to_show.append(("Performance", result.performance_score))
        if result.seo_score > 0:
            scores_to_show.append(("SEO", result.seo_score))
        if result.accessibility_score > 0:
            scores_to_show.append(("Accessibility", result.accessibility_score))
        if result.security_score > 0:
            scores_to_show.append(("Security", result.security_score))
        if hasattr(result, 'fraud_score') and result.fraud_score > 0:
            scores_to_show.append(("Fraud Detection", result.fraud_score))
        
        if scores_to_show:
            st.subheader("📊 Detailed Scores")
            
            # Create dynamic columns based on number of scores
            gauge_cols = st.columns(len(scores_to_show))
            
            for i, (score_name, score_value) in enumerate(scores_to_show):
                with gauge_cols[i]:
                    fig = create_score_gauge(score_value, score_name)
                    st.plotly_chart(fig, use_container_width=True)
        
        # Issues chart
        if result.issues:
            issues_chart = create_issues_chart(result.issues)
            if issues_chart:
                st.plotly_chart(issues_chart, use_container_width=True)
        
        # Display issues
        display_issues(result.issues)
        
        # Display metrics
        display_metrics(result.metrics)
        
        # Recommendations
        if result.recommendations:
            st.subheader("💡 Recommendations")
            for rec in result.recommendations:
                if rec.startswith('🔴') or rec.startswith('🟡'):
                    st.markdown(f"**{rec}**")
                else:
                    st.markdown(rec)
        
        # Export options
        st.subheader("📄 Export Report")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # JSON export
            json_report = ReportGenerator.generate_json_report(result)
            st.download_button(
                "📄 Download JSON",
                json_report,
                file_name=f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
        
        with col2:
            # Markdown export
            md_report = ReportGenerator.generate_markdown_report(result)
            st.download_button(
                "📝 Download Markdown",
                md_report,
                file_name=f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown"
            )
        
        with col3:
            # HTML export
            html_report = ReportGenerator.generate_html_report(result)
            st.download_button(
                "🌐 Download HTML",
                html_report,
                file_name=f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                mime="text/html"
            )
        
        # Raw data expander
        with st.expander("🔍 View Raw Data"):
            st.json(result.model_dump())
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>AI-Powered Web Quality Auditor v1.0</p>
        <p>Built with ❤️ using Streamlit, BeautifulSoup, and Selenium</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()