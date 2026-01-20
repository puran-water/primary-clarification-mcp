# Basis of Design Refactoring Plan

## Executive Summary

**Goal**: Align primary-clarifier-mcp's basis of design architecture with sibling MCP servers (aerobic-design-mcp, anaerobic-design-mcp) to enable seamless SFILES2 process flow integration where each unit's output state variables + MCAS become input to the downstream unit.

**Current Status**: Primary-clarifier-mcp accepts individual scalar parameters (flow, TSS, COD, BOD, TKN, TP, pH, alkalinity, etc.)

**Target Architecture**: Accept composite/bulk parameters + MCAS dict (matching RO design MCP / degasser design MCP), with optional ASM2d state variables from upstream units.

**Key Principle**: Translator service is ONLY called when:
1. First process unit in SFILES string (no upstream context), OR
2. Stand-alone process unit sizing/costing exercise

---

## Architecture Overview

### Current Input Structure (To Be Deprecated)
```python
# Direct scalar inputs
collect_clarifier_basis(
    flow_m3_d=1000,
    influent_tss_mg_l=250,
    influent_cod_mg_l=400,
    influent_bod5_mg_l=200,
    influent_tkn_mg_l=40,
    influent_tp_mg_l=8,
    ph=7.2,
    alkalinity_mg_l_caco3=150,
    temperature_c=20,
    # ... etc
)
```

### Target Input Structure
```python
# Composite parameters + MCAS dict + optional ASM2d state
basis = {
    "flow_m3_d": 1000,
    "temperature_c": 20,
    "composites": {
        "COD": 400,          # mg/L
        "BOD5": 200,         # mg/L
        "TSS": 250,          # mg/L
        "VSS": 175,          # mg/L
        "TKN": 40,           # mg/L as N
        "NH4_N": 30,         # mg/L as N
        "NO3_N": 0,          # mg/L as N
        "TP": 8,             # mg/L as P
        "PO4_P": 6,          # mg/L as P
        "alkalinity": 150,   # mg/L as CaCO3
        "VFA": 20,           # mg/L as COD
        "oil_grease": 40     # mg/L
    },
    "mcas": {
        # Cations (mg/L)
        "Na": 50, "K": 10, "Ca": 40, "Mg": 15, "NH4": 30,
        # Anions (mg/L)
        "Cl": 50, "SO4": 30, "HCO3": 150, "CO3": 0, "NO3": 0, "PO4": 6,
        # Others
        "SiO2": 15, "Fe": 0.1, "Al": 0.05
    },
    "asm2d_state": {  # Optional, from upstream unit or translator
        # 19-component ASM2d state vector
        "S_F": 20,    # Fermentable substrate (mg COD/L)
        "S_A": 10,    # Acetate (mg COD/L)
        "S_O": 0,     # Dissolved oxygen (mg O2/L)
        "S_NH4": 30,  # Ammonium (mg N/L)
        "S_NO3": 0,   # Nitrate (mg N/L)
        "S_PO4": 6,   # Phosphate (mg P/L)
        "S_ALK": 3.0, # Alkalinity (mol HCO3/m3)
        "S_I": 30,    # Soluble inert COD (mg COD/L)
        "X_I": 25,    # Particulate inert COD (mg COD/L)
        "X_S": 200,   # Slowly biodegradable substrate (mg COD/L)
        "X_H": 50,    # Heterotrophic biomass (mg COD/L)
        "X_PAO": 0,   # Phosphorus accumulating organisms (mg COD/L)
        "X_PP": 0,    # Polyphosphate (mg P/L)
        "X_PHA": 0,   # Polyhydroxyalkanoates (mg COD/L)
        "X_AUT": 0,   # Autotrophic nitrifying biomass (mg COD/L)
        "X_TSS": 250, # Total suspended solids (mg TSS/L)
        "X_MeOH": 0,  # Metal hydroxides (mg/L)
        "X_MeP": 0    # Metal phosphates (mg/L)
    }
}

# Call basis collection
collect_clarifier_basis(basis)
```

---

## Shared Translator Service Design

### Location
**Recommendation**: Build in existing `../plant_state/` package
- Already has placeholders: `plant_state/asm2d_converter.py`, `plant_state/mcas_tracker.py`
- Shared across all process unit MCPs (aerobic, anaerobic, primary clarifier, etc.)
- Can be exposed as lightweight Python API or FastMCP endpoint

### Interface

```python
# Translator API
class ASM2dTranslator:
    """Converts between composite parameters + MCAS and ASM2d state variables."""

    def composite_to_asm2d(
        self,
        composites: Dict[str, float],
        mcas: Dict[str, float],
        temperature_c: float = 20.0,
        fractionation_preset: str = "municipal"
    ) -> Dict[str, float]:
        """
        Convert composite/bulk parameters + MCAS to ASM2d state variables.

        Args:
            composites: Bulk parameters (COD, BOD5, TSS, VSS, TKN, TP, etc.)
            mcas: Ion-by-ion speciation (Na, K, Ca, Mg, NH4, Cl, SO4, HCO3, etc.)
            temperature_c: Temperature (°C)
            fractionation_preset: "municipal", "high_fat_industrial", "strong_industrial"

        Returns:
            ASM2d state dict with 19 components + derived pH + alkalinity
        """
        pass

    def asm2d_to_composite(
        self,
        asm2d_state: Dict[str, float],
        mcas: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Convert ASM2d state variables back to composite parameters.

        Args:
            asm2d_state: 19-component ASM2d state
            mcas: Ion-by-ion speciation

        Returns:
            {"composites": {...}, "mcas": {...}}
        """
        pass

    def validate_mcas_electroneutrality(
        self,
        mcas: Dict[str, float],
        tolerance: float = 0.05
    ) -> Dict[str, Any]:
        """
        Check MCAS charge balance.

        Returns:
            {
                "balanced": bool,
                "imbalance_pct": float,
                "cation_meq_l": float,
                "anion_meq_l": float,
                "warning": str or None
            }
        """
        pass

    def calculate_ph_alkalinity_from_mcas(
        self,
        mcas: Dict[str, float],
        temperature_c: float = 20.0
    ) -> Dict[str, float]:
        """
        Derive pH and alkalinity from carbonate equilibrium.

        Returns:
            {
                "pH": float,
                "alkalinity_mg_l_caco3": float,
                "hco3_mg_l": float,
                "co3_mg_l": float
            }
        """
        pass
```

### Fractionation Presets

**Municipal Baseline:**
- Particulate COD: 70% of total COD
- Slowly biodegradable (X_S): 50% of particulate
- Inert particulate (X_I): 10% of particulate
- Soluble fermentable (S_F): 15% of total COD
- Soluble inert (S_I): 5% of total COD
- Acetate (S_A): 10% of total COD
- BOD5/COD ratio: 0.5

**High-Fat Industrial:**
- Particulate COD: 85% of total COD
- Slowly biodegradable (X_S): 65% of particulate
- Inert particulate (X_I): 5% of particulate
- VFA/COD: 0.15-0.25
- BOD5/COD ratio: 0.6-0.7

**Strong Industrial:**
- Particulate COD: 60% of total COD
- Soluble fermentable (S_F): 25% of total COD
- BOD5/COD ratio: 0.4-0.5

---

## Primary Clarifier Mapping

### ASM2d State Variables → Clarifier Inputs

```python
def map_asm2d_to_clarifier_inputs(asm2d_state: Dict[str, float]) -> Dict[str, float]:
    """
    Map ASM2d state variables to primary clarifier inputs.

    Mapping logic:
    - TSS = X_TSS (direct)
    - VSS = X_S + X_H + X_PAO + X_AUT + X_PHA (biodegradable solids)
    - COD_total = S_F + S_A + S_I + X_I + X_S + X_H + X_PAO + X_PHA + X_AUT
    - COD_particulate = X_I + X_S + X_H + X_PAO + X_PHA + X_AUT
    - COD_soluble = S_F + S_A + S_I
    - TKN = S_NH4 + organic_N (from X_S, X_H via stoichiometry)
    - TP = S_PO4 + X_PP + organic_P (from X_S, X_H via stoichiometry)
    - Non-settleable fraction (X_ns) = (X_I_colloidal + S_I_adsorbed) / X_TSS
    """
    return {
        "influent_tss_mg_l": asm2d_state["X_TSS"],
        "influent_vss_mg_l": (
            asm2d_state["X_S"] + asm2d_state["X_H"] + asm2d_state["X_PAO"] +
            asm2d_state["X_AUT"] + asm2d_state["X_PHA"]
        ),
        "influent_cod_mg_l": (
            asm2d_state["S_F"] + asm2d_state["S_A"] + asm2d_state["S_I"] +
            asm2d_state["X_I"] + asm2d_state["X_S"] + asm2d_state["X_H"] +
            asm2d_state["X_PAO"] + asm2d_state["X_PHA"] + asm2d_state["X_AUT"]
        ),
        "influent_tkn_mg_l": asm2d_state["S_NH4"] + calculate_organic_n(asm2d_state),
        "influent_tp_mg_l": asm2d_state["S_PO4"] + asm2d_state["X_PP"] + calculate_organic_p(asm2d_state),
        "non_settleable_fraction": calculate_x_ns(asm2d_state),
        # ... other parameters
    }
```

### Clarifier Outputs → Updated ASM2d State

```python
def update_asm2d_after_clarification(
    influent_asm2d: Dict[str, float],
    clarifier_results: Dict[str, Any],
    chemistry: Dict[str, float] = None
) -> Dict[str, Any]:
    """
    Update ASM2d state based on clarifier performance.

    Returns:
        {
            "effluent_asm2d": {...},  # Clarified effluent
            "sludge_asm2d": {...},    # Settled sludge
            "effluent_mcas": {...},   # Updated MCAS (metals precipitated)
            "sludge_mcas": {...}      # Sludge MCAS (with metal hydroxides)
        }
    """
    # Apply TSS removal to particulate components
    tss_removal = clarifier_results["removal_efficiency"]

    # Settleable solids go to sludge
    sludge_fraction = {
        "X_S": influent_asm2d["X_S"] * tss_removal,
        "X_H": influent_asm2d["X_H"] * tss_removal,
        "X_PAO": influent_asm2d["X_PAO"] * tss_removal,
        # ... etc
    }

    # Non-settleable solids and solubles go to effluent
    effluent_fraction = {
        "X_I": influent_asm2d["X_I"] * (1 - tss_removal),
        "S_F": influent_asm2d["S_F"],  # Soluble, no removal
        "S_A": influent_asm2d["S_A"],  # Soluble, no removal
        # ... etc
    }

    # If chemistry provided, add metal hydroxide floc to sludge
    if chemistry:
        sludge_fraction["X_MeOH"] = clarifier_results.get("fe_precipitated_mg_l", 0) + \
                                     clarifier_results.get("al_precipitated_mg_l", 0)
        sludge_fraction["X_MeP"] = clarifier_results.get("p_precipitated_mg_l", 0)

        # Update MCAS: subtract precipitated metals from effluent
        effluent_mcas = mcas.copy()
        effluent_mcas["Fe"] -= chemistry.get("dose_fe_mg_l", 0)
        effluent_mcas["Al"] -= chemistry.get("dose_al_mg_l", 0)
        effluent_mcas["PO4"] -= clarifier_results.get("p_precipitated_mg_l", 0) * (31/95)  # P to PO4

    return {
        "effluent_asm2d": effluent_fraction,
        "sludge_asm2d": sludge_fraction,
        "effluent_mcas": effluent_mcas,
        "sludge_mcas": sludge_mcas
    }
```

---

## File Structure Refactoring

### Proposed Structure

```
primary-clarifier-mcp/
├── server.py                    # MCP tool definitions
├── utils/
│   ├── basis/
│   │   ├── __init__.py
│   │   ├── schema.py            # Pydantic models for composites + MCAS + ASM2d
│   │   ├── translator_client.py # Wraps shared translator MCP/API
│   │   ├── mapping.py           # ASM2d ↔ clarifier conversions
│   │   └── validation.py        # MCAS electroneutrality, bounds checking
│   ├── chemistry/
│   │   ├── __init__.py
│   │   ├── chemical_speciation.py
│   │   └── dose_response.py
│   ├── hydraulics/
│   │   ├── __init__.py
│   │   └── settling_models.py   # Takács, lamella models
│   ├── removal/
│   │   ├── __init__.py
│   │   └── removal_efficiency.py
│   └── qsdsan_imports.py
├── tests/
│   ├── test_basis_schema.py
│   ├── test_asm2d_mapping.py
│   ├── test_dose_response.py
│   ├── test_chemical_speciation.py
│   ├── test_removal_efficiency.py
│   ├── test_integration_phase23.py
│   └── fixtures/
│       ├── testdata_composites.json
│       ├── testdata_mcas.json
│       └── testdata_asm2d.json
└── mcp_config.json
```

### schema.py

```python
from pydantic import BaseModel, Field, validator
from typing import Dict, Optional

class Composites(BaseModel):
    """Composite/bulk wastewater parameters."""
    COD: float = Field(..., ge=0, description="COD (mg/L)")
    BOD5: float = Field(..., ge=0, description="5-day BOD (mg/L)")
    TSS: float = Field(..., ge=0, description="Total suspended solids (mg/L)")
    VSS: float = Field(..., ge=0, description="Volatile suspended solids (mg/L)")
    TKN: float = Field(..., ge=0, description="Total Kjeldahl nitrogen (mg/L as N)")
    NH4_N: float = Field(..., ge=0, description="Ammonium nitrogen (mg/L as N)")
    NO3_N: float = Field(0.0, ge=0, description="Nitrate nitrogen (mg/L as N)")
    TP: float = Field(..., ge=0, description="Total phosphorus (mg/L as P)")
    PO4_P: float = Field(..., ge=0, description="Phosphate (mg/L as P)")
    alkalinity: float = Field(..., ge=0, description="Alkalinity (mg/L as CaCO3)")
    VFA: float = Field(0.0, ge=0, description="Volatile fatty acids (mg/L as COD)")
    oil_grease: float = Field(0.0, ge=0, description="Oil & grease (mg/L)")

    @validator("VSS")
    def vss_less_than_tss(cls, v, values):
        if "TSS" in values and v > values["TSS"]:
            raise ValueError("VSS cannot exceed TSS")
        return v

    @validator("BOD5")
    def bod_less_than_cod(cls, v, values):
        if "COD" in values and v > values["COD"]:
            raise ValueError("BOD5 cannot exceed COD")
        return v

class MCAS(BaseModel):
    """Major cation-anion speciation (mg/L)."""
    # Cations
    Na: float = Field(..., ge=0)
    K: float = Field(..., ge=0)
    Ca: float = Field(..., ge=0)
    Mg: float = Field(..., ge=0)
    NH4: float = Field(..., ge=0)
    # Anions
    Cl: float = Field(..., ge=0)
    SO4: float = Field(..., ge=0)
    HCO3: float = Field(..., ge=0)
    CO3: float = Field(0.0, ge=0)
    NO3: float = Field(0.0, ge=0)
    PO4: float = Field(..., ge=0)
    # Others
    SiO2: float = Field(0.0, ge=0)
    Fe: float = Field(0.0, ge=0)
    Al: float = Field(0.0, ge=0)

class ASM2dState(BaseModel):
    """ASM2d 19-component state variables (mg/L or mg X/L)."""
    S_F: float = Field(..., ge=0, description="Fermentable substrate (mg COD/L)")
    S_A: float = Field(..., ge=0, description="Acetate (mg COD/L)")
    S_O: float = Field(0.0, ge=0, description="Dissolved oxygen (mg O2/L)")
    S_NH4: float = Field(..., ge=0, description="Ammonium (mg N/L)")
    S_NO3: float = Field(0.0, ge=0, description="Nitrate (mg N/L)")
    S_PO4: float = Field(..., ge=0, description="Phosphate (mg P/L)")
    S_ALK: float = Field(..., ge=0, description="Alkalinity (mol HCO3/m3)")
    S_I: float = Field(..., ge=0, description="Soluble inert COD (mg COD/L)")
    X_I: float = Field(..., ge=0, description="Particulate inert COD (mg COD/L)")
    X_S: float = Field(..., ge=0, description="Slowly biodegradable substrate (mg COD/L)")
    X_H: float = Field(..., ge=0, description="Heterotrophic biomass (mg COD/L)")
    X_PAO: float = Field(0.0, ge=0, description="PAO biomass (mg COD/L)")
    X_PP: float = Field(0.0, ge=0, description="Polyphosphate (mg P/L)")
    X_PHA: float = Field(0.0, ge=0, description="PHA (mg COD/L)")
    X_AUT: float = Field(0.0, ge=0, description="Autotrophic biomass (mg COD/L)")
    X_TSS: float = Field(..., ge=0, description="Total suspended solids (mg TSS/L)")
    X_MeOH: float = Field(0.0, ge=0, description="Metal hydroxides (mg/L)")
    X_MeP: float = Field(0.0, ge=0, description="Metal phosphates (mg/L)")

class BasisOfDesign(BaseModel):
    """Complete basis of design for primary clarifier."""
    flow_m3_d: float = Field(..., gt=0, description="Flow rate (m3/day)")
    temperature_c: float = Field(20.0, ge=0, le=50, description="Temperature (°C)")
    composites: Composites
    mcas: MCAS
    asm2d_state: Optional[ASM2dState] = None

    @validator("asm2d_state", pre=True, always=True)
    def generate_asm2d_if_missing(cls, v, values):
        """Auto-generate ASM2d state from composites if not provided."""
        if v is None and "composites" in values and "mcas" in values:
            # Call translator service
            from utils.basis.translator_client import translator
            v = translator.composite_to_asm2d(
                composites=values["composites"].dict(),
                mcas=values["mcas"].dict(),
                temperature_c=values.get("temperature_c", 20.0)
            )
        return v
```

---

## Migration Strategy

### Phase 1: Implement Shared Translator Service (Week 1-2)
1. Build `../plant_state/asm2d_converter.py` with core fractionation logic
2. Implement MCAS validation and pH/alkalinity derivation
3. Add fractionation presets (municipal, industrial, etc.)
4. Create unit tests for translator service
5. Expose as lightweight API (can add FastMCP endpoint later)

### Phase 2: Update Primary Clarifier Basis Collection (Week 3)
1. Create `utils/basis/schema.py` with Pydantic models
2. Implement `utils/basis/translator_client.py` wrapper
3. Create `utils/basis/mapping.py` for ASM2d ↔ clarifier conversions
4. Update `collect_clarifier_basis()` to accept new structure
5. Keep legacy scalar input behind compatibility flag (emit warnings)

### Phase 3: Update Clarifier Tools (Week 4)
1. Modify `size_clarifier_heuristic()` to work with new basis
2. Modify `simulate_clarifier_system()` to work with new basis
3. Update `calculate_removal_profile()` to accept ASM2d input
4. Implement effluent state calculation (updated ASM2d + MCAS)

### Phase 4: Testing & Validation (Week 5)
1. Create test fixtures with composite + MCAS + ASM2d data
2. Add `tests/test_basis_schema.py`
3. Add `tests/test_asm2d_mapping.py`
4. Validate against aerobic-design-mcp test cases
5. Test SFILES2 flow: primary → aerobic → secondary

### Phase 5: Documentation & Migration Guide (Week 6)
1. Write migration guide for existing users
2. Update API documentation with examples
3. Create tutorial: "Stand-alone clarifier sizing" vs. "SFILES2 integration"
4. Add example SFILES2 workflow notebook

---

## Technical Implementation Details

### Background Ionic Strength from MCAS

**Current**: Uses fixed 0.005 M background
**Target**: Calculate from MCAS

```python
def calculate_background_ionic_strength(mcas: Dict[str, float]) -> float:
    """
    Calculate background ionic strength from MCAS dict.

    Formula: I = 0.5 × Σ(c_i × z_i²) where c_i is mol/L
    """
    # Convert mg/L to mol/L and apply charge squared
    ionic_strength = 0.5 * (
        # Monovalent cations (z=+1)
        (mcas["Na"] / 22.99 + mcas["K"] / 39.10 + mcas["NH4"] / 18.04) / 1000 * 1 +
        # Divalent cations (z=+2)
        (mcas["Ca"] / 40.08 + mcas["Mg"] / 24.31) / 1000 * 4 +
        # Monovalent anions (z=-1)
        (mcas["Cl"] / 35.45 + mcas["HCO3"] / 61.02 + mcas["NO3"] / 62.00) / 1000 * 1 +
        # Divalent anions (z=-2)
        (mcas["SO4"] / 96.06 + mcas["CO3"] / 60.01) / 1000 * 4 +
        # Trivalent anion (z=-3)
        (mcas["PO4"] / 94.97) / 1000 * 9
    )
    return ionic_strength

# Use in dose_response.py
def calculate_ionic_strength_from_dose(
    dose_fe_mg_l: float = 0.0,
    dose_al_mg_l: float = 0.0,
    background_i_from_mcas: float = None  # NEW parameter
) -> float:
    """Calculate total ionic strength from dose + background."""
    if background_i_from_mcas is None:
        background_i_from_mcas = 0.005  # Fallback default

    # ... existing dose contribution logic ...

    return i_total + background_i_from_mcas
```

### pH and Alkalinity from MCAS

```python
def derive_ph_alkalinity_from_mcas(
    mcas: Dict[str, float],
    temperature_c: float = 20.0
) -> Dict[str, float]:
    """
    Derive pH and alkalinity from HCO3/CO3 in MCAS.

    Uses carbonate equilibrium:
    - K1 = [H+][HCO3-] / [H2CO3]
    - K2 = [H+][CO3--] / [HCO3-]
    - Alkalinity = [HCO3-] + 2[CO3--] + [OH-] - [H+]
    """
    # Convert mg/L to mol/L
    hco3_mol_l = mcas["HCO3"] / 61.02 / 1000
    co3_mol_l = mcas["CO3"] / 60.01 / 1000

    # Temperature-corrected equilibrium constants
    pK1 = 6.35 + (temperature_c - 25) * (-0.0055)
    pK2 = 10.33 + (temperature_c - 25) * (-0.009)
    pKw = 14.0 + (temperature_c - 25) * (-0.033)

    # Solve for pH using Newton iteration
    # Initial guess from ratio
    if hco3_mol_l > 0 and co3_mol_l > 0:
        ph_guess = pK2 + np.log10(co3_mol_l / hco3_mol_l)
    elif hco3_mol_l > 0:
        ph_guess = 8.3  # Typical for HCO3 dominated
    else:
        ph_guess = 7.0

    # Newton iteration to refine pH
    pH = solve_carbonate_equilibrium(hco3_mol_l, co3_mol_l, pK1, pK2, pKw, ph_guess)

    # Calculate alkalinity (mg/L as CaCO3)
    alkalinity_mg_l_caco3 = 50.04 * (hco3_mol_l + 2 * co3_mol_l) * 1000

    return {
        "pH": pH,
        "alkalinity_mg_l_caco3": alkalinity_mg_l_caco3,
        "hco3_mg_l": mcas["HCO3"],
        "co3_mg_l": mcas["CO3"]
    }
```

### Metal Hydroxide Floc Accounting

**Current Issue**: Precipitated metal hydroxides not added to solids

**Solution**: Include in sludge TSS and update MCAS

```python
# In chemical_speciation.py output
result = {
    "fe_precipitated_mg_l": fe_hydroxide_mg_l,
    "al_precipitated_mg_l": al_hydroxide_mg_l,
    "total_metal_floc_mg_l": fe_hydroxide_mg_l + al_hydroxide_mg_l,
    # ... existing outputs
}

# In removal_efficiency.py
def update_tss_with_metal_floc(
    influent_tss_mg_l: float,
    metal_floc_mg_l: float,
    tss_removal_efficiency: float
) -> Dict[str, float]:
    """
    Account for metal hydroxide floc in TSS balance.

    Metal floc is added to influent solids and captured in sludge.
    """
    # Total solids = influent TSS + precipitated metal floc
    total_solids = influent_tss_mg_l + metal_floc_mg_l

    # Apply removal efficiency
    removed_solids = total_solids * tss_removal_efficiency
    effluent_solids = total_solids * (1 - tss_removal_efficiency)

    return {
        "effluent_tss_mg_l": effluent_solids,
        "sludge_tss_mg_l": removed_solids,
        "metal_floc_in_sludge_mg_l": metal_floc_mg_l * tss_removal_efficiency
    }

# Update MCAS in effluent
def update_mcas_after_chemistry(
    influent_mcas: Dict[str, float],
    chemistry: Dict[str, float],
    chemistry_results: Dict[str, float]
) -> Dict[str, Any]:
    """
    Update MCAS dict after chemical precipitation.

    Subtracts precipitated metals from dissolved pool.
    """
    effluent_mcas = influent_mcas.copy()

    # Subtract precipitated Fe
    if "dose_fe_mg_l" in chemistry:
        effluent_mcas["Fe"] = max(0, effluent_mcas["Fe"] - chemistry["dose_fe_mg_l"])

    # Subtract precipitated Al
    if "dose_al_mg_l" in chemistry:
        effluent_mcas["Al"] = max(0, effluent_mcas["Al"] - chemistry["dose_al_mg_l"])

    # Subtract precipitated phosphate (convert P to PO4)
    p_precipitated = chemistry_results.get("p_precipitated_mg_l", 0)
    po4_precipitated = p_precipitated * (94.97 / 30.97)  # P to PO4
    effluent_mcas["PO4"] = max(0, effluent_mcas["PO4"] - po4_precipitated)

    return {
        "effluent_mcas": effluent_mcas,
        "precipitated_species": {
            "Fe_hydroxide_mg_l": chemistry_results.get("fe_precipitated_mg_l", 0),
            "Al_hydroxide_mg_l": chemistry_results.get("al_precipitated_mg_l", 0),
            "Metal_phosphate_mg_l": p_precipitated
        }
    }
```

---

## Process Flow Integration Example

### SFILES2 Sequence: Primary → Aerobic → Secondary

```python
# Step 1: User provides raw influent for first unit (primary clarifier)
raw_influent = {
    "flow_m3_d": 1000,
    "temperature_c": 20,
    "composites": {
        "COD": 400, "BOD5": 200, "TSS": 250, "TKN": 40, "TP": 8,
        "alkalinity": 150, "oil_grease": 40
    },
    "mcas": {
        "Na": 50, "K": 10, "Ca": 40, "Mg": 15, "NH4": 30,
        "Cl": 50, "SO4": 30, "HCO3": 150, "PO4": 6
    }
}

# Step 2: Call translator service to generate ASM2d state
from plant_state.asm2d_converter import ASM2dTranslator

translator = ASM2dTranslator()
asm2d_influent = translator.composite_to_asm2d(
    composites=raw_influent["composites"],
    mcas=raw_influent["mcas"],
    temperature_c=raw_influent["temperature_c"],
    fractionation_preset="municipal"
)

# Step 3: Run primary clarifier
from primary_clarifier_mcp import run_clarifier

primary_result = run_clarifier(
    flow_m3_d=raw_influent["flow_m3_d"],
    temperature_c=raw_influent["temperature_c"],
    asm2d_state=asm2d_influent,
    mcas=raw_influent["mcas"],
    chemistry={"dose_al_mg_l": 10.0}
)

# primary_result contains:
# {
#     "effluent_asm2d": {...},  # Updated state variables
#     "effluent_mcas": {...},   # Updated ion speciation
#     "sludge_asm2d": {...},    # Settled sludge
#     "sludge_mcas": {...},
#     "removal_profile": {...}  # TSS, BOD, COD, TP removals
# }

# Step 4: Pass effluent to aerobic reactor (NO translator call needed!)
from aerobic_design_mcp import run_aerobic_reactor

aerobic_result = run_aerobic_reactor(
    flow_m3_d=primary_result["effluent_flow_m3_d"],
    temperature_c=raw_influent["temperature_c"],
    asm2d_state=primary_result["effluent_asm2d"],  # Direct pass-through
    mcas=primary_result["effluent_mcas"],          # Direct pass-through
    srt_days=10,
    do_setpoint_mg_l=2.0
)

# Step 5: Pass aerobic effluent to secondary clarifier
from secondary_clarifier_mcp import run_secondary_clarifier

secondary_result = run_secondary_clarifier(
    flow_m3_d=aerobic_result["effluent_flow_m3_d"],
    temperature_c=raw_influent["temperature_c"],
    asm2d_state=aerobic_result["effluent_asm2d"],  # Direct pass-through
    mcas=aerobic_result["effluent_mcas"],          # Direct pass-through
    svi=120
)

# Step 6: Final effluent available in ASM2d + MCAS + composites
final_effluent = {
    "asm2d_state": secondary_result["effluent_asm2d"],
    "mcas": secondary_result["effluent_mcas"],
    "composites": translator.asm2d_to_composite(
        secondary_result["effluent_asm2d"],
        secondary_result["effluent_mcas"]
    )
}
```

---

## Validation & Testing Requirements

### Unit Tests

1. **MCAS electroneutrality**: Test charge balance validation
2. **pH/alkalinity derivation**: Test carbonate equilibrium solver
3. **ASM2d fractionation**: Test all presets produce valid states
4. **Clarifier mapping**: Test ASM2d → clarifier inputs → updated ASM2d

### Integration Tests

1. **Stand-alone clarifier**: Test with composites + MCAS (translator called)
2. **SFILES2 sequence**: Test primary → aerobic → secondary (translator called once)
3. **Recycle streams**: Test RAS/WAS handling with ASM2d states
4. **Metal chemistry**: Test MCAS updates after precipitation

### Validation Against Sibling MCPs

1. Compare MCAS structure with `../aerobic-design-mcp/`
2. Compare ASM2d state structure with `../anaerobic-design-mcp/`
3. Verify translator service works with both MCPs
4. Cross-validate process flow integration

---

## Open Questions for Resolution

1. **Translator service hosting**: FastMCP endpoint vs. Python package import?
2. **ASM2d X_MeOH and X_MeP**: Should these be standard ASM2d extensions or custom additions?
3. **Recycle stream handling**: How to handle RAS/WAS in process flow? Separate MCAS dicts?
4. **pH buffer capacity**: Should translator provide buffer capacity alongside pH?
5. **Industrial presets**: Do we need more fractionation presets (e.g., brewery, dairy, meat processing)?
6. **Calibration workflow**: Should parameters be stored in JSON/YAML for easy calibration?

---

## Success Criteria

✅ **Architecture Alignment**: Primary clarifier accepts same basis structure as aerobic/anaerobic MCPs
✅ **Translator Integration**: Shared translator service works across all process unit MCPs
✅ **Process Flow**: SFILES2 sequence runs without intermediate translator calls
✅ **Backward Compatibility**: Legacy interface deprecated with clear migration path
✅ **Testing**: Comprehensive test coverage with fixtures for composites + MCAS + ASM2d
✅ **Documentation**: Migration guide, API docs, and SFILES2 workflow examples

---

## Timeline Estimate

- **Phase 1** (Translator Service): 2 weeks
- **Phase 2** (Basis Collection): 1 week
- **Phase 3** (Tool Updates): 1 week
- **Phase 4** (Testing): 1 week
- **Phase 5** (Documentation): 1 week

**Total**: 6 weeks for complete refactoring

---

## References

- Aerobic-design-mcp: `../aerobic-design-mcp/`
- Anaerobic-design-mcp: `../anaerobic-design-mcp/`
- RO design MCP: `../ro-design-mcp/` (MCAS dict reference)
- Degasser design MCP: `../degasser-design-mcp/` (MCAS dict reference)
- SFILES2 block flow: `~/processeng/engineering-mcp-server/`
- ASM2d specification: Henze et al. (2000), Activated Sludge Models ASM1, ASM2, ASM2d and ASM3

---

**Document Status**: Draft for implementation planning
**Author**: Claude Code (AI Assistant)
**Date**: 2025-11-11
**Next Review**: Before Phase 1 implementation kickoff
