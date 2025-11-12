"""
QSDsan imports with mandatory runtime patches.

This module ensures that QSDsan can be imported successfully with runtime patches.
If imports fail, the system will fail loudly with a clear error message.

NO FALLBACKS. NO SILENT FAILURES.
"""

# Apply runtime patches FIRST - this MUST succeed
from utils.runtime_patches import apply_all_patches
apply_all_patches()

# Import QSDsan components - if this fails, let it fail loudly
try:
    from qsdsan import WasteStream, System, sanunits
    from qsdsan.sanunits import PrimaryClarifier, IdealClarifier
    from qsdsan.sanunits._clarifier import _settling_flux
except ImportError as e:
    raise ImportError(
        f"Failed to import QSDsan: {e}\n\n"
        "This is a CRITICAL ERROR. QSDsan must be available in venv312.\n"
        "Check that:\n"
        "1. QSDsan is installed: pip list | grep -i qsdsan\n"
        "2. Runtime patches were applied (fluids.numerics.PY37)\n"
        "3. Dependencies are correct (biosteam, thermosteam, fluids)\n\n"
        "DO NOT add fallback logic. Fix the dependency issue."
    ) from e

# Verify runtime patches worked
import fluids.numerics
assert hasattr(fluids.numerics, "PY37"), (
    "Runtime patches failed: fluids.numerics.PY37 not set.\n"
    "The apply_all_patches() function should have injected this attribute.\n"
    "Check utils/runtime_patches.py"
)

__all__ = [
    "WasteStream",
    "System",
    "sanunits",
    "PrimaryClarifier",
    "IdealClarifier",
    "_settling_flux"
]


# Expose commonly used functions
def get_qsdsan_version():
    """Get QSDsan version for diagnostics."""
    import qsdsan
    return qsdsan.__version__


def verify_qsdsan_ready():
    """
    Verify QSDsan is ready for use.

    Raises AssertionError if any components are not available.
    """
    # Check runtime patches
    assert hasattr(fluids.numerics, "PY37"), "Runtime patches not applied"

    # Check key imports
    assert WasteStream is not None, "WasteStream not available"
    assert PrimaryClarifier is not None, "PrimaryClarifier not available"
    assert _settling_flux is not None, "_settling_flux not available"

    return True
