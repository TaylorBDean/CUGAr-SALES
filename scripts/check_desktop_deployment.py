#!/usr/bin/env python3
"""
Installation test script for desktop deployment
Validates that all components are properly set up
"""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Verify Python version is 3.9+"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        return False, f"Python {version.major}.{version.minor} (need 3.9+)"
    return True, f"Python {version.major}.{version.minor}.{version.micro}"

def check_node_installed():
    """Verify Node.js is installed"""
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        return True, result.stdout.strip()
    except FileNotFoundError:
        return False, "Not installed"

def check_npm_installed():
    """Verify npm is installed"""
    try:
        result = subprocess.run(['npm', '--version'], capture_output=True, text=True)
        return True, result.stdout.strip()
    except FileNotFoundError:
        return False, "Not installed"

def check_file_exists(path):
    """Check if file exists"""
    return Path(path).exists()

def main():
    print("=" * 60)
    print("CUGAr Desktop Deployment - Installation Check")
    print("=" * 60)
    print()
    
    checks = []
    
    # Python version
    success, version = check_python_version()
    checks.append(("Python 3.9+", success, version))
    
    # Node.js
    success, version = check_node_installed()
    checks.append(("Node.js", success, version))
    
    # npm
    success, version = check_npm_installed()
    checks.append(("npm", success, version))
    
    # Critical files
    project_root = Path(__file__).parent.parent
    
    files_to_check = [
        ("Launch script (Unix)", project_root / "launch_sales_assistant.sh"),
        ("Launch script (Windows)", project_root / "launch_sales_assistant.bat"),
        ("Electron main", project_root / "src/frontend_workspaces/agentic_chat/electron.js"),
        ("Electron preload", project_root / "src/frontend_workspaces/agentic_chat/preload.js"),
        ("Quick Actions config", project_root / "src/frontend_workspaces/agentic_chat/src/config/quickActions.ts"),
        ("Quick Actions UI", project_root / "src/frontend_workspaces/agentic_chat/src/components/QuickActionsPanel.tsx"),
        ("Package.json", project_root / "src/frontend_workspaces/agentic_chat/package.json"),
        ("Deployment docs", project_root / "DESKTOP_DEPLOYMENT.md"),
    ]
    
    for name, path in files_to_check:
        exists = check_file_exists(path)
        checks.append((name, exists, str(path) if exists else "Missing"))
    
    # Print results
    print("\nInstallation Status:")
    print("-" * 60)
    
    all_passed = True
    for name, success, detail in checks:
        status = "✓" if success else "✗"
        color = "\033[92m" if success else "\033[91m"
        reset = "\033[0m"
        
        print(f"{color}{status}{reset} {name:30s} {detail}")
        if not success:
            all_passed = False
    
    print()
    print("=" * 60)
    
    if all_passed:
        print("\033[92m✓ All checks passed! Ready for deployment.\033[0m")
        print()
        print("Next steps:")
        print("  1. Wire QuickActionsPanel into main UI")
        print("  2. Create icon assets")
        print("  3. Build installers: npm run electron:build")
        print("  4. Test on target platforms")
        return 0
    else:
        print("\033[91m✗ Some checks failed. Please review above.\033[0m")
        print()
        print("Installation guide: DESKTOP_DEPLOYMENT.md")
        return 1

if __name__ == "__main__":
    sys.exit(main())
