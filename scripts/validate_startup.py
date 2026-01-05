#!/usr/bin/env python3
"""
Pre-flight validation script per AGENTS.md guardrails.
Run before starting servers to ensure clean state.

Validates:
- registry.yaml structure
- .env parity with .env.example
- Critical Python imports
- Port availability (8000, 3000)

Usage:
    uv run python scripts/validate_startup.py
"""
import sys
import yaml
import socket
from pathlib import Path
from typing import Tuple

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check_registry() -> Tuple[bool, str]:
    """Validate registry.yaml structure"""
    try:
        registry_path = Path("registry.yaml")
        if not registry_path.exists():
            return False, "registry.yaml not found"
        
        with open(registry_path) as f:
            data = yaml.safe_load(f)
        
        if not isinstance(data, dict):
            return False, "Registry is not a valid YAML dictionary"
        
        # Check for key sections (flexible for dev vs prod registries)
        has_servers = 'servers' in data or 'mcp_servers' in data
        has_tools = 'local_tools' in data or 'tools' in data
        
        if not (has_servers or has_tools):
            return False, "Registry missing servers/tools sections"
        
        return True, f"Registry valid"
    except yaml.YAMLError as e:
        return False, f"Invalid YAML: {e}"
    except Exception as e:
        return False, f"Registry error: {e}"

def check_env_parity() -> Tuple[bool, str]:
    """Ensure .env has all keys from .env.example"""
    try:
        env_example = Path(".env.example")
        env_file = Path(".env")
        
        if not env_example.exists():
            return False, ".env.example not found"
        
        if not env_file.exists():
            return False, ".env not found (copy from .env.example)"
        
        with open(env_example) as f:
            example_keys = {
                line.split('=')[0].strip() 
                for line in f 
                if '=' in line and not line.strip().startswith('#') and line.strip()
            }
        
        with open(env_file) as f:
            env_keys = {
                line.split('=')[0].strip() 
                for line in f 
                if '=' in line and not line.strip().startswith('#') and line.strip()
            }
        
        missing = example_keys - env_keys
        if missing:
            return False, f"Missing env vars: {', '.join(sorted(missing))}"
        
        return True, ".env parity confirmed"
    except Exception as e:
        return False, f"Environment check error: {e}"

def check_imports() -> Tuple[bool, str]:
    """Verify critical imports resolve"""
    critical_modules = [
        'cuga.backend.server.main',
        'cuga.backend.api.websocket',
        'cuga.orchestrator.trace_emitter',
        'cuga.orchestrator.trace_websocket_bridge',
    ]
    
    failures = []
    for mod in critical_modules:
        try:
            __import__(mod)
        except Exception as e:
            failures.append(f"  • {mod}: {str(e)[:60]}")
    
    if failures:
        return False, f"Import failures:\n" + "\n".join(failures)
    
    return True, f"All {len(critical_modules)} critical imports resolve"

def check_ports() -> Tuple[bool, str]:
    """Verify ports 8000 and 3000 are available"""
    ports = [8000, 3000]
    in_use = []
    
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) == 0:
                in_use.append(port)
    
    if in_use:
        ports_str = ', '.join(str(p) for p in in_use)
        return False, f"Ports in use: {ports_str} (run ./scripts/stop-dev.sh first)"
    
    return True, "Ports 8000 and 3000 available"

def check_frontend_workspace() -> Tuple[bool, str]:
    """Verify frontend workspace exists"""
    frontend_path = Path("src/frontend_workspaces")
    package_json = frontend_path / "package.json"
    
    if not frontend_path.exists():
        return False, "Frontend workspace directory missing"
    
    if not package_json.exists():
        return False, "Frontend package.json missing"
    
    return True, "Frontend workspace exists"

def main():
    """Run all pre-flight checks"""
    print(f"\n{YELLOW}🔍 CUGAr-SALES Pre-Flight Validation{RESET}")
    print("=" * 60)
    
    checks = [
        ("Registry", check_registry),
        ("Environment", check_env_parity),
        ("Python Imports", check_imports),
        ("Port Availability", check_ports),
        ("Frontend Workspace", check_frontend_workspace),
    ]
    
    failures = []
    warnings = []
    
    for name, check_fn in checks:
        try:
            success, message = check_fn()
            status = f"{GREEN}✅{RESET}" if success else f"{RED}❌{RESET}"
            print(f"{status} {name:20} {message}")
            
            if not success:
                failures.append(name)
        except Exception as e:
            print(f"{RED}❌{RESET} {name:20} Unexpected error: {e}")
            failures.append(name)
    
    print("=" * 60)
    
    if failures:
        print(f"\n{RED}❌ Validation failed: {', '.join(failures)}{RESET}")
        print(f"\n{YELLOW}Fix issues above before running ./scripts/start-dev.sh{RESET}\n")
        sys.exit(1)
    else:
        print(f"\n{GREEN}✅ All pre-flight checks passed!{RESET}")
        print(f"{GREEN}Ready to run: ./scripts/start-dev.sh{RESET}\n")
        sys.exit(0)

if __name__ == "__main__":
    main()
