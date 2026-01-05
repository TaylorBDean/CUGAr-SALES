"""
Profile-driven behavior per AGENTS.md memory & RAG requirements.
Loads profile configurations that drive budget, approval, and adapter policies.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import yaml
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProfileConfig:
    """
    Profile configuration per AGENTS.md requirements.
    
    Per AGENTS.md:
    - Metadata MUST include profile
    - Profiles drive budget, approval, and adapter allowlists
    - No cross-profile leakage
    """
    name: str
    budget: Dict[str, Any]
    approval_required: List[str]  # Side-effect classes requiring approval
    allowed_adapters: List[str]
    guardrails: str  # strict, moderate, relaxed
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API responses."""
        return asdict(self)


class ProfileLoader:
    """
    Loads and applies profile-driven behavior per AGENTS.md.
    
    Per AGENTS.md:
    - Profiles are orthogonal and independently governable
    - Profiles enforce domain-specific guardrails
    - Profiles enable enterprise data sovereignty
    """
    
    # Default profiles per AGENTS.md canonical domains
    DEFAULT_PROFILES = {
        "enterprise": ProfileConfig(
            name="enterprise",
            budget={
                "total_calls": 200,
                "calls_per_domain": {
                    "territory": 50,
                    "intelligence": 40,
                    "engagement": 30
                }
            },
            approval_required=["execute", "propose"],
            allowed_adapters=["salesforce", "dynamics", "mock"],
            guardrails="strict",
            description="Enterprise sales with strict governance"
        ),
        "smb": ProfileConfig(
            name="smb",
            budget={
                "total_calls": 100,
                "calls_per_domain": {
                    "engagement": 30,
                    "intelligence": 25,
                    "qualification": 20
                }
            },
            approval_required=["execute"],
            allowed_adapters=["hubspot", "pipedrive", "mock"],
            guardrails="moderate",
            description="SMB sales with balanced governance"
        ),
        "technical": ProfileConfig(
            name="technical",
            budget={
                "total_calls": 500,
                "calls_per_domain": {}
            },
            approval_required=[],  # Technical users trusted
            allowed_adapters=["mock"],  # Offline-first per AGENTS.md
            guardrails="relaxed",
            description="Technical specialists with offline-first tooling"
        )
    }
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize profile loader.
        
        Args:
            config_dir: Optional directory for custom profile configs
        """
        self.config_dir = config_dir
        self.profiles = self.DEFAULT_PROFILES.copy()
        
        if config_dir:
            self._load_custom_profiles()
    
    def load_profile(self, profile_name: str) -> ProfileConfig:
        """
        Load profile configuration.
        
        Per AGENTS.md:
        - Profiles MUST be explicitly selected
        - Unknown profiles raise error (no silent fallback)
        
        Args:
            profile_name: Name of profile to load
        
        Returns:
            ProfileConfig for requested profile
        
        Raises:
            ValueError: If profile not found
        """
        if profile_name not in self.profiles:
            available = ", ".join(self.profiles.keys())
            raise ValueError(
                f"Unknown profile: {profile_name}. "
                f"Available profiles: {available}"
            )
        
        logger.info(f"Loaded profile: {profile_name}")
        return self.profiles[profile_name]
    
    def get_budget(self, profile_name: str) -> Dict[str, Any]:
        """
        Get budget configuration for profile.
        
        Per AGENTS.md:
        - PlannerAgent MUST attach a ToolBudget to every plan
        - Budgets are profile-specific
        """
        profile = self.load_profile(profile_name)
        return profile.budget
    
    def requires_approval(
        self,
        profile_name: str,
        side_effect_class: str
    ) -> bool:
        """
        Check if side-effect class requires approval for profile.
        
        Per AGENTS.md Over-Automation Prohibitions:
        - Profile determines approval requirements
        - Conservative default (require approval if unknown)
        """
        try:
            profile = self.load_profile(profile_name)
            return side_effect_class in profile.approval_required
        except ValueError:
            # Conservative default: require approval
            return True
    
    def is_adapter_allowed(
        self,
        profile_name: str,
        adapter_name: str
    ) -> bool:
        """
        Check if adapter is allowed for profile.
        
        Per AGENTS.md:
        - Adapters are optional and profile-gated
        - Enables enterprise data sovereignty
        - Mock adapter always allowed (offline-first)
        """
        if adapter_name == "mock":
            return True  # Offline-first per AGENTS.md
        
        try:
            profile = self.load_profile(profile_name)
            return adapter_name in profile.allowed_adapters
        except ValueError:
            return False
    
    def list_profiles(self) -> List[str]:
        """List all available profile names."""
        return list(self.profiles.keys())
    
    def _load_custom_profiles(self) -> None:
        """Load custom profiles from config directory."""
        if not self.config_dir or not self.config_dir.exists():
            return
        
        for config_file in self.config_dir.glob("*.yaml"):
            try:
                with open(config_file) as f:
                    data = yaml.safe_load(f)
                
                profile = ProfileConfig(**data)
                self.profiles[profile.name] = profile
                logger.info(f"Loaded custom profile: {profile.name}")
                
            except Exception as e:
                logger.warning(f"Failed to load profile from {config_file}: {e}")
