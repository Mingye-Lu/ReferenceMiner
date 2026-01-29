"""Route modules for the ReferenceMiner API."""

from refminer.server.routes.projects import router as projects_router
from refminer.server.routes.settings import router as settings_router
from refminer.server.routes.chats import router as chats_router
from refminer.server.routes.files import router as files_router
from refminer.server.routes.ask import router as ask_router
from refminer.server.routes.bank import router as bank_router
from refminer.server.routes.queue import router as queue_router

__all__ = [
    "projects_router",
    "settings_router",
    "chats_router",
    "files_router",
    "ask_router",
    "bank_router",
    "queue_router",
]
