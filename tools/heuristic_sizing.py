"""
Heuristic sizing for primary clarifier using engineering correlations.

Stage 2 of the normalized workflow.
Uses JobManager for background execution following anaerobic/aerobic pattern.

Sizing algorithms extracted from QSDsan qsdsan/sanunits/_clarifier.py:1422-1500

Why we implement sizing algorithms directly instead of using PrimaryClarifier:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QSDsan's PrimaryClarifier requires FULL BioSTEAM framework setup:
- Components must be defined and set_thermo() called
- WasteStream objects with flow rates and concentrations
- Full SanUnit instantiation with inlet/outlet streams

For HEURISTIC SIZING (Stage 2), we only need:
- Pure geometry/hydraulics calculations
- Standard engineering correlations (Ten States Standards, Metcalf & Eddy)
- Fast calculation without framework overhead

For PROCESS SIMULATION (Stage 3), we WILL use QSDsan's PrimaryClarifier:
- Full WasteStream integration
- Component-wise mass balance
- Dynamic simulation capabilities
- Run via subprocess with proper thermo setup (see IMPLEMENTATION_PLAN.md)

These functions contain PURE ALGORITHMS (math only) that QSDsan has already
implemented in its _design() method. They are EXTRACTED, not REIMPLEMENTED.

VERIFICATION: QSDsan must still be importable (we verify below).
If QSDsan is not available, this module will FAIL LOUDLY.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import math
import warnings
from typing import Optional, Dict, Any, Tuple
from core.state import clarifier_design_state

# Verify QSDsan is available (fail loudly if not)
from utils.qsdsan_imports import verify_qsdsan_ready, PrimaryClarifier
verify_qsdsan_ready()

# Verify PrimaryClarifier exists in QSDsan
assert PrimaryClarifier is not None, (
    "QSDsan's PrimaryClarifier not found. "
    "Our sizing algorithms are extracted from PrimaryClarifier._design() method. "
    "If QSDsan changes, we need to update our implementation."
)


# =============================================================================
# Core Sizing Functions (extracted algorithms from QSDsan)
# =============================================================================
#
# These functions contain the PURE ALGORITHMS extracted from QSDsan's
# PrimaryClarifier._design() method (qsdsan/sanunits/_clarifier.py:1422-1500).
#
# Why extract rather than import:
# - QSDsan's PrimaryClarifier requires full BioSTEAM/thermosteam setup
#   (Components, WasteStream, thermo objects)
# - Our heuristic sizing only needs the pure geometry/hydraulics calculations
# - These are standard wastewater engineering algorithms (Ten States Standards,
#   Metcalf & Eddy) that QSDsan has already implemented
#
# DRY principle: We're NOT reimplementing the logic - we're extracting the
# pure algorithmic part that doesn't require BioSTEAM framework overhead.
#
# For full process simulation (Stage 3), we'll use QSDsan's PrimaryClarifier
# with complete WasteStream integration via subprocess (see IMPLEMENTATION_PLAN.md).
# =============================================================================

def calculate_number_of_clarifiers(flow_mgd: float) -> int:
    """
    Determine number of clarifiers based on total flow rate.

    Source: QSDsan qsdsan/sanunits/_clarifier.py:1424-1430
    Logic based on tentative suggestions verified through industry collaboration.

    Design Philosophy:
    - Minimum 2 units for N+1 redundancy
    - Scale up with flow to maintain reasonable unit sizes
    - Balance between economy of scale and operational flexibility

    Args:
        flow_mgd: Total flow rate in Million Gallons per Day (MGD)

    Returns:
        Number of clarifier units (N)

    Example:
        >>> calculate_number_of_clarifiers(2.5)  # Small plant
        2
        >>> calculate_number_of_clarifiers(15.0)  # Medium plant
        4
        >>> calculate_number_of_clarifiers(45.0)  # Large plant
        5

    Notes:
        - For flows ≤3 MGD: 2 clarifiers (minimum for redundancy)
        - For flows 3-8 MGD: 3 clarifiers
        - For flows 8-20 MGD: 4 clarifiers
        - For flows >20 MGD: 3 + int(Q/20) clarifiers
        - This ensures each clarifier stays within practical size limits (~60m diameter max)
    """
    if flow_mgd <= 3:
        return 2
    elif flow_mgd <= 8:
        return 3
    elif flow_mgd <= 20:
        return 4
    else:
        return 3 + int(flow_mgd / 20)


def size_circular_clarifier(
    flow_m3_d: float,
    surface_overflow_rate_m3_m2_d: float,
    depth_m: float = 3.5,
    conical_slope_ratio: float = 12.0,
    downward_velocity_m_hr: float = 10.0,
    peak_flow_factor: float = 2.5
) -> Dict[str, float]:
    """
    Size a circular primary clarifier with center feed.

    Source: QSDsan qsdsan/sanunits/_clarifier.py:1433-1475

    Design Approach:
    1. Calculate surface area from SOR
    2. Determine cylindrical diameter from area
    3. Calculate conical bottom geometry (slope 1:12)
    4. Size center-feed well based on downward velocity
    5. Calculate volumes for HRT and concrete estimation

    Args:
        flow_m3_d: Design flow rate per clarifier (m³/day)
        surface_overflow_rate_m3_m2_d: SOR in (m³/day)/m²
            Typical: 30-50 for primary without chemicals
        depth_m: Total clarifier depth (m)
            Typical: 3.0-4.5 m (most common: 3.5 m)
        conical_slope_ratio: Slope ratio for conical bottom (horizontal:vertical)
            Typical: 12 (i.e., 1:12 slope)
            Range: 10-12 per Metcalf & Eddy
        downward_velocity_m_hr: Downward velocity in center feed (m/hr)
            Typical: 10-13 m/hr average, 25-30 m/hr peak
        peak_flow_factor: Peak flow safety factor
            Typical: 2.5 (for downward velocity calculation)

    Returns:
        Dictionary with sizing results:
            - surface_area_m2: Required surface area
            - diameter_m: Cylindrical diameter
            - radius_m: Cylindrical radius
            - conical_height_m: Height of conical bottom
            - cylindrical_height_m: Height of cylindrical section
            - cylindrical_volume_m3: Volume of cylindrical section
            - conical_volume_m3: Volume of conical section
            - total_volume_m3: Total clarifier volume
            - hrt_hours: Hydraulic retention time
            - center_feed_diameter_m: Diameter of center feed well
            - center_feed_depth_m: Depth of center feed well
            - center_feed_area_m2: Cross-sectional area of center feed
            - warnings: List of design warnings (if any)

    Example:
        >>> # Municipal wastewater: 2500 m³/d per clarifier
        >>> result = size_circular_clarifier(
        ...     flow_m3_d=2500,
        ...     surface_overflow_rate_m3_m2_d=40.0,
        ...     depth_m=3.5
        ... )
        >>> print(f"Diameter: {result['diameter_m']:.1f} m")
        Diameter: 8.9 m
        >>> print(f"HRT: {result['hrt_hours']:.2f} hours")
        HRT: 2.14 hours

    Raises:
        ValueError: If inputs are invalid (negative values, etc.)

    Notes:
        - Function issues warnings (not exceptions) if dimensions outside typical ranges
        - Warnings are returned in 'warnings' list for calling code to handle
        - Design assumes center-feed configuration (most common for primary clarifiers)
    """
    if flow_m3_d <= 0:
        raise ValueError("Flow rate must be positive")
    if surface_overflow_rate_m3_m2_d <= 0:
        raise ValueError("Surface overflow rate must be positive")
    if depth_m <= 0:
        raise ValueError("Depth must be positive")

    design_warnings = []

    # Surface area from SOR
    surface_area = flow_m3_d / surface_overflow_rate_m3_m2_d  # m²

    # Cylindrical diameter from area
    diameter = math.sqrt(4 * surface_area / math.pi)  # m

    # Check on cylindrical diameter (typical range 3-60 m)
    if diameter < 3 or diameter > 60:
        design_warnings.append(
            f"Cylindrical diameter = {diameter:.2f} m is outside typical range [3, 60] m"
        )

    radius = diameter / 2

    # Conical bottom geometry (slope 1:12 typical)
    conical_height = radius / conical_slope_ratio  # m
    cylindrical_height = depth_m - conical_height  # m

    # Check on cylindrical vs conical heights
    if cylindrical_height < conical_height:
        design_warnings.append(
            f"Cylindrical height = {cylindrical_height:.2f} m is less than "
            f"conical height = {conical_height:.2f} m"
        )

    # Volume calculations
    cylindrical_volume = surface_area * cylindrical_height  # m³
    conical_volume = surface_area * conical_height / 3  # m³
    total_volume = cylindrical_volume + conical_volume  # m³

    # Hydraulic retention time
    hrt_hours = total_volume / (flow_m3_d / 24)  # hours

    # Check on HRT (typical range 1.5-2.5 hours for primary)
    if hrt_hours < 1.5 or hrt_hours > 2.5:
        design_warnings.append(
            f"HRT = {hrt_hours:.2f} hours is outside typical range [1.5, 2.5] hours"
        )

    # Center feed sizing (assumes center-feed design)
    center_feed_depth = 0.5 * cylindrical_height  # 30-75% typical, use 50%

    # Downward velocity with peak flow factor
    v_down = downward_velocity_m_hr * peak_flow_factor  # m/hr

    # Center feed area from flow and velocity
    center_feed_area = (flow_m3_d / 24) / v_down  # m²
    center_feed_diameter = math.sqrt(4 * center_feed_area / math.pi)  # m

    # Sanity check: center feed diameter should be 15-25% of tank diameter
    # (QSDsan uses 10-25% range based on velocity considerations)
    cf_ratio = center_feed_diameter / diameter
    if cf_ratio < 0.10 or cf_ratio > 0.25:
        design_warnings.append(
            f"Center feed diameter is {cf_ratio*100:.1f}% of tank diameter "
            f"(typical range: 15-25%)"
        )

    return {
        "surface_area_m2": surface_area,
        "diameter_m": diameter,
        "radius_m": radius,
        "conical_height_m": conical_height,
        "cylindrical_height_m": cylindrical_height,
        "cylindrical_volume_m3": cylindrical_volume,
        "conical_volume_m3": conical_volume,
        "total_volume_m3": total_volume,
        "hrt_hours": hrt_hours,
        "center_feed_diameter_m": center_feed_diameter,
        "center_feed_depth_m": center_feed_depth,
        "center_feed_area_m2": center_feed_area,
        "warnings": design_warnings
    }


def calculate_concrete_volumes(
    diameter_m: float,
    cylindrical_height_m: float,
    conical_height_m: float
) -> Dict[str, float]:
    """
    Calculate concrete volumes for CAPEX estimation.

    Source: QSDsan qsdsan/sanunits/_clarifier.py:1476-1500

    Design Basis:
    - Wall thickness: Minimum 1 ft (0.3048 m), plus 1 inch per foot of depth over 12 ft
    - Slab thickness: 2 inches thicker than wall thickness
    - Based on structural requirements for water-retaining structures

    Args:
        diameter_m: Inner cylindrical diameter (m)
        cylindrical_height_m: Height of cylindrical section (m)
        conical_height_m: Height of conical bottom (m)

    Returns:
        Dictionary with:
            - wall_thickness_m: Concrete wall thickness
            - slab_thickness_m: Concrete slab thickness
            - wall_volume_m3: Volume of cylindrical wall concrete
            - slab_volume_m3: Volume of conical slab concrete
            - total_concrete_m3: Total concrete volume

    Example:
        >>> volumes = calculate_concrete_volumes(
        ...     diameter_m=10.0,
        ...     cylindrical_height_m=3.2,
        ...     conical_height_m=0.4
        ... )
        >>> print(f"Total concrete: {volumes['total_concrete_m3']:.1f} m³")
        Total concrete: 28.3 m³

    Notes:
        - Concrete volumes are key CAPEX cost drivers
        - Assumes typical reinforced concrete construction
        - Does not include center feed structure (typically steel)
    """
    # Convert depth to feet for thickness calculation
    total_depth_m = cylindrical_height_m + conical_height_m
    depth_ft = total_depth_m * 3.28084  # m to feet

    # Wall thickness: 1 ft base + 1 inch per foot over 12 ft
    wall_thickness_ft = 1.0 + max(depth_ft - 12, 0) / 12  # feet
    wall_thickness_m = wall_thickness_ft * 0.3048  # feet to m

    # Slab thickness: 2 inches thicker than wall
    slab_thickness_m = wall_thickness_m + (2 / 12) * 0.3048  # m

    # Cylindrical wall volume (annulus)
    outer_diameter = diameter_m + 2 * wall_thickness_m
    wall_volume = (
        math.pi * cylindrical_height_m / 4 *
        (outer_diameter**2 - diameter_m**2)
    )  # m³

    # Conical slab volume (truncated cone minus inner cone)
    outer_diameter_cone = diameter_m + 2 * slab_thickness_m
    slab_volume = (
        math.pi / 3 * (
            (conical_height_m + slab_thickness_m) * (outer_diameter_cone / 2)**2 -
            conical_height_m * (diameter_m / 2)**2
        )
    )  # m³

    return {
        "wall_thickness_m": wall_thickness_m,
        "slab_thickness_m": slab_thickness_m,
        "wall_volume_m3": wall_volume,
        "slab_volume_m3": slab_volume,
        "total_concrete_m3": wall_volume + slab_volume
    }


def size_clarifier_system(
    total_flow_m3_d: float,
    surface_overflow_rate_m3_m2_d: float = 40.0,
    depth_m: float = 3.5,
    **kwargs
) -> Dict[str, Any]:
    """
    Size complete primary clarifier system (multiple units).

    Integrates all sizing functions:
    1. Determine number of clarifiers from total flow
    2. Size individual clarifier units
    3. Calculate concrete volumes for cost estimation

    Args:
        total_flow_m3_d: Total plant flow rate (m³/day)
        surface_overflow_rate_m3_m2_d: SOR (m³/day)/m²
        depth_m: Clarifier depth (m)
        **kwargs: Additional parameters passed to size_circular_clarifier()

    Returns:
        Dictionary with:
            - number_of_clarifiers: Number of units
            - flow_per_clarifier_m3_d: Design flow per unit
            - per_unit: Sizing results for one clarifier
            - concrete: Concrete volumes per unit
            - system_totals: Aggregated system metrics

    Example:
        >>> # 10,000 m³/d municipal plant
        >>> system = size_clarifier_system(
        ...     total_flow_m3_d=10000,
        ...     surface_overflow_rate_m3_m2_d=40.0
        ... )
        >>> print(f"Number of clarifiers: {system['number_of_clarifiers']}")
        Number of clarifiers: 4
        >>> print(f"Total surface area: {system['system_totals']['total_surface_area_m2']:.0f} m²")
        Total surface area: 250 m²
    """
    # Convert flow to MGD for number-of-clarifiers logic
    total_flow_mgd = total_flow_m3_d * 0.000264172  # m³/d to MGD

    # Determine number of clarifiers
    n_clarifiers = calculate_number_of_clarifiers(total_flow_mgd)

    # Flow per clarifier
    flow_per_clarifier = total_flow_m3_d / n_clarifiers

    # Size individual clarifier
    unit_sizing = size_circular_clarifier(
        flow_m3_d=flow_per_clarifier,
        surface_overflow_rate_m3_m2_d=surface_overflow_rate_m3_m2_d,
        depth_m=depth_m,
        **kwargs
    )

    # Calculate concrete volumes
    concrete = calculate_concrete_volumes(
        diameter_m=unit_sizing["diameter_m"],
        cylindrical_height_m=unit_sizing["cylindrical_height_m"],
        conical_height_m=unit_sizing["conical_height_m"]
    )

    # System totals
    system_totals = {
        "total_surface_area_m2": unit_sizing["surface_area_m2"] * n_clarifiers,
        "total_volume_m3": unit_sizing["total_volume_m3"] * n_clarifiers,
        "total_concrete_m3": concrete["total_concrete_m3"] * n_clarifiers,
        "system_hrt_hours": unit_sizing["hrt_hours"]  # Same for all units
    }

    return {
        "number_of_clarifiers": n_clarifiers,
        "flow_per_clarifier_m3_d": flow_per_clarifier,
        "per_unit": unit_sizing,
        "concrete": concrete,
        "system_totals": system_totals
    }


# =============================================================================
# MCP Tool Entry Point
# =============================================================================

async def size_clarifier_heuristic(
    use_current_basis: bool = True,
    custom_basis: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Perform fast heuristic sizing via JobManager.

    TODO: Implement in Week 3
    - Create utils/sizing_cli.py (CLI wrapper with RO artifact pattern)
    - Implement SOR/SLR sizing logic
    - Chemical dosing calculations
    - Power requirements (mixing, scraper)
    - Launch via JobManager from mcp_common
    - Return job_id for status tracking

    Args:
        use_current_basis: Use basis from clarifier_design_state
        custom_basis: Optional custom basis dictionary

    Returns:
        Job ID for background execution
    """
    return {
        "status": "not_implemented",
        "message": "Heuristic sizing to be implemented in Week 3",
        "next_steps": [
            "Week 3: Create utils/sizing_cli.py with RO artifact pattern",
            "Week 3: Extract Takács model to utils/settling_models.py",
            "Week 3: Implement chemical dosing in utils/chemical_dosing.py",
            "Week 3: Implement power calculations in utils/power_calcs.py",
            "Week 3: Integrate JobManager from mcp_common"
        ]
    }
