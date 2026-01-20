"""Check M3 accounting in birth/death terms."""

import numpy as np
from utils.population_balance import PopulationBalanceModel

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

print("M3 accounting analysis:")
print()

# Calculate M3 removal (death)
M3_death_total = 0.0
for k in range(pbm.n_bins):
    for j in range(pbm.n_bins):
        v_k = diameters[k]**3
        death_rate = pbm.K_matrix[k, j] * N[k] * N[j]
        M3_death_total += death_rate * v_k

print(f"M3 removal rate (death): {M3_death_total:.6e}")
print()

# Calculate M3 creation (birth)
# KEY: When particles i,j collide, they create volume v_i + v_j
# This volume is distributed to bins, but the TOTAL volume created is v_i + v_j

M3_birth_total = 0.0
for i in range(pbm.n_bins):
    for j in range(i, pbm.n_bins):
        v_i = diameters[i]**3
        v_j = diameters[j]**3
        v_combined = v_i + v_j

        if i == j:
            rate = 0.5 * pbm.K_matrix[i, j] * N[i] * N[j]
        else:
            rate = pbm.K_matrix[i, j] * N[i] * N[j]

        # Volume created = rate * v_combined
        M3_birth_total += rate * v_combined

print(f"M3 creation rate (birth): {M3_birth_total:.6e}")
print()

print(f"M3 balance: {M3_birth_total - M3_death_total:.6e}")
print(f"Relative error: {abs(M3_birth_total - M3_death_total) / M3_death_total * 100:.2f}%")
