"""
Tests for SafeClient HTTP wrapper per AGENTS.md § Tool Contract.

Validates canonical policies:
- Enforced timeouts (10.0s read, 5.0s connect)
- Automatic retry with exponential backoff (4 attempts, 8s max wait)
- URL redaction in logs
- No raw httpx/requests usage outside SafeClient
"""
import pytest
from unittest.mock import patch, MagicMock, call
import httpx
from cuga.security.http_client import SafeClient, DEFAULT_TIMEOUT, redact_url


class TestSafeClientTimeouts:
    """Test timeout enforcement per AGENTS.md § Tool Contract."""
    
    def test_default_timeout_configuration(self):
        """SafeClient should use canonical timeout policy."""
        client = SafeClient()
        
        # Per AGENTS.md: 10.0s read, 5.0s connect, 10.0s write, 10.0s total
        assert client._timeout.read == 10.0
        assert client._timeout.connect == 5.0
        assert client._timeout.write == 10.0
        assert client._timeout.timeout == 10.0
    
    def test_custom_timeout_allowed(self):
        """SafeClient should allow custom timeouts (stricter than default)."""
        custom_timeout = httpx.Timeout(timeout=5.0, connect=2.0)
        client = SafeClient(timeout=custom_timeout)
        
        assert client._timeout.timeout == 5.0
        assert client._timeout.connect == 2.0
    
    @patch('httpx.Client')
    def test_timeout_applied_to_requests(self, mock_client_class):
        """Timeouts should be applied to all HTTP requests."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        
        client = SafeClient()
        client.post("http://example.com/api", json={"test": "data"})
        
        # Verify timeout passed to httpx.Client constructor
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["timeout"] == DEFAULT_TIMEOUT


class TestSafeClientRetry:
    """Test retry policy per AGENTS.md § Tool Contract."""
    
    @patch('httpx.Client')
    def test_retries_on_timeout(self, mock_client_class):
        """SafeClient should retry on timeout errors (exponential backoff)."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        # Simulate timeout on first 3 attempts, success on 4th
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.side_effect = [
            httpx.TimeoutException("Timeout 1"),
            httpx.TimeoutException("Timeout 2"),
            httpx.TimeoutException("Timeout 3"),
            mock_response
        ]
        
        client = SafeClient()
        response = client.post("http://example.com/api", json={"test": "data"})
        
        # Should succeed after retries
        assert mock_client.post.call_count == 4
        assert response == mock_response
    
    @patch('httpx.Client')
    def test_gives_up_after_max_retries(self, mock_client_class):
        """SafeClient should give up after 4 attempts per AGENTS.md."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        # Simulate persistent timeout
        mock_client.post.side_effect = httpx.TimeoutException("Persistent timeout")
        
        client = SafeClient()
        with pytest.raises(httpx.TimeoutException):
            client.post("http://example.com/api", json={"test": "data"})
        
        # Should attempt 4 times (initial + 3 retries)
        assert mock_client.post.call_count == 4
    
    @patch('httpx.Client')
    def test_retries_on_connect_error(self, mock_client_class):
        """SafeClient should retry on connection errors."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        # Simulate connection error then success
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get.side_effect = [
            httpx.ConnectError("Connection refused"),
            mock_response
        ]
        
        client = SafeClient()
        response = client.get("http://example.com/api")
        
        # Should succeed after 1 retry
        assert mock_client.get.call_count == 2
        assert response == mock_response


class TestURLRedaction:
    """Test URL redaction per AGENTS.md § 5 (PII-safe logs)."""
    
    def test_redacts_credentials(self):
        """redact_url should strip username:password from URLs."""
        url = "https://user:password@api.example.com/endpoint"
        redacted = redact_url(url)
        
        # Credentials should be removed
        assert "password" not in redacted
        # Host should be preserved or marked as redacted
        assert "api.example.com" in redacted or "REDACTED" in redacted
    
    def test_redacts_query_parameters(self):
        """redact_url should strip query parameters (may contain secrets)."""
        url = "https://api.example.com/endpoint?token=secret123&user=alice"
        redacted = redact_url(url)
        
        assert "token=secret123" not in redacted
        assert "user=alice" not in redacted
    
    def test_redacts_api_keys_in_path(self):
        """redact_url should redact API keys in path segments."""
        url = "https://api.example.com/v1/api_key/sk-1234567890/data"
        redacted = redact_url(url)
        
        assert "sk-1234567890" not in redacted or "REDACTED" in redacted
        assert "api_key" in redacted  # Path structure preserved
    
    def test_preserves_safe_url_components(self):
        """redact_url should preserve scheme, host, safe path."""
        url = "https://api.example.com/v1/users/123/profile"
        redacted = redact_url(url)
        
        # Safe components should be preserved
        assert "https" in redacted or "api.example.com" in redacted
    
    def test_handles_invalid_urls(self):
        """redact_url should handle malformed URLs gracefully."""
        url = "not a valid url"
        redacted = redact_url(url)
        
        # Should return safe placeholder
        assert "INVALID" in redacted or redacted == url


class TestSafeClientMethods:
    """Test all HTTP methods are supported with retry."""
    
    @patch('httpx.Client')
    def test_get_method(self, mock_client_class):
        """Test GET method with retry."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response
        
        client = SafeClient()
        response = client.get("http://example.com/api")
        
        assert response == mock_response
        mock_client.get.assert_called_once()
    
    @patch('httpx.Client')
    def test_post_method(self, mock_client_class):
        """Test POST method with retry."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_client.post.return_value = mock_response
        
        client = SafeClient()
        response = client.post("http://example.com/api", json={"key": "value"})
        
        assert response == mock_response
        mock_client.post.assert_called_once()
    
    @patch('httpx.Client')
    def test_put_method(self, mock_client_class):
        """Test PUT method with retry."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.put.return_value = mock_response
        
        client = SafeClient()
        response = client.put("http://example.com/api/1", json={"key": "updated"})
        
        assert response == mock_response
        mock_client.put.assert_called_once()
    
    @patch('httpx.Client')
    def test_patch_method(self, mock_client_class):
        """Test PATCH method with retry."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.patch.return_value = mock_response
        
        client = SafeClient()
        response = client.patch("http://example.com/api/1", json={"key": "patched"})
        
        assert response == mock_response
        mock_client.patch.assert_called_once()
    
    @patch('httpx.Client')
    def test_delete_method(self, mock_client_class):
        """Test DELETE method with retry."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_client.delete.return_value = mock_response
        
        client = SafeClient()
        response = client.delete("http://example.com/api/1")
        
        assert response == mock_response
        mock_client.delete.assert_called_once()


class TestSafeClientContextManager:
    """Test context manager interface."""
    
    @patch('httpx.Client')
    def test_context_manager_closes_client(self, mock_client_class):
        """Test context manager closes client on exit."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client_class.return_value = mock_client
        
        with SafeClient() as client:
            assert client is not None
        
        # Should close underlying httpx.Client
        mock_client.close.assert_called_once()


def test_default_timeout_constants():
    """Test DEFAULT_TIMEOUT matches AGENTS.md canonical policy."""
    assert DEFAULT_TIMEOUT.timeout == 10.0
    assert DEFAULT_TIMEOUT.connect == 5.0
    assert DEFAULT_TIMEOUT.read == 10.0
    assert DEFAULT_TIMEOUT.write == 10.0


def test_redact_url_function():
    """Integration test for redact_url function."""
    from cuga.security.http_client import redact_url
    
    # Test comprehensive redaction
    url = "https://user:pass@api.example.com/v1/api_key/secret123?token=abc&data=xyz"
    redacted = redact_url(url)
    
    # Should remove sensitive parts
    assert "pass" not in redacted
    assert "secret123" not in redacted or "REDACTED" in redacted
    assert "token=abc" not in redacted
    assert "data=xyz" not in redacted
    
    # Should preserve safe parts or mark as redacted
    assert "api.example.com" in redacted or "REDACTED" in redacted
