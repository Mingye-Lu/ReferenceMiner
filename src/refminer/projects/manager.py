import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from .models import Project

class ProjectManager:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.projects_file = self.base_dir / "projects.json"
        self.projects_dir = self.base_dir / "projects"
        self.projects: Dict[str, Project] = {}
        self._ensure_paths()
        self._load_projects()

    def _ensure_paths(self):
        # Base data folders
        (self.base_dir / "references").mkdir(exist_ok=True)
        (self.base_dir / "index").mkdir(exist_ok=True)

        if not self.projects_file.exists():
            # Create a default project
            now = datetime.now().timestamp()
            default_project = Project(
                id="default",
                name="Default Project",
                root_path="default", # In the new model, root_path is just the folder name inside references/ and index/
                created_at=now,
                last_active=now,
                description="Your initial research project."
            )
            # Ensure folders exist
            (self.base_dir / "references" / "default").mkdir(parents=True, exist_ok=True)
            (self.base_dir / "index" / "default").mkdir(parents=True, exist_ok=True)
            
            self._save_projects_to_disk({"default": default_project.to_dict()})

    def _load_projects(self):
        try:
            with open(self.projects_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for pid, pdata in data.items():
                    self.projects[pid] = Project(
                        id=pdata["id"],
                        name=pdata["name"],
                        root_path=pdata.get("root_path", pid),
                        created_at=pdata["created_at"],
                        last_active=pdata["last_active"],
                        file_count=pdata.get("file_count", 0),
                        note_count=pdata.get("note_count", 0),
                        description=pdata.get("description")
                    )
        except Exception as e:
            print(f"Error loading projects: {e}")

    def _save_projects_to_disk(self, data: dict):
        with open(self.projects_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_projects(self) -> List[Project]:
        return list(self.projects.values())

    def get_project(self, project_id: str) -> Optional[Project]:
        return self.projects.get(project_id)

    def create_project(self, name: str, description: Optional[str] = None) -> Project:
        pid = name.lower().replace(" ", "-")
        # Ensure unique pid
        original_pid = pid
        counter = 1
        while pid in self.projects:
            pid = f"{original_pid}-{counter}"
            counter += 1
        
        root_path = pid
        
        # Create separate folders in references/ and index/
        (self.base_dir / "references" / pid).mkdir(parents=True, exist_ok=True)
        (self.base_dir / "index" / pid).mkdir(parents=True, exist_ok=True)
        
        now = datetime.now().timestamp()
        new_project = Project(
            id=pid,
            name=name,
            root_path=root_path,
            created_at=now,
            last_active=now,
            description=description
        )
        
        self.projects[pid] = new_project
        self._save_all()
        return new_project

    def _save_all(self):
        data = {pid: p.to_dict() for pid, p in self.projects.items()}
        self._save_projects_to_disk(data)

    def update_activity(self, project_id: str):
        if project_id in self.projects:
            self.projects[project_id].last_active = datetime.now().timestamp()
            self._save_all()

    def delete_project(self, project_id: str):
        if project_id in self.projects:
            project = self.projects[project_id]
            pid = project.id # Or project.root_path
            
            ref_path = self.base_dir / "references" / pid
            idx_path = self.base_dir / "index" / pid
            
            if ref_path.exists():
                shutil.rmtree(ref_path)
            if idx_path.exists():
                shutil.rmtree(idx_path)
                
            del self.projects[project_id]
            self._save_all()
