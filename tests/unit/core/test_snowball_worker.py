from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zotero_cli.core.models import Job
from zotero_cli.core.services.snowball_worker import SnowballDiscoveryWorker


@pytest.fixture(autouse=True)
def no_sleep():
    """The forward-discovery pacing (Issue #223) sleeps between real
    requests - stub it out so the test suite doesn't actually wait."""
    with patch(
        "zotero_cli.core.services.snowball_worker.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        yield mock_sleep


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
                {"DOI": "10.1002/ref2", "unstructured": "Unstructured Ref 2"},
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
        generation=1,
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
                    "abstract": "Abstract 1",
                },
                "isInfluential": True,
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
            "is_influential": True,
        },
        parent_doi=doi,
        direction="forward",
        generation=1,
    )
    # Issue #204: externalIds must be requested, or every citingPaper's DOI
    # lookup comes back empty and every candidate is silently dropped.
    _, kwargs = mock_gateway.get.call_args
    assert "externalIds" in kwargs["params"]["fields"]


@pytest.mark.anyio
async def test_discover_forward_skips_citations_without_doi(
    worker, mock_gateway, mock_graph_service
):
    """Issue #204 regression: a citingPaper missing externalIds.DOI (e.g. the
    field genuinely wasn't returned) must be skipped, not crash or leak in."""
    doi = "10.1001/paper1"

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"citingPaper": {"title": "No DOI Paper"}, "isInfluential": False},
        ]
    }
    mock_gateway.get = AsyncMock(return_value=mock_response)

    await worker._discover_forward(doi, generation=1)

    mock_graph_service.add_candidate.assert_not_called()


@pytest.mark.anyio
async def test_discover_forward_falls_back_to_unauthenticated_on_rejected_key(
    mock_gateway, mock_graph_service, mock_job_queue
):
    """Issue #223: a configured API key that gets rejected (NetworkGateway
    raises ValueError for a 403 that survives identity rotation with an
    auth header present) must not fail the whole job - retry once
    unauthenticated instead, since that's confirmed to work."""
    worker = SnowballDiscoveryWorker(
        mock_gateway, mock_graph_service, mock_job_queue, s2_api_key="bad-key"
    )
    doi = "10.1001/paper1"

    success_response = MagicMock()
    success_response.json.return_value = {
        "data": [
            {
                "citingPaper": {"externalIds": {"DOI": "10.1003/cite1"}, "title": "Citing Paper"},
                "isInfluential": False,
            }
        ]
    }
    mock_gateway.get = AsyncMock(side_effect=[ValueError("403 ... x-api-key ..."), success_response])

    await worker._discover_forward(doi, generation=1)

    assert mock_gateway.get.call_count == 2
    first_call, second_call = mock_gateway.get.call_args_list
    assert first_call.kwargs["headers"] == {"x-api-key": "bad-key"}
    assert second_call.kwargs["headers"] == {}
    mock_graph_service.add_candidate.assert_called_once()


@pytest.mark.anyio
async def test_discover_forward_no_key_reraises_value_error(
    mock_gateway, mock_graph_service, mock_job_queue
):
    """Without a configured key, a ValueError from the gateway is a
    genuine unexpected failure (not a rejected-credential signal) and
    must propagate, not be swallowed into an infinite fallback loop."""
    worker = SnowballDiscoveryWorker(mock_gateway, mock_graph_service, mock_job_queue)
    mock_gateway.get = AsyncMock(side_effect=ValueError("something else"))

    with pytest.raises(ValueError):
        await worker._discover_forward("10.1001/paper1", generation=1)

    assert mock_gateway.get.call_count == 1


@pytest.mark.anyio
async def test_process_jobs(worker, mock_job_queue):
    job = Job(
        id=1, item_key="10.1001/test", task_type=worker.TASK_BACKWARD, payload={"generation": 1}
    )

    # Mock queue behavior: return one job then None
    mock_job_queue.pop_next_job.side_effect = [job, None, None]

    # Mock the discovery method
    worker._discover_backward = AsyncMock()

    await worker.process_jobs(count=1)

    worker._discover_backward.assert_called_once_with("10.1001/test", 1)
    mock_job_queue.complete_job.assert_called_once_with(1)
