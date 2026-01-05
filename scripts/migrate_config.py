#!/usr/bin/env python3
"""
Configuration Migration Script

Consolidates scattered configuration files into unified structure:
- Merges registry.yaml (root) + docs/mcp/registry.yaml → config/registry.yaml
- Converts configurations/models/*.toml → config/defaults/models/*.yaml
- Moves routing/guards.yaml → config/guards.yaml
- Creates backups of original files

Usage:
    python scripts/migrate_config.py [--dry-run] [--no-backup]
    
Options:
    --dry-run: Show what would be changed without making changes
    --no-backup: Skip creating backups (not recommended)
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml")
    sys.exit(1)


def merge_registries(
    root_registry: Path, mcp_registry: Path, output: Path, dry_run: bool = False
) -> Dict[str, Any]:
    """
    Merge root registry.yaml + docs/mcp/registry.yaml into config/registry.yaml.
    
    Args:
        root_registry: Path to root registry.yaml
        mcp_registry: Path to docs/mcp/registry.yaml
        output: Output path for merged registry
        dry_run: If True, don't write files
        
    Returns:
        Merged registry dict
    """
    print(f"\n📋 Merging registries...")
    print(f"   Source 1: {root_registry}")
    print(f"   Source 2: {mcp_registry}")
    print(f"   Output: {output}")

    root_data = {}
    if root_registry.exists():
        with open(root_registry) as f:
            root_data = yaml.safe_load(f) or {}
        print(f"   ✓ Loaded {len(root_data.get('tools', {}))} tools from root registry")
    else:
        print(f"   ⚠ Root registry not found: {root_registry}")

    mcp_data = {}
    if mcp_registry.exists():
        with open(mcp_registry) as f:
            mcp_data = yaml.safe_load(f) or {}
        print(f"   ✓ Loaded {len(mcp_data.get('tools', {}))} tools from MCP registry")
    else:
        print(f"   ⚠ MCP registry not found: {mcp_registry}")

    # Merge tools (MCP takes precedence on conflicts)
    merged = {"tools": {}}
    merged["tools"].update(root_data.get("tools", {}))
    
    # Track conflicts
    conflicts = []
    for tool_name, tool_config in mcp_data.get("tools", {}).items():
        if tool_name in merged["tools"]:
            conflicts.append(tool_name)
        merged["tools"][tool_name] = tool_config

    if conflicts:
        print(f"   ⚠ {len(conflicts)} tool conflicts (MCP version used): {', '.join(conflicts)}")

    # Merge other top-level keys (preserve both if present)
    for key in set(root_data.keys()) | set(mcp_data.keys()):
        if key != "tools":
            if key in mcp_data:
                merged[key] = mcp_data[key]
            elif key in root_data:
                merged[key] = root_data[key]

    if not dry_run:
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            yaml.safe_dump(merged, f, sort_keys=False, default_flow_style=False)
        print(f"   ✅ Wrote {len(merged['tools'])} tools to {output}")
    else:
        print(f"   [DRY RUN] Would write {len(merged['tools'])} tools to {output}")

    return merged


def convert_toml_to_yaml(toml_dir: Path, yaml_dir: Path, dry_run: bool = False) -> List[Path]:
    """
    Convert configurations/models/*.toml to config/defaults/models/*.yaml.
    
    Args:
        toml_dir: Directory containing TOML files
        yaml_dir: Output directory for YAML files
        dry_run: If True, don't write files
        
    Returns:
        List of converted file paths
    """
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            print("   ⚠ tomllib/tomli not available. Install Python 3.11+ or: pip install tomli")
            return []

    print(f"\n🔄 Converting TOML configs to YAML...")
    print(f"   Source: {toml_dir}")
    print(f"   Output: {yaml_dir}")

    if not toml_dir.exists():
        print(f"   ⚠ TOML directory not found: {toml_dir}")
        return []

    toml_files = list(toml_dir.glob("*.toml"))
    if not toml_files:
        print(f"   ℹ No TOML files found in {toml_dir}")
        return []

    converted = []
    for toml_file in toml_files:
        try:
            with open(toml_file, "rb") as f:
                data = tomllib.load(f)

            yaml_file = yaml_dir / f"{toml_file.stem}.yaml"

            if not dry_run:
                yaml_dir.mkdir(parents=True, exist_ok=True)
                with open(yaml_file, "w") as f:
                    yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)
                print(f"   ✅ Converted {toml_file.name} → {yaml_file.name}")
                converted.append(yaml_file)
            else:
                print(f"   [DRY RUN] Would convert {toml_file.name} → {yaml_file.name}")
                converted.append(yaml_file)

        except Exception as e:
            print(f"   ❌ Failed to convert {toml_file.name}: {e}")

    return converted


def move_guards(old_guards: Path, new_guards: Path, dry_run: bool = False) -> bool:
    """
    Move routing/guards.yaml to config/guards.yaml.
    
    Args:
        old_guards: Source guards.yaml path
        new_guards: Destination guards.yaml path
        dry_run: If True, don't move files
        
    Returns:
        True if moved successfully
    """
    print(f"\n📦 Moving guards configuration...")
    print(f"   From: {old_guards}")
    print(f"   To: {new_guards}")

    if not old_guards.exists():
        print(f"   ℹ Guards file not found: {old_guards}")
        return False

    if not dry_run:
        new_guards.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(old_guards, new_guards)
        print(f"   ✅ Moved guards configuration")
        return True
    else:
        print(f"   [DRY RUN] Would move guards configuration")
        return True


def create_backups(files: List[Path], backup_dir: Path, dry_run: bool = False) -> List[Path]:
    """
    Create timestamped backups of files before migration.
    
    Args:
        files: List of file paths to backup
        backup_dir: Directory to store backups
        dry_run: If True, don't create backups
        
    Returns:
        List of backup file paths
    """
    if dry_run:
        print(f"\n[DRY RUN] Would create backups in {backup_dir}")
        return []

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = backup_dir / f"config_backup_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n💾 Creating backups in {backup_dir}...")

    backups = []
    for file_path in files:
        if file_path.exists():
            backup_path = backup_dir / file_path.name
            shutil.copy(file_path, backup_path)
            print(f"   ✓ Backed up {file_path.name}")
            backups.append(backup_path)

    return backups


def validate_migration(project_root: Path) -> bool:
    """
    Validate migrated configuration using ConfigValidator.
    
    Args:
        project_root: Project root directory
        
    Returns:
        True if validation passes
    """
    print(f"\n🔍 Validating migrated configuration...")

    try:
        from cuga.config import ConfigValidator

        # Validate registry
        registry_path = project_root / "config" / "registry.yaml"
        if registry_path.exists():
            with open(registry_path) as f:
                registry_data = yaml.safe_load(f)
            
            try:
                ConfigValidator.validate_registry(registry_data)
                print(f"   ✅ Registry validation passed")
            except ValueError as e:
                print(f"   ❌ Registry validation failed: {e}")
                return False
        
        # Validate guards
        guards_path = project_root / "config" / "guards.yaml"
        if guards_path.exists():
            with open(guards_path) as f:
                guards_data = yaml.safe_load(f)
            
            try:
                ConfigValidator.validate_guards(guards_data)
                print(f"   ✅ Guards validation passed")
            except ValueError as e:
                print(f"   ❌ Guards validation failed: {e}")
                return False

        print(f"   ✅ All validation checks passed")
        return True

    except ImportError as e:
        print(f"   ⚠ Cannot import ConfigValidator (run from project root): {e}")
        return True  # Skip validation if imports fail


def main():
    parser = argparse.ArgumentParser(
        description="Migrate configuration files to unified structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backups (not recommended)",
    )
    args = parser.parse_args()

    # Determine project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    print("=" * 70)
    print("Configuration Migration Script")
    print("=" * 70)
    print(f"Project root: {project_root}")
    if args.dry_run:
        print("⚠️  DRY RUN MODE - No files will be modified")
    if args.no_backup:
        print("⚠️  Backups disabled")
    print("=" * 70)

    # Define file paths
    root_registry = project_root / "registry.yaml"
    mcp_registry = project_root / "docs" / "mcp" / "registry.yaml"
    merged_registry = project_root / "config" / "registry.yaml"

    toml_models_dir = project_root / "configurations" / "models"
    yaml_models_dir = project_root / "config" / "defaults" / "models"

    old_guards = project_root / "routing" / "guards.yaml"
    new_guards = project_root / "config" / "guards.yaml"

    settings_toml = project_root / "src" / "cuga" / "settings.toml"
    backend_yaml = project_root / "config" / "defaults" / "backend.yaml"

    # Create backups if requested
    if not args.no_backup and not args.dry_run:
        files_to_backup = [
            root_registry,
            mcp_registry,
            old_guards,
            settings_toml,
        ]
        files_to_backup.extend(toml_models_dir.glob("*.toml") if toml_models_dir.exists() else [])
        
        backup_dir = project_root / "backups"
        backups = create_backups(files_to_backup, backup_dir, dry_run=args.dry_run)
        print(f"   ✅ Created {len(backups)} backups")

    # Perform migrations
    try:
        # 1. Merge registries
        merge_registries(root_registry, mcp_registry, merged_registry, dry_run=args.dry_run)

        # 2. Convert TOML models to YAML
        converted = convert_toml_to_yaml(toml_models_dir, yaml_models_dir, dry_run=args.dry_run)

        # 3. Move guards
        guards_moved = move_guards(old_guards, new_guards, dry_run=args.dry_run)

        # 4. Validate migrated config
        if not args.dry_run:
            validation_ok = validate_migration(project_root)
            if not validation_ok:
                print("\n❌ Migration validation failed. Check errors above.")
                return 1

        # Summary
        print("\n" + "=" * 70)
        print("Migration Summary")
        print("=" * 70)
        print(f"✅ Merged registry: {merged_registry}")
        print(f"✅ Converted {len(converted)} TOML files to YAML")
        print(f"✅ Moved guards: {guards_moved}")
        
        if args.dry_run:
            print("\n⚠️  DRY RUN COMPLETE - No files were modified")
            print("   Run without --dry-run to apply changes")
        else:
            print("\n✅ Migration complete!")
            print("\nNext steps:")
            print("1. Review migrated files in config/")
            print("2. Update imports in code to use new paths")
            print("3. Test configuration loading with ConfigResolver")
            print("4. After verification, delete deprecated files:")
            print(f"   - {root_registry}")
            print(f"   - {mcp_registry}")
            print(f"   - {old_guards}")
            print(f"   - {toml_models_dir}/*.toml")

        return 0

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
