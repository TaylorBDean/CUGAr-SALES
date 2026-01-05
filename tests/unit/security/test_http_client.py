"""
Tests for SafeClient HTTP wrapper with retry logic and timeout enforcement.

Per AGENTS.md:
- Verify enforced timeouts (10.0s read, 5.0s connect)
- Verify automatic retry with exponential backoff (4 attempts max, 8s max wait)
- Verify redirect following
- Verify URL redaction in logs
"""

import pytest
import httpx
from unittest.mock import Mock, patch
from cuga.security.http_client import (
    SafeClient,
    AsyncSafeClient,
    DEFAULT_TIMEOUT,
)


class TestSafeClient:
    """Test suite for SafeClient HTTP wrapper."""
    
    def test_default_timeout_config(self):
        """Verify DEFAULT_TIMEOUT matches specification."""
        assert DEFAULT_TIMEOUT.timeout == 10.0
        assert DEFAULT_TIMEOUT.connect == 5.0
        assert DEFAULT_TIMEOUT.read == 10.0
        assert DEFAULT_TIMEOUT.write == 10.0
    
    def test_client_initialization(self):
        """Test SafeClient initializes with correct defaults."""
        client = SafeClient()
        assert client._timeout == DEFAULT_TIMEOUT
        assert client._client.follow_redirects is True
        client.close()
    
    def test_context_manager(self):
        """Test SafeClient works as context manager with automatic cleanup."""
        with SafeClient() as client:
            assert client._client is not None
        # Client should be closed after context exit
    
    @patch('httpx.Client.get')
    def test_get_request_with_timeout(self, mock_get):
        """Verify GET requests enforce timeout."""
        mock_response = Mock(spec=httpx.Response)
        mock_get.return_value = mock_response
        
        with SafeClient() as client:
            response = client.get("https://api.example.com/data")
            
            # Verify timeout was passed
            call_args = mock_get.call_args
            assert call_args.kwargs['timeout'] == DEFAULT_TIMEOUT
            assert response == mock_response
    
    @patch('httpx.Client.post')
    def test_post_request_with_timeout(self, mock_post):
        """Verify POST requests enforce timeout."""
        mock_response = Mock(spec=httpx.Response)
        mock_post.return_value = mock_response
        
        with SafeClient() as client:
            response = client.post("https://api.example.com/data", json={"key": "value"})
            
            call_args = mock_post.call_args
            assert call_args.kwargs['timeout'] == DEFAULT_TIMEOUT
            assert response == mock_response
    
    @patch('httpx.Client.get')
    def test_retry_on_timeout(self, mock_get):
        """Verify automatic retry on timeout exceptions."""
        # Simulate 3 timeouts then success
        mock_get.side_effect = [
            httpx.TimeoutException("Timeout 1"),
            httpx.TimeoutException("Timeout 2"),
            httpx.TimeoutException("Timeout 3"),
            Mock(spec=httpx.Response),
        ]
        
        with SafeClient() as client:
            response = client.get("https://api.example.com/slow")
            
            # Should have called 4 times (3 retries + 1 success)
            assert mock_get.call_count == 4
            assert response is not None
    
    @patch('httpx.Client.get')
    def test_retry_exhaustion(self, mock_get):
        """Verify retry exhaustion after max attempts."""
        # Simulate persistent failures
        mock_get.side_effect = httpx.TimeoutException("Persistent timeout")
        
        with SafeClient() as client:
            with pytest.raises(httpx.TimeoutException):
                client.get("https://api.example.com/always-timeout")
            
            # Should have called 4 times (max attempts)
            assert mock_get.call_count == 4
    
    @patch('httpx.Client.get')
    def test_retry_on_network_error(self, mock_get):
        """Verify retry on network errors."""
        mock_get.side_effect = [
            httpx.NetworkError("Network error"),
            Mock(spec=httpx.Response),
        ]
        
        with SafeClient() as client:
            response = client.get("https://api.example.com/flaky")
            
            # Should have retried and succeeded
            assert mock_get.call_count == 2
            assert response is not None
    
    def test_url_redaction(self):
        """Verify URL redaction strips sensitive data."""
        # Test query param redaction
        redacted = SafeClient._redact_url("https://api.example.com/data?token=secret123")
        assert "secret123" not in redacted
        assert "<redacted>" in redacted or redacted == "https://api.example.com/data"
        
        # Test credential redaction
        redacted = SafeClient._redact_url("https://user:pass@api.example.com/data")
        assert "user" not in redacted or "pass" not in redacted
        assert "api.example.com" in redacted
    
    def test_custom_timeout_override(self):
        """Verify custom timeout can override default."""
        custom_timeout = httpx.Timeout(5.0)
        client = SafeClient(timeout=custom_timeout)
        
        assert client._timeout == custom_timeout
        client.close()
    
    @patch('httpx.Client.get')
    def test_all_http_methods_supported(self, mock_get):
        """Verify all HTTP methods (GET/POST/PUT/PATCH/DELETE) supported."""
        mock_response = Mock(spec=httpx.Response)
        
        with SafeClient() as client:
            with patch.object(client._client, 'get', return_value=mock_response):
                client.get("https://example.com")
            
            with patch.object(client._client, 'post', return_value=mock_response):
                client.post("https://example.com")
            
            with patch.object(client._client, 'put', return_value=mock_response):
                client.put("https://example.com")
            
            with patch.object(client._client, 'patch', return_value=mock_response):
                client.patch("https://example.com")
            
            with patch.object(client._client, 'delete', return_value=mock_response):
                client.delete("https://example.com")


class TestAsyncSafeClient:
    """Test suite for AsyncSafeClient."""
    
    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test AsyncSafeClient works as async context manager."""
        async with AsyncSafeClient() as client:
            assert client._client is not None
        # Client should be closed after context exit
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.get')
    async def test_async_get_with_timeout(self, mock_get):
        """Verify async GET requests enforce timeout."""
        mock_response = Mock(spec=httpx.Response)
        mock_get.return_value = mock_response
        
        async with AsyncSafeClient() as client:
            response = await client.get("https://api.example.com/data")
            
            call_args = mock_get.call_args
            assert call_args.kwargs['timeout'] == DEFAULT_TIMEOUT
            assert response == mock_response
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.get')
    async def test_async_retry_logic(self, mock_get):
        """Verify async retry on failures."""
        mock_get.side_effect = [
            httpx.TimeoutException("Timeout"),
            Mock(spec=httpx.Response),
        ]
        
        async with AsyncSafeClient() as client:
            response = await client.get("https://api.example.com/slow")
            
            assert mock_get.call_count == 2
            assert response is not None


class TestHTTPSecurityIntegration:
    """Integration tests for HTTP security guardrails."""
    
    def test_redirect_following_enabled(self):
        """Verify redirect following is enabled by default."""
        client = SafeClient()
        assert client._client.follow_redirects is True
        client.close()
    
    def test_timeout_cannot_be_none(self):
        """Verify timeout is always enforced."""
        client = SafeClient()
        assert client._timeout is not None
        assert client._timeout.timeout > 0
        client.close()
    
    @patch('httpx.Client.get')
    def test_timeout_applied_to_all_requests(self, mock_get):
        """Verify timeout applied even when not explicitly specified."""
        mock_get.return_value = Mock(spec=httpx.Response)
        
        with SafeClient() as client:
            # Call without explicit timeout
            client.get("https://example.com")
            
            # Timeout should still be applied
            call_args = mock_get.call_args
            assert 'timeout' in call_args.kwargs
            assert call_args.kwargs['timeout'] is not None
