"""
GitHub Repository Info Tool Example

Demonstrates advanced tool features:
- External API integration
- Retry on network errors
- Parameter validation
- Response transformation
- Error classification
"""

from typing import Dict, Any
import os


def github_repo_info_handler(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch GitHub repository information.
    
    Args:
        inputs:
            - owner: str (required) - Repository owner username
            - repo: str (required) - Repository name
            - include_stats: bool (optional) - Include detailed stats
        context:
            - profile: Execution profile
            - trace_id: Trace ID
    
    Returns:
        Repository information including name, description, stars, etc.
    
    Raises:
        ValueError: Invalid owner/repo format
        ConnectionError: GitHub API unavailable (retryable)
        TimeoutError: Request timeout (retryable)
        RuntimeError: Repository not found or API error
    """
    # Import here to avoid import at module level (sandbox isolation)
    try:
        import requests
    except ImportError:
        raise RuntimeError("requests library not available. Add to allowlist.")
    
    # Extract inputs
    owner = inputs.get("owner", "").strip()
    repo = inputs.get("repo", "").strip()
    include_stats = inputs.get("include_stats", False)
    
    # Validation
    if not owner:
        raise ValueError("Repository owner is required")
    if not repo:
        raise ValueError("Repository name is required")
    
    # Validate format (basic check)
    if not owner.replace("-", "").replace("_", "").isalnum():
        raise ValueError(f"Invalid owner format: {owner}")
    if not repo.replace("-", "").replace("_", "").isalnum():
        raise ValueError(f"Invalid repo format: {repo}")
    
    # Build API URL
    url = f"https://api.github.com/repos/{owner}/{repo}"
    
    # Get GitHub token from environment (optional but recommended for rate limits)
    github_token = os.getenv("GITHUB_TOKEN")
    headers = {}
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    headers["Accept"] = "application/vnd.github.v3+json"
    
    # Make API request with error handling
    try:
        response = requests.get(url, headers=headers, timeout=10.0)
        
        # Handle rate limiting (retryable with backoff)
        if response.status_code == 429:
            raise ConnectionError("GitHub API rate limit exceeded. Retry after delay.")
        
        # Handle not found (not retryable)
        if response.status_code == 404:
            raise RuntimeError(f"Repository not found: {owner}/{repo}")
        
        # Handle other errors
        response.raise_for_status()
        
        data = response.json()
        
        # Extract relevant information
        result = {
            "owner": data["owner"]["login"],
            "name": data["name"],
            "full_name": data["full_name"],
            "description": data["description"],
            "url": data["html_url"],
            "stars": data["stargazers_count"],
            "forks": data["forks_count"],
            "language": data["language"],
            "topics": data.get("topics", []),
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
            "open_issues": data["open_issues_count"],
            "license": data["license"]["name"] if data["license"] else None,
        }
        
        # Add detailed stats if requested
        if include_stats:
            result["watchers"] = data["watchers_count"]
            result["subscribers"] = data["subscribers_count"]
            result["size_kb"] = data["size"]
            result["default_branch"] = data["default_branch"]
            result["has_wiki"] = data["has_wiki"]
            result["has_issues"] = data["has_issues"]
        
        return result
    
    except requests.ConnectionError as e:
        # Network errors are retryable
        raise ConnectionError(f"GitHub API connection failed: {e}")
    
    except requests.Timeout as e:
        # Timeouts are retryable
        raise TimeoutError(f"GitHub API request timed out: {e}")
    
    except requests.HTTPError as e:
        # HTTP errors (except 429) are not retryable
        if e.response.status_code >= 500:
            # Server errors are retryable
            raise ConnectionError(f"GitHub API server error: {e}")
        raise RuntimeError(f"GitHub API error: {e}")


# Import ToolSpec
from cuga.modular.tools import ToolSpec, ToolRegistry
from cuga.modular.agents import WorkerAgent
from cuga.modular.memory import VectorMemory


# Create ToolSpec
GITHUB_REPO_TOOL = ToolSpec(
    name="github_repo_info",
    description="Fetch detailed information about a GitHub repository including stars, forks, language, and topics",
    handler=github_repo_info_handler,
    parameters={
        "owner": {
            "type": "string",
            "required": True,
            "description": "GitHub username or organization name",
            "minLength": 1,
            "maxLength": 39,  # GitHub username limit
            "pattern": r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$",
        },
        "repo": {
            "type": "string",
            "required": True,
            "description": "Repository name",
            "minLength": 1,
            "maxLength": 100,  # GitHub repo name limit
        },
        "include_stats": {
            "type": "boolean",
            "required": False,
            "default": False,
            "description": "Include detailed repository statistics",
        },
    },
    cost=0.5,  # Medium cost (external API call)
    sandbox_profile="py-full",  # Need network access
    network_allowed=True,
    read_only=True,
    timeout=15.0,
    allowlist=["requests", "os", "json"],  # Required imports
    tags=["github", "api", "repository", "external"],
    version="1.0.0",
)


# Example usage
def main():
    """Demonstrate GitHub repo info tool usage."""
    
    # Setup
    registry = ToolRegistry(tools=[GITHUB_REPO_TOOL])
    worker = WorkerAgent(registry=registry, memory=VectorMemory())
    
    # Example 1: Basic repository info
    print("Example 1: Fetch repository info")
    result = worker.execute([
        {
            "tool": "github_repo_info",
            "input": {
                "owner": "python",
                "repo": "cpython",
            }
        }
    ])
    print(f"  Repository: {result.output['full_name']}")
    print(f"  Description: {result.output['description']}")
    print(f"  Stars: {result.output['stars']:,}")
    print(f"  Language: {result.output['language']}")
    
    # Example 2: With detailed stats
    print("\nExample 2: With detailed statistics")
    result = worker.execute([
        {
            "tool": "github_repo_info",
            "input": {
                "owner": "torvalds",
                "repo": "linux",
                "include_stats": True,
            }
        }
    ])
    print(f"  Repository: {result.output['full_name']}")
    print(f"  Stars: {result.output['stars']:,}")
    print(f"  Forks: {result.output['forks']:,}")
    print(f"  Default branch: {result.output.get('default_branch', 'N/A')}")
    print(f"  Size: {result.output.get('size_kb', 0):,} KB")
    
    # Example 3: Error handling (not found)
    print("\nExample 3: Repository not found")
    try:
        result = worker.execute([
            {
                "tool": "github_repo_info",
                "input": {
                    "owner": "nonexistent",
                    "repo": "repository123",
                }
            }
        ])
    except Exception as e:
        print(f"  Error caught: {type(e).__name__}: {e}")
    
    # Example 4: Multiple repositories
    print("\nExample 4: Query multiple repositories")
    repos = [
        {"owner": "microsoft", "repo": "vscode"},
        {"owner": "facebook", "repo": "react"},
        {"owner": "tensorflow", "repo": "tensorflow"},
    ]
    
    for repo_info in repos:
        try:
            result = worker.execute([
                {"tool": "github_repo_info", "input": repo_info}
            ])
            print(f"  {result.output['full_name']}: {result.output['stars']:,} ⭐")
        except Exception as e:
            print(f"  {repo_info['owner']}/{repo_info['repo']}: Error - {e}")


if __name__ == "__main__":
    # Note: Set GITHUB_TOKEN environment variable for higher rate limits
    # export GITHUB_TOKEN=your_github_token
    main()
