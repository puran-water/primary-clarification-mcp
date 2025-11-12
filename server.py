#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Primary Clarifier Design MCP Server

A modular MCP server for industrial wastewater primary clarifier design.
Provides tools for:
- Basis of design parameter collection and validation
- Heuristic sizing (SOR/SLR-based for conventional circular clarifiers)
- Empirical process simulation with removal efficiency modeling
- Chemical dosing calculations (coagulation/flocculation)
- Power requirements (flash mixing, flocculation, scraper)
- Economic analysis (CAPEX, OPEX, LCOW)

Workflow: Basis of Design → Heuristic Sizing → Process Simulation → Costing
"""

import os
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

# Set required environment variables
if 'LOCALAPPDATA' not in os.environ:
    if sys.platform == 'win32':
        os.environ['LOCALAPPDATA'] = os.path.join(os.path.expanduser('~'), 'AppData', 'Local')
    else:
        os.environ['LOCALAPPDATA'] = os.path.join(os.path.expanduser('~'), '.local')

# Set Jupyter platform dirs to avoid warnings
if 'JUPYTER_PLATFORM_DIRS' not in os.environ:
    os.environ['JUPYTER_PLATFORM_DIRS'] = '1'

# Configure logging BEFORE importing other modules
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add mcp_common to path if needed
mcp_common_path = Path(__file__).parent.parent / "mcp_common"
if mcp_common_path.exists() and str(mcp_common_path) not in sys.path:
    sys.path.insert(0, str(mcp_common_path))

# Apply STDIO buffering patch from mcp_common
try:
    from mcp_common import apply_stdio_patch
    apply_stdio_patch()
    logger.info("Applied STDIO buffer patch (max_buffer_size=256) from mcp_common")
except ImportError as e:
    logger.warning(f"Could not import mcp_common STDIO patch: {e}")
    logger.warning("Proceeding without STDIO patch - may experience blocking on WSL2")

from fastmcp import FastMCP

# FastMCP lifespan (currently disabled to avoid I/O contention)
@asynccontextmanager
async def lifespan(server):
    """Lifespan context manager."""
    logger.info("Primary Clarifier Design Server started")
    yield
    logger.info("Primary Clarifier Design Server shutting down")

# Create FastMCP instance
mcp = FastMCP("Primary Clarifier Design Server", lifespan=lifespan)

# ==============================================================================
# LAZY IMPORTS: Tools imported only when called to speed up server startup
# Heavy dependencies (QSDsan, WaterTAP) imported on-demand
# ==============================================================================

# =====================
# Stage 1: Basis of Design
# =====================

@mcp.tool()
async def collect_clarifier_basis(
    flow_m3_d: float = None,
    peak_factor: float = None,
    temperature_c: float = None,
    influent_tss_mg_l: float = None,
    influent_vss_mg_l: float = None,
    influent_cod_mg_l: float = None,
    influent_bod5_mg_l: float = None,
    influent_tkn_mg_l: float = None,
    influent_tp_mg_l: float = None,
    influent_oil_grease_mg_l: float = None,
    influent_ph: float = None,
    target_tss_removal_pct: float = None,
    target_underflow_solids_pct: float = None,
    coagulant_type: str = None,
    polymer_type: str = None
):
    """
    Collect and validate basis of design parameters for primary clarifier.

    Args:
        flow_m3_d: Average flow rate (m³/day)
        peak_factor: Peak flow multiplier (typically 2.0-3.0)
        temperature_c: Operating temperature (°C)
        influent_tss_mg_l: Influent total suspended solids (mg/L)
        influent_vss_mg_l: Influent volatile suspended solids (mg/L)
        influent_cod_mg_l: Influent chemical oxygen demand (mg/L)
        influent_bod5_mg_l: Influent 5-day biochemical oxygen demand (mg/L)
        influent_tkn_mg_l: Influent total Kjeldahl nitrogen (mg/L)
        influent_tp_mg_l: Influent total phosphorus (mg/L)
        influent_oil_grease_mg_l: Influent oil & grease (mg/L)
        influent_ph: Influent pH
        target_tss_removal_pct: Target TSS removal efficiency (%)
        target_underflow_solids_pct: Target underflow solids concentration (%)
        coagulant_type: Coagulant type ("alum", "ferric", "none")
        polymer_type: Polymer type ("anionic", "cationic", "none")

    Returns:
        Dictionary with status, validated parameters, warnings, and next steps
    """
    from tools.basis_of_design import collect_clarifier_basis as _impl
    return await _impl(
        flow_m3_d, peak_factor, temperature_c,
        influent_tss_mg_l, influent_vss_mg_l, influent_cod_mg_l, influent_bod5_mg_l,
        influent_tkn_mg_l, influent_tp_mg_l, influent_oil_grease_mg_l, influent_ph,
        target_tss_removal_pct, target_underflow_solids_pct,
        coagulant_type, polymer_type
    )

# =====================
# Stage 2: Heuristic Sizing
# =====================

@mcp.tool()
async def size_clarifier_heuristic(
    use_current_basis: bool = True,
    custom_basis: dict = None
):
    """
    Perform fast heuristic sizing of primary clarifier using engineering correlations.

    Sizing approach:
    - Surface overflow rate (SOR): 30-50 m³/m²/d
    - Solids loading rate (SLR): 100-150 kg/m²/d
    - Hydraulic retention time (HRT): 1.5-2.5 hours
    - Chemical dosing rates
    - Power requirements (mixing, scraper)

    Args:
        use_current_basis: Use basis of design from current state (default: True)
        custom_basis: Optional custom basis dictionary

    Returns:
        Job ID for background execution. Use get_job_status() and get_job_results()
    """
    from tools.heuristic_sizing import size_clarifier_heuristic as _impl
    return await _impl(use_current_basis, custom_basis)

# =====================
# Stage 3: Process Simulation
# =====================

@mcp.tool()
async def simulate_clarifier_system(
    use_current_state: bool = True,
    simulation_mode: str = "empirical",
    include_costing: bool = True
):
    """
    Run clarifier system simulation with removal efficiency modeling.

    Simulation modes:
    - "empirical": Fast empirical correlations (default, <5s)
    - "qsdsan": Detailed QSDsan simulation with ASM/ADM fractionation (future)

    Args:
        use_current_state: Use sizing results from current state (default: True)
        simulation_mode: Simulation mode ("empirical" or "qsdsan")
        include_costing: Include economic analysis (default: True)

    Returns:
        Job ID for background execution. Use get_job_status() and get_job_results()
    """
    from tools.simulation import simulate_clarifier_system as _impl
    return await _impl(use_current_state, simulation_mode, include_costing)

# =====================
# Job Management Tools
# =====================

@mcp.tool()
async def get_job_status(job_id: str):
    """
    Check status of a background job.

    Args:
        job_id: Job identifier returned by sizing or simulation tools

    Returns:
        Job status, progress, and any available partial results
    """
    from tools.job_management import get_job_status as _impl
    return await _impl(job_id)

@mcp.tool()
async def get_job_results(job_id: str):
    """
    Retrieve results from a completed background job.

    Args:
        job_id: Job identifier

    Returns:
        Complete job results or error if job not finished
    """
    from tools.job_management import get_job_results as _impl
    return await _impl(job_id)

@mcp.tool()
async def list_jobs(status_filter: str = None, limit: int = 10):
    """
    List all background jobs with optional filtering.

    Args:
        status_filter: Filter by status ("running", "completed", "failed", "all")
        limit: Maximum number of jobs to return (default: 10)

    Returns:
        List of jobs with status and metadata
    """
    from tools.job_management import list_jobs as _impl
    return await _impl(status_filter, limit)

@mcp.tool()
async def terminate_job(job_id: str):
    """
    Cancel a running background job.

    Args:
        job_id: Job identifier

    Returns:
        Termination status
    """
    from tools.job_management import terminate_job as _impl
    return await _impl(job_id)

# =====================
# State Management Tools
# =====================

@mcp.tool()
async def get_design_state():
    """
    Get current clarifier design state.

    Returns:
        Complete design state including basis, sizing, simulation results, and economics
    """
    from tools.state_management import get_design_state as _impl
    return await _impl()

@mcp.tool()
async def reset_design(scope: str = "all"):
    """
    Reset design state to start a new project.

    Args:
        scope: Reset scope ("all", "simulation", "costing")

    Returns:
        Reset confirmation
    """
    from tools.state_management import reset_design as _impl
    return await _impl(scope)

@mcp.tool()
async def export_design_state(filepath: str = None):
    """
    Export current design state to JSON file.

    Args:
        filepath: Output file path (default: ./clarifier_design_state.json)

    Returns:
        Export status and filepath
    """
    from tools.state_management import export_design_state as _impl
    return await _impl(filepath)

@mcp.tool()
async def import_design_state(filepath: str):
    """
    Import design state from JSON file.

    Args:
        filepath: Input file path

    Returns:
        Import status and loaded state summary
    """
    from tools.state_management import import_design_state as _impl
    return await _impl(filepath)

@mcp.tool()
async def summarize_clarifier_effluent():
    """
    Generate effluent summary for downstream MCP consumption.

    Returns:
        Effluent characteristics with min/max removal envelopes
    """
    from tools.state_management import summarize_clarifier_effluent as _impl
    return await _impl()

# ==============================================================================
# Server Entry Point
# ==============================================================================

if __name__ == "__main__":
    logger.info("Starting Primary Clarifier Design MCP Server...")
    mcp.run()
