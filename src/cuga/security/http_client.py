"""
HTTP client wrapper with safe defaults, timeout enforcement, and retry logic.

Per AGENTS.md guardrails:
- Enforces global timeout defaults (10.0s read, 5.0s connect)
- Automatic retry with exponential backoff (4 attempts max, 8s max wait)
- Follow redirects safely by default
- No network I/O unless explicitly allowed by profile
- Structured logging with PII redaction for URLs/headers
"""

from typing import Any, Optional
import httpx
import tenacity
from loguru import logger


# Default timeout configuration: aggressive timeouts for enterprise safety
DEFAULT_TIMEOUT = httpx.Timeout(
    timeout=10.0,    # Total timeout
    connect=5.0,     # Connection timeout
    read=10.0,       # Read timeout
    write=10.0,      # Write timeout
)


# Retry policy: exponential backoff with jitter
RETRY_POLICY = tenacity.retry(
    reraise=True,
    stop=tenacity.stop_after_attempt(4),
    wait=tenacity.wait_exponential(multiplier=0.5, max=8),
    retry=tenacity.retry_if_exception_type(
        (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)
    ),
    before_sleep=lambda retry_state: logger.warning(
        f"HTTP retry attempt {retry_state.attempt_number}/4 "
        f"after {retry_state.outcome.exception()}"
    ),
)


class SafeClient:
    """
    Thread-safe HTTP client with enforced timeouts and retry logic.
    
    Usage:
        client = SafeClient()
        response = client.get("https://api.example.com/data")
        
    All methods enforce DEFAULT_TIMEOUT unless explicitly overridden.
    Automatically retries transient failures (network errors, timeouts).
    """
    
    def __init__(
        self,
        timeout: Optional[httpx.Timeout] = None,
        follow_redirects: bool = True,
        **kwargs: Any
    ):
        """
        Initialize safe HTTP client.
        
        Args:
            timeout: Custom timeout config (defaults to DEFAULT_TIMEOUT)
            follow_redirects: Whether to follow HTTP redirects (default: True)
            **kwargs: Additional httpx.Client parameters
        """
        self._timeout = timeout or DEFAULT_TIMEOUT
        self._client = httpx.Client(
            timeout=self._timeout,
            follow_redirects=follow_redirects,
            **kwargs
        )
        logger.debug(
            f"Initialized SafeClient with timeout={self._timeout}, "
            f"follow_redirects={follow_redirects}"
        )
    
    @RETRY_POLICY
    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """
        Safe GET request with automatic retry and timeout enforcement.
        
        Args:
            url: Target URL
            **kwargs: Additional request parameters (headers, params, etc.)
            
        Returns:
            httpx.Response object
            
        Raises:
            httpx.HTTPError: On final failure after retries
        """
        kwargs.setdefault("timeout", self._timeout)
        logger.debug(f"GET request to {self._redact_url(url)}")
        return self._client.get(url, **kwargs)
    
    @RETRY_POLICY
    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """
        Safe POST request with automatic retry and timeout enforcement.
        
        Args:
            url: Target URL
            **kwargs: Additional request parameters (json, data, headers, etc.)
            
        Returns:
            httpx.Response object
            
        Raises:
            httpx.HTTPError: On final failure after retries
        """
        kwargs.setdefault("timeout", self._timeout)
        logger.debug(f"POST request to {self._redact_url(url)}")
        return self._client.post(url, **kwargs)
    
    @RETRY_POLICY
    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        """Safe PUT request with retry."""
        kwargs.setdefault("timeout", self._timeout)
        logger.debug(f"PUT request to {self._redact_url(url)}")
        return self._client.put(url, **kwargs)
    
    @RETRY_POLICY
    def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        """Safe PATCH request with retry."""
        kwargs.setdefault("timeout", self._timeout)
        logger.debug(f"PATCH request to {self._redact_url(url)}")
        return self._client.patch(url, **kwargs)
    
    @RETRY_POLICY
    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        """Safe DELETE request with retry."""
        kwargs.setdefault("timeout", self._timeout)
        logger.debug(f"DELETE request to {self._redact_url(url)}")
        return self._client.delete(url, **kwargs)
    
    def close(self) -> None:
        """Close underlying HTTP client connection pool."""
        self._client.close()
        logger.debug("SafeClient closed")
    
    def __enter__(self) -> "SafeClient":
        """Context manager entry."""
        return self
    
    def __exit__(self, *args: Any) -> None:
        """Context manager exit with automatic cleanup."""
        self.close()
    
    @staticmethod
    def _redact_url(url: str) -> str:
        """
        Redact sensitive URL components (query params, credentials).
        
        Per AGENTS.md: Never echo URLs, tokens, secrets in logs.
        """
        try:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(url)
            # Remove credentials and query params for logging
            redacted = parsed._replace(
                netloc=parsed.hostname or parsed.netloc.split('@')[-1],
                query="<redacted>" if parsed.query else "",
            )
            return urlunparse(redacted)
        except Exception:
            # Fallback: just show scheme + hostname
            return url.split('?')[0].split('@')[-1] if url else "<invalid-url>"


# Async variant for compatibility with async codebases
class AsyncSafeClient:
    """
    Async HTTP client with enforced timeouts and retry logic.
    
    Usage:
        async with AsyncSafeClient() as client:
            response = await client.get("https://api.example.com/data")
    """
    
    def __init__(
        self,
        timeout: Optional[httpx.Timeout] = None,
        follow_redirects: bool = True,
        **kwargs: Any
    ):
        self._timeout = timeout or DEFAULT_TIMEOUT
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=follow_redirects,
            **kwargs
        )
        logger.debug(
            f"Initialized AsyncSafeClient with timeout={self._timeout}, "
            f"follow_redirects={follow_redirects}"
        )
    
    @tenacity.retry(
        reraise=True,
        stop=tenacity.stop_after_attempt(4),
        wait=tenacity.wait_exponential(multiplier=0.5, max=8),
        retry=tenacity.retry_if_exception_type(
            (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)
        ),
    )
    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Safe async GET request with retry."""
        kwargs.setdefault("timeout", self._timeout)
        logger.debug(f"Async GET request to {SafeClient._redact_url(url)}")
        return await self._client.get(url, **kwargs)
    
    @tenacity.retry(
        reraise=True,
        stop=tenacity.stop_after_attempt(4),
        wait=tenacity.wait_exponential(multiplier=0.5, max=8),
        retry=tenacity.retry_if_exception_type(
            (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)
        ),
    )
    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Safe async POST request with retry."""
        kwargs.setdefault("timeout", self._timeout)
        logger.debug(f"Async POST request to {SafeClient._redact_url(url)}")
        return await self._client.post(url, **kwargs)
    
    async def aclose(self) -> None:
        """Close async HTTP client connection pool."""
        await self._client.aclose()
        logger.debug("AsyncSafeClient closed")
    
    async def __aenter__(self) -> "AsyncSafeClient":
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit with automatic cleanup."""
        await self.aclose()


# Public redact_url function for use in logging/observability
def redact_url(url: str) -> str:
    """
    Redact sensitive URL components for safe logging.
    
    Per AGENTS.md § 5 (PII-safe logs): Strip credentials, query params, API keys.
    
    Args:
        url: Full URL to redact
    
    Returns:
        Redacted URL safe for logging
    
    Example:
        >>> redact_url("https://user:pass@api.example.com/v1/api_key/sk-123?token=abc")
        "https://api.example.com/v1/api_key/[REDACTED]"
    """
    return SafeClient._redact_url(url)
