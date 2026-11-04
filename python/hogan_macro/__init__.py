"""Hogan global macro data: explicit snapshots, native frequencies and verified bytes."""

from .client import IntegrityError, MacroData, MacroDataError, ReadOnlyQueryError

__version__ = "0.2.0"
__all__ = ["MacroData", "MacroDataError", "IntegrityError", "ReadOnlyQueryError", "__version__"]

