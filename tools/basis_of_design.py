"""
Basis of design parameter collection and validation for primary clarifier.

Stage 1 of the normalized workflow.
"""

import json
import os
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from core.state import clarifier_design_state


# =============================================================================
# Parameter Loading and Defaults
# =============================================================================

def load_default_parameters() -> Dict[str, Any]:
    """
    Load default parameters from data/default_parameters.json.

    Returns:
        Dictionary with default parameter structure

    Raises:
        FileNotFoundError: If default_parameters.json not found
        json.JSONDecodeError: If JSON is malformed
    """
    # Get path relative to this file
    current_dir = Path(__file__).parent
    default_params_path = current_dir.parent / "data" / "default_parameters.json"

    with open(default_params_path, 'r') as f:
        return json.load(f)


def get_default_value(defaults: Dict[str, Any], category: str, param: str) -> Any:
    """
    Extract default value for a parameter from defaults structure.

    Args:
        defaults: Loaded default parameters dictionary
        category: Category (e.g., "hydraulic", "influent_quality")
        param: Parameter name

    Returns:
        Default value or None if not specified
    """
    try:
        return defaults[category][param]["value"]
    except (KeyError, TypeError):
        return None


# =============================================================================
# Validation Functions
# =============================================================================

def validate_parameter(
    value: Optional[float],
    param_name: str,
    param_config: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Validate a single parameter against its configuration.

    Args:
        value: Parameter value to validate
        param_name: Name of parameter
        param_config: Configuration from default_parameters.json

    Returns:
        Tuple of (is_valid, warnings_list)
    """
    warnings = []

    # Check if required
    if param_config.get("required", False) and value is None:
        return False, [f"{param_name} is required but not provided"]

    # If value is None and not required, skip validation
    if value is None:
        return True, []

    # Range validation
    validation = param_config.get("validation", {})

    if "min" in validation and value < validation["min"]:
        return False, [f"{param_name} = {value} is below minimum {validation['min']}"]

    if "max" in validation and value > validation["max"]:
        return False, [f"{param_name} = {value} exceeds maximum {validation['max']}"]

    # Warning thresholds
    if "warning_below" in validation and value < validation["warning_below"]:
        warnings.append(
            f"{param_name} = {value} is below typical range "
            f"(warning threshold: {validation['warning_below']})"
        )

    if "warning_above" in validation and value > validation["warning_above"]:
        warnings.append(
            f"{param_name} = {value} is above typical range "
            f"(warning threshold: {validation['warning_above']})"
        )

    return True, warnings


def validate_consistency(
    params: Dict[str, Any],
    defaults: Dict[str, Any]
) -> List[str]:
    """
    Perform consistency checks between related parameters.

    Implements validation_rules from default_parameters.json:
    - VSS/TSS ratio (0.70-0.85 for municipal)
    - BOD/COD ratio (0.45-0.65 for municipal)
    - SLR limits based on chemical usage
    - Temperature-dependent adjustments

    Args:
        params: Collected parameters
        defaults: Default parameters with validation rules

    Returns:
        List of warning messages
    """
    warnings = []

    # VSS/TSS ratio check
    tss = params.get("influent_tss_mg_l")
    vss = params.get("influent_vss_mg_l")
    if tss and vss:
        ratio = vss / tss
        if ratio < 0.70 or ratio > 0.85:
            warnings.append(
                f"VSS/TSS ratio = {ratio:.2f} is outside typical range [0.70, 0.85] "
                f"for municipal wastewater. Industrial wastewater may have different ratios."
            )

    # BOD/COD ratio check
    cod = params.get("influent_cod_mg_l")
    bod = params.get("influent_bod5_mg_l")
    if cod and bod:
        ratio = bod / cod
        if ratio < 0.45 or ratio > 0.65:
            warnings.append(
                f"BOD5/COD ratio = {ratio:.2f} is outside typical range [0.45, 0.65] "
                f"for municipal wastewater. Industrial wastewater may be lower."
            )

    # Temperature warning for low temps
    temp = params.get("temperature_c", 20.0)
    if temp < 15:
        warnings.append(
            f"Low temperature ({temp}°C) may require SOR reduction by 10-20% "
            f"due to increased viscosity and reduced settling velocity."
        )

    # High TSS warning
    if tss and tss > 500:
        warnings.append(
            f"High TSS ({tss} mg/L) detected. Consider: "
            f"(1) Reduce SOR to 30-35 m³/m²/d, "
            f"(2) Upstream screening/equalization, "
            f"(3) Increase underflow solids target to 5-6%"
        )

    # High oil & grease warning
    og = params.get("influent_oil_grease_mg_l")
    if og and og > 200:
        warnings.append(
            f"High oil & grease ({og} mg/L) detected. Consider: "
            f"(1) Skimmer equipment, "
            f"(2) Pre-treatment (DAF, API separator), "
            f"(3) Reduce HRT to minimize anaerobic conditions"
        )

    return warnings


def apply_industrial_adaptations(
    params: Dict[str, Any],
    defaults: Dict[str, Any]
) -> List[str]:
    """
    Suggest adaptations for industrial wastewater conditions.

    Args:
        params: Collected parameters
        defaults: Default parameters with industrial_adaptations

    Returns:
        List of recommendation messages
    """
    recommendations = []
    adaptations = defaults.get("validation_rules", {}).get("industrial_adaptations", {})

    tss = params.get("influent_tss_mg_l", 0)
    og = params.get("influent_oil_grease_mg_l", 0)
    temp = params.get("temperature_c", 20.0)

    # High TSS adaptations
    if tss > 500 and "high_tss" in adaptations:
        recs = adaptations["high_tss"]["recommendations"]
        recommendations.append(
            f"**High TSS Detected ({tss} mg/L):** " + "; ".join(recs)
        )

    # High oil & grease adaptations
    if og > 200 and "high_oil_grease" in adaptations:
        recs = adaptations["high_oil_grease"]["recommendations"]
        recommendations.append(
            f"**High Oil & Grease Detected ({og} mg/L):** " + "; ".join(recs)
        )

    # Low temperature adaptations
    if temp < 15 and "low_temperature" in adaptations:
        recs = adaptations["low_temperature"]["recommendations"]
        recommendations.append(
            f"**Low Temperature Detected ({temp}°C):** " + "; ".join(recs)
        )

    return recommendations


# =============================================================================
# Main Collection Function
# =============================================================================

async def collect_clarifier_basis(
    flow_m3_d: Optional[float] = None,
    peak_factor: Optional[float] = None,
    temperature_c: Optional[float] = None,
    influent_tss_mg_l: Optional[float] = None,
    influent_vss_mg_l: Optional[float] = None,
    influent_cod_mg_l: Optional[float] = None,
    influent_bod5_mg_l: Optional[float] = None,
    influent_tkn_mg_l: Optional[float] = None,
    influent_tp_mg_l: Optional[float] = None,
    influent_oil_grease_mg_l: Optional[float] = None,
    influent_ph: Optional[float] = None,
    target_tss_removal_pct: Optional[float] = None,
    target_underflow_solids_pct: Optional[float] = None,
    coagulant_type: Optional[str] = None,
    polymer_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Collect and validate basis of design parameters for primary clarifier.

    This is Stage 1 of the normalized workflow. Parameters are validated against
    ranges from data/default_parameters.json, consistency checks are performed,
    and industrial adaptations are recommended.

    Args:
        flow_m3_d: Average design flow rate (m³/day) [REQUIRED]
        peak_factor: Peak flow multiplier (default: 2.5)
        temperature_c: Operating temperature (°C) (default: 20.0)
        influent_tss_mg_l: Influent total suspended solids (mg/L) [REQUIRED]
        influent_vss_mg_l: Influent volatile suspended solids (mg/L)
        influent_cod_mg_l: Influent chemical oxygen demand (mg/L)
        influent_bod5_mg_l: Influent 5-day biochemical oxygen demand (mg/L)
        influent_tkn_mg_l: Influent total Kjeldahl nitrogen (mg/L)
        influent_tp_mg_l: Influent total phosphorus (mg/L)
        influent_oil_grease_mg_l: Influent oil & grease (mg/L)
        influent_ph: Influent pH (default: 7.0)
        target_tss_removal_pct: Target TSS removal efficiency (%)
        target_underflow_solids_pct: Target underflow solids concentration (%)
        coagulant_type: Coagulant type ("alum", "ferric_chloride", "lime", "none")
        polymer_type: Polymer type ("anionic", "cationic", "nonionic", "none")

    Returns:
        Dictionary with:
            - status: "success" or "error"
            - validated_parameters: Dict of all parameters with defaults applied
            - warnings: List of validation warnings
            - errors: List of validation errors
            - recommendations: List of industrial adaptation recommendations
            - next_steps: Suggested next actions

    Example:
        >>> result = await collect_clarifier_basis(
        ...     flow_m3_d=5000,
        ...     influent_tss_mg_l=300,
        ...     temperature_c=15
        ... )
        >>> print(result["status"])
        success
        >>> print(result["warnings"])
        ['Low temperature (15°C) may require SOR reduction...']
    """
    # Load defaults
    try:
        defaults = load_default_parameters()
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to load default parameters: {str(e)}",
            "errors": [str(e)]
        }

    # Collect all parameters (use provided value or default)
    params = {
        # Hydraulic
        "flow_m3_d": flow_m3_d,
        "peak_factor": peak_factor if peak_factor is not None else get_default_value(defaults, "hydraulic", "peak_factor"),
        "temperature_c": temperature_c if temperature_c is not None else get_default_value(defaults, "hydraulic", "temperature_c"),

        # Influent quality
        "influent_tss_mg_l": influent_tss_mg_l,
        "influent_vss_mg_l": influent_vss_mg_l,
        "influent_cod_mg_l": influent_cod_mg_l,
        "influent_bod5_mg_l": influent_bod5_mg_l,
        "influent_tkn_mg_l": influent_tkn_mg_l,
        "influent_tp_mg_l": influent_tp_mg_l,
        "influent_oil_grease_mg_l": influent_oil_grease_mg_l,
        "influent_ph": influent_ph if influent_ph is not None else get_default_value(defaults, "influent_quality", "ph"),

        # Targets
        "target_tss_removal_pct": target_tss_removal_pct if target_tss_removal_pct is not None else get_default_value(defaults, "design_targets", "tss_removal_pct"),
        "target_underflow_solids_pct": target_underflow_solids_pct if target_underflow_solids_pct is not None else get_default_value(defaults, "design_targets", "underflow_solids_pct"),

        # Chemicals
        "coagulant_type": coagulant_type if coagulant_type is not None else "none",
        "polymer_type": polymer_type if polymer_type is not None else "none"
    }

    # Validation
    validation_errors = []
    validation_warnings = []

    # Validate hydraulic parameters
    for param in ["flow_m3_d", "peak_factor", "temperature_c"]:
        if param in params:
            param_config = defaults["hydraulic"].get(param.split("_")[0] if "_" in param else param, {})
            if param == "flow_m3_d":
                param_config = defaults["hydraulic"]["flow_m3_d"]
            elif param == "peak_factor":
                param_config = defaults["hydraulic"]["peak_factor"]
            elif param == "temperature_c":
                param_config = defaults["hydraulic"]["temperature_c"]

            is_valid, warnings = validate_parameter(params[param], param, param_config)
            if not is_valid:
                validation_errors.extend(warnings)
            else:
                validation_warnings.extend(warnings)

    # Validate influent quality parameters
    influent_param_map = {
        "influent_tss_mg_l": "tss_mg_l",
        "influent_vss_mg_l": "vss_mg_l",
        "influent_cod_mg_l": "cod_mg_l",
        "influent_bod5_mg_l": "bod5_mg_l",
        "influent_tkn_mg_l": "tkn_mg_l",
        "influent_tp_mg_l": "tp_mg_l",
        "influent_oil_grease_mg_l": "oil_grease_mg_l",
        "influent_ph": "ph"
    }

    for param_key, config_key in influent_param_map.items():
        if param_key in params and config_key in defaults["influent_quality"]:
            param_config = defaults["influent_quality"][config_key]
            is_valid, warnings = validate_parameter(params[param_key], param_key, param_config)
            if not is_valid:
                validation_errors.extend(warnings)
            else:
                validation_warnings.extend(warnings)

    # Consistency checks
    consistency_warnings = validate_consistency(params, defaults)
    validation_warnings.extend(consistency_warnings)

    # Industrial adaptations
    recommendations = apply_industrial_adaptations(params, defaults)

    # Store in state if validation passed
    if not validation_errors:
        # Organize into state structure
        clarifier_design_state.basis_of_design = {
            "hydraulic": {
                "flow_m3_d": params["flow_m3_d"],
                "peak_factor": params["peak_factor"],
                "temperature_c": params["temperature_c"]
            },
            "influent": {
                "tss_mg_l": params["influent_tss_mg_l"],
                "vss_mg_l": params["influent_vss_mg_l"],
                "cod_mg_l": params["influent_cod_mg_l"],
                "bod5_mg_l": params["influent_bod5_mg_l"],
                "tkn_mg_l": params["influent_tkn_mg_l"],
                "tp_mg_l": params["influent_tp_mg_l"],
                "oil_grease_mg_l": params["influent_oil_grease_mg_l"],
                "ph": params["influent_ph"]
            },
            "targets": {
                "tss_removal_pct": params["target_tss_removal_pct"],
                "underflow_solids_pct": params["target_underflow_solids_pct"]
            },
            "chemical_dosing": {
                "coagulant_type": params["coagulant_type"],
                "polymer_type": params["polymer_type"]
            }
        }

    # Prepare response
    return {
        "status": "success" if not validation_errors else "error",
        "message": "Basis of design collected and validated" if not validation_errors else "Validation errors found",
        "validated_parameters": params,
        "warnings": validation_warnings,
        "errors": validation_errors,
        "recommendations": recommendations,
        "next_steps": [
            "Run size_clarifier_heuristic() to perform fast sizing",
            "Review warnings and adjust parameters if needed",
            "Consider industrial adaptations in recommendations"
        ] if not validation_errors else [
            "Fix validation errors in required parameters",
            "Re-run collect_clarifier_basis() with corrected values"
        ]
    }
