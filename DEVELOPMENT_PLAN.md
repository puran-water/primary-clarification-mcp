# Primary Clarifier MCP - Development Plan

## Overview

This document outlines the development roadmap for the Primary Clarifier MCP, covering three major clarification technologies:

1. **Conventional Circular Clarifiers** (Phase 1-7, Current)
2. **Lamella Clarifiers** (Phase 8-10, Planned)
3. **Dissolved Air Flotation (DAF)** (Phase 11-13, Planned)

Each technology follows a standardized **heuristic → simulation** workflow pattern with custom QSDsan SanUnits for rigorous modeling.

---

## Phase 1-7: ASM2d + MCAS State Integration (Conventional Clarifiers)

### Status: Phase 1 Complete (30%)

### Phase 1: Comprehensive Basis Collection ✅ COMPLETE
**Duration**: Completed 2025-11-12
**Goal**: Collect all design parameters with ASM2d + MCAS state integration

**Deliverables**:
- ✅ Extended `ClarifierBasisOfDesign` with 44 fields
- ✅ Nitrogen speciation (NH4-N, NO3-N, NO2-N, TN)
- ✅ Water quality parameters (DO, ORP, conductivity, TOC, DOC, silica)
- ✅ Ion composition (12 major ions) with charge balance validation
- ✅ Smart TDS validation with ion coverage checking (≥80% threshold)
- ✅ 44 passing tests with comprehensive edge case coverage
- ✅ Codex review approval

**Key Achievements**:
- Fixed critical charge balance bug (×1000 error)
- Corrected NH4/NO3/PO4 molecular weights to N/P-basis
- Implemented transient validation fields to prevent stale states
- Enhanced next_steps logic to catch missing ion requirements

---

### Phase 2: Shared plant_state Utilities
**Duration**: 1-2 weeks
**Goal**: Create reusable utilities for cross-MCP state management

**Deliverables**:
- [ ] Unit conversion utilities (mg/L ↔ mol/m³ ↔ molality)
- [ ] Charge balance validation functions
- [ ] Carbonate chemistry calculations (Henderson-Hasselbalch)
- [ ] Wastewater composition templates (municipal, industrial, high-strength)
- [ ] Ion estimation from TDS (Pitzer model or simple correlations)

**Implementation Approach**:
```python
# plant_state/unit_conversions.py
def mg_l_to_mol_m3(conc_mg_l: float, mw: float) -> float:
    """Convert mg/L to mol/m³."""
    return (conc_mg_l / mw) * 1.0  # mg/L / (g/mol) = mol/m³

# plant_state/charge_balance.py
def calculate_charge_balance(ion_composition: Dict[str, float]) -> Dict[str, Any]:
    """Calculate charge balance and anion/cation gap."""
    # Implementation from basis_collection.py
    ...

# plant_state/carbonate_chemistry.py
def calculate_carbonate_equilibrium(pH: float, alkalinity: float, temp_c: float) -> Dict[str, float]:
    """Calculate CO2/HCO3/CO3 speciation using Henderson-Hasselbalch."""
    ...
```

**Testing**:
- Unit tests for all conversion functions
- Edge cases: extreme pH, high ionic strength, temperature effects
- Validation against PHREEQC for carbonate chemistry

---

### Phase 3: Codex-Based State Estimator
**Duration**: 2-3 weeks
**Goal**: Implement AI-powered fractionation for industrial wastewater

**Deliverables**:
- [ ] Codex MCP integration for mASM2d state estimation
- [ ] Fractionation algorithms (COD → X_I, X_S, S_S, S_I)
- [ ] Nitrogen fractionation (TKN → S_NH4, X_ND, S_ND)
- [ ] Phosphorus fractionation (TP → S_PO4, X_PP, X_PAO, X_PHA)
- [ ] Validation tools (mass balance, COD closure, charge balance)
- [ ] Uncertainty quantification for estimates

**Implementation Approach**:
```python
# tools/state_estimator.py
async def estimate_masm2d_state(
    basis: ClarifierBasisOfDesign,
    codex_session_id: Optional[str] = None,
    validation_mode: str = "strict"
) -> Dict[str, Any]:
    """
    Estimate mASM2d state variables from influent characteristics.

    Uses Codex MCP server to intelligently fractionate:
    - COD components (X_I, X_S, S_S, S_I)
    - Nitrogen components (S_NH4, S_NO3, X_ND, S_ND)
    - Phosphorus components (S_PO4, X_PP, X_PAO, X_PHA)
    - Inert solids (X_I from VSS/TSS ratio)

    Returns:
        dict: {
            "masm2d_state": {...},  # 25 components
            "validation": {...},     # Mass balance, charge balance
            "uncertainty": {...},    # Confidence intervals
            "codex_session_id": "..."
        }
    """
    # Call Codex MCP with validation tools
    # Iterative refinement until mass balance closes
    # Return validated state + uncertainty
```

**Codex Validation Tools**:
- COD mass balance checker (should equal influent_cod_mg_l)
- Nitrogen mass balance checker (should equal influent_tkn_mg_l)
- Phosphorus mass balance checker (should equal influent_tp_mg_l)
- VSS/TSS ratio validator
- Charge balance validator (if ions provided)

**Testing**:
- Compare against known industrial wastewater characterizations
- Sensitivity analysis on input parameters
- Validation against aerobic-design-mcp state estimation

---

### Phase 4: Combined State Schema (mASM2d + MCAS)
**Duration**: 1 week
**Goal**: Define unified state representation for cross-MCP communication

**Deliverables**:
- [ ] `CombinedState` dataclass (mASM2d + MCAS)
- [ ] JSON schema definition
- [ ] Validation rules (charge balance, mass balance, ionic strength)
- [ ] Serialization/deserialization utilities

**Schema Structure**:
```python
@dataclass
class CombinedState:
    """
    Combined mASM2d + MCAS state for cross-MCP communication.

    Enables seamless integration with:
    - Aerobic MCPs: Use mASM2d biological state
    - Anaerobic MCPs: Convert mASM2d → ADM1
    - IX/RO MCPs: Use MCAS ionic composition
    - Degasser MCPs: Use MCAS + carbonate chemistry
    """
    # mASM2d biological state (25 components)
    S_O2: float  # Dissolved oxygen (mg O2/L)
    S_F: float   # Fermentable substrates (mg COD/L)
    S_A: float   # Acetate (mg COD/L)
    S_NH4: float # Ammonium (mg N/L)
    S_NO3: float # Nitrate (mg N/L)
    S_PO4: float # Orthophosphate (mg P/L)
    S_I: float   # Inert soluble organics (mg COD/L)
    S_ALK: float # Alkalinity (mol HCO3/m³)
    X_I: float   # Inert particulate organics (mg COD/L)
    X_S: float   # Slowly biodegradable substrates (mg COD/L)
    X_H: float   # Heterotrophic biomass (mg COD/L)
    X_PAO: float # Phosphorus accumulating organisms (mg COD/L)
    X_PP: float  # Polyphosphate (mg P/L)
    X_PHA: float # Polyhydroxyalkanoates (mg COD/L)
    X_AUT: float # Autotrophic nitrifying biomass (mg COD/L)
    X_MeOH: float # Metal hydroxides (mg COD/L)
    X_MeP: float  # Metal phosphates (mg COD/L)
    # ... (remaining mASM2d components)

    # MCAS ionic composition (12+ ions)
    Ca: float    # Calcium (mg/L or mol/m³)
    Mg: float    # Magnesium (mg/L or mol/m³)
    Na: float    # Sodium (mg/L or mol/m³)
    K: float     # Potassium (mg/L or mol/m³)
    NH4: float   # Ammonium (mg/L as N or mol/m³)
    Cl: float    # Chloride (mg/L or mol/m³)
    SO4: float   # Sulfate (mg/L or mol/m³)
    HCO3: float  # Bicarbonate (mg/L or mol/m³)
    CO3: float   # Carbonate (mg/L or mol/m³)
    NO3: float   # Nitrate (mg/L as N or mol/m³)
    PO4: float   # Phosphate (mg/L as P or mol/m³)
    H: float     # Hydrogen (mol/m³, from pH)
    OH: float    # Hydroxide (mol/m³, from pH)

    # Water quality parameters
    temperature_c: float
    pH: float
    ionic_strength: float  # Calculated from MCAS

    # Metadata
    units: str = "mixed"  # "mg_l" or "mol_m3"
    source: str = "primary_clarifier_effluent"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
```

---

### Phase 5: State Converters (mASM2d ↔ MCAS)
**Duration**: 1-2 weeks
**Goal**: Enable bidirectional conversion between biological and ionic states

**Deliverables**:
- [ ] `masm2d_to_mcas()` - Extract ionic composition from mASM2d
- [ ] `mcas_to_masm2d()` - Initialize mASM2d from ionic composition
- [ ] Consistency checks (charge balance, nitrogen balance, phosphorus balance)
- [ ] Unit conversion utilities (mg/L ↔ mol/m³)

**Implementation Approach**:
```python
# tools/state_converters.py
def masm2d_to_mcas(masm2d_state: Dict[str, float], basis: ClarifierBasisOfDesign) -> Dict[str, float]:
    """
    Extract MCAS ionic composition from mASM2d state.

    Conversions:
    - NH4 (MCAS) = S_NH4 (mASM2d)
    - NO3 (MCAS) = S_NO3 (mASM2d)
    - PO4 (MCAS) = S_PO4 (mASM2d)
    - HCO3/CO3 (MCAS) = S_ALK (mASM2d) via carbonate chemistry
    - Ca/Mg/Na/K/Cl/SO4 (MCAS) = from basis if provided, else estimated
    """
    ...

def mcas_to_masm2d(mcas_state: Dict[str, float], basis: ClarifierBasisOfDesign) -> Dict[str, float]:
    """
    Initialize mASM2d state from MCAS ionic composition.

    Use Codex estimator to fractionate organics (COD, BOD) if provided in basis.
    """
    ...
```

---

### Phase 6: Effluent Summarization Tool
**Duration**: 1 week
**Goal**: Generate standardized effluent summary for downstream MCPs

**Deliverables**:
- [ ] `summarize_clarifier_effluent()` MCP tool
- [ ] JSON format with removal envelopes (min/typical/max)
- [ ] Optional mASM2d state export
- [ ] Optional MCAS state export
- [ ] Uncertainty quantification

**Output Format**:
```json
{
  "effluent": {
    "flow_m3_d": 5000,
    "temperature_c": 20,
    "pH": 7.2,
    "tss_mg_l": 105,
    "vss_mg_l": 73,
    "cod_mg_l": 420,
    "bod5_mg_l": 210,
    "tkn_mg_l": 34,
    "nh4_n_mg_l": 28,
    "no3_n_mg_l": 2,
    "tp_mg_l": 6.8,
    "po4_p_mg_l": 5.5,
    "alkalinity_mg_caco3_l": 180,
    "tds_mg_l": 650,
    "conductivity_us_cm": 980
  },
  "removal_envelope": {
    "tss_removal_pct": {"min": 60, "typical": 65, "max": 70},
    "vss_removal_pct": {"min": 58, "typical": 63, "max": 68},
    "cod_removal_pct": {"min": 28, "typical": 30, "max": 35},
    "bod_removal_pct": {"min": 28, "typical": 30, "max": 35},
    "tp_removal_pct": {"min": 12, "typical": 15, "max": 18}
  },
  "sludge": {
    "flow_m3_d": 78,
    "solids_concentration_pct": 4.0,
    "dry_solids_kg_d": 975,
    "volatile_fraction": 0.70
  },
  "optional_masm2d_state": {
    "S_O2": 0.5, "S_F": 60, "S_A": 40, "S_NH4": 28, "S_NO3": 2,
    "S_PO4": 5.5, "S_I": 80, "S_ALK": 3.0, "X_I": 45, "X_S": 180,
    "X_H": 120, "X_PAO": 10, "X_PP": 1.0, "X_PHA": 5, "X_AUT": 8
  },
  "optional_mcas_state": {
    "Ca": 120, "Mg": 35, "Na": 180, "K": 25, "NH4": 28,
    "Cl": 220, "SO4": 110, "HCO3": 180, "CO3": 5, "NO3": 2, "PO4": 5.5
  },
  "uncertainty": {
    "tss_removal_std_pct": 3.5,
    "cod_removal_std_pct": 2.8,
    "masm2d_confidence": "medium"
  }
}
```

---

### Phase 7: Integration Testing
**Duration**: 1 week
**Goal**: End-to-end validation of state management pipeline

**Deliverables**:
- [ ] Integration tests: Basis → State Estimation → Effluent Summary
- [ ] Cross-MCP communication tests (mock aerobic/IX/RO MCPs)
- [ ] Mass balance validation across all conversions
- [ ] Performance benchmarking (Codex call latency)

---

## Phase 8-10: Lamella Clarifier Support

### Overview
Lamella (inclined plate) clarifiers provide high-rate settling in a compact footprint using inclined plates to increase effective settling area. Ideal for:
- Space-constrained sites
- High solids loading (>150 kg/m²/d)
- Retrofit/upgrade of existing clarifiers
- Applications requiring minimal footprint

### Phase 8: Lamella Heuristic Sizing
**Duration**: 1-2 weeks
**Goal**: Fast screening using lamella-specific correlations

**Deliverables**:
- [ ] Lamella-specific parameters in `ClarifierBasisOfDesign`:
  - Plate spacing (50-100 mm typical)
  - Plate angle (55-60° typical)
  - Plate length (1-3 m typical)
  - Target hydraulic loading rate (10-20 m³/m²/h)
- [ ] Heuristic sizing algorithm:
  - Calculate effective settling area (plates + base)
  - Estimate number of plates required
  - Calculate footprint and height
  - Estimate sludge removal requirements
- [ ] Comparison tool vs conventional circular clarifiers

**Heuristic Equations**:
```python
# Effective settling area per unit plan area
A_eff = A_plan * (1 + L * cos(θ) / h)

Where:
  A_plan = Plan area of lamella module
  L = Plate length (m)
  θ = Plate angle from horizontal (degrees)
  h = Plate spacing (m)

# Hydraulic loading rate (much higher than conventional)
HLR = 10-20 m³/m²/h (vs 1-2 m³/m²/h for conventional)

# TSS removal efficiency
η_TSS = f(v_s, HLR, θ, h)  # Empirical correlation
```

**Data Sources**:
- AguaClara lamella design equations (MIT License)
- Vendor data (Meurer, Parkson, WesTech)
- Literature correlations (Yao theory, Camp & Shields)

---

### Phase 9: Lamella Simulation with Custom SanUnit
**Duration**: 2-3 weeks
**Goal**: Rigorous simulation using QSDsan custom SanUnit

**Deliverables**:
- [ ] Custom `LamellaClarifier` SanUnit class
- [ ] Plate settling model (Yao theory)
- [ ] Particle size distribution tracking
- [ ] Sludge blanket dynamics
- [ ] Integration with ASM2d/ADM1 biological models
- [ ] Validation against pilot plant data

**QSDsan Custom SanUnit Implementation**:
```python
# sanunits/lamella_clarifier.py
from qsdsan import SanUnit, WasteStream
import numpy as np

class LamellaClarifier(SanUnit):
    """
    Custom SanUnit for lamella (inclined plate) clarifiers.

    Implements rigorous settling model based on Yao theory with:
    - Plate angle effects on settling efficiency
    - Particle size distribution tracking
    - Sludge blanket rise velocity
    - Biological kinetics (if ASM2d components present)
    """

    def __init__(
        self,
        ID='',
        ins=None,
        outs=('effluent', 'sludge'),
        plate_length_m=2.0,
        plate_spacing_m=0.05,
        plate_angle_deg=60,
        num_plates=100,
        plan_area_m2=50,
        **kwargs
    ):
        super().__init__(ID, ins, outs, **kwargs)
        self.plate_length_m = plate_length_m
        self.plate_spacing_m = plate_spacing_m
        self.plate_angle_deg = plate_angle_deg
        self.num_plates = num_plates
        self.plan_area_m2 = plan_area_m2

    def _run(self):
        """Simulate lamella clarifier operation."""
        influent = self.ins[0]
        effluent, sludge = self.outs

        # Calculate hydraulic loading rate
        HLR = influent.F_vol / (self.plan_area_m2 / 24)  # m³/m²/h

        # Calculate effective settling velocity with plate effects
        v_eff = self._calculate_effective_settling_velocity(
            influent.particle_size_distribution,
            self.plate_angle_deg,
            self.plate_spacing_m
        )

        # Calculate removal efficiency per particle size
        eta = self._calculate_removal_efficiency(v_eff, HLR)

        # Apply removal to TSS/VSS/particulate COD
        self._fractionate_solids(influent, effluent, sludge, eta)

        # Apply biological kinetics if ASM2d present
        if hasattr(influent, 'X_H'):
            self._apply_asm2d_kinetics(effluent, sludge)

    def _calculate_effective_settling_velocity(self, psd, angle_deg, spacing_m):
        """
        Calculate effective settling velocity using Yao theory.

        Accounts for:
        - Particle size distribution
        - Plate angle effects (settling distance reduction)
        - Turbulence in plate channels
        """
        # Yao theory: v_eff = v_s * sin(θ) / (sin(θ) + cos(θ) * v_s / v_scour)
        # Simplified for engineering design
        theta_rad = np.radians(angle_deg)
        enhancement_factor = 1 / np.sin(theta_rad)
        return psd * enhancement_factor

    def _calculate_removal_efficiency(self, v_eff, HLR):
        """Calculate removal efficiency per particle size."""
        # Camp-Shields equation with lamella corrections
        eta = 1 - np.exp(-v_eff / HLR)
        return eta

    def _fractionate_solids(self, influent, effluent, sludge, eta):
        """Apply removal efficiency to particulate components."""
        # TSS/VSS removal
        effluent.set_TSS((1 - eta) * influent.TSS)
        effluent.set_VSS((1 - eta) * influent.VSS)

        # Particulate COD removal (X_I, X_S, X_H, etc.)
        for component in ['X_I', 'X_S', 'X_H', 'X_PAO', 'X_AUT']:
            if hasattr(influent, component):
                setattr(effluent, component, (1 - eta) * getattr(influent, component))

        # Sludge stream = removed solids
        sludge.copy_like(influent)
        sludge.set_TSS(eta * influent.TSS)
        sludge.set_VSS(eta * influent.VSS)
```

**Validation**:
- Compare against AguaClara design software
- Validate against pilot plant data (Cornell, AguaClara)
- Sensitivity analysis on plate angle, spacing, length

---

### Phase 10: Lamella Design Optimization
**Duration**: 1 week
**Goal**: Automated design optimization and comparison tools

**Deliverables**:
- [ ] Multi-objective optimization (footprint, cost, removal efficiency)
- [ ] Comparison tool: Lamella vs Conventional vs DAF
- [ ] Sensitivity analysis on plate geometry
- [ ] Integration with knowledge base (clarifier_kb)

---

## Phase 11-13: Dissolved Air Flotation (DAF) Support

### Overview
DAF systems use micro-bubbles to float low-density solids (oil & grease, biological flocs, algae) to the surface for removal. Ideal for:
- Oil & grease removal (refineries, food processing)
- Low-density biological flocs (MBR pretreatment, algae removal)
- Cold water applications (enhanced performance vs sedimentation)
- Thickening of waste activated sludge (WAS)

### Phase 11: DAF Heuristic Sizing
**Duration**: 1-2 weeks
**Goal**: Fast screening using DAF-specific correlations

**Deliverables**:
- [ ] DAF-specific parameters in `ClarifierBasisOfDesign`:
  - Hydraulic loading rate (4-10 m³/m²/h typical)
  - Recycle ratio (8-12% typical)
  - Air-to-solids ratio (0.005-0.06 kg air/kg solids)
  - Pressure (450-600 kPa typical)
  - Contact time (1-3 minutes)
- [ ] Heuristic sizing algorithm:
  - Calculate tank dimensions (depth, surface area)
  - Estimate air requirements (compressor sizing)
  - Calculate recycle flow and pump sizing
  - Estimate polymer dosing requirements
  - Calculate float solids concentration (2-4% typical)
- [ ] Integration with `daf_kb` knowledge base collection

**Heuristic Equations**:
```python
# Surface loading rate (much higher than sedimentation)
SLR_daf = 4-10 m³/m²/h (vs 1-2 m³/m²/h for sedimentation)

# Recycle ratio (portion of effluent recycled through saturation tank)
R = 0.08-0.12 (8-12%)

# Air requirement (Dissolved air flotation stoichiometry)
A/S = 0.005-0.06 kg air / kg solids removed

# Saturation tank pressure (to dissolve air)
P = 450-600 kPa (65-87 psi)

# Float solids concentration
C_float = 2-4% (higher than sedimentation underflow)

# Removal efficiency (oil & grease, TSS)
η_OG = 80-95% (excellent for O&G)
η_TSS = 85-95% (higher than sedimentation for low-density solids)
```

**Data Sources**:
- Vendor data (DAF Corporation, KWI, Evoqua)
- Literature correlations (Edzwald, Haarhoff, Leppinen)
- Industrial case studies (daf_kb collection)

---

### Phase 12: DAF Simulation with Custom SanUnit
**Duration**: 2-3 weeks
**Goal**: Rigorous simulation using QSDsan custom SanUnit

**Deliverables**:
- [ ] Custom `DAFClarifier` SanUnit class
- [ ] Bubble-particle attachment model
- [ ] Dissolved air release model (Henry's law)
- [ ] Float thickening dynamics
- [ ] Integration with ASM2d/ADM1 biological models
- [ ] Validation against pilot plant data

**QSDsan Custom SanUnit Implementation**:
```python
# sanunits/daf_clarifier.py
from qsdsan import SanUnit, WasteStream
import numpy as np

class DAFClarifier(SanUnit):
    """
    Custom SanUnit for dissolved air flotation (DAF) clarifiers.

    Implements rigorous DAF model with:
    - Bubble-particle attachment kinetics
    - Dissolved air release (Henry's law)
    - Float layer thickening
    - Biological kinetics (if ASM2d components present)
    """

    def __init__(
        self,
        ID='',
        ins=None,
        outs=('effluent', 'float'),
        surface_area_m2=100,
        depth_m=2.5,
        recycle_ratio=0.10,
        pressure_kpa=500,
        air_to_solids_ratio=0.02,
        polymer_dose_mg_l=2.0,
        **kwargs
    ):
        super().__init__(ID, ins, outs, **kwargs)
        self.surface_area_m2 = surface_area_m2
        self.depth_m = depth_m
        self.recycle_ratio = recycle_ratio
        self.pressure_kpa = pressure_kpa
        self.air_to_solids_ratio = air_to_solids_ratio
        self.polymer_dose_mg_l = polymer_dose_mg_l

    def _run(self):
        """Simulate DAF clarifier operation."""
        influent = self.ins[0]
        effluent, float_sludge = self.outs

        # Calculate hydraulic loading rate
        HLR = influent.F_vol / (self.surface_area_m2 / 24)  # m³/m²/h

        # Calculate air release (Henry's law)
        air_released_kg_m3 = self._calculate_air_release(
            self.pressure_kpa,
            influent.T  # Temperature
        )

        # Calculate bubble-particle attachment efficiency
        attachment_eff = self._calculate_attachment_efficiency(
            influent.particle_size_distribution,
            self.polymer_dose_mg_l,
            air_released_kg_m3
        )

        # Calculate flotation efficiency
        flotation_eff = self._calculate_flotation_efficiency(
            attachment_eff,
            HLR,
            self.depth_m
        )

        # Apply removal to TSS/VSS/oil & grease/particulate COD
        self._fractionate_solids(influent, effluent, float_sludge, flotation_eff)

        # Apply biological kinetics if ASM2d present
        if hasattr(influent, 'X_H'):
            self._apply_asm2d_kinetics(effluent, float_sludge)

    def _calculate_air_release(self, pressure_kpa, temp_c):
        """
        Calculate air released using Henry's law.

        S_air = K_H * P

        Where:
          S_air = Dissolved air concentration (mg/L)
          K_H = Henry's constant (temperature dependent)
          P = Pressure (kPa)
        """
        # Henry's constant for air in water (temperature correction)
        K_H_20C = 0.019  # mg/L/kPa at 20°C
        theta = 1.024
        K_H = K_H_20C * theta**(temp_c - 20)

        # Air released when pressure drops to atmospheric
        S_air_saturated = K_H * pressure_kpa
        S_air_atmospheric = K_H * 101.325  # Atmospheric pressure
        air_released = S_air_saturated - S_air_atmospheric

        return air_released * self.recycle_ratio  # Only recycle stream is pressurized

    def _calculate_attachment_efficiency(self, psd, polymer_dose, air_released):
        """
        Calculate bubble-particle attachment efficiency.

        Depends on:
        - Particle size (larger particles attach better)
        - Polymer dose (enhances attachment)
        - Air availability (more bubbles = more attachment)
        """
        # Empirical correlation (Edzwald 2010)
        base_eff = 0.7  # Baseline with polymer
        size_factor = np.tanh(psd / 10)  # μm → efficiency
        polymer_factor = 1 + 0.3 * (polymer_dose / 5.0)  # Normalized to 5 mg/L
        air_factor = 1 + 0.2 * (air_released / 8.0)  # Normalized to 8 mg/L

        attachment_eff = base_eff * size_factor * polymer_factor * air_factor
        return np.clip(attachment_eff, 0, 0.98)

    def _calculate_flotation_efficiency(self, attachment_eff, HLR, depth):
        """
        Calculate overall flotation efficiency.

        Combines attachment efficiency with rise velocity:
        η = attachment_eff * (1 - exp(-v_rise * A / Q))
        """
        # Bubble-particle aggregate rise velocity (0.5-2 m/min typical)
        v_rise = 1.0  # m/min (conservative)

        # Retention time
        HRT = depth / (HLR / 60)  # minutes

        # Flotation efficiency (Camp-Shields analogue)
        flotation_eff = attachment_eff * (1 - np.exp(-v_rise * HRT / depth))
        return flotation_eff

    def _fractionate_solids(self, influent, effluent, float_sludge, eta):
        """Apply flotation efficiency to particulate components and O&G."""
        # TSS/VSS removal (higher than sedimentation for low-density solids)
        effluent.set_TSS((1 - eta * 1.1) * influent.TSS)  # 10% boost vs sedimentation
        effluent.set_VSS((1 - eta * 1.1) * influent.VSS)

        # Oil & grease removal (excellent for DAF)
        if hasattr(influent, 'oil_grease_mg_l'):
            effluent.oil_grease_mg_l = (1 - 0.90) * influent.oil_grease_mg_l

        # Particulate COD removal
        for component in ['X_I', 'X_S', 'X_H', 'X_PAO', 'X_AUT']:
            if hasattr(influent, component):
                setattr(effluent, component, (1 - eta * 1.1) * getattr(influent, component))

        # Float sludge = removed solids (concentrated 2-4%)
        float_sludge.copy_like(influent)
        float_sludge.set_TSS(eta * 1.1 * influent.TSS)
        float_sludge.set_VSS(eta * 1.1 * influent.VSS)
        float_concentration_pct = 3.0  # Typical float solids
        float_sludge.F_vol = (float_sludge.TSS * influent.F_vol) / (float_concentration_pct * 10000)
```

**Validation**:
- Compare against vendor pilot data (DAF Corporation, KWI)
- Validate against literature models (Edzwald, Leppinen)
- Industrial case studies (oil & grease removal, MBR pretreatment)

---

### Phase 13: DAF Design Optimization & Multi-Technology Comparison
**Duration**: 1-2 weeks
**Goal**: Automated design optimization and technology selection

**Deliverables**:
- [ ] Multi-objective optimization (footprint, energy, cost, removal efficiency)
- [ ] Comprehensive comparison tool: **Conventional vs Lamella vs DAF**
  - Side-by-side performance comparison
  - CAPEX/OPEX analysis (DAF has higher OPEX due to air compression)
  - Footprint comparison (DAF ~ Lamella < Conventional)
  - Application suitability matrix (O&G → DAF, high TSS → Conventional, space-constrained → Lamella)
- [ ] Decision support tool with scoring matrix
- [ ] Integration with all knowledge base collections (clarifier_kb, daf_kb, misc_process_kb)

**Technology Comparison Matrix**:

| Parameter | Conventional Clarifier | Lamella Clarifier | DAF Clarifier |
|-----------|----------------------|------------------|---------------|
| **Footprint** | Large (SOR 30-50 m³/m²/d) | Small (5-10× area reduction) | Small (HLR 4-10 m³/m²/h) |
| **TSS Removal** | 50-70% | 60-80% | 85-95% (low-density) |
| **O&G Removal** | 10-30% | 20-40% | 80-95% |
| **CAPEX** | Baseline ($$$) | 1.3-1.5× ($$$$) | 1.5-2.0× ($$$$$) |
| **OPEX** | Low ($$) | Medium ($$$) | High ($$$$) due to air |
| **Solids Loading** | 100-150 kg/m²/d | 150-300 kg/m²/d | 100-200 kg/m²/d |
| **HRT** | 1.5-2.5 hours | 10-20 minutes | 10-20 minutes |
| **Best For** | Municipal, high TSS | Retrofits, limited space | O&G, MBR pretreat, algae |
| **Cold Water** | Reduced performance | Reduced performance | Enhanced performance |

---

## Implementation Timeline

### Completed (30%)
- ✅ **Phase 1**: Comprehensive Basis Collection (Weeks 1-2, Completed 2025-11-12)

### Near-Term (Next 6-8 weeks, 40%)
- **Phase 2**: Shared plant_state Utilities (Weeks 3-4)
- **Phase 3**: Codex-Based State Estimator (Weeks 5-7)
- **Phase 4**: Combined State Schema (Week 8)
- **Phase 5**: State Converters (Weeks 9-10)

### Mid-Term (Weeks 11-12, 10%)
- **Phase 6**: Effluent Summarization Tool (Week 11)
- **Phase 7**: Integration Testing (Week 12)

### Long-Term (Weeks 13-20, 20%)
- **Phase 8**: Lamella Heuristic Sizing (Weeks 13-14)
- **Phase 9**: Lamella Simulation with Custom SanUnit (Weeks 15-17)
- **Phase 10**: Lamella Design Optimization (Week 18)
- **Phase 11**: DAF Heuristic Sizing (Weeks 19-20)

### Future (Weeks 21-26)
- **Phase 12**: DAF Simulation with Custom SanUnit (Weeks 21-23)
- **Phase 13**: DAF Optimization & Multi-Technology Comparison (Weeks 24-26)

---

## Success Criteria

### Phase 1-7 (ASM2d + MCAS)
- ✅ All tests passing (44/44 for Phase 1)
- [ ] State estimator achieves <10% error on known datasets
- [ ] Effluent summary validates against downstream MCPs
- [ ] Cross-MCP communication tested with aerobic-design-mcp, ix-design-mcp, ro-design-mcp

### Phase 8-10 (Lamella)
- [ ] Lamella SanUnit validates against AguaClara design software (<15% error)
- [ ] Pilot plant data validation (Cornell/AguaClara datasets)
- [ ] Optimization tool identifies Pareto-optimal designs

### Phase 11-13 (DAF)
- [ ] DAF SanUnit validates against vendor pilot data (<20% error)
- [ ] Industrial case study validation (oil & grease removal, MBR pretreatment)
- [ ] Multi-technology comparison tool matches engineering judgment on 10 test cases

---

## References

### ASM2d & MCAS
- Henze et al. (2000): Activated Sludge Models ASM1, ASM2, ASM2d, ASM3
- Li et al. (2021): QSDsan documentation
- WaterTAP MCAS property package documentation

### Lamella Clarifiers
- AguaClara design equations: https://github.com/AguaClara/Textbook
- Yao (1970): Theoretical study of high rate sedimentation
- Camp & Shields (1953): Sedimentation and design of settling tanks

### Dissolved Air Flotation
- Edzwald (2010): Dissolved air flotation and me
- Leppinen (1999): Dissolved air flotation in industrial wastewaters
- Haarhoff & Edzwald (2004): Dissolved air flotation modeling

---

## Notes

- **Custom SanUnits**: Both Lamella and DAF require custom QSDsan SanUnit classes since they're not in the standard library
- **Knowledge Base Integration**: All three technologies leverage semantic search (clarifier_kb, daf_kb) for context-aware design recommendations
- **Heuristic → Simulation Pattern**: All three follow the same workflow (fast heuristic screening, then rigorous simulation), enabling fair comparisons
- **Cross-MCP Communication**: All effluent summaries follow the same standardized format (mASM2d + MCAS) for seamless integration with downstream MCPs
