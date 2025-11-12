# Primary Clarifier MCP

**Model Context Protocol (MCP) Server for Industrial Wastewater Primary Clarifier Design**

## Overview

The Primary Clarifier MCP is a specialized design tool for primary clarification systems in industrial wastewater treatment plants. It provides a structured, multi-stage workflow for sizing, simulating, and costing primary clarifiers with support for chemical addition (coagulation/flocculation), high solids loading, and oil & grease removal.

This MCP is part of a normalized design ecosystem that spans the complete wastewater treatment train, from preliminary treatment through biological processes to tertiary treatment and water reuse. The primary clarifier serves as a critical upstream component that removes settleable solids and reduces organic loading to downstream biological or chemical treatment processes.

The tool follows a standardized 4-stage workflow pattern: **Basis of Design → Heuristic Sizing → Process Simulation → Economic Analysis**. This approach balances fast screening (heuristic sizing) with rigorous validation (process simulation) to support both preliminary scoping and detailed engineering design.

## Current Status

**Progress**: Phase 1 Complete - ASM2d + MCAS State Integration (30% of planned implementation)

**What's Implemented**:
- ✅ Complete infrastructure foundation (server, state management, logging)
- ✅ Shared packages for cross-MCP integration (mcp_common, plant_state)
- ✅ 11 MCP tools registered (Phase 1 complete, others planned)
- ✅ Multi-collection semantic search (clarifier_kb, daf_kb, misc_process_kb)
- ✅ Background job orchestration framework (JobManager integration)
- ✅ Structured logging with trace ID correlation
- ✅ **NEW: Comprehensive basis of design collection with ASM2d + MCAS state integration**
  - Extended parameter collection (44 fields including nitrogen speciation, DO, ORP, conductivity, TOC, silica)
  - Smart TDS validation with ion coverage checking
  - Charge balance validation (corrected meq/L calculations)
  - JSON serialization with transient validation fields
  - 44 passing tests with comprehensive edge case coverage

**What's Planned** (Remaining Phases):
- 🔄 Phase 2: Shared plant_state utilities (unit conversions, charge balance, carbonate chemistry, wastewater templates)
- 🔄 Phase 3: Codex-based state estimator for mASM2d fractionation
- 🔄 Phase 4: Combined state schema (mASM2d + MCAS)
- 🔄 Phase 5: State converters (mASM2d ↔ MCAS)
- 🔄 Phase 6: Effluent summarization tool
- 🔄 Phase 7: Integration testing

**Details**:
- See [WEEK1_SUMMARY.md](./WEEK1_SUMMARY.md) for infrastructure completion
- See [CHANGELOG.md](./CHANGELOG.md) for Phase 1 implementation details

## Quick Start

### Prerequisites

**Shared Dependencies**:
```bash
# Install shared infrastructure packages (if not already installed)
cd /mnt/c/Users/hvksh/mcp-servers/mcp_common
pip install -e .

cd /mnt/c/Users/hvksh/mcp-servers/plant_state
pip install -e .
```

**Primary Clarifier Dependencies**:
```bash
cd /mnt/c/Users/hvksh/mcp-servers/primary-clarifier-mcp
pip install fastmcp>=0.1.0
# Additional dependencies to be added in Weeks 2-4
```

### Configuration

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "primary-clarifier-mcp": {
      "type": "stdio",
      "command": "/path/to/venv/Scripts/python.exe",
      "args": [
        "C:\\Users\\hvksh\\mcp-servers\\primary-clarifier-mcp\\server.py"
      ],
      "env": {
        "MCP_TIMEOUT": "600000",
        "PRIMARY_CLARIFIER_MCP_ROOT": "C:\\Users\\hvksh\\mcp-servers\\primary-clarifier-mcp"
      },
      "autoApprove": [
        "kb.sparse", "kb.dense", "kb.hybrid", "kb.rerank", "kb.colbert",
        "kb.batch", "kb.quality", "kb.hint", "kb.table", "kb.open",
        "kb.neighbors", "kb.summary", "kb.outline", "kb.entities",
        "kb.linkouts", "kb.graph", "kb.promote", "kb.demote",
        "kb.collections", "kb.search", "kb.sparse_splade"
      ]
    }
  }
}
```

**Note**: Adjust paths for your environment (Windows/WSL/Linux).

### Basic Usage

```python
# 1. Collect basis of design parameters
await collect_clarifier_basis(
    flow_m3_d=5000,
    peak_factor=2.5,
    temperature_c=20,
    influent_tss_mg_l=300,
    influent_vss_mg_l=210,
    influent_cod_mg_l=600,
    influent_bod5_mg_l=300,
    influent_tkn_mg_l=40,
    influent_tp_mg_l=8,
    target_tss_removal_pct=65
)

# 2. Size clarifier using heuristic approach (fast screening)
job_id = await size_clarifier_heuristic(
    use_current_basis=True
)

# 3. Monitor job progress
status = await get_job_status(job_id=job_id)

# 4. Retrieve results when complete
results = await get_job_results(job_id=job_id)

# 5. Run detailed simulation (optional)
sim_job_id = await simulate_clarifier_system(
    use_current_state=True,
    simulation_mode="empirical",
    include_costing=True
)
```

## Architecture

### High-Level Components

```
primary-clarifier-mcp/
├── server.py              # FastMCP entry point with 11 tool registrations
├── core/
│   └── state.py          # ClarifierDesignState (4-stage workflow)
├── tools/
│   ├── basis_of_design.py        # Stage 1: Parameter collection
│   ├── heuristic_sizing.py       # Stage 2: Fast screening
│   ├── simulation.py             # Stage 3: Detailed simulation
│   ├── job_management.py         # Background job control
│   └── state_management.py       # State export/import
├── utils/
│   └── logging_config.py         # Structured logging with trace IDs
└── data/                          # Configuration and defaults
```

### Shared Packages

**mcp_common** (`/mcp-servers/mcp_common/`):
- `job_manager.py` - Background job orchestration
- `mcp_stdio_patch.py` - STDIO buffering fix for WSL2
- `artifacts.py` - Deterministic run ID generation

**plant_state** (`/mcp-servers/plant_state/`):
- `fractionation.py` - COD/TSS fractionation (implemented)
- `asm2d_converter.py` - ASM2d state variables (planned)
- `adm1_converter.py` - ADM1 state variables (planned)
- `mcas_tracker.py` - Major cations/anions tracking (planned)

These shared packages enable seamless integration with upstream (screening, pretreatment) and downstream (aerobic, anaerobic, IX, RO) MCPs in the treatment train.

### State Management

The design state follows a 4-stage structure:

1. **Basis of Design**: Hydraulic parameters, influent characteristics, targets, chemical dosing strategy
2. **Heuristic Config**: Clarifier geometry, performance estimates, power requirements, chemical consumption
3. **Simulation Results**: Settling model results, removal efficiencies, effluent/sludge properties
4. **Economics**: CAPEX, OPEX, levelized cost of water (LCOW)

State can be exported/imported as JSON, supports partial resets (e.g., reset simulation without losing sizing), and tracks completion status for each stage.

## Tool Reference

### Stage 1: Basis of Design

**`collect_clarifier_basis()`**
- Collects and validates design parameters
- Parameters: flow rate, temperature, influent characteristics (TSS, VSS, COD, BOD, TKN, TP, O&G), targets
- Returns: Validation results and stored parameters

### Stage 2: Heuristic Sizing

**`size_clarifier_heuristic()`**
- Fast sizing using SOR/SLR correlations
- Background job (returns job_id immediately)
- Calculates: geometry, hydraulic performance, removal efficiencies, chemical doses, power requirements
- Mode: Conventional circular clarifiers (future: rectangular, lamella)

### Stage 3: Process Simulation

**`simulate_clarifier_system()`**
- Detailed simulation with removal efficiency modeling
- Background job (returns job_id immediately)
- Modes: "empirical" (fast correlations), "qsdsan" (rigorous ASM/ADM fractionation - future)
- Optional: Include economic analysis

### Job Management

**`get_job_status(job_id)`** - Check background job progress
**`get_job_results(job_id)`** - Retrieve completed job results
**`list_jobs(status_filter, limit)`** - List all jobs with filtering
**`terminate_job(job_id)`** - Cancel running job

### State Management

**`get_design_state()`** - Export current design state as JSON
**`reset_design(scope)`** - Clear state (scopes: "all", "simulation", "costing")
**`export_design_state(filepath)`** - Save state to file
**`import_design_state(filepath)`** - Load state from file
**`summarize_clarifier_effluent()`** - Generate effluent summary for downstream MCPs

### Workflow Sequence

```
1. collect_clarifier_basis()
   ↓
2. size_clarifier_heuristic() → job_id
   ↓
3. get_job_status(job_id) [poll until complete]
   ↓
4. get_job_results(job_id)
   ↓
5. simulate_clarifier_system() → job_id [optional]
   ↓
6. get_job_results(job_id)
   ↓
7. summarize_clarifier_effluent() [pass to downstream MCP]
```

## Development

### Directory Structure

```
primary-clarifier-mcp/
├── README.md                      # This file
├── IMPLEMENTATION_PLAN.md         # Detailed 6-week roadmap (outdated)
├── SERVER_OUTLINE.md              # Original architecture document
├── WEEK1_SUMMARY.md               # Week 1 completion summary
├── .mcp.json                      # MCP server configuration
├── server.py                      # FastMCP entry point (354 lines)
│
├── core/
│   ├── __init__.py
│   └── state.py                   # ClarifierDesignState (167 lines)
│
├── tools/
│   ├── __init__.py
│   ├── basis_of_design.py         # Stage 1 (stub)
│   ├── heuristic_sizing.py        # Stage 2 (stub)
│   ├── simulation.py              # Stage 3 (stub)
│   ├── job_management.py          # Job control (stub)
│   └── state_management.py        # State tools (2/5 implemented)
│
├── utils/
│   ├── __init__.py
│   └── logging_config.py          # Structured logging (208 lines)
│
├── data/                          # Configuration files (Week 2-4)
├── jobs/                          # Job artifacts directory
└── tests/                         # Unit and integration tests (Week 2-5)
```

### Testing Approach

**Unit Tests** (Week 2-3):
- Parameter validation edge cases
- State persistence and serialization
- Job lifecycle (creation, status, retrieval, termination)

**Integration Tests** (Week 3-4):
- Full workflow: basis → sizing → simulation
- State reset and export/import
- Multi-collection semantic search

**Validation Tests** (Week 4-5):
- Compare against WEF Manual of Practice No. 8
- EPA guidelines for primary clarification
- Industrial case studies (high TSS, O&G)

### Week-by-Week Roadmap

**Week 1 (COMPLETE)**: Infrastructure foundation
- ✅ Shared packages (mcp_common, plant_state)
- ✅ Server architecture and tool registration
- ✅ State management and structured logging

**Week 2**: Basis of Design + Validation
- Parameter collection and validation
- Industrial wastewater adaptations (high TSS, O&G)
- Data files (default_parameters.json)
- Unit tests and job lifecycle exercises

**Week 3**: Heuristic Sizing
- SOR/SLR-based sizing algorithms
- CLI wrapper with JobManager
- Chemical dosing calculations
- Power requirements (flash mixing, flocculation, scraper)

**Week 4**: Process Simulation
- Empirical removal correlations
- Component fractionation (TSS/VSS/COD/BOD)
- CLI wrapper for simulation
- Integration tests

**Week 5**: Economics + Polish
- CAPEX/OPEX estimation
- Levelized cost of water (LCOW)
- Report generation
- Documentation and examples

## Integration

### Knowledge Base Collections

The MCP integrates with three knowledge base collections:

1. **clarifier_kb**: Primary clarifier design guidelines, case studies, vendor data
2. **daf_kb**: Dissolved air flotation (alternative to sedimentation)
3. **misc_process_kb**: General process engineering knowledge

These collections are queried during design to provide context-aware recommendations and validate design decisions against industry best practices.

### Upstream MCPs

**Inputs from**:
- Screening MCP: Influent characteristics post-screening
- Pretreatment MCP: Oil & grease removal efficiency
- Flow equalization: Peak flow factors

### Downstream MCPs

**Outputs to**:
- **Aerobic MCP**: Effluent BOD/COD, ASM2d state variables (optional)
- **Anaerobic MCP**: Sludge characteristics, ADM1 state variables (optional)
- **IX/RO MCPs**: Major cations/anions (MCAS) if chemical softening used
- **Chemical treatment**: Effluent for tertiary coagulation/flocculation

**Effluent Summary Format**:
```json
{
  "effluent": {
    "flow_m3_d": 5000,
    "tss_mg_l": 105,
    "vss_mg_l": 73,
    "cod_mg_l": 420,
    "bod5_mg_l": 210,
    "tkn_mg_l": 34,
    "tp_mg_l": 6.8,
    "temperature_c": 20
  },
  "removal_envelope": {
    "tss_removal_pct": { "min": 60, "typical": 65, "max": 70 },
    "bod_removal_pct": { "min": 25, "typical": 30, "max": 35 }
  },
  "sludge": {
    "flow_m3_d": 78,
    "solids_concentration_pct": 4.0,
    "dry_solids_kg_d": 975
  },
  "optional_state_variables": {
    "asm2d": { "X_I": 45, "X_S": 180, "S_S": 120, ... },
    "mcas": { "Ca_mg_l": 120, "Mg_mg_l": 35, ... }
  }
}
```

## References

### Documentation

- **[IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)**: Original 6-week implementation plan (outdated, kept for reference)
- **[WEEK1_SUMMARY.md](./WEEK1_SUMMARY.md)**: Week 1 completion summary with architectural decisions
- **[SERVER_OUTLINE.md](./SERVER_OUTLINE.md)**: Original architecture outline

### Technical Standards

- WEF Manual of Practice No. 8: Clarifier Design
- EPA Technology Transfer: Wastewater Treatment
- Metcalf & Eddy: Wastewater Engineering (7th Edition)
- Ten States Standards: Recommended Standards for Wastewater Facilities

### Design Guidelines

| Parameter | Range | Notes |
|-----------|-------|-------|
| Surface Overflow Rate (SOR) | 30-50 m³/m²/d | Primary clarification |
| Solids Loading Rate (SLR) | 100-150 kg/m²/d | Without chemicals |
| Hydraulic Retention Time (HRT) | 1.5-2.5 hours | Typical |
| Weir Loading | 125-250 m³/m/d | Peripheral weir |
| TSS Removal | 50-70% | Baseline (higher with coagulation) |
| BOD Removal | 25-40% | Typical |

## License

This project is part of the QSD-Group wastewater treatment MCP ecosystem. See individual component licenses for details:

- QSDsan algorithms: NCSA Open Source License
- WaterTAP costing: DOE open source with attribution
- AguaClara lamella: MIT License

## Contributing

This MCP is under active development (Week 1 of 5 complete). Contributions are welcome after the initial implementation is complete.

**Contact**: See project maintainers

## Version History

- **v0.1.0** (Week 1, 2025-11-10): Infrastructure foundation complete
  - Server architecture and tool registration
  - Shared packages (mcp_common v0.1.0, plant_state v0.1.0)
  - State management and structured logging
  - 11 tool stubs with implementation roadmap

---

**Next Milestone**: Week 2 - Basis of Design Implementation
**Overall Progress**: 20% complete (1 of 5 weeks)
