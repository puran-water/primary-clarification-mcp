"""
Basis of Design Collection for Primary Clarifier

Extended to support ASM2d + MCAS state integration for cross-MCP communication.

Collects:
- Flow and hydraulic parameters
- Influent water quality (bulk + optional ion-by-ion)
- Operating conditions (temperature, pH, alkalinity)
- Chemical dosing information
- Wastewater characterization

Validation:
- TDS vs sum of ions (if both provided)
- Charge balance warning (>5% imbalance)
- Physical parameter ranges
"""

from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
import json


@dataclass
class ClarifierBasisOfDesign:
    """Complete basis of design for primary clarifier with state integration."""

    # === Required Parameters (no defaults) ===
    flow_m3_d: float
    influent_tss_mg_l: float

    # === Hydraulic Parameters ===
    peak_factor: float = 2.5

    # === Operating Conditions ===
    temperature_c: float = 20.0
    influent_ph: float = 7.2

    # === Bulk Water Quality (Optional) ===
    influent_vss_mg_l: Optional[float] = None
    vss_tss_ratio: float = 0.80  # Default if VSS not provided
    influent_cod_mg_l: Optional[float] = None
    influent_bod5_mg_l: Optional[float] = None
    influent_tkn_mg_l: Optional[float] = None
    influent_tp_mg_l: Optional[float] = None
    influent_oil_grease_mg_l: Optional[float] = 0.0

    # === Nitrogen Speciation (for ASM2d fractionation) ===
    influent_nh4_n_mg_l: Optional[float] = None  # Ammonium nitrogen (mg N/L)
    influent_no3_n_mg_l: Optional[float] = None  # Nitrate nitrogen (mg N/L)
    influent_no2_n_mg_l: Optional[float] = None  # Nitrite nitrogen (mg N/L)
    total_nitrogen_mg_n_l: Optional[float] = None  # Total nitrogen (mg N/L)

    # === Dissolved Oxygen & Redox ===
    influent_do_mg_l: Optional[float] = 0.0  # Dissolved oxygen (mg/L)
    influent_orp_mv: Optional[float] = None  # Oxidation-reduction potential (mV)

    # === Dissolved Solids & Alkalinity ===
    tds_mg_l: Optional[float] = None
    alkalinity_mg_caco3_l: float = 200.0  # Critical for carbonate chemistry
    total_inorganic_carbon_mg_c_l: Optional[float] = None
    specific_conductivity_us_cm: Optional[float] = None  # Conductivity (µS/cm)

    # === Organics Characterization ===
    influent_toc_mg_l: Optional[float] = None  # Total organic carbon (mg C/L)
    influent_doc_mg_l: Optional[float] = None  # Dissolved organic carbon (mg C/L)
    influent_silica_mg_l: Optional[float] = None  # Silica (mg SiO2/L)

    # === Wastewater Characterization ===
    wastewater_type: str = "municipal"  # municipal, dairy, brewery, pharmaceutical, industrial

    # === Ion Composition (Optional - for full water analysis) ===
    # If provided, used directly; otherwise estimated from TDS
    ion_composition: Optional[Dict[str, float]] = None
    # Expected keys if provided:
    #   Major ions: Ca_mg_l, Mg_mg_l, Na_mg_l, K_mg_l, Cl_mg_l, SO4_mg_l
    #   Carbonate: HCO3_mg_l, CO3_mg_l
    #   Nutrients: NH4_mg_l (as N), NO3_mg_l (as N), PO4_mg_l (as P)
    #   Trace metals: Fe_mg_l, Al_mg_l, Ba_mg_l, Sr_mg_l (for scaling/coagulation)

    estimate_ions_from_tds: bool = True  # Fallback if ions not provided

    # === Design Targets ===
    target_tss_removal_pct: float = 60.0
    target_underflow_solids_pct: float = 3.0

    # === Chemical Dosing ===
    coagulant_type: Optional[str] = None  # "alum", "ferric_chloride", None
    coagulant_dose_mg_l: float = 0.0
    polymer_type: Optional[str] = None  # "anionic", "cationic", None
    polymer_dose_mg_l: float = 0.0
    alkalinity_consumed_mg_caco3_l: Optional[float] = None  # Measured or estimated

    # === Validation Results (transient - recomputed on load) ===
    validation_warnings: list = field(default_factory=list, init=False, repr=False)
    validation_passed: bool = field(default=True, init=False, repr=False)

    def __post_init__(self):
        """Calculate derived parameters and validate."""
        # Calculate VSS from ratio if not provided
        if self.influent_vss_mg_l is None:
            self.influent_vss_mg_l = self.influent_tss_mg_l * self.vss_tss_ratio

        # Validate and run checks
        self._validate_parameters()

    def _validate_parameters(self):
        """Validate all parameters and populate warnings."""
        self.validation_warnings = []
        self.validation_passed = True

        # 1. Flow validation
        if self.flow_m3_d <= 0:
            self.validation_warnings.append("Flow must be positive")
            self.validation_passed = False

        # 2. Temperature validation
        if not (0 <= self.temperature_c <= 40):
            self.validation_warnings.append(
                f"Temperature {self.temperature_c}°C outside typical range (0-40°C)"
            )

        # 3. pH validation
        if not (5.0 <= self.influent_ph <= 10.0):
            self.validation_warnings.append(
                f"pH {self.influent_ph} outside typical range (5-10)"
            )

        # 4. TSS/VSS consistency
        if self.influent_vss_mg_l > self.influent_tss_mg_l:
            self.validation_warnings.append(
                "VSS cannot exceed TSS"
            )
            self.validation_passed = False

        # 5. VSS/TSS ratio check
        vss_tss_calc = self.influent_vss_mg_l / self.influent_tss_mg_l if self.influent_tss_mg_l > 0 else 0
        if not (0.5 <= vss_tss_calc <= 0.95):
            self.validation_warnings.append(
                f"VSS/TSS ratio {vss_tss_calc:.2f} outside typical range (0.5-0.95)"
            )

        # 6. TDS check if ions provided
        if self.ion_composition and self.tds_mg_l:
            # Define expected major ions for TDS contribution
            expected_major_ions = {
                "Ca_mg_l", "Mg_mg_l", "Na_mg_l", "K_mg_l",
                "Cl_mg_l", "SO4_mg_l", "HCO3_mg_l", "CO3_mg_l"
            }

            # Check ion coverage (what % of expected ions are provided)
            provided_major_ions = expected_major_ions.intersection(self.ion_composition.keys())
            ion_coverage_pct = len(provided_major_ions) / len(expected_major_ions) * 100

            # Only validate TDS closure if ≥80% of major ions are provided
            if ion_coverage_pct >= 80:
                ion_sum = sum(self.ion_composition.values())
                tds_diff_pct = abs(ion_sum - self.tds_mg_l) / self.tds_mg_l * 100

                # Relaxed threshold: 20% (was 10%)
                if tds_diff_pct > 20:
                    self.validation_warnings.append(
                        f"Sum of ions ({ion_sum:.1f} mg/L) differs from TDS "
                        f"({self.tds_mg_l:.1f} mg/L) by {tds_diff_pct:.1f}% "
                        f"(coverage: {ion_coverage_pct:.0f}% of major ions)"
                    )

        # 7. Charge balance check if ions provided
        if self.ion_composition:
            is_balanced, imbalance_pct = self._check_charge_balance(self.ion_composition)
            if not is_balanced:
                self.validation_warnings.append(
                    f"Charge imbalance {imbalance_pct:.1f}% (threshold 5%)"
                )

        # 8. Total nitrogen check
        if self.influent_tkn_mg_l and self.total_nitrogen_mg_n_l:
            # TN should be ≥ TKN (includes organic N + NH4-N)
            if self.total_nitrogen_mg_n_l < self.influent_tkn_mg_l:
                self.validation_warnings.append(
                    f"Total nitrogen ({self.total_nitrogen_mg_n_l} mg/L) "
                    f"cannot be less than TKN ({self.influent_tkn_mg_l} mg/L)"
                )

        # 9. Removal efficiency validation
        if not (10 <= self.target_tss_removal_pct <= 90):
            self.validation_warnings.append(
                f"Target TSS removal {self.target_tss_removal_pct}% "
                "outside typical range (10-90%)"
            )

        # 10. Underflow solids validation
        if not (1.0 <= self.target_underflow_solids_pct <= 10.0):
            self.validation_warnings.append(
                f"Target underflow solids {self.target_underflow_solids_pct}% "
                "outside typical range (1-10%)"
            )

    def _check_charge_balance(
        self,
        ions: Dict[str, float],
        tolerance_pct: float = 5.0
    ) -> Tuple[bool, float]:
        """
        Check electroneutrality of ion composition.

        Args:
            ions: Ion concentrations in mg/L
            tolerance_pct: Acceptable imbalance percentage

        Returns:
            (is_balanced, imbalance_percentage)
        """
        # Define ion properties (charge, molecular weight)
        # Note: NH4, NO3, PO4 are typically reported "as N" or "as P" in wastewater
        ion_properties = {
            "Ca_mg_l": {"charge": 2, "mw": 40.08},
            "Mg_mg_l": {"charge": 2, "mw": 24.31},
            "Na_mg_l": {"charge": 1, "mw": 22.99},
            "K_mg_l": {"charge": 1, "mw": 39.10},
            "NH4_mg_l": {"charge": 1, "mw": 14.01},  # As N basis (NH4-N)
            "Cl_mg_l": {"charge": -1, "mw": 35.45},
            "SO4_mg_l": {"charge": -2, "mw": 96.06},
            "HCO3_mg_l": {"charge": -1, "mw": 61.02},
            "CO3_mg_l": {"charge": -2, "mw": 60.01},
            "NO3_mg_l": {"charge": -1, "mw": 14.01},  # As N basis (NO3-N)
            "PO4_mg_l": {"charge": -3, "mw": 30.97},  # As P basis (PO4-P)
        }

        # Calculate total positive and negative charges (meq/L)
        cations_meq_l = 0.0
        anions_meq_l = 0.0

        for ion_key, conc_mg_l in ions.items():
            if ion_key not in ion_properties:
                continue

            props = ion_properties[ion_key]
            charge = props["charge"]
            mw = props["mw"]

            # Convert mg/L to meq/L: (mg/L) / (g/mol) * |charge|
            # mg/L ÷ (g/mol) = mmol/L, and mmol/L * charge = meq/L
            meq_l = (conc_mg_l / mw) * abs(charge)

            if charge > 0:
                cations_meq_l += meq_l
            else:
                anions_meq_l += meq_l

        # Calculate imbalance percentage
        total_charge = cations_meq_l + anions_meq_l
        if total_charge == 0:
            return True, 0.0

        imbalance_pct = abs(cations_meq_l - anions_meq_l) / total_charge * 100
        is_balanced = imbalance_pct <= tolerance_pct

        return is_balanced, imbalance_pct

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_json(self, filepath: Optional[str] = None) -> str:
        """Export to JSON string or file."""
        data = self.to_dict()
        json_str = json.dumps(data, indent=2)

        if filepath:
            with open(filepath, 'w') as f:
                f.write(json_str)

        return json_str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClarifierBasisOfDesign':
        """Create instance from dictionary.

        Filters out transient validation fields that will be recomputed.
        """
        # Remove transient fields (validation_warnings, validation_passed)
        filtered_data = {k: v for k, v in data.items()
                        if k not in ('validation_warnings', 'validation_passed')}
        return cls(**filtered_data)

    @classmethod
    def from_json(cls, json_str: str) -> 'ClarifierBasisOfDesign':
        """Create instance from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


def collect_clarifier_basis(
    # Required hydraulic
    flow_m3_d: float,
    peak_factor: float = 2.5,

    # Required water quality
    temperature_c: float = 20.0,
    influent_ph: float = 7.2,
    influent_tss_mg_l: float = 200.0,

    # Optional bulk parameters
    influent_vss_mg_l: Optional[float] = None,
    vss_tss_ratio: float = 0.80,
    influent_cod_mg_l: Optional[float] = None,
    influent_bod5_mg_l: Optional[float] = None,
    influent_tkn_mg_l: Optional[float] = None,
    influent_tp_mg_l: Optional[float] = None,
    influent_oil_grease_mg_l: float = 0.0,

    # Nitrogen speciation
    influent_nh4_n_mg_l: Optional[float] = None,
    influent_no3_n_mg_l: Optional[float] = None,
    influent_no2_n_mg_l: Optional[float] = None,
    total_nitrogen_mg_n_l: Optional[float] = None,

    # Dissolved oxygen & redox
    influent_do_mg_l: Optional[float] = 0.0,
    influent_orp_mv: Optional[float] = None,

    # TDS and alkalinity
    tds_mg_l: Optional[float] = None,
    alkalinity_mg_caco3_l: float = 200.0,
    total_inorganic_carbon_mg_c_l: Optional[float] = None,
    specific_conductivity_us_cm: Optional[float] = None,

    # Organics characterization
    influent_toc_mg_l: Optional[float] = None,
    influent_doc_mg_l: Optional[float] = None,
    influent_silica_mg_l: Optional[float] = None,

    # Wastewater characterization
    wastewater_type: str = "municipal",

    # Optional ion composition
    ion_composition: Optional[Dict[str, float]] = None,
    estimate_ions_from_tds: bool = True,

    # Design targets
    target_tss_removal_pct: float = 60.0,
    target_underflow_solids_pct: float = 3.0,

    # Chemicals
    coagulant_type: Optional[str] = None,
    coagulant_dose_mg_l: float = 0.0,
    polymer_type: Optional[str] = None,
    polymer_dose_mg_l: float = 0.0,
    alkalinity_consumed_mg_caco3_l: Optional[float] = None
) -> Dict[str, Any]:
    """
    Collect and validate basis of design parameters for primary clarifier.

    Extended for ASM2d + MCAS state integration to enable cross-MCP communication.

    Args:
        flow_m3_d: Average flow rate (m³/day)
        peak_factor: Peak flow multiplier (typically 2.0-3.0)
        temperature_c: Operating temperature (°C)
        influent_ph: pH value (critical for carbonate speciation)
        influent_tss_mg_l: Influent total suspended solids (mg/L)
        influent_vss_mg_l: Influent volatile suspended solids (mg/L)
        vss_tss_ratio: VSS/TSS ratio if VSS not provided (default 0.80)
        influent_cod_mg_l: Influent chemical oxygen demand (mg/L)
        influent_bod5_mg_l: Influent 5-day biochemical oxygen demand (mg/L)
        influent_tkn_mg_l: Influent total Kjeldahl nitrogen (mg/L)
        influent_tp_mg_l: Influent total phosphorus (mg/L)
        influent_oil_grease_mg_l: Influent oil & grease (mg/L)
        tds_mg_l: Total dissolved solids (mg/L)
        alkalinity_mg_caco3_l: Total alkalinity as CaCO₃ (mg/L)
        total_inorganic_carbon_mg_c_l: Total inorganic carbon (mg C/L)
        total_nitrogen_mg_n_l: Total nitrogen (mg N/L)
        wastewater_type: Wastewater classification (municipal/dairy/brewery/pharmaceutical/industrial)
        ion_composition: Optional full water analysis dict with keys:
            Ca_mg_l, Mg_mg_l, Na_mg_l, K_mg_l, Cl_mg_l, SO4_mg_l, etc.
        estimate_ions_from_tds: Fallback to estimate ions if not provided
        target_tss_removal_pct: Target TSS removal efficiency (%)
        target_underflow_solids_pct: Target underflow solids concentration (%)
        coagulant_type: Coagulant type ("alum", "ferric_chloride", None)
        coagulant_dose_mg_l: Coagulant dose (mg/L)
        polymer_type: Polymer type ("anionic", "cationic", None)
        polymer_dose_mg_l: Polymer dose (mg/L)
        alkalinity_consumed_mg_caco3_l: Alkalinity consumed by coagulant (mg CaCO₃/L)

    Returns:
        Dictionary with status, validated parameters, warnings, and next steps
    """
    try:
        # Create basis object
        basis = ClarifierBasisOfDesign(
            flow_m3_d=flow_m3_d,
            peak_factor=peak_factor,
            temperature_c=temperature_c,
            influent_ph=influent_ph,
            influent_tss_mg_l=influent_tss_mg_l,
            influent_vss_mg_l=influent_vss_mg_l,
            vss_tss_ratio=vss_tss_ratio,
            influent_cod_mg_l=influent_cod_mg_l,
            influent_bod5_mg_l=influent_bod5_mg_l,
            influent_tkn_mg_l=influent_tkn_mg_l,
            influent_tp_mg_l=influent_tp_mg_l,
            influent_oil_grease_mg_l=influent_oil_grease_mg_l,
            influent_nh4_n_mg_l=influent_nh4_n_mg_l,
            influent_no3_n_mg_l=influent_no3_n_mg_l,
            influent_no2_n_mg_l=influent_no2_n_mg_l,
            total_nitrogen_mg_n_l=total_nitrogen_mg_n_l,
            influent_do_mg_l=influent_do_mg_l,
            influent_orp_mv=influent_orp_mv,
            tds_mg_l=tds_mg_l,
            alkalinity_mg_caco3_l=alkalinity_mg_caco3_l,
            total_inorganic_carbon_mg_c_l=total_inorganic_carbon_mg_c_l,
            specific_conductivity_us_cm=specific_conductivity_us_cm,
            influent_toc_mg_l=influent_toc_mg_l,
            influent_doc_mg_l=influent_doc_mg_l,
            influent_silica_mg_l=influent_silica_mg_l,
            wastewater_type=wastewater_type,
            ion_composition=ion_composition,
            estimate_ions_from_tds=estimate_ions_from_tds,
            target_tss_removal_pct=target_tss_removal_pct,
            target_underflow_solids_pct=target_underflow_solids_pct,
            coagulant_type=coagulant_type,
            coagulant_dose_mg_l=coagulant_dose_mg_l,
            polymer_type=polymer_type,
            polymer_dose_mg_l=polymer_dose_mg_l,
            alkalinity_consumed_mg_caco3_l=alkalinity_consumed_mg_caco3_l
        )

        # Prepare response
        response = {
            "status": "success" if basis.validation_passed else "warning",
            "basis": basis.to_dict(),
            "warnings": basis.validation_warnings,
            "next_steps": _generate_next_steps(basis)
        }

        return response

    except (TypeError, ValueError) as e:
        # Handle type/value errors (wrong parameter types, invalid values)
        return {
            "status": "error",
            "error": f"{type(e).__name__}: {str(e)}",
            "basis": None,
            "warnings": [],
            "next_steps": ["Check parameter types and values, then retry collection"]
        }
    except Exception as e:
        # Unexpected errors - log full traceback
        import traceback
        return {
            "status": "error",
            "error": f"Unexpected error: {type(e).__name__}: {str(e)}",
            "traceback": traceback.format_exc(),
            "basis": None,
            "warnings": [],
            "next_steps": ["Report this error - unexpected exception occurred"]
        }


def _generate_next_steps(basis: ClarifierBasisOfDesign) -> list:
    """Generate recommended next steps based on basis completeness."""
    steps = []

    # Check for missing critical data
    if basis.influent_cod_mg_l is None and basis.influent_bod5_mg_l is None:
        steps.append(
            "Provide COD or BOD5 for ASM2d fractionation. Use Codex estimator if needed."
        )

    if basis.influent_tkn_mg_l is None:
        steps.append(
            "Provide TKN (total Kjeldahl nitrogen) for nitrogen balance"
        )

    if basis.influent_tp_mg_l is None:
        steps.append(
            "Provide TP (total phosphorus) for phosphorus balance"
        )

    # Ion composition check
    if basis.ion_composition is None:
        if basis.estimate_ions_from_tds:
            # Estimation mode enabled
            if basis.tds_mg_l is None:
                steps.append(
                    "Provide either full ion composition OR TDS for MCAS state estimation"
                )
            else:
                steps.append(
                    f"Will estimate ion composition from TDS ({basis.tds_mg_l} mg/L) "
                    f"using {basis.wastewater_type} wastewater template"
                )
        else:
            # Estimation mode disabled but no ions provided - CRITICAL
            steps.append(
                "CRITICAL: Ion composition required for MCAS state. "
                "Either provide full ion panel OR enable estimate_ions_from_tds."
            )

    # Recommend next phase
    if not steps:
        steps.append("Basis collection complete. Ready for Phase 3: Codex state estimator")

    return steps
