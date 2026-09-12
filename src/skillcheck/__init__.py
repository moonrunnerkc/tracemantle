"""Deprecated public imports; uninstall the old distribution before installing TraceMantle."""
import warnings

from tracemantle import (
    Diagnostic,
    ParsedSkill,
    ParseError,
    Severity,
    ValidationResult,
    __version__,
    validate,
)

warnings.warn("skillcheck imports are deprecated; import tracemantle instead", DeprecationWarning, stacklevel=2)

__all__ = ["Diagnostic", "ParseError", "ParsedSkill", "Severity", "ValidationResult", "__version__", "validate"]
