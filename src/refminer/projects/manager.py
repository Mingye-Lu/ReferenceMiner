import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from .models import Project


class ProjectManager:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.projects_file = self.base_dir / "projects.json"
        self.projects: Dict[str, Project] = {}
        self._ensure_paths()
        self._load_projects()

    def _ensure_paths(self):
        # Base data folders
        (self.base_dir / "references").mkdir(exist_ok=True)
        (self.base_dir / ".index").mkdir(exist_ok=True)

        if not self.projects_file.exists():
            # Create a default project
            now = datetime.now().timestamp()
            default_project = Project(
                id="default",
                name="Default Project",
                root_path="default",
                created_at=now,
                last_active=now,
                description="Your initial research project.",
            )

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
                        file_count=pdata.get(
                            "file_count", len(pdata.get("selected_files", []) or [])
                        ),
                        note_count=pdata.get("note_count", 0),
                        description=pdata.get("description"),
                        selected_files=pdata.get("selected_files", []) or [],
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

        now = datetime.now().timestamp()
        new_project = Project(
            id=pid,
            name=name,
            root_path=root_path,
            created_at=now,
            last_active=now,
            description=description,
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
            del self.projects[project_id]
            self._save_all()

    def get_selected_files(self, project_id: str) -> list[str]:
        project = self.projects.get(project_id)
        if not project:
            return []
        return list(project.selected_files)

    def set_selected_files(self, project_id: str, rel_paths: list[str]) -> list[str]:
        project = self.projects.get(project_id)
        if not project:
            return []
        unique = list(dict.fromkeys(rel_paths))
        project.selected_files = unique
        project.file_count = len(unique)
        self._save_all()
        return unique

    def add_selected_files(self, project_id: str, rel_paths: list[str]) -> list[str]:
        project = self.projects.get(project_id)
        if not project:
            return []
        current = set(project.selected_files)
        for rel_path in rel_paths:
            current.add(rel_path)
        project.selected_files = sorted(current)
        project.file_count = len(project.selected_files)
        self._save_all()
        return list(project.selected_files)

    def remove_selected_files(self, project_id: str, rel_paths: list[str]) -> list[str]:
        project = self.projects.get(project_id)
        if not project:
            return []
        remove_set = set(rel_paths)
        project.selected_files = [
            p for p in project.selected_files if p not in remove_set
        ]
        project.file_count = len(project.selected_files)
        self._save_all()
        return list(project.selected_files)

    def remove_file_from_all_projects(self, rel_path: str) -> None:
        changed = False
        for project in self.projects.values():
            if rel_path in project.selected_files:
                project.selected_files = [
                    p for p in project.selected_files if p != rel_path
                ]
                project.file_count = len(project.selected_files)
                changed = True
        if changed:
            self._save_all()
