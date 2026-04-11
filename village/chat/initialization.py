"""Task store initialization for chat mode."""

import logging

from village.config import Config
from village.tasks import get_task_store

logger = logging.getLogger(__name__)


def ensure_tasks_initialized(config: Config) -> None:
    store = get_task_store(config=config)
    store.initialize()
    logger.info("Task store ready")


def is_tasks_available(config: Config) -> bool:
    store = get_task_store(config=config)
    return store.is_available()
