from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from zotero_cli.core.exceptions import RetryableError
from zotero_cli.core.services.identity_manager import IdentityManager
from zotero_cli.core.services.network_gateway import NetworkGateway


@pytest.fixture
def identity_manager():
    return IdentityManager()

@pytest.fixture
async def gateway(identity_manager):
    gw = NetworkGateway(identity_manager)
    yield gw
    await gw.close()

@pytest.mark.anyio
async def test_successful_request(gateway):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200

    gateway._client.request = AsyncMock(return_value=mock_resp)

    response = await gateway.get("http://example.com")
    assert response.status_code == 200

    # Verify User-Agent was injected
    call_args = gateway._client.request.call_args
    assert "User-Agent" in call_args.kwargs["headers"]

@pytest.mark.anyio
async def test_rate_limit_429(gateway):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 429
    mock_resp.headers = {"Retry-After": "120"}

    gateway._client.request = AsyncMock(return_value=mock_resp)

    with pytest.raises(RetryableError) as exc:
        await gateway.get("http://example.com")

    assert exc.value.retry_after == 120

@pytest.mark.anyio
async def test_soft_block_403_rotation(gateway):
    # First call 403, Second call 200
    mock_resp_403 = MagicMock(spec=httpx.Response)
    mock_resp_403.status_code = 403

    mock_resp_200 = MagicMock(spec=httpx.Response)
    mock_resp_200.status_code = 200

    gateway._client.request = AsyncMock(side_effect=[mock_resp_403, mock_resp_200])

    # Capture initial identity
    initial_ua = gateway.identity_manager.get_current_identity()

    response = await gateway.get("http://example.com")
    assert response.status_code == 200

    # Verify two calls were made
    assert gateway._client.request.call_count == 2

    # Verify identity was rotated
    final_ua = gateway.identity_manager.get_current_identity()
    assert initial_ua != final_ua
