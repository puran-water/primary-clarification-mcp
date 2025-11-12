# Changelog

All notable changes to the Primary Clarifier MCP will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Phase 2-7: ASM2d + MCAS State Integration (Planned)
- Phase 2: Shared plant_state utilities
- Phase 3: Codex-based state estimator for mASM2d fractionation
- Phase 4: Combined state schema (mASM2d + MCAS)
- Phase 5: State converters (mASM2d ↔ MCAS)
- Phase 6: Effluent summarization tool
- Phase 7: Integration testing

### Lamella Clarifier Workflow (Planned)
- Custom SanUnit for lamella clarifiers (high-rate settling)
- Heuristic sizing based on plate spacing, angle, and surface area
- Simulation integration with QSDsan for rigorous performance modeling
- Comparison tools vs conventional circular clarifiers

### DAF (Dissolved Air Flotation) Workflow (Planned)
- Custom SanUnit for DAF systems (oil & grease removal, low-density solids)
- Heuristic sizing based on hydraulic loading rate, recycle ratio, air-to-solids ratio
- Simulation integration with empirical correlations and vendor data
- Comparison tools vs sedimentation clarifiers
- Integration with daf_kb knowledge base collection

## [0.2.0] - 2025-11-12

### Phase 1 Complete: ASM2d + MCAS State Integration

#### Added
- **Extended Basis of Design Collection** (`tools/basis_collection.py`)
  - Added 11 new water quality parameters for ASM2d + MCAS state integration:
    - Nitrogen speciation: `influent_nh4_n_mg_l`, `influent_no3_n_mg_l`, `influent_no2_n_mg_l`, `total_nitrogen_mg_n_l`
    - Dissolved oxygen & redox: `influent_do_mg_l`, `influent_orp_mv`
    - Conductivity: `specific_conductivity_us_cm`
    - Organics: `influent_toc_mg_l`, `influent_doc_mg_l`, `influent_silica_mg_l`
  - Total parameters collected: 44 fields (up from 33)

- **Smart TDS Validation** (`basis_collection.py:143-166`)
  - Ion coverage checking: only validates TDS closure when ≥80% of major ions provided
  - Relaxed tolerance: 20% (from 10%) to handle partial lab data
  - Explicit warnings when ion coverage is insufficient

- **Enhanced Next Steps Logic** (`basis_collection.py:463-481`)
  - CRITICAL warnings when `estimate_ions_from_tds=False` and no ions provided
  - Prevents silent MCAS initialization failures downstream
  - Clear guidance on ion composition requirements

- **Transient Validation Fields** (`basis_collection.py:94-96`)
  - `validation_warnings` and `validation_passed` marked as transient
  - Prevents stale validation states in serialized JSON
  - Recomputed on load via `__post_init__()`

- **Comprehensive Test Coverage** (`tests/test_basis_collection.py`)
  - Added 13 new test cases (31 → 44 tests):
    - `TestEdgeCases`: Zero flow, negative temperature, extreme values, missing required fields (4 tests)
    - `TestJSONSerialization`: String and file I/O with transient field handling (2 tests)
    - `TestIonEstimationModes`: Estimation enabled, disabled with ions, disabled without ions (3 tests)
    - `TestPartialIonCoverage`: Partial ions with/without TDS (2 tests)
    - `TestNitrogenSpeciation`: Storage and retrieval of nitrogen species (2 tests)
  - All 44 tests passing with comprehensive edge case coverage

#### Fixed
- **Critical Charge Balance Bug** (`basis_collection.py:208-211`)
  - BEFORE: `meq_l = (conc_mg_l / mw) * abs(charge) * 1000` (off by 1000×)
  - AFTER: `meq_l = (conc_mg_l / mw) * abs(charge)` (correct meq/L calculation)
  - Impact: Ca 80 mg/L now correctly calculates as 3.99 meq/L (was 3990 meq/L)
  - Identified by Codex review

- **Molecular Weight Corrections** (`basis_collection.py:182-195`)
  - NH4: 18.04 → 14.01 (changed from NH4+ ion basis to NH4-N nitrogen basis)
  - NO3: 62.00 → 14.01 (changed from NO3- ion basis to NO3-N nitrogen basis)
  - PO4: 94.97 → 30.97 (changed from PO4³⁻ ion basis to PO4-P phosphorus basis)
  - Rationale: Wastewater labs report N-basis and P-basis, not ion-basis
  - Identified by Codex review

- **JSON Deserialization with Transient Fields** (`basis_collection.py:276-285`)
  - BEFORE: `from_dict()` passed all dict keys to `__init__()`, causing TypeError
  - AFTER: Filters out transient fields (`validation_warnings`, `validation_passed`) before initialization
  - Impact: JSON loading now works correctly after making validation fields transient

#### Changed
- **Improved Exception Handling** (`basis_collection.py:433-452`)
  - Split into two catch blocks:
    - `TypeError`/`ValueError`: Expected errors from parameter validation
    - `Exception`: Unexpected errors with full traceback logging
  - More actionable error messages for users
  - Better debugging information for unexpected failures

#### Validated
- **Codex Review Approval** (2025-11-12)
  - All critical bugs fixed and verified
  - All recommended improvements implemented
  - 44/44 tests passing
  - Approval granted to proceed with Phase 2

## [0.1.0] - 2025-11-10

### Week 1 Complete: Infrastructure Foundation

#### Added
- **FastMCP Server Infrastructure** (`server.py`)
  - 11 tool registrations with complete function signatures
  - Integrated with mcp_common JobManager for background orchestration
  - Structured logging with trace ID correlation

- **Shared Packages**
  - `mcp_common` v0.1.0: Job orchestration, STDIO patching, artifact management
  - `plant_state` v0.1.0: COD/TSS fractionation utilities

- **State Management** (`core/state.py`)
  - 4-stage design workflow (Basis → Heuristic → Simulation → Economics)
  - JSON export/import with partial reset capabilities
  - Completion tracking for each stage

- **Multi-Collection Semantic Search**
  - `clarifier_kb`: Primary clarifier design guidelines
  - `daf_kb`: Dissolved air flotation knowledge
  - `misc_process_kb`: General process engineering

- **Tool Stubs** (`tools/`)
  - `basis_of_design.py`: Parameter collection (stub)
  - `heuristic_sizing.py`: Fast screening (stub)
  - `simulation.py`: Detailed simulation (stub)
  - `job_management.py`: Background job control (stub)
  - `state_management.py`: State export/import (2/5 implemented)

#### Documentation
- `README.md`: Comprehensive project overview
- `IMPLEMENTATION_PLAN.md`: 6-week roadmap (outdated, kept for reference)
- `WEEK1_SUMMARY.md`: Week 1 completion summary
- `SERVER_OUTLINE.md`: Original architecture document

---

## Version History Summary

- **v0.2.0** (2025-11-12): Phase 1 Complete - ASM2d + MCAS State Integration (30% overall progress)
- **v0.1.0** (2025-11-10): Week 1 Complete - Infrastructure Foundation (20% overall progress)

---

## Next Milestone

**Phase 2**: Shared plant_state utilities (unit conversions, charge balance, carbonate chemistry, wastewater templates)
