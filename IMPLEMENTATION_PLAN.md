# Primary Clarifier MCP - Implementation Plan

**Status**: Week 1 Complete, Phase 2 Complete (Mechanistic Removal Models)
**Timeline**: 5 weeks (normalized from original 6 weeks)
**Last Updated**: 2025-11-11 (Updated with Phase 2 completion and refined mechanistic layer plan)

---

## 1. Executive Summary

### 1.1 Normalized Workflow Pattern

This MCP server follows the standardized workflow pattern established across all design MCPs:

```
Stage 1: Basis of Design → Stage 2: Heuristic Sizing → Stage 3: Process Simulation → Stage 4: Economic Analysis
```

**Key Characteristics**:
- Composite parameters as canonical interface (TSS, COD, BOD, TKN, TP)
- Optional ASM2d/ADM1 state variables on request (via shared plant_state package)
- Background job execution for all stages using JobManager
- Multi-collection semantic search (clarifier_kb, daf_kb, misc_process_kb)
- State persistence with scoped reset capability

### 1.2 Timeline: 5 Weeks (Revised)

**Original Plan**: 6 weeks with separate subprocess strategies per stage
**Revised Plan**: 5 weeks with consistent JobManager architecture

**Changes**:
- Consolidated job management reduces implementation time by 1 week
- Shared infrastructure packages (mcp_common, plant_state) accelerate development
- Multi-collection semantic search provides broader knowledge access

### 1.3 Key Architectural Decisions

1. **JobManager for All Operations**: Sizing, simulation, and costing all use JobManager (no cherry-picking of strategies)
2. **Shared Infrastructure Packages**: Extract common patterns to mcp_common and plant_state
3. **Multi-Collection KB**: Expand from single clarifier_kb to 3 collections for richer context
4. **Structured Logging from Day 1**: Trace IDs and context-aware logging for debugging
5. **Artifact Pattern for CLI Wrappers**: RO-style deterministic run IDs for CLI subprocess isolation

---

## 2. Architecture Overview

### 2.1 Reference MCPs Used as Templates

| MCP | Pattern Adopted | Rationale |
|-----|-----------------|-----------|
| **anaerobic-design-mcp** | JobManager, STDIO patch, lazy imports | Proven background job orchestration |
| **aerobic-design-mcp** | mcp_stdio_patch.py, state structure | FastMCP compatibility fixes |
| **ro-design-mcp** | Artifacts.py for deterministic run IDs | CLI wrapper pattern for subprocess isolation |
| **degasser/ix-design-mcp** | State export/import, multi-mode simulation | State persistence and flexibility |

### 2.2 Shared Infrastructure

#### A. mcp_common Package (v0.1.0)

**Location**: `/mnt/c/Users/hvksh/mcp-servers/mcp_common/`

**Purpose**: Single source of truth for shared infrastructure across all MCPs

**Components**:
- `job_manager.py` - Background job orchestration (from anaerobic-design-mcp)
- `mcp_stdio_patch.py` - STDIO buffering fix (from aerobic-design-mcp)
- `artifacts.py` - Deterministic run IDs (from ro-design-mcp)
- `version.py` - Version tracking

**Impact**: No more copying code per MCP, explicit versioning, easier maintenance

#### B. plant_state Package (v0.1.0)

**Location**: `/mnt/c/Users/hvksh/mcp-servers/plant_state/`

**Purpose**: Bidirectional state conversion for upstream/downstream MCP integration

**Components**:
- `fractionation.py` - COD/TSS fractionation (IMPLEMENTED in Week 1)
- `asm2d_converter.py` - ASM2d state variables (STUB - Phase 2)
- `adm1_converter.py` - ADM1 state variables (STUB - Phase 2)
- `mcas_tracker.py` - Major cations/anions tracking (STUB - Phase 2)

**Usage**:
- Primary clarifier: Composite parameters → ASM2d state (optional)
- Aerobic MCP: ASM2d state input/output
- Anaerobic MCP: ADM1 state input/output

### 2.3 State Management Approach

**State Structure** (`core/state.py`):

```python
@dataclass
class ClarifierDesignState:
    basis_of_design: Optional[Dict] = None      # Stage 1
    heuristic_config: Optional[Dict] = None     # Stage 2
    simulation_results: Optional[Dict] = None   # Stage 3
    economics: Optional[Dict] = None            # Stage 4
```

**Features**:
- Singleton pattern (`clarifier_design_state`)
- Partial reset capability (scope: "all", "simulation", "costing")
- Serialization (to_dict/from_dict)
- Completion status tracking
- Next steps recommendation engine

### 2.4 Background Job Execution Pattern

**JobManager Integration** (from mcp_common):

```python
from mcp_common.job_manager import JobManager

# Stage 2: Heuristic Sizing
job_id = job_manager.start_job(
    "sizing",
    target=run_sizing_cli,
    kwargs={...}
)

# Poll for completion
status = job_manager.get_job_status(job_id)

# Retrieve results
results = job_manager.get_job_results(job_id)
```

**CLI Wrapper Pattern** (RO artifacts approach):
- Each stage has a CLI script (sizing_cli.py, simulate_cli.py, costing_cli.py)
- Deterministic run IDs from artifacts.py
- Results written to jobs/{run_id}/ directory
- JobManager orchestrates subprocess execution

### 2.5 Open Source Software (OSS) Integration Strategy

**Based on Codex analysis (2025-11-10)**: Review of QSDsan, WaterTAP, AguaClara, PySWMM, and other relevant repositories

#### A. QSDsan Integration

**Repository**: `QSD-Group/QSDsan` (BSD 3-Clause)

**Models Available**:

1. **PrimaryClarifier** (`qsdsan/sanunits/_clarifier.py:1230-1542`) - ✅ HIGH PRIORITY
   - Industrial design + costing with SOR/SLR checks
   - Geometric calculations, center-feed sizing
   - Concrete/steel quantity takeoffs
   - **Action**: Extract `_design()` and `_cost()` logic to `tools/heuristic_sizing.py`
   - **Timeline**: Week 3

2. **IdealClarifier** (`qsdsan/sanunits/_clarifier.py:884-990`) - ✅ HIGH PRIORITY
   - Fast algebraic solids splitter (no ODE solver)
   - Pure NumPy, lightweight
   - **Action**: Use for Week 2 heuristic sizing and empirical simulation fallback
   - **Timeline**: Week 3

3. **Takács Settling Flux** (`qsdsan/sanunits/_clarifier.py:57-63`) - ✅ IMMEDIATE
   - Core settling algorithm: `v = v_max*(exp(-rh*X) - exp(-rp*X))`
   - ~15 lines, numpy only
   - **Action**: Extract to `utils/settling_models.py`
   - **Timeline**: Week 3 (Quick Win)

4. **nCOD Removal Correlations** (`qsdsan/sanunits/_clarifier.py:993-1002`) - ✅ IMMEDIATE
   - BSM2-based COD removal vs. particulate fraction and HRT
   - ~10 lines
   - **Action**: Extract to `utils/removal_efficiency.py`
   - **Timeline**: Week 3 (Quick Win)

5. **FlatBottomCircularClarifier** (`qsdsan/sanunits/_clarifier.py:71-203`) - ⏸️ PHASE 2
   - Dynamic N-layer model with Numba/SciPy
   - Full ASM/ADM state vector integration
   - **Action**: Keep in subprocess for rigorous validation mode
   - **Timeline**: Phase 2

6. **PrimaryClarifierBSM2** (`qsdsan/sanunits/_clarifier.py:1004-1213`) - ⏸️ PHASE 2
   - BSM2 compliance model
   - Requires ASM state vectors
   - **Action**: Subprocess integration after plant_state ASM converters complete
   - **Timeline**: Phase 2

**Extraction Strategy**:
- **Extract**: Lightweight algorithms (Takács, nCOD, PrimaryClarifier sizing/costing)
- **Subprocess**: Heavy models requiring Numba/SciPy (FlatBottom, BSM2)
- **Reference**: Keep provenance in docstrings citing QSDsan file paths

#### B. WaterTAP Integration

**Repository**: `watertap-org/watertap` (BSD 3-Clause)

**Costing Models** (`watertap/costing/unit_models/clarifier.py:30-223`):
- Pyomo-based clarifier costing blocks
- Circular/rectangular/primary unit economics
- A-B-C capital regressions + electricity factoring
- IDAES costing framework integration

**Action**:
- Week 4: Import WaterTAP costing block
- Week 5: Map SOR/HRT outputs to WaterTAP parameters (`surface_area`, `flow_in`)
- Use as single source of truth for CAPEX/OPEX (avoid duplicate logic)

**ROI**: HIGH - Plugs into established TEA framework, avoids maintaining regressions

#### C. PySWMM Integration

**Repository**: `pyswmm/pyswmm` (BSD 3-Clause)

**Functionality**:
- Pythonic control of SWMM5 hydraulic networks
- Dynamic inflow stepping, binary output inspection
- Realistic peak factor derivation from storm events

**Action**:
- Week 2: Optional peak factor validation using SWMM time series
- Keep SWMM `.inp` templates in `data/`
- Run `PySWMM Simulation` to compute max hourly flow before heuristics

**ROI**: HIGH - Generates realistic hydraulic loading, avoids flat peaking factors

**Implementation**: Opt-in cached analysis (not required for every run)

#### D. AguaClara Integration

**Repository**: `AguaClara-Reach/aguaclara` (MIT)

**Modules** (`aguaclara/design/sed.py`, `aguaclara/design/sed_tank.py`):
- Plate-settler (lamella) design algorithms
- Default upflow velocity (1 mm/s), diffuser geometry
- Lamella spacing and manifold design

**Action**:
- Week 3: Seed `data/lamella_defaults.json` with AguaClara parameters
- Week 5: Add lamella option to heuristic sizing
- Adapt formulas while keeping Pint unit helpers out of hot path

**ROI**: MEDIUM - Ready-made lamella templates for industrial geometry

#### E. Not Recommended

**PooPyLab** (`toogad/PooPyLab_Project`) - GPL v3 License
- Excellent reference implementation for clarifier splitters
- **Cannot vendor code** due to GPL license conflict
- **Action**: Reference only - codify equivalent logic independently

---

## 3. Implementation Timeline (5 Weeks)

### Week 1: Infrastructure Foundation ✅ COMPLETE

**Status**: 100% complete (all 7 tasks done)

**Deliverables**:
- [x] mcp_common package created and documented (500 lines)
- [x] plant_state package structure established (600 lines)
- [x] server.py with 11 tool registrations (354 lines)
- [x] ClarifierDesignState with 4-stage structure (167 lines)
- [x] Structured logging with trace IDs (208 lines)
- [x] Complete tool stub infrastructure (5 modules)
- [x] Multi-collection semantic search configured (.mcp.json)

**Files Created**: 23 files, ~2,110 lines of code

**Key Achievements**:
- Shared infrastructure packages eliminate code duplication
- Structured logging enables debugging across background jobs
- Tool stubs define clear implementation path for Weeks 2-5
- Multi-collection search provides broader knowledge access

**Reference**: See WEEK1_SUMMARY.md for detailed completion report

---

### Phase 2: Mechanistic Removal Models ✅ COMPLETE

**Status**: 100% complete (all critical tasks done)

**Timeline**: Completed ahead of original Week 2-3 schedule

#### What Was Built:

**Phase 2.1: PHREEQC Metal Speciation (✅ Complete)**
- Created `utils/chemical_speciation.py` with PHREEQC integration (366 lines)
- Function: `metal_speciation()` - calculates pH, alkalinity, precipitated metals, ionic strength
- Uses `phreeqpython` for equilibrium chemistry
- Dual ionic strength exposure:
  - Pre-precipitation (monotonic with dose) for dose-response
  - Equilibrium (from PHREEQC) for validation
- Safety clamps on precipitated metal calculations
- Test suite: `tests/test_chemical_speciation.py` (17 tests passing)

**Phase 2.2: Empirical Dose-Response Models (✅ Complete)**
- Created `utils/dose_response.py` with Hill equation models (520 lines)
- TSS removal: Hill function with ionic strength → attachment efficiency
- BOD removal: Particulate (tracks TSS) + soluble (independent dose-response)
- Three parameter sets: municipal_baseline, industrial_high_tss, cept_optimized
- Deep copy for parameter sets to prevent mutation
- Test suite: `tests/test_dose_response.py` (23 tests passing)

**Phase 2.3: Integration with BSM2 Models (✅ Complete)**
- Updated `utils/removal_efficiency.py` with dose-response integration (major refactor)
- Modified `tss_removal_bsm2()` to return comprehensive dict:
  - removal_efficiency (final removal)
  - baseline_removal (BSM2 Otterpohl)
  - chemically_enhanced_removal (dose-response)
  - ionic_strength_mol_l (chemistry state)
  - enhancement_source (none or dose_response)
- Added zero-dose guard: only activates chemistry if doses > 0
- Updated `calculate_removal_profile()` with chemistry parameter
- Removed all backward compatibility (`with_coagulation` parameter)
- Fixed `calc_f_i()` call signature (3 parameters, not 4)
- Test suite: `tests/test_integration_phase23.py` (17 tests passing)

**Architecture Implemented:**
```
┌─────────────────────────────────────────────────────┐
│         Primary Clarifier Removal Models            │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Tier 1: Baseline (BSM2 Otterpohl)                 │
│  ├─ Hydraulic settling                             │
│  ├─ HRT-dependent removal                          │
│  └─ Validated against full-scale data              │
│                                                      │
│  Tier 2: Dose-Response (Empirical Hill)            │
│  ├─ Ionic strength from dose (monotonic)           │
│  ├─ Hill equation: y = y_min + (y_max-y_min)×...   │
│  ├─ Parameter sets: municipal/industrial/CEPT      │
│  └─ Coupled TSS + BOD (pBOD + sBOD)                │
│                                                      │
│  Blending: removal = max(baseline, enhanced)        │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**Validation:**
- All 63 tests passing (17 chemical speciation + 23 dose-response + 17 integration + 6 QSDsan verification)
- Codex review completed (3 rounds of feedback)
- Critical bugs fixed:
  - Zero-dose enhancement bug
  - API breaking changes simplified
  - Double-counting risk eliminated
  - Test location and format corrected

**Deliverables:**
- `utils/chemical_speciation.py` (366 lines)
- `utils/dose_response.py` (520 lines)
- Updated `utils/removal_efficiency.py` (major refactor)
- `tests/test_chemical_speciation.py` (17 tests)
- `tests/test_dose_response.py` (23 tests)
- `tests/test_integration_phase23.py` (17 tests)
- `PHASE_2_3_SUMMARY.md` (documentation)
- `PHASE_2_3_FIXES_SUMMARY.md` (critical fixes)
- `BASIS_OF_DESIGN_REFACTORING_PLAN.md` (future work)

**Reference**: See PHASE_2_3_SUMMARY.md and PHASE_2_3_FIXES_SUMMARY.md for detailed completion reports

**Impact**: Dose-responsive removal models fully functional and validated, ready for integration with heuristic sizing and simulation tools.

---

### Approved Refinement: Two-Tier Mechanistic Layer

**Status**: Phase 2 complete (Empirical Tier), Physics Tier deferred to Week 4-5

Based on Codex validation and discovery of reusable OSS components, the mechanistic removal layer follows a two-tier architecture:

```
User specifies dose + chemistry
        ↓
PHREEQC speciation (always) ✅ IMPLEMENTED
        ↓
├─ TIER 1: Empirical (default, fast) ✅ IMPLEMENTED
│  └─ Hill/logistic I→alpha→removal
│     └─ Blending with BSM2 baseline
│
└─ TIER 2: Mechanistic (optional, rigorous) ⏸️ FUTURE
   └─ DLVO: I,zeta→alpha
      └─ PBM: alpha,G,t→d32
         └─ Settling: d32→v_max_eff→removal
            └─ DAF: A/S,d32→attachment→removal
```

**Tier 1 Implementation (✅ Complete):**
- PHREEQC metal speciation for ionic strength calculation
- Hill equation dose-response: `eta = eta_min + (eta_max - eta_min) / (1 + (I/I_50)^n)`
- Three calibrated parameter sets (municipal, industrial, CEPT)
- Zero-dose guard prevents spurious enhancement
- Blending with BSM2 baseline ensures chemistry never degrades performance

**Tier 2 Roadmap (Week 4-5):**

**PHASE 3: Physics Tier - Mechanistic Modules (8-12 hours)**

3.1 **DLVO Attachment Efficiency (3-4 hours)**
- New file: `utils/dlvo_attachment.py`
- Library: ContactEngineering/Adhesion (MIT license)
  - Repo: https://github.com/ContactEngineering/Adhesion
  - Files: `Adhesion/Interactions/VdW82.py`, `Adhesion/Interactions/Coulomb.py`
- Function: `dlvo_alpha(ionic_strength, zeta_particle, zeta_fluid, hamaker_const)`
- Implementation:
  ```python
  from Adhesion.Interactions import VdW82, Coulomb
  # Compute U_vdw + U_edl across gap → max barrier height
  alpha = exp(-barrier_height / kT)
  ```
- Returns: Collision efficiency α (0-1)

3.2 **Population Balance Model for Floc Growth (4-5 hours)**
- New file: `utils/floc_model.py`
- Library Options:
  - Option 1: pmocz/Smoluchowski (MIT, sectional method)
    - Repo: https://github.com/pmocz/Smoluchowski
    - File: `smoluchowski.py`
    - Kernel: Configure orthokinetic `K = (x^(1/3) + y^(1/3))^3`
  - Option 2: rktherala27/particle-transport-methods (MIT, moment methods)
    - Repo: https://github.com/rktherala27/particle-transport-methods
    - Files: `DQMoM.py`, `QMoM.py`
    - For cases where full PSD not needed (only d32)
- Function: `pbm_floc(alpha, G_velocity, t_mix, psd_in)` → `{d32, psd_out}`
- Returns: Sauter mean diameter d32 for settling calculations

3.3 **Wire DLVO→PBM→Settling (1-2 hours)**
- Update: `tss_removal_bsm2()` to accept optional `d32_floc`
- Update: `takacs_settling_velocity()` to accept optional `d32_floc`
- Correlation: `v_max_effective = v_max_base × (d32_floc / d32_ref)^m`
- Feature flag: Use empirical if d32 not provided, mechanistic if provided

3.4 **DAF A/S Calculator & Capture Model (1-2 hours)**
- New file: `utils/daf_model.py`
- Library: CalebBell/thermo (MIT) for Henry's constants
  - Repo: https://github.com/CalebBell/thermo
  - File: `thermo/Interaction Parameters/ChemSep/henry.json`
- Function: `as_calculator(pressure_kPa, recycle_pct, temp_c, salinity)`
  - Uses Henry's law + mass balance → A/S ratio (kg air / kg solids)
  - Typical range check: 0.02-0.06 for clarification
- Function: `daf_capture(as_ratio, psd_bubbles, psd_floc, alpha_bp)`
  - Filtration-analogue: collision × attachment
  - Returns: `{eta_tss, eta_og, eta_bod}`

**Dependencies for Physics Tier (Week 4):**
```bash
pip install ContactEngineering-Adhesion  # MIT - DLVO
pip install thermo                       # MIT - Henry's constants
# Choose ONE of:
pip install git+https://github.com/pmocz/Smoluchowski.git      # MIT - PBM sectional
pip install git+https://github.com/rktherala27/particle-transport-methods.git  # MIT - PBM moments
```

**Validation Strategy:**
- Default parameter sets published as YAML config
- Consultants can override priors (Codex recommendation)
- Reality checks:
  - Fe doses: 30-50 mg/L → 70-85% TSS removal (WaterTAP, MIT jar tests)
  - Polymer: 0.5-3 mg/L → +5-15% enhancement
  - pH drop: -0.3 to -1.0 per 50 mg/L Fe/Al
  - Alkalinity: ~0.5 meq/L per 10 mg/L Fe

**Scope Decision Point**: After Week 3 sizing integration, assess:
- If empirical tier meets needs → defer Phase 3 to post-Week 5
- If mechanistic required → proceed with Phase 3 in Week 4-5

**Benefits:**
- MVP (Tier 1) delivers 80% value in Phase 2 (complete)
- Physics (Tier 2) drops in Week 4-5 without breaking MVP
- Users choose complexity vs. speed

---

### Week 2: Basis of Design + Validation (DEFERRED)

**Focus**: Complete Stage 1 (Basis of Design) with validation and testing

**Status**: In Progress

#### Tasks:

1. **Implement `tools/basis_of_design.py` (2 days)**
   - Parameter collection:
     - Hydraulic: flow_m3_d, peak_factor
     - Influent: TSS, VSS, COD, BOD5, TKN, TP, oil & grease, pH
     - Operating: temperature_c
     - Targets: removal efficiencies, underflow solids concentration
     - Chemicals: coagulant_type, polymer_type
   - Validation logic:
     - Range checks (e.g., TSS 50-5000 mg/L, temperature 5-40°C)
     - Consistency checks (VSS/TSS ratio 0.65-0.85, COD fractionation)
     - Industrial adaptations (high TSS >500 mg/L warnings)
   - Store in `clarifier_design_state.basis_of_design`

2. **Create Data Files (1 day)**
   - `data/default_parameters.json`:
     ```json
     {
       "surface_overflow_rate_m3_m2_d": {"min": 30, "typical": 40, "max": 50},
       "solids_loading_rate_kg_m2_d": {"min": 100, "typical": 125, "max": 150},
       "hydraulic_retention_time_h": {"min": 1.5, "typical": 2.0, "max": 2.5},
       "removal_efficiency_tss_pct": {"min": 50, "typical": 60, "max": 70},
       "removal_efficiency_bod_pct": {"min": 25, "typical": 32, "max": 40}
     }
     ```
   - `data/validation_rules.json`:
     - Parameter ranges by wastewater type (municipal, industrial)
     - Consistency check rules
     - Warning thresholds

3. **Unit Tests (1 day)**
   - `tests/test_basis_validation.py`:
     - Golden tests with hand-calculated examples
     - Parameter validation edge cases (out of range, invalid combinations)
     - State persistence tests (save/load basis)
   - Coverage target: >80% for basis_of_design.py

4. **Exercise Job Lifecycle (1 day)**
   - Test JobManager with fake payloads:
     - Job creation and ID generation
     - Status tracking (queued → running → completed)
     - Result retrieval
     - Error handling and crash recovery
   - Verify job_management.py tools:
     - `get_job_status(job_id)`
     - `get_job_results(job_id)`
     - `list_jobs(status_filter)`
     - `terminate_job(job_id)`

**Deliverables**:
- Fully functional `collect_clarifier_basis()` tool
- Validated basis stored in design state
- Unit test suite with >80% coverage
- Job lifecycle verification tests

**Testing Approach**:
- 3-tier testing: Golden (hand-calculated), property-based (hypothetical ranges), lifecycle (job manager)
- Example golden test: Municipal WWTP with 300 mg/L TSS, 5000 m³/d flow
- Example property test: High TSS industrial case (1500 mg/L) triggers warnings

**Files to Create**:
- `tools/basis_of_design.py` (implementation)
- `data/default_parameters.json`
- `data/validation_rules.json`
- `tests/test_basis_validation.py`
- `tests/test_job_lifecycle.py`

---

### Week 3: Heuristic Sizing + QSDsan Algorithm Extraction

**Focus**: Complete Stage 2 (Heuristic Sizing) with JobManager integration + Extract QSDsan algorithms

**REVISED**: Accelerated timeline based on Codex analysis - pull in algorithm extraction from Week 4

#### Tasks:

1. **Extract QSDsan Algorithms (1 day)** - ✅ QUICK WIN
   - **Extract Takács settling flux** (`qsdsan/sanunits/_clarifier.py:57-63`):
     - Create `utils/settling_models.py`
     - Implement `takacs_settling_velocity(X, v_max, rh, rp)`
     - Add docstring citing QSDsan source
     - ~15 lines, numpy only
   - **Extract nCOD removal correlations** (`qsdsan/sanunits/_clarifier.py:993-1002`):
     - Add to `utils/removal_efficiency.py`
     - Implement `ncod_removal(nCOD, HRT, particulate_fraction)`
     - ~10 lines
   - **Port PrimaryClarifier sizing logic** (`qsdsan/sanunits/_clarifier.py:1422-1500`):
     - Extract `_design()` method to `tools/heuristic_sizing.py`
     - SOR-based area calculation
     - Center-feed diameter checks
     - Number of basins calculation
     - ~110 lines
   - **Seed AguaClara lamella defaults**:
     - Create `data/lamella_defaults.json`
     - Extract parameters from `aguaclara/design/sed_tank.py:45-88`
     - Upflow velocity, plate angle, diffuser spacing

2. **Implement `cli/sizing_cli.py` (2 days)**
   - CLI wrapper for heuristic sizing calculations
   - Artifact pattern from ro-design-mcp:
     - Deterministic run IDs using artifacts.py
     - Results written to jobs/{run_id}/sizing_results.json
   - Calculations WITHOUT simulation:
     - Clarifier geometry (diameter, depth, volume)
     - Surface overflow rate (SOR) and solids loading rate (SLR) checks
     - Hydraulic retention time (HRT)
     - Weir loading rate
     - Number of units (minimum 2 for redundancy)
   - Chemical dosing (if requested):
     - Coagulant dose (alum, ferric chloride)
     - Polymer dose (anionic, cationic)
     - Annual consumption and cost
   - Power requirements:
     - Flash mixing power (G = 700-1000 s⁻¹)
     - Flocculation power (tapered G = 20-80 s⁻¹)
     - Scraper mechanism power (lookup table by diameter)
     - Sludge pump power
   - Sludge production:
     - Volume and mass calculations
     - Underflow concentration

2. **Integrate with JobManager (1 day)**
   - Update `tools/heuristic_sizing.py`:
     - Use JobManager to start background job
     - Execute sizing_cli.py in subprocess
     - Poll for completion
     - Return job_id to user
   - Structured logging:
     - Trace IDs for job correlation
     - Log sizing parameters and results
     - Error tracking and recovery

3. **Create Data Files (1 day)**
   - `data/scraper_power_curves.json`:
     - Circular clarifier power by diameter (10-60m)
     - Rectangular clarifier power by area
   - `data/chemical_properties.json`:
     - Alum: molecular weight, density, typical dose, cost
     - Ferric chloride: properties and cost
     - Polymers: types and dosing ranges

4. **Unit Tests (1 day)**
   - `tests/test_heuristic_sizing.py`:
     - Golden test: 5 MGD municipal WWTP (expected diameter ~40m, SOR ~40 m³/m²/d)
     - Industrial high TSS case (1500 mg/L, SLR warning expected)
     - Chemical dosing calculations (verify stoichiometry)
     - Power calculations (flash mixing, flocculation, scraper)
   - Integration test: Full sizing workflow (basis → sizing → results)

**Deliverables**:
- Functional `size_clarifier_heuristic()` tool with JobManager
- CLI wrapper (sizing_cli.py) with artifact pattern
- Chemical dosing and power calculation modules
- Unit and integration tests with >80% coverage

**Files to Create**:
- `cli/sizing_cli.py` (CLI wrapper)
- `tools/heuristic_sizing.py` (implementation)
- `utils/geometry_calculations.py`
- `utils/chemical_dosing.py`
- `utils/power_calculations.py`
- `utils/sludge_calculations.py`
- `data/scraper_power_curves.json`
- `data/chemical_properties.json`
- `tests/test_heuristic_sizing.py`
- `tests/test_integration_basis_sizing.py`

---

### Week 4: Empirical Simulation + WaterTAP Integration

**Focus**: Complete Stage 3 (Process Simulation) with calibration + WaterTAP costing integration

**REVISED**: Refocused on calibration and integration (algorithm extraction moved to Week 3)

#### Tasks:

1. **Calibrate Extracted Algorithms (1 day)**
   - **Validate Takács settling model**:
     - Test against QSDsan reference examples (`qsdsan/sanunits/_clarifier.py:1251-1314`)
     - Verify settling velocity predictions within ±5%
     - Document parameter ranges (v_max, rh, rp typical values)
   - **Validate nCOD removal correlations**:
     - Compare against BSM2 clarifier outputs
     - Test temperature correction factors
     - Validate HRT dependencies
   - **Regression tests**:
     - Create fixtures from QSDsan doctest streams
     - Add golden tests for known scenarios
     - Property-based tests for mass conservation

2. **Integrate WaterTAP Costing (1 day)**
   - Import WaterTAP clarifier costing block:
     - `from watertap.costing.unit_models.clarifier import cost_circular_clarifier`
   - Map our outputs to WaterTAP inputs:
     - `surface_area` from heuristic sizing
     - `flow_in` from basis of design
     - `chemical_flow_mass` from chemical dosing
   - Create costing wrapper in `utils/watertap_costing.py`
   - Test CAPEX/OPEX calculations against known values

3. **Add PySWMM Peak Factor Validation (Optional - 0.5 day)**
   - Create `utils/hydraulic_loading.py`
   - Import PySWMM for storm event simulation
   - Generate time series from SWMM `.inp` templates
   - Compute max hourly flow for SOR validation
   - Cache results to avoid repeated simulations
   - Mark as optional (not required for baseline runs)

4. **Implement `cli/simulate_cli.py` (1.5 days)**
   - CLI wrapper for empirical simulation
   - Artifact pattern for results storage
   - Simulation mode: "empirical" (fast, correlation-based)
   - Removal efficiency modeling:
     - TSS removal: Function of SOR, SLR, particle settling velocity
     - BOD/COD removal: Particulate vs. soluble fractionation
     - TP removal: Baseline (10-20%) + enhanced with chemicals (70-90%)
     - Oil & grease removal: Free-floating vs. emulsified
     - TKN removal: Organic nitrogen in particulates
   - Effluent calculations:
     - Component-wise mass balance
     - Particulate vs. soluble fractionation (use plant_state.fractionation)
     - Optional ASM2d state output (if requested)
   - Sludge underflow:
     - Concentration (2-6% solids typical)
     - Volume and mass
     - Characteristics (VSS/TSS, COD, nutrients)

2. **Implement Removal Correlations (1 day)**
   - `utils/removal_correlations.py`:
     - TSS removal vs. SOR/SLR (empirical curves from literature)
     - BOD/COD removal correlations
     - Temperature effects (Arrhenius-type corrections)
     - Particle size distribution effects
     - Enhanced removal with coagulation (dose-response curves)

3. **Integrate Static Costing (1 day)**
   - `utils/economic_calculations.py`:
     - CAPEX estimation:
       - Clarifier basin (concrete volume, excavation)
       - Mechanical equipment (scraper, mixers, pumps)
       - Chemical feed systems
       - Instrumentation and control
     - OPEX estimation:
       - Chemical costs (annual consumption × unit cost)
       - Energy costs (power × runtime × electricity rate)
       - Maintenance (5-7% of CAPEX annually)
       - Sludge disposal costs
     - LCOW calculation:
       - 20-year project lifetime
       - 8% discount rate
       - Net present value (NPV)

4. **Unit Tests (1 day)**
   - `tests/test_simulation.py`:
     - Golden test: Municipal case with known removal efficiencies
     - Industrial case: High TSS with coagulation
     - Effluent validation: Mass balance closure
     - ASM2d state output test (if requested)
   - Integration test: Basis → sizing → simulation workflow

**Deliverables**:
- Functional `simulate_clarifier_system()` tool with empirical mode
- CLI wrapper (simulate_cli.py) with artifact pattern
- Removal correlation module with literature-based models
- Static costing integration
- Unit and integration tests with >80% coverage

**Files to Create**:
- `cli/simulate_cli.py` (CLI wrapper)
- `tools/simulation.py` (implementation)
- `utils/removal_correlations.py`
- `utils/settling_theory.py`
- `utils/economic_calculations.py`
- `data/removal_curves.json`
- `data/cost_correlations.json`
- `tests/test_simulation.py`
- `tests/test_integration_full_workflow.py`

---

### Week 5: WaterTAP Costing Upgrade (Phase 1.5)

**Focus**: Replace static costing with WaterTAP coefficients via JobManager

#### Tasks:

1. **Extract WaterTAP Costing Coefficients (2 days)**
   - Research WaterTAP clarifier costing module:
     - Repository: watertap-org/watertap
     - Module: `watertap/costing/unit_models/clarifier.py`
     - Coefficients for circular, rectangular, lamella clarifiers
   - Extract to local data files:
     - `data/watertap_clarifier_costs.json`:
       - Capital cost correlations (diameter/area scaling)
       - Scraper power curves
       - Installation factors
       - Regional cost indices
   - Document attribution:
     - Source: WaterTAP (watertap-org/watertap)
     - License: DOE open source with attribution required
     - Citation in all outputs

2. **Implement Costing CLI Wrapper (2 days)**
   - `cli/costing_cli.py`:
     - CLI wrapper for WaterTAP-based costing
     - Artifact pattern for results storage
     - JobManager integration (subprocess isolation)
   - Calculations:
     - CAPEX using WaterTAP correlations
     - OPEX with detailed breakdowns (chemicals, energy, maintenance, sludge)
     - LCOW with NPV over 20-year lifetime
   - Update `tools/simulation.py`:
     - Add JobManager call for costing_cli.py
     - Handle costing as separate background job (can be chained or standalone)

3. **Crash Recovery Testing (1 day)**
   - Test job crash scenarios:
     - Simulate crash during sizing (incomplete results)
     - Simulate crash during simulation (partial output)
     - Simulate crash during costing (missing data)
   - Verify JobManager recovery:
     - Job status reflects crash (status: "failed")
     - Error messages logged with trace IDs
     - Ability to retry failed jobs
   - Test state persistence:
     - Partial results saved before crash
     - State can be restored from file
     - Reset capability for failed stages

**Deliverables**:
- WaterTAP costing coefficients extracted and documented
- Functional costing_cli.py with JobManager integration
- Crash recovery tests passing
- Full workflow (basis → sizing → simulation → costing) operational

**Files to Create**:
- `cli/costing_cli.py` (CLI wrapper)
- `utils/watertap_costing.py`
- `data/watertap_clarifier_costs.json`
- `tests/test_costing.py`
- `tests/test_crash_recovery.py`
- `tests/test_end_to_end_workflow.py`

---

## 3.6 Quick Wins (Immediate Actions)

**Based on Codex OSS analysis** - High-ROI tasks that can be completed immediately:

### A. Extract Takács Settling Flux (30 minutes)
```python
# Create utils/settling_models.py
def takacs_settling_velocity(X, v_max=474, rh=0.000576, rp=0.00286, X_min=0):
    """
    Takács double-exponential settling velocity model.

    Source: QSDsan qsdsan/sanunits/_clarifier.py:57-63
    Reference: Takács et al. (1991)

    Args:
        X: Solids concentration (kg/m³)
        v_max: Maximum settling velocity (m/d)
        rh: Hindered zone parameter (m³/kg)
        rp: Flocculant zone parameter (m³/kg)
        X_min: Non-settleable concentration (kg/m³)

    Returns:
        Settling velocity (m/d)
    """
    import numpy as np
    X_eff = np.maximum(X - X_min, 0)
    v = v_max * (np.exp(-rh * X_eff) - np.exp(-rp * X_eff))
    return np.maximum(v, 0)
```

### B. Extract nCOD Removal Correlation (20 minutes)
```python
# Add to utils/removal_efficiency.py
def ncod_tss_removal(nCOD, HRT_hours, particulate_fraction=0.75):
    """
    BSM2 primary clarifier COD/TSS removal correlation.

    Source: QSDsan qsdsan/sanunits/_clarifier.py:993-1002
    Reference: Otterpohl & Freund (1992)

    Args:
        nCOD: Normalized COD (unitless)
        HRT_hours: Hydraulic retention time (hours)
        particulate_fraction: Fraction of particulate COD (default 0.75)

    Returns:
        Removal efficiency (fraction)
    """
    f_i = 1 - nCOD / 100  # Effluent solids factor
    removal = particulate_fraction * (1 - f_i)
    # HRT correction (longer HRT = better removal)
    removal *= min(HRT_hours / 2.0, 1.0)  # Normalize to 2 hr HRT
    return removal
```

### C. Seed Lamella Defaults (15 minutes)
```json
// Create data/lamella_defaults.json
{
  "design_type": "lamella_settler",
  "source": "AguaClara aguaclara/design/sed_tank.py:45-88",
  "upflow_velocity_mm_s": 1.0,
  "capture_velocity_mm_s": 0.12,
  "plate_angle_degrees": 60,
  "plate_spacing_cm": 2.5,
  "diffuser_spacing_cm": 15,
  "plate_thickness_mm": 1.5,
  "manifold_orifice_diameter_mm": 12,
  "typical_applications": [
    "High-rate sedimentation",
    "Retrofit of existing clarifiers",
    "Space-constrained installations"
  ],
  "hydraulic_loading_multiplier": 3.5,
  "notes": "Industrial adaptations: increase plate spacing to 3-4 cm for high TSS (>500 mg/L)"
}
```

### D. Port PrimaryClarifier Sizing Snippet (1 hour)
Extract key sizing logic from `qsdsan/sanunits/_clarifier.py:1422-1500` to `tools/heuristic_sizing.py`:
- SOR-based area calculation
- Number of clarifiers (minimum 2 for N+1 redundancy)
- Center-feed diameter check (20-25% of tank diameter)
- Side water depth (typically 3-4.5 m)
- Concrete volume calculation for CAPEX estimation

**Total Time**: ~2 hours to implement all quick wins

**Impact**: Immediate functional algorithms for Week 3 sizing implementation

---

## 4. Phase 2 (Deferred to Post-MVP)

**Timeline**: TBD (after Phase 1 complete and validated)

### 4.1 QSDsan Integration

**Purpose**: Detailed component-wise simulation with ASM2d/ADM1 fractionation

**Components**:
- QSDsan PrimaryClarifier wrapper
- Component mapping (ASM2d: S_I, S_S, X_I, X_S, X_H, etc.)
- Settling flux model (Takács double-exponential)
- Sludge blanket dynamics

**Rationale for Deferral**:
- Empirical correlations sufficient for most industrial applications
- QSDsan adds complexity (BioSTEAM dependency, long runtimes)
- ASM2d fractionation requires upstream wastewater characterization
- Phase 1 delivers 90% of value with 50% of effort

### 4.2 Advanced Clarifier Types

**Lamella (Plate Settler)**:
- Port from AguaClara (aguaclara/design/sed_tank.py)
- Adapt for industrial wastewater (increase plate spacing, adjust capture velocity)
- Higher hydraulic loading rates (3-5× conventional)

**Solids Contact Clarifier**:
- Integrated mixing, flocculation, clarification, thickening
- Sludge recirculation for nucleation sites
- Common for lime softening applications

**Clariflocculator**:
- Combined flocculation + clarification in single unit
- Center flocculation well, peripheral clarification zone
- Space-constrained installations

### 4.3 water-chemistry-mcp Integration

**Purpose**: Rigorous chemical equilibrium for lime softening and coagulation

**Use Cases**:
- Lime softening: Ca/Mg precipitation, pH effects, alkalinity consumption
- Coagulation pH optimization: Al/Fe speciation, optimal dose
- MCAS parameter tracking: Ion balance through treatment train

**Integration Points**:
- Call water-chemistry-mcp from chemical_dosing.py
- Pass MCAS parameters to downstream MCPs (aerobic, IX, RO)

### 4.4 Advanced Features

- Particle size distribution analysis
- Computational fluid dynamics (CFD) integration
- Real-time optimization with online sensors
- Multi-objective optimization (CAPEX, OPEX, footprint, removal efficiency)

---

## 5. Design Criteria (Extracted from SERVER_OUTLINE.md)

### 5.1 Surface Overflow Rate (SOR)

**Typical Range**: 30-50 m³/m²/d for primary clarification

**Factors**:
- Wastewater type (municipal vs. industrial)
- Particle settling characteristics
- Temperature (affects viscosity)
- Coagulation/flocculation (enables higher SOR)

**Conversions**:
- Daily basis: m³/m²/d
- Hourly basis: m/h (divide daily by 24)
- US customary: gpd/ft² (multiply daily by 589)

### 5.2 Solids Loading Rate (SLR)

**Typical Range**: 100-150 kg/m²/d for primary clarification

**Critical Limits**:
- Primary without chemicals: 200-400 kg/m²/h
- With coagulation: 300-600 kg/m²/h

**Industrial Considerations**:
- High TSS (>500 mg/L): May exceed calibration range
- Jar tests recommended for validation
- Multiple units or larger clarifiers if SLR near limits

### 5.3 Hydraulic Retention Time (HRT)

**Typical Range**: 1.5-2.5 hours for primary clarification

**Calculation**:
```
HRT (hours) = Volume (m³) / Flow (m³/h)
```

**Factors**:
- Longer HRT improves settling (diminishing returns beyond 2.5h)
- Shorter HRT reduces footprint and cost
- Industrial wastewater may need longer HRT for difficult-to-settle solids

### 5.4 Removal Efficiency Targets

**TSS Removal**:
- Baseline: 50-70%
- With coagulation: 80-90%

**BOD Removal**:
- Typical: 25-40%
- Primarily particulate organic matter

**COD Removal**:
- Typical: 30-50%
- Function of particulate vs. soluble fraction

**TP Removal**:
- Baseline: 10-20%
- With alum/ferric: 70-90% (chemical precipitation)

**Oil & Grease**:
- Free-floating: 40-60%
- Emulsified: 10-20% (needs enhanced treatment)

**TKN Removal**:
- Typical: 15-25%
- Primarily organic nitrogen in particulates

### 5.5 Chemical Dosing Guidelines

**Alum (Al₂(SO₄)₃·18H₂O)**:
- Typical dose: 50-250 mg/L
- Optimal pH: 5.5-6.5
- Alkalinity consumption: ~0.5 mg/L CaCO₃ per mg/L alum
- Enhanced TP removal: 70-85%

**Ferric Chloride (FeCl₃)**:
- Typical dose: 30-150 mg/L
- Less pH-sensitive than alum (optimal pH: 5-8)
- Enhanced TP removal: 80-90%
- Better performance in presence of organics

**Polymer (Anionic/Cationic)**:
- Typical dose: 0.5-3 mg/L
- Floc strength enhancement
- Charge neutralization
- Reduces chemical coagulant dose by 20-40%

### 5.6 Power Requirement Calculations

**Flash Mixing**:
- Detention time: 30-60 seconds
- Velocity gradient (G): 700-1000 s⁻¹
- Power: P = G²μV
  - μ = dynamic viscosity (1.002×10⁻³ Pa·s at 20°C)
  - V = basin volume (m³)
- Typical: 20-40 W/m³

**Flocculation (Tapered)**:
- Detention time: 20-30 minutes
- Stage 1: G = 70-100 s⁻¹ (initial floc formation)
- Stage 2: G = 40-60 s⁻¹ (floc growth)
- Stage 3: G = 20-30 s⁻¹ (gentle agitation)
- Power: P = G²μV for each stage
- Typical: 2-8 W/m³

**Scraper Mechanism**:
- Circular clarifier: rotating bridge with squeegees
- Power lookup table by diameter:
  - 10-20 m: 0.4-0.8 kW
  - 20-40 m: 0.8-2.0 kW
  - 40-60 m: 2.0-3.5 kW
- Function of rotational speed (0.02-0.05 rpm) and torque

**Sludge Pumps**:
- Flow rate: function of SLR and sludge concentration
- Head: typically 5-10 m
- Power: P = ρgQH/η
  - ρ = sludge density (~1020 kg/m³)
  - g = 9.81 m/s²
  - Q = flow rate (m³/s)
  - H = head (m)
  - η = pump efficiency (0.6-0.8)

### 5.7 Geometry Constraints

**Circular Clarifier**:
- Diameter: 10-60 m typical (larger for high flows)
- Side water depth: 3-5 m
- Bottom slope: 1:12 (minimum for sludge removal)
- Weir loading: 125-250 m³/m/d

**Rectangular Clarifier**:
- Length: 15-100 m typical
- Width: 3-24 m typical
- Length:Width ratio: 3:1 to 5:1 preferred
- Bottom slope: 2-4% towards sludge hoppers

**Number of Units**:
- Minimum 2 for redundancy (allow maintenance without shutdown)
- Maximum 6-8 per plant (diminishing returns, operational complexity)

---

## 6. Testing Strategy

### 6.1 Three-Tier Testing Approach

**Tier 1: Golden Tests**
- Hand-calculated examples with known results
- Municipal baseline: 5 MGD, 300 mg/L TSS, 40 m³/m²/d SOR
- Industrial high TSS: 1 MGD, 1500 mg/L TSS, SLR warning expected
- Chemical dosing: Verify stoichiometry and consumption

**Tier 2: Property-Based Tests**
- Hypothetical parameter ranges
- Mass balance closure (influent = effluent + sludge)
- Physical constraint validation (positive values, realistic ranges)
- Edge case handling (zero flow, extreme TSS)

**Tier 3: Lifecycle Tests**
- Full workflow: basis → sizing → simulation → costing
- Job crash recovery
- State persistence and restoration
- Multi-stage error propagation

### 6.2 Coverage Targets

**Per-Module Coverage**: >80%

**Critical Modules** (must achieve >90%):
- `tools/basis_of_design.py` - Validation logic
- `utils/removal_correlations.py` - Core calculations
- `core/state.py` - State persistence

**Integration Coverage**: >70% of end-to-end workflows

### 6.3 Validation Approach

**Literature Comparison**:
- Cross-validate removal correlations with WEF Manual of Practice No. 8
- Compare power calculations with EPA guidelines
- Verify chemical dosing with Metcalf & Eddy (7th Edition)

**Industrial Case Studies**:
- Food processing: High TSS, high oil & grease
- Petrochemical: Variable flow, temperature extremes
- Municipal: Baseline for comparison

---

## 7. Key Decisions & Rationale

### 7.1 Why JobManager for All Operations

**Decision**: Use JobManager consistently for sizing, simulation, AND costing

**Rationale**:
- User feedback: "Standardize on JobManager rather than cherry-picking subprocess strategies"
- Consistent infrastructure across all stages
- No duplicate job orchestration code
- RO "artifact pattern" applies to CLI wrappers, not job management
- Crash recovery built into JobManager (no need for separate mechanisms)

**Impact**:
- Reduced implementation time (1 week saved vs. original plan)
- Easier maintenance and debugging
- Consistent user experience across all tools

### 7.2 Why Multi-Collection Semantic Search

**Decision**: Expand from single clarifier_kb to 3 collections (clarifier_kb, daf_kb, misc_process_kb)

**Rationale**:
- User requirement: "Include daf_kb and misc_process_kb"
- Broader knowledge access during design (DAF often considered as alternative)
- Matches reference pattern from ~/knowledgebase/.mcp.json
- Enables cross-process learning (e.g., DAF flocculation insights)

**Impact**:
- Richer context for design decisions
- Better handling of edge cases (e.g., high oil & grease → DAF recommendation)
- Consistent with other design MCPs

### 7.3 Why Defer WaterTAP to Phase 1.5 (Week 5)

**Decision**: Start with static costing, upgrade to WaterTAP in Week 5

**Rationale**:
- Static costing sufficient for initial validation (Weeks 2-4)
- WaterTAP extraction requires research and coefficient mapping
- Allows parallel development (sizing/simulation in Weeks 3-4, costing in Week 5)
- Reduces risk of WaterTAP complexity blocking core functionality

**Impact**:
- Faster time to functional MVP (Week 4)
- Costing upgrade is additive, not blocking
- Can defer to post-MVP if schedule slips

### 7.4 Why Create Shared Packages

**Decision**: Extract common patterns to mcp_common and plant_state packages

**Rationale**:
- Codex recommendation: "Stop copying JobManager/STDIO patch per MCP"
- Single source of truth with explicit versioning
- Easier maintenance and bug fixes (fix once, propagate to all MCPs)
- plant_state enables seamless upstream/downstream integration

**Impact**:
- Reduced code duplication (~500 lines saved per MCP)
- Consistent behavior across all design MCPs
- Foundation for future agentic workflows (chain primary → aerobic → anaerobic)

---

## 8. Success Metrics

### 8.1 Per-Week Deliverables

**Week 1** ✅ COMPLETE:
- [x] mcp_common package operational
- [x] plant_state package structure established
- [x] All 11 tools registered in server.py
- [x] State management with 4-stage structure
- [x] Structured logging with trace IDs

**Phase 2: Mechanistic Removal Models** ✅ COMPLETE:
- [x] PHREEQC metal speciation integration (utils/chemical_speciation.py)
- [x] Empirical dose-response models (utils/dose_response.py)
- [x] BSM2 integration with chemistry (utils/removal_efficiency.py)
- [x] Zero-dose guard and API simplification
- [x] 63 tests passing (17 speciation + 23 dose-response + 17 integration + 6 verification)
- [x] Codex validation (3 rounds of feedback)
- [x] Documentation (PHASE_2_3_SUMMARY.md, PHASE_2_3_FIXES_SUMMARY.md)

**Week 2: Basis of Design** (Deferred - Prioritized for Week 3):
- [ ] `collect_clarifier_basis()` tool functional
- [ ] Validation logic operational (ranges, consistency)
- [ ] Unit tests with >80% coverage
- [ ] Job lifecycle tests passing

**Week 3**:
- [ ] `size_clarifier_heuristic()` tool functional with JobManager
- [ ] CLI wrapper (sizing_cli.py) operational
- [ ] Chemical dosing and power calculations implemented
- [ ] Integration test: basis → sizing workflow

**Week 4**:
- [ ] `simulate_clarifier_system()` tool functional with empirical mode
- [ ] CLI wrapper (simulate_cli.py) operational
- [ ] Removal correlations implemented and validated
- [ ] Static costing integrated
- [ ] Integration test: basis → sizing → simulation workflow

**Week 5**:
- [ ] WaterTAP costing coefficients extracted and documented
- [ ] Costing CLI wrapper (costing_cli.py) operational
- [ ] Crash recovery tests passing
- [ ] End-to-end workflow: basis → sizing → simulation → costing

### 8.2 Integration Checkpoints

**Checkpoint 1 (End of Week 2)**:
- Basis of design can be collected and validated
- State persists correctly (save/load)
- Job creation and tracking functional

**Checkpoint 2 (End of Week 3)**:
- Heuristic sizing produces reasonable results (geometry, power, chemicals)
- JobManager executes sizing_cli.py successfully
- Results stored in artifact directories

**Checkpoint 3 (End of Week 4)**:
- Empirical simulation produces mass-balanced effluent
- Removal correlations match literature values (±10%)
- Static costing provides order-of-magnitude CAPEX/OPEX

**Checkpoint 4 (End of Week 5)**:
- WaterTAP costing replaces static estimates
- Full workflow operational (all 4 stages)
- Crash recovery restores state correctly

### 8.3 Performance Targets

**Response Time**:
- Tool invocation (stubs): <500 ms
- Basis collection: <2 seconds
- Heuristic sizing: <30 seconds (background job)
- Empirical simulation: <60 seconds (background job)
- WaterTAP costing: <45 seconds (background job)

**Memory**:
- Server idle: <100 MB
- Peak during simulation: <500 MB
- Job artifacts: <10 MB per run

**Reliability**:
- Job success rate: >95% (excluding user input errors)
- Crash recovery: 100% (state always restorable)
- Test suite pass rate: 100% (no flaky tests)

---

## 9. Open Questions for Week 2+

1. **mcp_common packaging**: Install as editable package (`pip install -e`) or keep in sys.path?
   - Recommendation: Editable package for versioning and dependency management

2. **plant_state scope**: Defer full ASM2d/ADM1 converters to Phase 2?
   - Recommendation: Keep stubs, implement fractionation.py only (sufficient for Phase 1)

3. **Test framework**: pytest-asyncio configuration needed for async tools?
   - Recommendation: Use pytest-asyncio with asyncio mode "auto"

4. **Job timeout**: Default timeout for sizing/simulation jobs?
   - Recommendation: 300 seconds (5 minutes) for sizing/simulation, 600 seconds (10 minutes) for costing

5. **WaterTAP attribution**: How to display in every output?
   - Recommendation: Add "citations" field to all tool outputs with attribution text

---

## 10. References

### 10.1 Technical Standards

- WEF Manual of Practice No. 8: Clarifier Design
- EPA Technology Transfer: Wastewater Treatment
- Metcalf & Eddy: Wastewater Engineering (7th Edition)
- Ten States Standards: Recommended Standards for Wastewater Facilities (2014 Edition)

### 10.2 Open Source Repositories

- **QSDsan**: https://github.com/QSD-Group/QSDsan (Phase 2)
- **WaterTAP**: https://github.com/watertap-org/watertap (Week 5 costing)
- **AguaClara**: https://github.com/AguaClara-Reach/aguaclara (Phase 2 lamella)

### 10.3 Internal References

- **anaerobic-design-mcp**: JobManager and STDIO patch source
- **aerobic-design-mcp**: mcp_stdio_patch.py and state structure
- **ro-design-mcp**: Artifacts.py for deterministic run IDs
- **~/knowledgebase/.mcp.json**: Multi-collection search pattern

### 10.4 Design Criteria

- Surface overflow rate: 30-50 m³/m²/d (primary)
- Solids loading rate: 100-150 kg/m²/d
- Detention time: 1.5-2.5 hours
- Weir loading: 125-250 m³/m/d
- Flash mixing G: 700-1000 s⁻¹
- Flocculation G: 20-80 s⁻¹ (tapered)

---

## Appendix: Original vs. Revised Timeline

| Phase | Original (6 weeks) | Revised (5 weeks) | Change |
|-------|-------------------|-------------------|--------|
| Week 1 | Core infrastructure | Infrastructure foundation | ✅ Same |
| Week 2 | Algorithm extraction | Basis + validation | Simplified (no extraction) |
| Week 3 | Industrial adaptations | Heuristic sizing | Consolidated |
| Week 4 | Advanced configs | Empirical simulation | Focused scope |
| Week 5 | Chemical integration | WaterTAP costing upgrade | New focus |
| Week 6 | Testing & docs | ~~Removed~~ | Integrated into Weeks 2-5 |

**Key Changes**:
- Consolidated job management (1 week saved)
- Deferred advanced features to Phase 2 (lamella, solids contact, QSDsan)
- Focused Phase 1 on empirical correlations (sufficient for most use cases)
- Integrated testing throughout (not separate week at end)

---

**END OF IMPLEMENTATION PLAN**

**Status**: Week 1 complete (100%), Phase 2 complete (100% - Mechanistic Removal Models)
**Next Milestone**: Week 3 - Heuristic Sizing with Dose-Response Integration
**Overall Progress**: ~45% complete
- ✅ Week 1: Infrastructure (100%)
- ✅ Phase 2: Mechanistic Removal Models (100%)
- ⏸️ Week 2: Basis of Design (deferred to Week 3)
- 🎯 Next: Week 3 - Heuristic Sizing + Basis Collection

**Recommended Next Steps**:
1. Implement Codex's additional recommendations (helper function, dose threshold ~0.05 mg/L)
2. Start Week 3 heuristic sizing implementation leveraging Phase 2 dose-response models
3. Integrate basis collection with sizing workflow
4. Consider Basis of Design refactoring (see BASIS_OF_DESIGN_REFACTORING_PLAN.md)
