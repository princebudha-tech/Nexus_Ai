"""Permission profiles and levels."""
from enum import Enum
from dataclasses import dataclass, field


class PermissionLevel(str, Enum):
    RESTRICTED = "restricted"
    STANDARD = "standard"
    ELEVATED = "elevated"


@dataclass(frozen=True, slots=True)
class PermissionProfile:
    name: str
    level: PermissionLevel
    blocked_action_types: tuple[str, ...] = field(default_factory=tuple)


# Predefined profiles
RESTRICTED_PROFILE = PermissionProfile(
    name="restricted",
    level=PermissionLevel.RESTRICTED,
    blocked_action_types=(
        "delete_app",
        "power_state",
        "delete_file",
        "deploy_code",
    )
)

STANDARD_PROFILE = PermissionProfile(
    name="standard",
    level=PermissionLevel.STANDARD,
    blocked_action_types=("deploy_code",)  # only blocks deploy_code
)

ELEVATED_PROFILE = PermissionProfile(
    name="elevated",
    level=PermissionLevel.ELEVATED,
    blocked_action_types=()
)

# Mapping from level to profile for convenience
DEFAULT_PROFILES = {
    PermissionLevel.RESTRICTED: RESTRICTED_PROFILE,
    PermissionLevel.STANDARD: STANDARD_PROFILE,
    PermissionLevel.ELEVATED: ELEVATED_PROFILE,
}