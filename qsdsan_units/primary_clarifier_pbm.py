"""
Primary Clarifier with Population Balance Model (PBM) and Fractal Settling

A custom QSDsan SanUnit that extends clarifier modeling with:
- Size-resolved particle tracking (N_layer × N_bins state space)
- Population Balance Model for aggregation/breakage
- Fractal settling velocities (size-dependent density)
- DLVO-based attachment efficiency
- Takács hindered settling corrections

References:
    Based on QSDsan FlatBottomCircularClarifier architecture with extensions for:
    - Kumar & Ramkrishna (1996). Chem. Eng. Sci., 51(8), 1311-1332. (PBM discretization)
    - Logan & Wilkinson (1990). J. Hydraul. Eng., 116(9), 1121-1138. (Fractal settling)
    - Takács et al. (1991). Water Research, 25(10), 1263-1271. (Hindered settling)

Attribution:
    Architecture inspired by QSD-Group/QSDsan FlatBottomCircularClarifier.
    Physics modules are custom implementations.
"""

import numpy as np
from numba import njit
from scipy.integrate import solve_ivp
from typing import Optional, Sequence
import sys
from pathlib import Path

# Add utils to path for our physics modules
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))

# Import our physics modules
from population_balance import PopulationBalanceModel, AggregationKernels
from fractal_settling import FractalFlocProperties, FractalSettlingVelocity
from dlvo_attachment import calculate_alpha_matrix


class PrimaryClarifierPBM:
    """
    Primary clarifier with size-resolved particle tracking using Population Balance Model.
    
    This unit extends traditional clarifier models (which track only bulk TSS) to include:
    - N_bins size classes for discrete particle size distribution
    - Aggregation kinetics (orthokinetic, perikinetic, differential sedimentation)
    - Size-dependent settling velocities (fractal density + Stokes/Dietrich drag)
    - DLVO attachment efficiency between particles
    - Takács hindered settling correction
    - N_layer vertical discretization for settling flux
    
    State Variables:
        For each layer j (j=0...N_layer-1) and size bin i (i=0...N_bins-1):
        - N_ij: Number concentration of particles [#/m³]
        - Plus soluble components (handled by QSDsan WasteStream)
    
    Parameters
    ----------
    ID : str
        Unit identifier
    ins : WasteStream
        Influent stream
    outs : tuple of WasteStream  
        (effluent, underflow, wastage) streams
    underflow : float
        Recycle sludge flowrate [m³/day], optional
    wastage : float
        Waste sludge flowrate [m³/day], optional
    surface_area : float
        Clarifier surface area [m²]
    height : float
        Clarifier height [m]
    N_layer : int
        Number of vertical layers for settling model
    feed_layer : int
        Layer index where influent enters (0=top)
    diameter_bins : array_like
        Particle diameter bin centers [m]
    zeta_potentials_mV : array_like
        Zeta potential for each bin [mV]
    ionic_strength_M : float
        Ionic strength [M]
    temperature_c : float
        Temperature [°C]
    velocity_gradient : float
        Turbulent velocity gradient G [1/s]
    particle_density : float
        Particle density [kg/m³]
    fractal_dimension : float
        Fractal dimension Df (typically 1.8-2.5)
    primary_particle_diameter : float
        Primary particle size d₀ [m]
    v_max : float
        Maximum Takács settling velocity [m/day]
    rh : float
        Takács hindered zone parameter [m³/kg]
    rp : float
        Takács low concentration parameter [m³/kg]
    fns : float
        Non-settleable fraction [-]
    """
    
    # QSDsan SanUnit attributes (following FlatBottomCircularClarifier pattern)
    _N_ins = 1
    _N_outs = 3  # effluent, recycle (RAS), wastage (WAS)
    _ins_size_is_fixed = False
    _outs_size_is_fixed = False
    
    def __init__(
        self,
        ID='',
        ins: Optional[Sequence] = None,
        outs: Optional[Sequence] = (),
        # Hydraulic parameters
        underflow: Optional[float] = None,  # m³/day
        wastage: Optional[float] = None,  # m³/day
        surface_area: float = 1500.0,  # m²
        height: float = 4.0,  # m
        N_layer: int = 10,
        feed_layer: int = 5,
        # PBM parameters
        diameter_bins: Optional[np.ndarray] = None,
        zeta_potentials_mV: Optional[np.ndarray] = None,
        ionic_strength_M: float = 0.01,
        temperature_c: float = 20.0,
        velocity_gradient: float = 50.0,
        particle_density: float = 1050.0,
        # Fractal settling parameters
        fractal_dimension: float = 2.3,
        primary_particle_diameter: float = 1e-6,  # m
        # Takács hindered settling parameters
        v_max: float = 474.0,  # m/day
        rh: float = 0.000576,  # m³/kg
        rp: float = 0.00286,  # m³/kg
        fns: float = 0.00228,  # -
        # QSDsan parameters
        thermo=None,
        init_with='WasteStream',
        isdynamic: bool = True,
        **kwargs
    ):
        """
        Initialize PrimaryClarifierPBM unit.
        
        Note: This is a skeleton implementation following QSDsan SanUnit patterns.
        Full integration with QSDsan framework requires proper stream handling.
        """
        # Store parameters
        self.ID = ID
        self._Qras = underflow  # Recycle flowrate
        self._Qwas = wastage  # Wastage flowrate
        self._A = surface_area
        self._h = height
        self._N_layer = N_layer
        self._feed_layer = feed_layer
        
        # Default diameter bins (1 μm to 1 mm, 20 bins log-spaced)
        if diameter_bins is None:
            diameter_bins = np.logspace(-6, -3, 20)
        self.diameter_bins = np.array(diameter_bins)
        self._N_bins = len(self.diameter_bins)
        
        # Default zeta potentials (uniform -20 mV)
        if zeta_potentials_mV is None:
            zeta_potentials_mV = np.full(self._N_bins, -20.0)
        self.zeta_potentials_mV = np.array(zeta_potentials_mV)
        
        # Physics parameters
        self.ionic_strength_M = ionic_strength_M
        self.temperature_c = temperature_c
        self.velocity_gradient = velocity_gradient
        self.particle_density = particle_density
        self.fractal_dimension = fractal_dimension
        self.primary_particle_diameter = primary_particle_diameter
        
        # Takács parameters
        self.v_max = v_max
        self.rh = rh
        self.rp = rp
        self.fns = fns
        
        # Initialize physics modules
        self._init_physics_modules()
        
        # State variables (N_layer × N_bins for particle concentrations)
        self._state = None
        self._dstate = None
        
        print(f"[OK] Initialized {self.ID} with {self._N_layer} layers and {self._N_bins} size bins")
        print(f"  Size range: {self.diameter_bins[0]*1e6:.2f} - {self.diameter_bins[-1]*1e6:.0f} um")
        print(f"  Total state variables: {self._N_layer * self._N_bins}")
    
    def _init_physics_modules(self):
        """Initialize PBM, fractal settling, and DLVO modules."""
        # Initialize PBM
        self.pbm = PopulationBalanceModel(
            diameter_bins=self.diameter_bins,
            zeta_potentials_mV=self.zeta_potentials_mV,
            ionic_strength_M=self.ionic_strength_M,
            temperature_c=self.temperature_c,
            velocity_gradient=self.velocity_gradient,
            particle_density=self.particle_density
        )
        
        # Initialize fractal settling
        self.floc_props = FractalFlocProperties(
            fractal_dimension=self.fractal_dimension,
            primary_particle_diameter=self.primary_particle_diameter,
            primary_particle_density=self.particle_density,
            temperature_c=self.temperature_c
        )
        
        self.settling_calc = FractalSettlingVelocity(
            floc_properties=self.floc_props,
            shape_factor=45.0 / 24.0  # Irregular flocs
        )
        
        print(f"  [OK] PBM initialized: {self._N_bins}x{self._N_bins} kernel matrix")
        print(f"  [OK] Fractal settling: Df={self.fractal_dimension}, d0={self.primary_particle_diameter*1e6:.1f} um")
        print(f"  [OK] DLVO efficiency: {self._N_bins}x{self._N_bins} alpha matrix")
    
    def _run(self):
        """
        Steady-state mass balance (placeholder for QSDsan integration).
        
        For dynamic simulation, use _compile_ODE() instead.
        """
        raise NotImplementedError(
            "PrimaryClarifierPBM requires dynamic simulation. "
            "Use system.simulate() with isdynamic=True."
        )
    
    def _design(self):
        """
        Design the clarifier dimensions and materials.
        
        Follows PrimaryClarifier pattern from QSDsan.
        Calculates concrete/steel volumes for costing.
        """
        # TODO: Implement design calculations
        # - Number of clarifiers needed
        # - Diameter from surface area
        # - Concrete volumes (walls, slab)
        # - Stainless steel volume
        pass
    
    def _cost(self):
        """
        Calculate capital and operating costs.
        
        Follows PrimaryClarifier pattern from QSDsan.
        """
        # TODO: Implement costing
        # - Concrete costs (wall, slab)
        # - Stainless steel costs
        # - Pump costs
        # - Power utility
        pass
    
    def _init_state(self, influent_TSS_mg_L: float = 200.0, initial_distribution: Optional[np.ndarray] = None):
        """
        Initialize size-resolved state variables for each layer.
        
        Parameters
        ----------
        influent_TSS_mg_L : float
            Influent TSS concentration [mg/L] for initial guess
        initial_distribution : array_like, optional
            Initial particle number distribution [#/m³]
            If None, uses log-normal distribution
        
        Returns
        -------
        state : ndarray
            Initial state vector of shape (N_layer * N_bins,)
        """
        if initial_distribution is None:
            # Default: log-normal distribution centered at 50 μm
            # Convert TSS to number concentration assuming spherical particles
            # This is a simplified initialization - real systems would use measurements
            mean_diameter = 50e-6  # 50 μm
            std_log = 0.5  # Log-scale standard deviation
            
            # Log-normal distribution
            log_d = np.log(self.diameter_bins)
            log_mean = np.log(mean_diameter)
            distribution = np.exp(-0.5 * ((log_d - log_mean) / std_log)**2)
            distribution = distribution / np.sum(distribution)  # Normalize
            
            # Scale to match TSS
            # TSS [kg/m³] = Σ N_i · ρ_particle · (π/6) · d_i³
            TSS_kg_m3 = influent_TSS_mg_L / 1000.0  # mg/L to kg/m³
            particle_volumes = (np.pi / 6) * self.diameter_bins**3
            total_mass_per_particle = np.sum(distribution * self.particle_density * particle_volumes)
            
            # Scale distribution to match TSS
            initial_distribution = distribution * (TSS_kg_m3 / total_mass_per_particle)
        
        # Initialize all layers with influent distribution
        # In reality, layers would have different concentrations
        state = np.tile(initial_distribution, self._N_layer)
        
        self._state = state
        print(f"  [OK] Initialized state: {len(state)} variables ({self._N_layer} layers x {self._N_bins} bins)")
        print(f"    Total particles: {np.sum(state):.2e} #/m^3")
        
        return state
    
    def _compile_ODE(self):
        """
        Compile ODE system for dynamic simulation.

        Returns
        -------
        dy_dt : callable
            Function that computes dN/dt for all state variables
            Signature: dy_dt(t, y) -> dy

        Notes
        -----
        The ODE system includes:
        1. Aggregation kinetics (birth/death terms from PBM)
        2. Settling flux between layers (size-resolved)
        3. Hydraulic advection (flow in/out of layers)
        4. Hindered settling correction (Takács)

        State vector structure:
        y = [N_00, N_01, ..., N_0(n-1), N_10, ..., N_(m-1)(n-1)]
        where N_ij is concentration in layer i, bin j

        Implementation:
        Following Codex guidance, this integrates the tested physics modules:
        - compute_bin_settling_velocities() for hindered settling
        - PBM aggregation rates for birth/death terms
        - Vertical flux with mass→number conversion: Ṅ = J_mass / (ρ_eff × V)
        """
        # Import coupling utility
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))

        from pbm_settling_coupling import (
            compute_bin_settling_velocities,
            compute_bin_mass_concentrations
        )
        from hindered_settling import PRIMARY_PARAMS

        # Precompute constants
        N_layer = self._N_layer
        N_bins = self._N_bins
        layer_height = self._h / N_layer  # m
        layer_volume = self._A * layer_height  # m³

        # Hydraulic parameters
        Q_in = 1000.0  # m³/day (placeholder - should come from influent stream)
        Q_ras = self._Qras if self._Qras is not None else 0.0  # m³/day
        Q_was = self._Qwas if self._Qwas is not None else 0.0  # m³/day

        # Influent TSS for Takács X_min calculation
        X_influent = 0.2  # kg/m³ (placeholder - should come from stream)

        # Guard against zero influent (Codex recommendation)
        if X_influent <= 0.0:
            print("[WARN] X_influent <= 0, setting to minimum 0.001 kg/m³")
            X_influent = 0.001

        # Takács parameters
        takacs_params = PRIMARY_PARAMS.copy()

        print(f"  [OK] Compiled ODE system:")
        print(f"    State variables: {N_layer * N_bins}")
        print(f"    Layer volume: {layer_volume:.2f} m³")
        print(f"    Influent flow: {Q_in:.1f} m³/day")

        def dy_dt(t, y):
            """
            Compute dN/dt for all state variables.

            Args:
                t: Time [days]
                y: State vector [#/m³], shape (N_layer * N_bins,)

            Returns:
                dy: Rate of change [#/(m³·day)], shape (N_layer * N_bins,)
            """
            # Initialize rate array
            dy = np.zeros_like(y)

            # Reshape state vector: y[layer, bin]
            N_state = y.reshape((N_layer, N_bins))
            dy_reshaped = dy.reshape((N_layer, N_bins))

            # Process each layer
            for i in range(N_layer):
                N_layer_i = N_state[i, :]  # Number concentration in this layer

                # Skip if layer is empty
                if np.all(N_layer_i <= 0):
                    continue

                # ============================================================
                # TERM 1: Aggregation kinetics (Module 3 - PBM)
                # ============================================================
                dN_dt_agg = self.pbm.aggregation_rate(N_layer_i)

                dy_reshaped[i, :] += dN_dt_agg

                # ============================================================
                # TERM 2: Settling flux (Module 4 + hindered settling)
                # ============================================================
                # Compute hindered settling velocities for this layer
                vs_hindered = compute_bin_settling_velocities(
                    diameter_bins=self.diameter_bins,
                    number_concentrations=N_layer_i,
                    floc_properties=self.floc_props,
                    settling_calculator=self.settling_calc,
                    X_influent=X_influent,
                    use_hindered_correction=True,
                    takacs_params=takacs_params
                )  # Returns [m/day]

                # Settling flux OUT of this layer (downward to layer i+1)
                if i < N_layer - 1:
                    # Number flux = N × vs [#/m³ × m/day = #/(m²·day)]
                    flux_out = N_layer_i * vs_hindered

                    # Convert flux to rate: dN/dt = -flux / layer_height
                    # [#/(m²·day)] / [m] = [#/(m³·day)]
                    dy_reshaped[i, :] -= flux_out / layer_height

                    # Add flux to layer below
                    dy_reshaped[i+1, :] += flux_out / layer_height

                # Settling flux IN from layer above (layer i-1)
                # (Already handled in previous iteration when layer i-1 settled out)

                # Bottom layer: particles accumulate (no flux out)
                # In real system, this would be sludge withdrawal

                # ============================================================
                # TERM 3: Hydraulic advection
                # ============================================================
                # Simplified hydraulic model:
                # - Top layer (i=0): receives influent
                # - Middle layers: plug flow
                # - Bottom layer: sludge withdrawal (RAS + WAS)

                if i == 0:
                    # Top layer: effluent withdrawal
                    Q_eff = Q_in - Q_ras - Q_was  # m³/day
                    residence_time = layer_volume / Q_eff  # days

                    # Washout rate: dN/dt = -N / τ
                    dy_reshaped[i, :] -= N_layer_i / residence_time

                elif i == N_layer - 1:
                    # Bottom layer: sludge withdrawal
                    Q_underflow = Q_ras + Q_was
                    if Q_underflow > 0:
                        residence_time = layer_volume / Q_underflow
                        dy_reshaped[i, :] -= N_layer_i / residence_time

                # ============================================================
                # TERM 4: Feed injection (if this is feed layer)
                # ============================================================
                if i == self._feed_layer:
                    # Add influent particles
                    # For now, assume uniform distribution over bins
                    # In real system, this would come from influent stream
                    N_influent = np.ones(N_bins) * 1e10  # #/m³ placeholder
                    feed_rate = Q_in / layer_volume  # 1/day

                    dy_reshaped[i, :] += N_influent * feed_rate

            # Flatten back to 1D
            return dy

        return dy_dt


# Factory function for easy testing without full QSDsan integration
def create_test_clarifier(
    surface_area: float = 100.0,
    height: float = 4.0,
    N_layer: int = 5,
    N_bins: int = 10
) -> PrimaryClarifierPBM:
    """
    Create a test PrimaryClarifierPBM instance with simplified parameters.
    
    Useful for development and testing without full QSDsan streams.
    """
    diameter_bins = np.logspace(-6, -4, N_bins)  # 1-100 μm
    
    clarifier = PrimaryClarifierPBM(
        ID='test_clarifier',
        surface_area=surface_area,
        height=height,
        N_layer=N_layer,
        diameter_bins=diameter_bins,
        isdynamic=True
    )
    
    # Initialize state
    clarifier._init_state(influent_TSS_mg_L=200.0)
    
    return clarifier


if __name__ == "__main__":
    print("=== Testing PrimaryClarifierPBM Skeleton ===\n")
    
    # Test creation
    clarifier = create_test_clarifier(
        surface_area=150.0,
        height=4.5,
        N_layer=10,
        N_bins=20
    )
    
    print(f"\n[OK] PrimaryClarifierPBM skeleton created successfully")
    print(f"  Ready for ODE system implementation")
