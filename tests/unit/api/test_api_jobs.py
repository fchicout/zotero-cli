from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from zotero_cli.api.dependencies import get_job_queue_service
from zotero_cli.api.main import create_app
from zotero_cli.core.models import Job

mock_job_queue = MagicMock()
mock_job_queue.library_id = "lib-A"


def override_get_job_queue_service():
    return mock_job_queue


app = create_app()
app.dependency_overrides[get_job_queue_service] = override_get_job_queue_service
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_mocks():
    mock_job_queue.reset_mock()
    mock_job_queue.library_id = "lib-A"


def test_list_jobs():
    job = Job(
        id=1,
        item_key="K1",
        task_type="fetch_pdf",
        payload={},
        status="PENDING",
        attempts=0,
        library_id="lib-A",
    )
    mock_job_queue.list_jobs.return_value = [job]

    response = client.get("/jobs")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == 1
    assert data[0]["item_key"] == "K1"
    assert data[0]["task_type"] == "fetch_pdf"
    mock_job_queue.list_jobs.assert_called_with(task_type=None, limit=100)


def test_list_jobs_filters_by_task_type():
    mock_job_queue.list_jobs.return_value = []

    response = client.get("/jobs", params={"task_type": "fetch_pdf", "limit": 10})

    assert response.status_code == 200
    mock_job_queue.list_jobs.assert_called_with(task_type="fetch_pdf", limit=10)


def test_get_job_detail():
    job = Job(
        id=1,
        item_key="K1",
        task_type="fetch_pdf",
        payload={},
        status="COMPLETED",
        library_id="lib-A",
    )
    mock_job_queue.repo.get_job.return_value = job

    response = client.get("/jobs/1")

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"


def test_get_job_not_found():
    mock_job_queue.repo.get_job.return_value = None

    response = client.get("/jobs/999")

    assert response.status_code == 404


def test_get_job_from_another_library_is_not_found():
    other_library_job = Job(
        id=2,
        item_key="K2",
        task_type="fetch_pdf",
        payload={},
        status="PENDING",
        library_id="lib-B",
    )
    mock_job_queue.repo.get_job.return_value = other_library_job

    response = client.get("/jobs/2")

    assert response.status_code == 404
