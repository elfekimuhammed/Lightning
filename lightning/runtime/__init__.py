"""Shared, platform-neutral application runtime primitives."""

from lightning.runtime.paths import (
    ProfileInfo,
    ProfilePaths,
    choose_data_root,
    create_profile,
    discover_profiles,
    legacy_database_candidates,
    resolve_profile,
    user_data_root,
)

__all__ = [
    "ProfileInfo",
    "ProfilePaths",
    "choose_data_root",
    "create_profile",
    "discover_profiles",
    "legacy_database_candidates",
    "resolve_profile",
    "user_data_root",
]
