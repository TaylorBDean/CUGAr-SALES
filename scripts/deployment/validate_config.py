#!/usr/bin/env python3
"""
Configuration Validation Script

Validates all required environment variables and configuration
before deployment to staging/production.

Usage:
    python scripts/deployment/validate_config.py
"""

import os
import sys
from typing import Dict, List, Tuple


def check_crm_config() -> Tuple[bool, str]:
    """Check if at least one CRM is configured."""
    hubspot_key = os.getenv("HUBSPOT_API_KEY")
    salesforce_username = os.getenv("SALESFORCE_USERNAME")
    salesforce_password = os.getenv("SALESFORCE_PASSWORD")
    salesforce_token = os.getenv("SALESFORCE_SECURITY_TOKEN")
    pipedrive_token = os.getenv("PIPEDRIVE_API_TOKEN")
    
    if hubspot_key:
        return True, "HubSpot"
    elif salesforce_username and salesforce_password and salesforce_token:
        return True, "Salesforce"
    elif pipedrive_token:
        return True, "Pipedrive"
    else:
        return False, "None"


def check_budget_config() -> Tuple[bool, Dict[str, str]]:
    """Check budget enforcement configuration."""
    ceiling = os.getenv("AGENT_BUDGET_CEILING", "100")
    escalation = os.getenv("AGENT_ESCALATION_MAX", "2")
    policy = os.getenv("AGENT_BUDGET_POLICY", "warn")
    
    try:
        ceiling_val = float(ceiling)
        escalation_val = int(escalation)
        
        if ceiling_val <= 0:
            return False, {"error": "AGENT_BUDGET_CEILING must be positive"}
        if escalation_val < 0:
            return False, {"error": "AGENT_ESCALATION_MAX must be non-negative"}
        if policy not in ["warn", "block"]:
            return False, {"error": "AGENT_BUDGET_POLICY must be 'warn' or 'block'"}
        
        return True, {
            "ceiling": ceiling,
            "escalation": escalation,
            "policy": policy,
        }
    except (ValueError, TypeError) as e:
        return False, {"error": f"Invalid budget config: {e}"}


def check_observability_config() -> Tuple[bool, List[str]]:
    """Check observability configuration (optional)."""
    configured = []
    
    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        configured.append("OTEL")
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        configured.append("LangFuse")
    if os.getenv("LANGSMITH_API_KEY"):
        configured.append("LangSmith")
    
    return len(configured) > 0, configured


def main():
    """Run all configuration validations."""
    print("=" * 60)
    print("CUGAr Sales Agent - Configuration Validation")
    print("=" * 60)
    print()
    
    all_valid = True
    
    # Check CRM configuration
    print("1. CRM Configuration")
    print("-" * 40)
    crm_valid, crm_type = check_crm_config()
    if crm_valid:
        print(f"✅ CRM adapter detected: {crm_type}")
    else:
        print("⚠️  No CRM configured (optional - will run in offline mode)")
        print("   To configure CRM, set one of:")
        print("   - HUBSPOT_API_KEY")
        print("   - SALESFORCE_USERNAME + SALESFORCE_PASSWORD + SALESFORCE_SECURITY_TOKEN")
        print("   - PIPEDRIVE_API_TOKEN")
    print()
    
    # Check budget configuration
    print("2. Budget Enforcement")
    print("-" * 40)
    budget_valid, budget_config = check_budget_config()
    if budget_valid:
        print(f"✅ Budget ceiling configured: {budget_config['ceiling']}")
        print(f"✅ Escalation max: {budget_config['escalation']}")
        print(f"✅ Budget policy: {budget_config['policy']}")
    else:
        print(f"❌ Budget configuration invalid: {budget_config.get('error')}")
        all_valid = False
    print()
    
    # Check observability configuration
    print("3. Observability (Optional)")
    print("-" * 40)
    obs_valid, obs_backends = check_observability_config()
    if obs_valid:
        print(f"✅ Observability configured: {', '.join(obs_backends)}")
    else:
        print("ℹ️  No observability backends configured (optional)")
        print("   To configure, set one or more of:")
        print("   - OTEL_EXPORTER_OTLP_ENDPOINT")
        print("   - LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY")
        print("   - LANGSMITH_API_KEY")
    print()
    
    # Check Python environment
    print("4. Python Environment")
    print("-" * 40)
    python_version = sys.version_info
    if python_version >= (3, 9):
        print(f"✅ Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    else:
        print(f"❌ Python version too old: {python_version.major}.{python_version.minor}.{python_version.micro}")
        print("   Requires Python 3.9+")
        all_valid = False
    print()
    
    # Final summary
    print("=" * 60)
    if all_valid:
        print("✅ Configuration valid - Ready for deployment")
        print()
        print("Next steps:")
        print("  1. Run smoke tests: pytest tests/sales/ -k 'not unit' --tb=short")
        print("  2. Test CRM connectivity: python scripts/deployment/test_crm_connection.py")
        print("  3. Deploy to staging")
        return 0
    else:
        print("❌ Configuration invalid - Fix errors before deployment")
        return 1


if __name__ == "__main__":
    sys.exit(main())
