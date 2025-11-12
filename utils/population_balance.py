"""
Population Balance Model (PBM) for Particle Aggregation in Primary Clarifiers

Implements the method of classes discretization for solving the population balance
equation with aggregation kernels and DLVO-based attachment efficiency.

Key Features:
- Orthokinetic aggregation (Saffman-Turner turbulent shear)
- Perikinetic aggregation (Smoluchowski Brownian motion)
- Differential sedimentation aggregation
- DLVO attachment efficiency integration
- BDF solver for stiff ODEs (scipy.integrate.solve_ivp)

References:
    - Edzwald (2010). Water Research, 44, 2077-2106.
    - Saffman & Turner (1956). J. Fluid Mech., 1, 16-30.
    - Smoluchowski (1917). Z. Phys. Chem., 92, 129-168.
    - Kumar & Ramkrishna (1996). Chem. Eng. Sci., 51(8), 1311-1332.

Attribution:
    Aggregation kernel formulations adapted from literature.
    Inspired by DAF-Sim conceptual framework (neuron-box/DAF-Sim).
"""

import numpy as np
from typing import Dict, Tuple, Optional, Callable
from scipy.integrate import solve_ivp
from scipy.constants import Boltzmann as k_B

from utils.dlvo_attachment import calculate_alpha_matrix


# Physical constants
GRAVITY = 9.81  # m/s²
WATER_DENSITY = 998.0  # kg/m³ at 20°C
WATER_VISCOSITY_DYNAMIC = 1.002e-3  # Pa·s at 20°C


def calculate_water_viscosity(temperature_c: float) -> float:
    """
    Calculate dynamic viscosity of water as function of temperature.

    Uses Vogel-Fulcher-Tammann equation for liquid water.

    Args:
        temperature_c: Temperature [°C]

    Returns:
        Dynamic viscosity [Pa·s]

    References:
        Viswanath & Natarajan (1989). Data Book on Viscosity of Liquids.
    """
    T = temperature_c + 273.15  # K

    # Vogel equation for water (accurate to ~2% for 0-100°C)
    # μ(T) = A·10^(B/(T-C))
    A = 2.414e-5  # Pa·s
    B = 247.8     # K
    C = 140.0     # K

    mu = A * 10**(B / (T - C))

    return mu


class AggregationKernels:
    """
    Aggregation collision frequency functions (kernels) for population balance modeling.

    Implements three fundamental aggregation mechanisms:
    1. Orthokinetic (turbulent shear) - dominant for >1 μm particles
    2. Perikinetic (Brownian diffusion) - dominant for <1 μm particles
    3. Differential sedimentation - important for large size ratios
    """

    def __init__(
        self,
        temperature_c: float = 20.0,
        dynamic_viscosity: Optional[float] = None,
        particle_density: float = 1050.0
    ):
        """
        Initialize aggregation kernel calculator.

        Args:
            temperature_c: Temperature [°C]
            dynamic_viscosity: Dynamic viscosity [Pa·s] (auto-computed if None)
            particle_density: Particle density [kg/m³]
        """
        self.temperature_c = temperature_c
        self.temperature_K = temperature_c + 273.15
        self.particle_density = particle_density

        # Dynamic viscosity
        if dynamic_viscosity is None:
            self.mu = calculate_water_viscosity(temperature_c)
        else:
            self.mu = dynamic_viscosity

        # Kinematic viscosity
        self.nu = self.mu / WATER_DENSITY

        # Density difference (for sedimentation)
        self.delta_rho = abs(particle_density - WATER_DENSITY)

    def beta_orthokinetic(
        self,
        d_i: float,
        d_j: float,
        velocity_gradient: float
    ) -> float:
        """
        Orthokinetic (turbulent shear) aggregation kernel.

        Saffman-Turner kernel for turbulent shear-induced collisions:
        β_ortho = 1.3·G·(d_i + d_j)³

        Valid for particles in turbulent flow with velocity gradient G.

        Args:
            d_i: Diameter of particle i [m]
            d_j: Diameter of particle j [m]
            velocity_gradient: Velocity gradient G [1/s]

        Returns:
            Collision frequency kernel β [m³/s]

        References:
            Saffman & Turner (1956). J. Fluid Mech., 1, 16-30.
        """
        beta = 1.3 * velocity_gradient * (d_i + d_j)**3

        return beta

    def beta_perikinetic(self, d_i: float, d_j: float) -> float:
        """
        Perikinetic (Brownian diffusion) aggregation kernel.

        Smoluchowski kernel for Brownian motion-induced collisions:
        β_peri = (2k_B T)/(3μ) · (d_i + d_j)²/(d_i·d_j)

        Valid for colloidal particles (<1 μm) where Brownian motion dominates.

        Args:
            d_i: Diameter of particle i [m]
            d_j: Diameter of particle j [m]

        Returns:
            Collision frequency kernel β [m³/s]

        References:
            Smoluchowski (1917). Z. Phys. Chem., 92, 129-168.
        """
        prefactor = (2.0 * k_B * self.temperature_K) / (3.0 * self.mu)

        beta = prefactor * (d_i + d_j)**2 / (d_i * d_j)

        return beta

    def beta_differential_sedimentation(self, d_i: float, d_j: float) -> float:
        """
        Differential sedimentation aggregation kernel.

        For particles settling at different velocities:
        β_ds = (π/72)·g·Δρ/μ·(d_i + d_j)²·|d_i² - d_j²|

        Derived from β = (π/4)·(d_i+d_j)²·|v_i-v_j| with Stokes settling
        v = Δρ·g·d²/(18μ), giving prefactor π/72.

        Assumes Stokes settling (valid for Re < 1).

        Args:
            d_i: Diameter of particle i [m]
            d_j: Diameter of particle j [m]

        Returns:
            Collision frequency kernel β [m³/s]

        References:
            Friedlander (2000). Smoke, Dust, and Haze (2nd ed.).
            Codex review (2025-11-11): Corrected prefactor from π/4 to π/72.
        """
        # Correct prefactor including Stokes factor 1/18
        prefactor = (np.pi / 72.0) * GRAVITY * self.delta_rho / self.mu

        beta = prefactor * (d_i + d_j)**2 * abs(d_i**2 - d_j**2)

        return beta

    def beta_total(
        self,
        d_i: float,
        d_j: float,
        velocity_gradient: float,
        include_perikinetic: bool = True,
        include_sedimentation: bool = True
    ) -> float:
        """
        Total aggregation kernel (sum of all mechanisms).

        β_total = β_ortho + β_peri + β_ds

        Args:
            d_i: Diameter of particle i [m]
            d_j: Diameter of particle j [m]
            velocity_gradient: Velocity gradient G [1/s]
            include_perikinetic: Include Brownian diffusion (default True)
            include_sedimentation: Include differential sedimentation (default True)

        Returns:
            Total collision frequency kernel β [m³/s]
        """
        beta = self.beta_orthokinetic(d_i, d_j, velocity_gradient)

        if include_perikinetic:
            beta += self.beta_perikinetic(d_i, d_j)

        if include_sedimentation:
            beta += self.beta_differential_sedimentation(d_i, d_j)

        return beta


class PopulationBalanceModel:
    """
    Population Balance Model for particle aggregation using method of classes.

    Solves the discrete population balance equation:
    dN_k/dt = (1/2)·Σ_{i+j=k} β_ij·α_ij·N_i·N_j - N_k·Σ_j β_kj·α_kj·N_j

    where:
    - N_k = number concentration in size class k [#/m³]
    - β_ij = collision frequency kernel [m³/s]
    - α_ij = attachment efficiency (from DLVO) [-]
    """

    def __init__(
        self,
        diameter_bins: np.ndarray,
        zeta_potentials_mV: np.ndarray,
        ionic_strength_M: float,
        temperature_c: float = 20.0,
        velocity_gradient: float = 50.0,
        particle_density: float = 1050.0
    ):
        """
        Initialize population balance model.

        Args:
            diameter_bins: Particle diameter bin centers [m]
            zeta_potentials_mV: Zeta potential for each bin [mV]
            ionic_strength_M: Ionic strength [M]
            temperature_c: Temperature [°C]
            velocity_gradient: Turbulent velocity gradient G [1/s]
            particle_density: Particle density [kg/m³]
        """
        self.diameter_bins = np.array(diameter_bins)
        self.zeta_potentials_mV = np.array(zeta_potentials_mV)
        self.ionic_strength_M = ionic_strength_M
        self.temperature_c = temperature_c
        self.velocity_gradient = velocity_gradient
        self.particle_density = particle_density

        self.n_bins = len(diameter_bins)

        # Initialize aggregation kernels
        self.kernels = AggregationKernels(
            temperature_c=temperature_c,
            particle_density=particle_density
        )

        # Pre-compute DLVO attachment efficiency matrix
        self._compute_alpha_matrix()

        # Pre-compute aggregation kernel matrix
        self._compute_beta_matrix()

        # Pre-compute aggregation rate matrix (β·α)
        self.K_matrix = self.beta_matrix * self.alpha_matrix

    def _compute_alpha_matrix(self):
        """Pre-compute DLVO attachment efficiency matrix."""
        self.alpha_matrix = calculate_alpha_matrix(
            diameters=self.diameter_bins.tolist(),
            zeta_potentials_mV=self.zeta_potentials_mV.tolist(),
            ionic_strength_M=self.ionic_strength_M,
            temperature_c=self.temperature_c
        )

    def _compute_beta_matrix(self):
        """Pre-compute collision frequency kernel matrix."""
        n = self.n_bins
        self.beta_matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(n):
                self.beta_matrix[i, j] = self.kernels.beta_total(
                    self.diameter_bins[i],
                    self.diameter_bins[j],
                    self.velocity_gradient
                )

    def _find_pivot_bins(self, v_combined: float) -> Tuple[int, int, float]:
        """
        Find bins for fixed-pivot discretization (Kumar & Ramkrishna 1996).

        Given a combined volume, find the two adjacent bins and the
        weight for distributing mass between them.

        Args:
            v_combined: Combined volume [m³]

        Returns:
            (k_lower, k_upper, eta): Lower bin, upper bin, weight to upper bin
        """
        # Convert volumes to diameters
        d_combined = v_combined**(1.0/3.0)

        # Find bracketing bins
        k_lower = np.searchsorted(self.diameter_bins, d_combined, side='right') - 1
        k_lower = np.clip(k_lower, 0, self.n_bins - 2)  # Ensure valid range
        k_upper = k_lower + 1

        # Volume of bracketing bins
        v_lower = self.diameter_bins[k_lower]**3
        v_upper = self.diameter_bins[k_upper]**3

        # Weight for distributing to upper bin (linear interpolation)
        if v_upper > v_lower:
            eta = (v_combined - v_lower) / (v_upper - v_lower)
            eta = np.clip(eta, 0.0, 1.0)
        else:
            eta = 0.5

        return k_lower, k_upper, eta

    def aggregation_rate(self, N: np.ndarray) -> np.ndarray:
        """
        Calculate aggregation rate dN/dt using fixed-pivot method.

        Implements discrete population balance (Kumar & Ramkrishna 1996):
        dN_k/dt = (birth rate) - (death rate)

        Birth rate distributes aggregates to adjacent bins using
        volume-weighted interpolation for mass conservation.

        Args:
            N: Number concentration in each bin [#/m³]

        Returns:
            Rate of change dN/dt [#/(m³·s)]

        References:
            Kumar & Ramkrishna (1996). Chem. Eng. Sci., 51(8), 1311-1332.
            Codex review (2025-11-11): Implemented fixed-pivot discretization.
        """
        dN_dt = np.zeros(self.n_bins)

        # Birth contributions from all i+j collisions
        for i in range(self.n_bins):
            for j in range(i, self.n_bins):  # j >= i to avoid double counting
                # Combined volume
                v_i = self.diameter_bins[i]**3
                v_j = self.diameter_bins[j]**3
                v_combined = v_i + v_j

                # Find bins to distribute birth
                k_lower, k_upper, eta = self._find_pivot_bins(v_combined)

                # Collision rate
                if i == j:
                    rate = 0.5 * self.K_matrix[i, j] * N[i] * N[j]
                else:
                    rate = self.K_matrix[i, j] * N[i] * N[j]

                # Distribute to bracketing bins
                dN_dt[k_lower] += (1.0 - eta) * rate
                dN_dt[k_upper] += eta * rate

        # Death: particles in each class aggregating away
        for k in range(self.n_bins):
            death_rate = 0.0
            for j in range(self.n_bins):
                death_rate += self.K_matrix[k, j] * N[k] * N[j]

            dN_dt[k] -= death_rate

        return dN_dt

    def solve(
        self,
        N0: np.ndarray,
        t_span: Tuple[float, float],
        method: str = "BDF",
        rtol: float = 1e-6,
        atol: float = 1e-8
    ) -> Dict:
        """
        Solve population balance equation over time.

        Args:
            N0: Initial number concentration distribution [#/m³]
            t_span: Time span (t_start, t_end) [s]
            method: Integration method (default "BDF" for stiff ODEs)
            rtol: Relative tolerance
            atol: Absolute tolerance

        Returns:
            Dictionary with:
            - "t": Time points [s]
            - "N": Number concentration evolution [#/m³]
            - "success": Whether integration succeeded
            - "message": Status message
        """
        def rhs(t, N):
            """Right-hand side function for ODE solver."""
            return self.aggregation_rate(N)

        # Solve using scipy BDF solver (optimized for stiff ODEs)
        sol = solve_ivp(
            fun=rhs,
            t_span=t_span,
            y0=N0,
            method=method,
            rtol=rtol,
            atol=atol,
            dense_output=True
        )

        return {
            "t": sol.t,
            "N": sol.y,
            "success": sol.success,
            "message": sol.message,
            "solver": sol
        }

    def calculate_moments(self, N: np.ndarray) -> Dict[str, float]:
        """
        Calculate statistical moments of the size distribution.

        Args:
            N: Number concentration distribution [#/m³]

        Returns:
            Dictionary with moments:
            - "M0": Total number concentration [#/m³]
            - "M1": Mean diameter [m]
            - "M2": Surface area moment [m²/m³]
            - "M3": Volume moment [m³/m³]
            - "d10": Number-average diameter [m]
            - "d32": Sauter mean diameter [m]
        """
        M0 = np.sum(N)  # Total number
        M1 = np.sum(N * self.diameter_bins)
        M2 = np.sum(N * self.diameter_bins**2)
        M3 = np.sum(N * self.diameter_bins**3)

        # Mean diameters
        d10 = M1 / M0 if M0 > 0 else 0.0  # Number-average
        d32 = M3 / M2 if M2 > 0 else 0.0  # Sauter mean (volume/surface)

        return {
            "M0": M0,
            "M1": M1,
            "M2": M2,
            "M3": M3,
            "d10": d10,
            "d32": d32
        }
