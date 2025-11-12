# Primary Clarification MCP Server - Architecture Outline

## Overview

This MCP server provides tools for primary clarifier design for industrial wastewater treatment, following the established workflow pattern from ro-design-mcp, ix-design-mcp, aerobic-design-mcp, and anaerobic-design-mcp.

**Workflow:** Basis of Design → Heuristic Sizing → Process Simulation → Economic Analysis

## Architecture Decision: QSDsan Base + Custom Extensions

**Rationale:** QSDsan's `PrimaryClarifier` and `PrimaryClarifierBSM2` provide robust ASM/ADM state variable fractionation (particulate vs. soluble components), but lack:
- Chemical dosing calculations (coagulant, flocculant)
- Flash mixing and flocculation power requirements
- Enhanced removal modeling with chemical addition

**Solution:** Hybrid approach similar to ix-design-mcp (PHREEQC + WaterTAP) and ro-design-mcp (custom membrane catalog + WaterTAP)

---

## MCP Tools

### 1. `elicit_basis_of_design`
Collect design parameters:
- Flow rate: m³/d (average and peak factor)
- Influent characteristics:
  - TSS (total suspended solids): mg/L
  - VSS (volatile suspended solids): mg/L
  - COD (total, soluble, particulate): mg/L
  - BOD5: mg/L
  - TKN (total Kjeldahl nitrogen): mg/L
  - TP (total phosphorus): mg/L
  - Oil & grease: mg/L
- Operating conditions:
  - Temperature: °C
  - pH
- Optional:
  - Particle size distribution
  - Settling velocity data

**Output:** Stored in design state

---

### 2. `validate_design_inputs`
Validate parameter ranges and consistency:
- Flow rate reasonableness
- TSS/VSS ratio (typically 0.7-0.85)
- COD fractionation (particulate + soluble = total)
- Temperature range (5-40°C typical)
- pH range (5-9 typical)

**Output:** Validation results with warnings/errors

---

### 3. `heuristic_sizing_clarifier` (Configuration Tool)

Calculate clarifier dimensions and equipment WITHOUT simulation (fast screening).

#### 3.1 Clarifier Geometry
- Surface overflow rate (SOR): 30-50 m³/m²/d for primary clarification
- Solids loading rate (SLR): 100-150 kg/m²/d
- Hydraulic detention time (HRT): 1.5-2.5 hours
- Clarifier type: circular vs. rectangular
- Diameter or length×width
- Side water depth: 3-5 m
- Bottom slope: 1:12 (circular), 2-4% (rectangular)
- Weir loading rate: 125-250 m³/m/d
- Number of units (minimum 2 for redundancy)

#### 3.2 Removal Efficiency Estimation
Based on empirical correlations and particle settling theory:
- TSS removal: 50-70% (baseline), up to 90% with coagulation
- BOD removal: 25-40%
- COD removal: 30-50%
- TP removal: 10-20% (baseline), 70-90% with chemical precipitation
- Oil & grease: 40-60% (free-floating)
- TKN removal: 15-25% (primarily organic nitrogen in particulates)

#### 3.3 Chemical Dosing Calculations
Jar test correlations for optimal dose:
- **Alum (Al₂(SO₄)₃·18H₂O)**:
  - Typical dose: 50-250 mg/L
  - Function of turbidity, TOC, pH
  - Alkalinity consumption
  - pH depression
- **Ferric Chloride (FeCl₃)**:
  - Typical dose: 30-150 mg/L
  - Less pH-sensitive than alum
  - Enhanced phosphorus removal
- **Polymer (anionic/cationic)**:
  - Typical dose: 0.5-3 mg/L
  - Floc strength enhancement
  - Charge neutralization
- **Lime (pH adjustment)**:
  - As needed for pH control
  - Enhanced phosphorus precipitation

**Chemical consumption calculation:**
```
Annual consumption (kg/yr) = Dose (mg/L) × Flow (m³/d) × 365 days × 10⁻³
```

#### 3.4 Power Requirements
Calculate equipment power WITHOUT simulation:

**Flash Mixing:**
- Detention time: 30-60 seconds
- Velocity gradient (G): 700-1000 s⁻¹
- Power: P = G²μV
  - μ = dynamic viscosity (function of temperature)
  - V = basin volume (m³)
- Typical: 20-40 W/m³

**Flocculation:**
- Detention time: 20-30 minutes
- Velocity gradient (G): 20-80 s⁻¹ (tapered: 3 stages)
  - Stage 1: 70-100 s⁻¹ (initial floc formation)
  - Stage 2: 40-60 s⁻¹ (floc growth)
  - Stage 3: 20-30 s⁻¹ (gentle agitation)
- Power: P = G²μV for each stage
- Typical: 2-8 W/m³

**Scraper Mechanism:**
- Circular clarifier: rotating bridge with squeegees
- Power lookup table by diameter:
  - 10-20 m: 0.4-0.8 kW
  - 20-40 m: 0.8-2.0 kW
  - 40-60 m: 2.0-3.5 kW
- Function of rotational speed (0.02-0.05 rpm) and torque

**Sludge Pumps:**
- Flow rate: function of SLR and sludge concentration
- Head: typically 5-10 m
- Power: P = ρgQH/η
  - ρ = sludge density (~1020 kg/m³)
  - g = 9.81 m/s²
  - Q = flow rate (m³/s)
  - H = head (m)
  - η = pump efficiency (0.6-0.8)

#### 3.5 Sludge Production
- Sludge concentration: 2-6% solids (20,000-60,000 mg/L)
- Sludge volume calculation:
  ```
  V_sludge = (TSS_in × Flow × Removal_eff) / Sludge_concentration
  ```
- Sludge mass balance:
  - VSS/TSS ratio
  - Dry solids production (kg/d)
  - Annual sludge production (m³/yr, dry tonnes/yr)

**Output:** Complete design specification without simulation

---

### 4. `simulate_clarifier_system` (Process Simulation Tool)

Detailed simulation using **QSDsan PrimaryClarifier** with custom extensions.

#### 4.1 QSDsan Simulation Core
Use `qsdsan.sanunits.PrimaryClarifier` or `PrimaryClarifierBSM2`:

**Capabilities:**
- Component-wise fractionation based on `particle_size` attribute:
  - 's' = soluble
  - 'x' = particulate
  - 'c' = colloidal
- ASM2d state variables:
  - S_I, S_S, S_F, S_A, S_NH4, S_NO3, S_PO4, S_O2, S_ALK
  - X_I, X_S, X_H, X_PAO, X_PP, X_PHA, X_AUT
- ADM1 state variables:
  - S_su, S_aa, S_fa, S_va, S_bu, S_pro, S_ac, S_h2, S_ch4
  - X_c, X_ch, X_pr, X_li, X_su, X_aa, X_fa, X_c4, X_pro, X_ac, X_h2
- Mass balance validation
- Sludge underflow properties

**Integration approach:**
```python
from qsdsan import WasteStream, sanunits

# Create influent stream with ASM2d/ADM1 components
influent = WasteStream('influent', ...)

# Initialize primary clarifier
clarifier = sanunits.PrimaryClarifier(
    ID='primary_clarifier',
    ins=influent,
    outs=('effluent', 'sludge'),
    surface_overflow_rate=40,  # m3/m2/d
    solids_removal_efficiency=0.65
)

# Run simulation
clarifier.simulate()
```

#### 4.2 Custom Chemistry Module (`utils/coagulation_chemistry.py`)

Extend QSDsan results with enhanced removal calculations:

**Coagulation Dose Optimization:**
- Turbidity-based correlations
- TOC-based correlations
- pH-dependent speciation:
  - Alum: Al³⁺, Al(OH)₂⁺, Al(OH)₂⁺, Al(OH)₃, Al(OH)₄⁻
  - Ferric: Fe³⁺, Fe(OH)₂⁺, Fe(OH)₂⁺, Fe(OH)₃
- Alkalinity consumption
- Optimal pH range determination

**Enhanced Removal with Coagulation:**
- Baseline removal (from QSDsan)
- Incremental removal with chemicals:
  - TP: +50-70% (phosphorus precipitation)
  - TSS: +10-20% (micro-floc aggregation)
  - COD: +5-15% (colloidal organics)
  - BOD: +5-10%

**Chemical Consumption:**
- Stoichiometric calculations
- Excess dosing for non-ideal conditions
- Annual consumption and cost

#### 4.3 Custom Power Module (`utils/power_calculations.py`)

Calculate energy consumption for mixing and clarification:

**Flash Mixing Basin:**
- Volume based on HRT
- G value selection (700-1000 s⁻¹)
- Power = G²μV
- Equipment selection (mechanical mixer vs. hydraulic)

**Flocculation Basin:**
- Volume based on HRT (20-30 min)
- Tapered G values (3 stages)
- Power for each stage
- Total flocculation power

**Scraper Power:**
- Diameter-based lookup
- Rotational speed adjustment
- Torque calculation

**Total Energy:**
- kWh/d
- kWh/m³ treated
- Annual energy consumption

#### 4.4 Economic Analysis

**CAPEX (Capital Expenditure):**
- Clarifier basin (concrete volume, excavation)
- Mechanical equipment:
  - Scraper mechanism
  - Flash mixer
  - Flocculator
  - Sludge pumps
- Chemical feed systems (alum, polymer, pH control)
- Piping and valves
- Instrumentation and control

**OPEX (Operating Expenditure):**
- Chemical costs (alum/ferric, polymer, lime)
- Energy costs (mixing, scraping, pumping)
- Maintenance (5-7% of CAPEX annually)
- Sludge disposal costs
- Labor

**WaterTAP Costing Integration:**
- Use WaterTAPCosting framework for basin and equipment
- EPA-WBS correlations for cost scaling
- Regional cost indices

**LCOW Calculation:**
- 20-year project lifetime
- 8% discount rate
- Net present value (NPV)
- Levelized cost of water ($/m³)

**Output:** Detailed simulation results with performance prediction and economics

---

### 5. `get_design_state`
Return current design state as JSON.

---

### 6. `reset_design`
Clear design state for new project.

---

## Custom Modules

### `utils/settling_theory.py`
Particle settling velocity calculations:
- **Stokes' Law** (discrete settling):
  ```
  v = (ρₚ - ρw) × g × d² / (18μ)
  ```
  - ρₚ = particle density
  - ρw = water density
  - d = particle diameter
  - μ = dynamic viscosity
- **Hindered settling** (high concentrations):
  - Richardson-Zaki equation
  - Camp model
- **Type II settling** (flocculent):
  - Floc density evolution
  - Collision frequency

### `utils/coagulation_chemistry.py`
- Jar test correlation models
- pH-dependent speciation
- Alkalinity consumption
- Optimal dose calculation
- Enhanced removal factors

### `utils/flocculation_kinetics.py`
- Camp-Stein flocculation model
- Collision efficiency (α)
- Floc size distribution
- Breakup and reformation kinetics

### `utils/power_calculations.py`
- Flash mixing power: P = G²μV
- Flocculation power (tapered)
- Scraper power (lookup + adjustment)
- Pump power: P = ρgQH/η

### `utils/chemical_dosing.py`
- Alum properties and stoichiometry
- Ferric chloride properties
- Polymer properties
- Annual consumption calculations
- Cost estimation

### `utils/qsdsan_wrapper.py`
QSDsan integration:
- WasteStream creation from basis of design
- Component mapping (ASM2d/ADM1)
- PrimaryClarifier configuration
- Result extraction and formatting
- Subprocess isolation (avoid GIL issues)

### `utils/removal_correlations.py`
Empirical models for removal efficiency:
- TSS removal vs. SOR and SLR
- BOD/COD removal correlations
- Phosphorus removal (baseline and enhanced)
- Temperature effects
- Particle size distribution effects

### `utils/economic_defaults.py`
Cost data and correlations:
- Clarifier basin: $/m³
- Mechanical equipment: $ per unit
- Chemical costs: $/kg
- Energy costs: $/kWh
- Maintenance factors
- Regional cost indices

---

## Subprocess Isolation

Following the pattern from aerobic-design-mcp and anaerobic-design-mcp:

```python
# core/subprocess_runner.py
def run_simulation_in_subprocess(sim_input: Dict) -> Dict:
    """
    Run QSDsan simulation in subprocess to avoid:
    - GIL issues with FastMCP
    - Import graph conflicts
    - Memory leaks from repeated simulations
    """
    payload = json.dumps(sim_input)
    proc = subprocess.run(
        [sys.executable, "-m", "utils.qsdsan_worker"],
        input=payload,
        capture_output=True,
        text=True,
        timeout=300
    )
    return json.loads(proc.stdout)
```

---

## Data Files

### `data/default_removal_rates.json`
```json
{
  "tss_removal_percent": {
    "min": 50,
    "typical": 60,
    "max": 70,
    "with_coagulation": 85
  },
  "bod_removal_percent": {
    "min": 25,
    "typical": 32,
    "max": 40
  },
  "tp_removal_percent": {
    "baseline": 15,
    "with_alum": 80,
    "with_ferric": 85
  }
}
```

### `data/chemical_properties.json`
```json
{
  "alum": {
    "formula": "Al2(SO4)3·18H2O",
    "molecular_weight": 666.43,
    "density": 1.69,
    "typical_dose_mg_l": 120,
    "cost_usd_per_kg": 0.35
  },
  "ferric_chloride": {
    "formula": "FeCl3",
    "molecular_weight": 162.2,
    "density": 1.42,
    "typical_dose_mg_l": 80,
    "cost_usd_per_kg": 0.45
  }
}
```

### `data/scraper_power_curves.json`
```json
{
  "circular_clarifier_power_kw": {
    "10m": 0.5,
    "20m": 0.9,
    "30m": 1.4,
    "40m": 2.1,
    "50m": 2.9,
    "60m": 3.7
  }
}
```

---

## State Management

### Design State Structure
```python
@dataclass
class DesignState:
    basis_of_design: Optional[Dict] = None
    heuristic_config: Optional[Dict] = None
    simulation_results: Optional[Dict] = None
    economic_results: Optional[Dict] = None
    validation_results: Optional[Dict] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
```

### State Persistence
- JSON files: `primary_clarifier_state.json`
- Export/import functionality
- Timestamped backups

---

## Testing Strategy

### Unit Tests
- `tests/test_settling_theory.py`: Stokes law, hindered settling
- `tests/test_coagulation.py`: Dose calculations, pH effects
- `tests/test_power.py`: Flash mixing, flocculation, scraper power
- `tests/test_removal.py`: Removal correlations

### Integration Tests
- `tests/test_heuristic_sizing.py`: End-to-end configuration tool
- `tests/test_simulation.py`: QSDsan integration
- `tests/test_workflow.py`: Basis → sizing → simulation flow

### Validation Tests
- Compare with WEF Manual of Practice No. 8
- EPA guidelines for primary clarification
- Industrial case studies

---

## References

### Technical Standards
- WEF Manual of Practice No. 8: Clarifier Design
- EPA Technology Transfer: Wastewater Treatment
- Metcalf & Eddy: Wastewater Engineering (7th Edition)

### QSDsan Documentation
- `qsdsan.sanunits.PrimaryClarifier`
- `qsdsan.sanunits.PrimaryClarifierBSM2`
- ASM2d and ADM1 component definitions

### Design Guidelines
- Surface overflow rate: 30-50 m³/m²/d (primary)
- Solids loading rate: 100-150 kg/m²/d
- Detention time: 1.5-2.5 hours
- Weir loading: 125-250 m³/m/d
- Flash mixing G: 700-1000 s⁻¹
- Flocculation G: 20-80 s⁻¹ (tapered)

---

## Example Workflow

```python
# 1. Collect basis of design
basis = elicit_basis_of_design(
    flow_m3d=5000,
    tss_mg_l=300,
    cod_mg_l=600,
    temperature_c=20,
    ...
)

# 2. Validate inputs
validation = validate_design_inputs()

# 3. Heuristic sizing (fast screening)
config = heuristic_sizing_clarifier(
    use_coagulation=True,
    coagulant_type="ferric_chloride"
)
# Output: geometry, chemical doses, power estimates

# 4. Process simulation (detailed validation)
results = simulate_clarifier_system(
    use_current_state=True,
    costing_method="WaterTAPCosting"
)
# Output: component-wise effluent, sludge, CAPEX/OPEX

# 5. Review results
state = get_design_state()
```

---

## Configuration Files

### `.mcp.json`
```json
{
  "mcpServers": {
    "primary-clarifier-mcp": {
      "type": "stdio",
      "command": "/mnt/c/Users/hvksh/mcp-servers/venv312/Scripts/python.exe",
      "args": ["C:\\Users\\hvksh\\mcp-servers\\primary-clarifier-mcp\\server.py"],
      "env": {
        "MCP_TIMEOUT": "600000",
        "PRIMARY_CLARIFIER_MCP_ROOT": "C:\\Users\\hvksh\\mcp-servers\\primary-clarifier-mcp",
        "QSDSAN_TIMEOUT_S": "300"
      }
    }
  }
}
```

### `requirements.txt`
```
fastmcp>=0.1.0
qsdsan>=1.3.0
watertap>=0.12.0
numpy>=1.24.0
pandas>=2.0.0
scipy>=1.10.0
```

---

## Implementation Priorities

1. **Phase 1 (MVP):**
   - Basic directory structure
   - `elicit_basis_of_design`
   - `validate_design_inputs`
   - `heuristic_sizing_clarifier` (without chemicals)
   - State management

2. **Phase 2 (Configuration Tool Enhancement):**
   - Chemical dosing calculations
   - Power calculations
   - Sludge production
   - Economic estimation (heuristic)

3. **Phase 3 (Simulation Integration):**
   - QSDsan wrapper
   - Component fractionation
   - Subprocess isolation
   - Result extraction

4. **Phase 4 (Advanced Features):**
   - Enhanced removal with coagulation
   - WaterTAP costing integration
   - Report generation
   - Optimization tools