"""Debug PBM birth and death terms separately."""

import numpy as np
from utils.population_balance import PopulationBalanceModel

# Simple 5-bin test
diameters = np.logspace(-6, -4, 5)
zeta_potentials = np.full(5, -20.0)

pbm = PopulationBalanceModel(
    diameter_bins=diameters,
    zeta_potentials_mV=zeta_potentials,
    ionic_strength_M=0.01,
    temperature_c=20.0,
    velocity_gradient=50.0
)

N = np.array([1e12, 5e11, 1e11, 5e10, 1e10])

print("Diameter bins (um):", diameters * 1e6)
print("Initial N:", N)
print()

# Calculate birth and death separately
birth = np.zeros(pbm.n_bins)
death = np.zeros(pbm.n_bins)

# Birth contributions
for i in range(pbm.n_bins):
    for j in range(i, pbm.n_bins):
        v_combined = diameters[i]**3 + diameters[j]**3
        k_lower, k_upper, eta = pbm._find_pivot_bins(v_combined)

        if i == j:
            rate = 0.5 * pbm.K_matrix[i, j] * N[i] * N[j]
        else:
            rate = pbm.K_matrix[i, j] * N[i] * N[j]

        birth[k_lower] += (1.0 - eta) * rate
        birth[k_upper] += eta * rate

# Death
for k in range(pbm.n_bins):
    for j in range(pbm.n_bins):
        death[k] += pbm.K_matrix[k, j] * N[k] * N[j]

print("Birth rates:")
print(birth)
print()
print("Death rates:")
print(death)
print()
print("Net (birth - death):")
print(birth - death)
print()

# Check mass balance
M3_birth = np.sum(birth * diameters**3)
M3_death = np.sum(death * diameters**3)

print(f"M3 birth rate: {M3_birth:.3e}")
print(f"M3 death rate: {M3_death:.3e}")
print(f"M3 net rate: {M3_birth - M3_death:.3e}")
