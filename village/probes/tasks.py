"""Task store availability detection."""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TaskStoreStatus:
    available: bool
    error: Optional[str] = None


def task_store_available() -> TaskStoreStatus:
    from village.tasks import get_task_store

    try:
        store = get_task_store()
        available = store.is_available()
        return TaskStoreStatus(available=available)
    except Exception as e:
        logger.debug(f"Task store check failed: {e}")
        return TaskStoreStatus(available=False, error=str(e))
