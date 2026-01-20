# QSDsan Integration Strategy

## Fail-Loud Philosophy

**NO FALLBACKS. NO SILENT FAILURES.**

This codebase integrates with QSDsan following a strict fail-loud policy:
- If QSDsan cannot be imported, the system **MUST** fail with a clear error message
- No `try/except ImportError` blocks that silently fall back to manual implementations
- Runtime patches are **REQUIRED** and verified on module import
- All modules verify QSDsan availability before proceeding

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Runtime Patches                              │
│  utils/runtime_patches.py - MUST be applied before QSDsan       │
│  Fixes: fluids.numerics.PY37 compatibility                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    QSDsan Import Verification                    │
│  utils/qsdsan_imports.py - Centralized import & verification    │
│  • Applies runtime patches                                      │
│  • Imports QSDsan components                                    │
│  • Fails loudly if anything is missing                          │
│  • Provides verify_qsdsan_ready() for downstream modules        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────┬──────────────────┬──────────────────────────┐
│ Settling Models  │ Heuristic Sizing │ Removal Efficiency       │
│ (Takács)         │ (Geometry)       │ (Correlations)           │
│                  │                  │                          │
│ WHY IMPLEMENT:   │ WHY IMPLEMENT:   │ WHY IMPLEMENT:           │
│ • Numba-compiled │ • Needs thermo   │ • Multiple sources       │
│   private func   │   setup          │   (not just QSDsan)      │
│ • Published      │ • Pure math      │ • Published correlations │
│   algorithm      │   extracted      │   from literature        │
│                  │                  │                          │
│ VERIFICATION:    │ VERIFICATION:    │ VERIFICATION:            │
│ ✓ QSDsan avail   │ ✓ QSDsan avail   │ ✓ QSDsan avail           │
│ ✓ _settling_flux │ ✓ PrimaryClar    │ ✓ verify_qsdsan_ready()  │
│   exists         │   exists         │                          │
└──────────────────┴──────────────────┴──────────────────────────┘
```

## When We Import vs. Implement

### ✅ We Import from QSDsan:
- **Full process simulation** (Stage 3): Use `PrimaryClarifier` via subprocess
- **WasteStream utilities**: Component fractionation, bulk composites
- **Standard components**: Use `create_components()` functions
- **Costing**: WaterTAP costing blocks (future integration)

### ✅ We Implement Ourselves (with verification):
- **Takács settling model**: Published algorithm (Takács et al. 1991)
  - QSDsan version is Numba-compiled private function
  - Would require Numba dependency for 2-line equation
  - **Verification**: Assert `_settling_flux` exists in QSDsan

- **Heuristic sizing**: Pure geometry/hydraulics calculations
  - Extracted from QSDsan's `PrimaryClarifier._design()` method
  - QSDsan version requires full BioSTEAM setup (Components, thermo)
  - **Verification**: Assert `PrimaryClarifier` exists in QSDsan

- **Removal correlations**: Industry-standard models from literature
  - Metcalf & Eddy, WEF MOP 8, BSM2 Otterpohl
  - QSDsan implements some, but tied to specific SanUnit classes
  - We combine multiple sources for industrial applications
  - **Verification**: verify_qsdsan_ready()

## Implementation Details

### Runtime Patches (`utils/runtime_patches.py`)

Copied from `anaerobic-design-mcp/utils/runtime_patches.py`:

```python
def ensure_py37_flag():
    """Patch fluids.numerics.PY37 for thermo<=0.4.2 compatibility."""
    import fluids.numerics
    if not hasattr(fluids.numerics, "PY37"):
        fluids.numerics.PY37 = True
```

**Issue**: fluids>=1.2 removed PY37, but thermo<=0.4.2 (QSDsan dependency) still checks for it.
**Solution**: Inject the flag at runtime before QSDsan imports.

### QSDsan Imports (`utils/qsdsan_imports.py`)

Centralized import module that:
1. Applies runtime patches
2. Imports QSDsan components
3. Verifies imports succeeded
4. Fails loudly with clear error messages

```python
from utils.runtime_patches import apply_all_patches
apply_all_patches()

try:
    from qsdsan import WasteStream, System, sanunits
    from qsdsan.sanunits import PrimaryClarifier
    from qsdsan.sanunits._clarifier import _settling_flux
except ImportError as e:
    raise ImportError(
        f"Failed to import QSDsan: {e}\n\n"
        "This is a CRITICAL ERROR. QSDsan must be available.\n"
        "DO NOT add fallback logic. Fix the dependency issue."
    ) from e
```

### Module Verification Pattern

Every module that implements algorithms follows this pattern:

```python
"""
Module docstring with clear explanation of:
- What we implement
- Why we implement it (vs importing)
- Reference to QSDsan source
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Box with detailed rationale]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# Verify QSDsan is available (fail loudly if not)
from utils.qsdsan_imports import verify_qsdsan_ready, RelevantClass
verify_qsdsan_ready()

# Verify upstream source exists
assert RelevantClass is not None, (
    "QSDsan's RelevantClass not found. "
    "Our implementation is based on this. "
    "If QSDsan changes, we need to update."
)

# ... implementation ...
```

## Testing

Verification tests in `tests/test_qsdsan_verification.py`:

1. **Runtime patches work**: `fluids.numerics.PY37` is set
2. **QSDsan imports work**: All components available
3. **Settling models work**: Takács implementation verified
4. **Heuristic sizing works**: Geometry calculations verified
5. **Removal efficiency works**: Correlations verified
6. **Error messages clear**: Failures provide actionable guidance

Run tests:
```bash
python tests/test_qsdsan_verification.py
```

Expected output:
```
[PASS] Runtime patches work
[PASS] QSDsan imports work (version: 1.4.2)
[PASS] Settling models work
[PASS] Heuristic sizing work
[PASS] Removal efficiency works
[PASS] Error messages are clear

ALL TESTS PASSED - System fails loudly if QSDsan unavailable
```

## Stage-Specific Integration

### Stage 1: Basis of Design
- **No QSDsan required**: Pure parameter validation
- Uses `data/default_parameters.json`
- Validates against industry standards

### Stage 2: Heuristic Sizing
- **Lightweight algorithms** extracted from QSDsan
- No BioSTEAM framework setup required
- Fast calculation for preliminary design
- **Verification**: Assert `PrimaryClarifier` exists

### Stage 3: Process Simulation
- **FULL QSDsan integration** via subprocess
- Use `PrimaryClarifier` with WasteStream
- Component-wise mass balance
- Dynamic simulation capabilities
- See `IMPLEMENTATION_PLAN.md` Week 4 for details

### Stage 4: Costing
- **WaterTAP integration** (future)
- QSDsan costing blocks
- TEA (Techno-Economic Analysis)
- See `IMPLEMENTATION_PLAN.md` Week 5 for details

## Dependency Requirements

### venv312 Requirements
```
qsdsan>=1.4.2
biosteam>=2.0.0
thermosteam>=0.4.2
fluids>=1.2.0  # With PY37 patch
numpy>=1.20.0
```

### Verification on Startup
```python
from utils.qsdsan_imports import verify_qsdsan_ready, get_qsdsan_version

# Check QSDsan is ready
verify_qsdsan_ready()
print(f"QSDsan {get_qsdsan_version()} ready")
```

## Troubleshooting

### Error: "module 'fluids.numerics' has no attribute 'PY37'"
**Cause**: Runtime patches not applied
**Fix**: Ensure `apply_all_patches()` called before QSDsan imports

### Error: "no available 'Thermo' object"
**Cause**: Trying to instantiate QSDsan units without thermo setup
**Fix**: For heuristic sizing, use extracted algorithms (Stage 2)
         For full simulation, use subprocess with proper setup (Stage 3)

### Error: "Failed to import QSDsan"
**Cause**: QSDsan not installed or dependency issues
**Fix**: Check venv312 installation: `pip list | grep -i qsdsan`
         DO NOT add fallback logic - fix the dependency

## References

- **QSDsan**: https://github.com/QSD-Group/QSDsan
- **anaerobic-design-mcp**: Reference implementation for runtime patches
- **aerobic-design-mcp**: Reference implementation for WasteStream integration
- **Takács et al. (1991)**: A dynamic model of the clarification-thickening process
- **Metcalf & Eddy (2014)**: Wastewater Engineering, 5th Ed.
- **WEF MOP 8 (2005)**: Design of Municipal Wastewater Treatment Plants
