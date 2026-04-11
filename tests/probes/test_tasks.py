"""Test task store availability detection via probes."""

from unittest.mock import MagicMock, patch

import pytest

from village.probes.tasks import TaskStoreStatus, task_store_available
from village.tasks import TaskStoreError


def test_task_store_available_returns_status():
    status = task_store_available()
    assert isinstance(status, TaskStoreStatus)


def test_task_store_available_when_store_unavailable():
    with patch("village.tasks.get_task_store") as mock_store:
        mock_store.side_effect = TaskStoreError("not initialized")

        status = task_store_available()

        assert status.available is False
        assert status.error is not None


def test_task_store_available_when_store_available():
    with patch("village.tasks.get_task_store") as mock_store:
        mock_store_obj = MagicMock()
        mock_store_obj.is_available.return_value = True
        mock_store.return_value = mock_store_obj

        status = task_store_available()

        assert status.available is True


def test_task_store_available_when_store_not_initialized():
    with patch("village.tasks.get_task_store") as mock_store:
        mock_store_obj = MagicMock()
        mock_store_obj.is_available.return_value = False
        mock_store.return_value = mock_store_obj

        status = task_store_available()

        assert status.available is False


@pytest.mark.integration
def test_task_store_available_integration():
    status = task_store_available()
    assert isinstance(status, TaskStoreStatus)
