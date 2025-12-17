"""
Web UI routes for serving HTML pages.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.dependencies import get_db
from app.models.job import Job

router = APIRouter(tags=["web"])

# Templates directory
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the home page."""
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/job/{job_id}", response_class=HTMLResponse)
async def job_page(request: Request, job_id: str):
    """
    Render the job status page.

    Args:
        request: FastAPI request
        job_id: Job ID to display
    """
    db = get_db()
    job = await db.get_job(job_id)

    if not job:
        # Return a simple error page or redirect
        raise HTTPException(status_code=404, detail="Job not found")

    return templates.TemplateResponse(
        "job.html",
        {"request": request, "job": job},
    )
