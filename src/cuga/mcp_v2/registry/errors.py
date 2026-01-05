"""Exceptions for MCP registry loading and validation."""

from __future__ import annotations


class RegistryLoadError(Exception):
    """Raised when a registry file cannot be loaded."""


class RegistryValidationError(RegistryLoadError):
    """Raised when a registry document fails structural validation."""


class RegistryMergeError(RegistryLoadError):
    """Raised when registry fragments conflict during merge."""
