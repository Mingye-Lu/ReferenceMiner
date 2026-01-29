"""Project management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from refminer.server.globals import project_manager
from refminer.server.models import ProjectCreate

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
async def get_projects():
    """List all projects."""
    return [p.to_dict() for p in project_manager.get_projects()]


@router.post("")
async def create_project(req: ProjectCreate):
    """Create a new project."""
    project = project_manager.create_project(req.name, req.description)
    return project.to_dict()


@router.get("/{project_id}")
async def get_project(project_id: str):
    """Get a specific project."""
    project = project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.to_dict()


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """Delete a project."""
    project_manager.delete_project(project_id)
    return {"success": True}


@router.post("/{project_id}/activate")
async def activate_project(project_id: str):
    """Mark a project as recently active."""
    project_manager.update_activity(project_id)
    return {"success": True}
