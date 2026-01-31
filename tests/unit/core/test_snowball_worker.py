from unittest.mock import AsyncMock, MagicMock

import pytest

from zotero_cli.core.models import Job
from zotero_cli.core.services.snowball_worker import SnowballDiscoveryWorker


@pytest.fixture
def mock_gateway():
    return MagicMock()

@pytest.fixture
def mock_graph_service():
    return MagicMock()

@pytest.fixture
def mock_job_queue():
    return MagicMock()

@pytest.fixture
def worker(mock_gateway, mock_graph_service, mock_job_queue):
    return SnowballDiscoveryWorker(mock_gateway, mock_graph_service, mock_job_queue)

@pytest.mark.anyio
async def test_discover_backward_success(worker, mock_gateway, mock_graph_service):
    doi = "10.1001/paper1"

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {
            "reference": [
                {"DOI": "10.1002/ref1", "article-title": "Ref 1"},
                {"DOI": "10.1002/ref2", "unstructured": "Unstructured Ref 2"}
            ]
        }
    }
    mock_gateway.get = AsyncMock(return_value=mock_response)

    await worker._discover_backward(doi, generation=1)

    # Verify add_candidate calls
    assert mock_graph_service.add_candidate.call_count == 2
    mock_graph_service.add_candidate.assert_any_call(
        {"doi": "10.1002/ref1", "title": "Ref 1"},
        parent_doi=doi,
        direction="backward",
        generation=1
    )

@pytest.mark.anyio
async def test_discover_forward_success(worker, mock_gateway, mock_graph_service):
    doi = "10.1001/paper1"

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {
                "citingPaper": {
                    "externalIds": {"DOI": "10.1003/cite1"},
                    "title": "Citing Paper 1",
                    "abstract": "Abstract 1"
                },
                "isInfluential": True
            }
        ]
    }
    mock_gateway.get = AsyncMock(return_value=mock_response)

    await worker._discover_forward(doi, generation=1)

    mock_graph_service.add_candidate.assert_called_once_with(
        {
            "doi": "10.1003/cite1",
            "title": "Citing Paper 1",
            "abstract": "Abstract 1",
            "is_influential": True
        },
        parent_doi=doi,
        direction="forward",
        generation=1
    )

@pytest.mark.anyio
async def test_process_jobs(worker, mock_job_queue):
    job = Job(id=1, item_key="10.1001/test", task_type=worker.TASK_BACKWARD, payload={"generation": 1})

    # Mock queue behavior: return one job then None
    mock_job_queue.pop_next_job.side_effect = [job, None, None]

    # Mock the discovery method
    worker._discover_backward = AsyncMock()

    await worker.process_jobs(count=1)

    worker._discover_backward.assert_called_once_with("10.1001/test", 1)
    mock_job_queue.complete_job.assert_called_once_with(1)
