from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Project:
    id: str
    name: str
    root_path: str  # Path relative to base data dir
    created_at: float  # epoch timestamp
    last_active: float  # epoch timestamp
    file_count: int = 0
    note_count: int = 0
    description: Optional[str] = None
    selected_files: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)
