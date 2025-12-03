"""Platform abstraction for EntropPy."""

from entroppy.core.types import MatchDirection

from .base import PlatformBackend, PlatformConstraints
from .espanso import EspansoBackend
from .qmk import QMKBackend

# Platform registry
_PLATFORMS = {
    "espanso": EspansoBackend,
    "qmk": QMKBackend,
}


def get_platform_backend(platform_name: str) -> PlatformBackend:
    """Factory function to get platform backend instance.

    Args:
        platform_name: Name of platform ('espanso', 'qmk', etc.)

    Returns:
        Platform backend instance

    Raises:
        ValueError: If platform name is unknown
    """
    platform_name = platform_name.lower()

    if platform_name not in _PLATFORMS:
        available = ", ".join(_PLATFORMS.keys())
        raise ValueError(f"Unknown platform '{platform_name}'. Available platforms: {available}")

    backend_class = _PLATFORMS[platform_name]
    return backend_class()


def list_platforms() -> list[str]:
    """Return list of supported platform names."""
    return list(_PLATFORMS.keys())


__all__ = [
    "PlatformBackend",
    "PlatformConstraints",
    "MatchDirection",
    "EspansoBackend",
    "QMKBackend",
    "get_platform_backend",
    "list_platforms",
]
