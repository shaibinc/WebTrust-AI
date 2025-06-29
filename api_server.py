#!/usr/bin/env python3
"""
FastAPI REST API Server for AI-Powered Web Quality Auditor
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, HttpUrl
import uvicorn

from web_quality_auditor import WebQualityAuditor, AuditConfig, AuditResult, ReportGenerator


# Pydantic models for API
class AuditRequest(BaseModel):
    """Request model for audit"""
    url: HttpUrl
    timeout: int = 30
    user_agent: str = "WebQualityAuditor-API/1.0"
    check_performance: bool = True
    check_seo: bool = True
    check_accessibility: bool = True
    check_security: bool = True
    check_mobile: bool = True
    output_format: str = "json"


class AuditStatus(BaseModel):
    """Status model for audit jobs"""
    job_id: str
    status: str  # pending, running, completed, failed
    created_at: datetime
    completed_at: Optional[datetime] = None
    url: str
    result: Optional[AuditResult] = None
    error: Optional[str] = None


class HealthCheck(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    version: str


# Global storage for audit jobs (in production, use Redis or database)
AUDIT_JOBS: Dict[str, AuditStatus] = {}


# FastAPI app
app = FastAPI(
    title="AI-Powered Web Quality Auditor API",
    description="REST API for comprehensive website quality analysis",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def run_audit_job(job_id: str, config: AuditConfig):
    """Background task to run audit"""
    try:
        # Update status to running
        AUDIT_JOBS[job_id].status = "running"
        
        # Run audit
        async with WebQualityAuditor(config) as auditor:
            result = await auditor.audit_website()
        
        # Update job with result
        AUDIT_JOBS[job_id].status = "completed"
        AUDIT_JOBS[job_id].completed_at = datetime.now()
        AUDIT_JOBS[job_id].result = result
        
    except Exception as e:
        # Update job with error
        AUDIT_JOBS[job_id].status = "failed"
        AUDIT_JOBS[job_id].completed_at = datetime.now()
        AUDIT_JOBS[job_id].error = str(e)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with API documentation"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI-Powered Web Quality Auditor API</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f8f9fa; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .header { text-align: center; margin-bottom: 30px; }
            .endpoint { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #007bff; }
            .method { display: inline-block; padding: 4px 8px; border-radius: 3px; color: white; font-weight: bold; margin-right: 10px; }
            .get { background: #28a745; }
            .post { background: #007bff; }
            code { background: #e9ecef; padding: 2px 4px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔍 AI-Powered Web Quality Auditor API</h1>
                <p>Comprehensive website quality analysis REST API</p>
            </div>
            
            <h2>📚 API Endpoints</h2>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <strong>/health</strong>
                <p>Check API health status</p>
            </div>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <strong>/audit</strong>
                <p>Start a new website audit (async)</p>
                <p><strong>Body:</strong> <code>{"url": "https://example.com", "check_performance": true, ...}</code></p>
            </div>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <strong>/audit/sync</strong>
                <p>Run website audit synchronously</p>
                <p><strong>Body:</strong> <code>{"url": "https://example.com", "check_performance": true, ...}</code></p>
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <strong>/audit/{job_id}</strong>
                <p>Get audit job status and results</p>
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <strong>/audit/{job_id}/report</strong>
                <p>Download audit report in specified format</p>
                <p><strong>Query:</strong> <code>?format=json|markdown|html</code></p>
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <strong>/jobs</strong>
                <p>List all audit jobs</p>
            </div>
            
            <h2>🚀 Quick Start</h2>
            <pre><code># Start an audit
curl -X POST "http://localhost:8000/audit" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com"}'

# Check status
curl "http://localhost:8000/audit/{job_id}"

# Download report
curl "http://localhost:8000/audit/{job_id}/report?format=html" > report.html</code></pre>
            
            <p><a href="/docs">📖 Interactive API Documentation (Swagger)</a></p>
            <p><a href="/redoc">📋 Alternative Documentation (ReDoc)</a></p>
        </div>
    </body>
    </html>
    """


@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint"""
    return HealthCheck(
        status="healthy",
        timestamp=datetime.now(),
        version="1.0.0"
    )


@app.post("/audit", response_model=AuditStatus)
async def start_audit(request: AuditRequest, background_tasks: BackgroundTasks):
    """Start an asynchronous audit job"""
    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Create audit config
    config = AuditConfig(
        url=request.url,
        timeout=request.timeout,
        user_agent=request.user_agent,
        check_performance=request.check_performance,
        check_seo=request.check_seo,
        check_accessibility=request.check_accessibility,
        check_security=request.check_security,
        check_mobile=request.check_mobile,
        output_format=request.output_format
    )
    
    # Create job status
    job_status = AuditStatus(
        job_id=job_id,
        status="pending",
        created_at=datetime.now(),
        url=str(request.url)
    )
    
    # Store job
    AUDIT_JOBS[job_id] = job_status
    
    # Start background task
    background_tasks.add_task(run_audit_job, job_id, config)
    
    return job_status


@app.post("/audit/sync", response_model=AuditResult)
async def audit_sync(request: AuditRequest):
    """Run audit synchronously"""
    # Create audit config
    config = AuditConfig(
        url=request.url,
        timeout=request.timeout,
        user_agent=request.user_agent,
        check_performance=request.check_performance,
        check_seo=request.check_seo,
        check_accessibility=request.check_accessibility,
        check_security=request.check_security,
        check_mobile=request.check_mobile,
        output_format=request.output_format
    )
    
    try:
        # Run audit
        async with WebQualityAuditor(config) as auditor:
            result = await auditor.audit_website()
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit failed: {str(e)}")


@app.get("/audit/{job_id}", response_model=AuditStatus)
async def get_audit_status(job_id: str):
    """Get audit job status"""
    if job_id not in AUDIT_JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return AUDIT_JOBS[job_id]


@app.get("/audit/{job_id}/report")
async def download_report(
    job_id: str,
    format: str = Query("json", regex="^(json|markdown|html)$")
):
    """Download audit report in specified format"""
    if job_id not in AUDIT_JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = AUDIT_JOBS[job_id]
    
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")
    
    if not job.result:
        raise HTTPException(status_code=500, detail="No result available")
    
    # Generate report
    if format == "json":
        content = ReportGenerator.generate_json_report(job.result)
        media_type = "application/json"
        filename = f"audit_{job_id}.json"
    elif format == "markdown":
        content = ReportGenerator.generate_markdown_report(job.result)
        media_type = "text/markdown"
        filename = f"audit_{job_id}.md"
    elif format == "html":
        content = ReportGenerator.generate_html_report(job.result)
        media_type = "text/html"
        filename = f"audit_{job_id}.html"
    else:
        raise HTTPException(status_code=400, detail="Invalid format")
    
    # Save to temporary file and return
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f'.{format}') as f:
        f.write(content)
        temp_path = f.name
    
    return FileResponse(
        temp_path,
        media_type=media_type,
        filename=filename,
        background=BackgroundTasks().add_task(os.unlink, temp_path)
    )


@app.get("/jobs", response_model=List[AuditStatus])
async def list_jobs(
    status: Optional[str] = Query(None, regex="^(pending|running|completed|failed)$"),
    limit: int = Query(50, ge=1, le=100)
):
    """List audit jobs"""
    jobs = list(AUDIT_JOBS.values())
    
    # Filter by status if provided
    if status:
        jobs = [job for job in jobs if job.status == status]
    
    # Sort by creation time (newest first)
    jobs.sort(key=lambda x: x.created_at, reverse=True)
    
    # Limit results
    return jobs[:limit]


@app.delete("/audit/{job_id}")
async def delete_job(job_id: str):
    """Delete an audit job"""
    if job_id not in AUDIT_JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    
    del AUDIT_JOBS[job_id]
    return {"message": "Job deleted successfully"}


@app.get("/stats")
async def get_stats():
    """Get API statistics"""
    total_jobs = len(AUDIT_JOBS)
    completed_jobs = len([j for j in AUDIT_JOBS.values() if j.status == "completed"])
    failed_jobs = len([j for j in AUDIT_JOBS.values() if j.status == "failed"])
    running_jobs = len([j for j in AUDIT_JOBS.values() if j.status == "running"])
    pending_jobs = len([j for j in AUDIT_JOBS.values() if j.status == "pending"])
    
    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "running_jobs": running_jobs,
        "pending_jobs": pending_jobs,
        "success_rate": (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
    }


if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )