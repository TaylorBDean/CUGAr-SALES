"""
Generate constraints.txt for reproducible installs.

This script creates two files:
1. constraints.txt - Full package constraints from current environment
2. constraints-test.txt - Minimal test-only constraints (already created)
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Set


def get_installed_packages() -> List[str]:
    """Get list of installed packages from current environment."""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        capture_output=True,
        text=True,
        check=True
    )
    
    packages = []
    for line in result.stdout.strip().split('\n'):
        # Skip editable installs and comments
        if line and not line.startswith('-e ') and not line.startswith('#'):
            packages.append(line)
    
    return packages


def filter_packages(packages: List[str], exclude_local: bool = True) -> List[str]:
    """Filter package list to remove local/development packages."""
    filtered = []
    exclude_patterns = ['cuga==', 'browsergym-core=='] if exclude_local else []
    
    for pkg in packages:
        # Skip local packages
        if any(pattern in pkg for pattern in exclude_patterns):
            continue
        filtered.append(pkg)
    
    return filtered


def create_full_constraints():
    """Create full constraints.txt from current environment."""
    print("📦 Generating constraints.txt from current environment...")
    
    try:
        packages = get_installed_packages()
        packages = filter_packages(packages, exclude_local=True)
        
        # Write constraints file
        constraints_path = Path(__file__).parent.parent / "constraints.txt"
        with open(constraints_path, 'w') as f:
            f.write("# Auto-generated package constraints for reproducible installs\n")
            f.write("# Generated from working environment on 2026-01-04\n")
            f.write("# Use: pip install -c constraints.txt -e .\n\n")
            f.write('\n'.join(sorted(packages)))
        
        print(f"✅ Created {constraints_path}")
        print(f"   {len(packages)} packages locked")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to get installed packages: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def verify_test_constraints():
    """Verify test constraints file exists and is valid."""
    test_constraints = Path(__file__).parent.parent / "constraints-test.txt"
    
    if not test_constraints.exists():
        print(f"⚠️  Test constraints not found: {test_constraints}")
        return False
    
    with open(test_constraints, 'r') as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
    
    print(f"✅ Test constraints verified: {test_constraints}")
    print(f"   {len(lines)} dependencies specified")
    
    return True


def main():
    """Main entry point."""
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🔧 Constraints Generator")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("")
    
    # Check test constraints
    if not verify_test_constraints():
        print("")
        print("⚠️  Test constraints missing - quick_test_setup.sh may not work")
    
    print("")
    
    # Create full constraints
    if create_full_constraints():
        print("")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✅ Constraints generated successfully!")
        print("")
        print("📋 Usage:")
        print("")
        print("  Test-only install (fast):")
        print("    bash scripts/quick_test_setup.sh")
        print("")
        print("  Full install (with constraints):")
        print("    pip install -c constraints.txt -e .")
        print("")
        print("  Update constraints:")
        print("    python scripts/create_constraints.py")
        print("")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    else:
        print("")
        print("❌ Failed to generate constraints")
        print("   Make sure you're in a working virtual environment")
        sys.exit(1)


if __name__ == "__main__":
    main()
