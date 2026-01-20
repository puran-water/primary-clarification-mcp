"""Quick diagnostic for coupling test failures."""
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "utils"))

from pbm_settling_coupling import compute_total_tss, compute_bin_settling_velocities, PRIMARY_PARAMS, BSM2_PARAMS
from fractal_settling import FractalFlocProperties, FractalSettlingVelocity

# Test bins
test_bins = np.logspace(-6, -4, 10)

# Floc properties
floc_props = FractalFlocProperties(
    fractal_dimension=2.3,
    primary_particle_diameter=1e-6,
    primary_particle_density=1050.0,
    temperature_c=20.0
)

settling_calc = FractalSettlingVelocity(floc_props, shape_factor=45.0/24.0)

# Realistic distribution
mean_diameter = 50e-6
std_log = 0.5
log_d = np.log(test_bins)
log_mean = np.log(mean_diameter)
distribution = np.exp(-0.5 * ((log_d - log_mean) / std_log)**2)
distribution = distribution / np.sum(distribution)
total_number = 1e12  # #/m³
realistic_dist = distribution * total_number

print("=== Diagnostic 1: Realistic Distribution TSS ===")
TSS = compute_total_tss(test_bins, realistic_dist, floc_props)
print(f"TSS = {TSS:.6f} kg/m³ = {TSS*1000:.1f} mg/L")
print(f"Total number: {np.sum(realistic_dist):.2e} #/m³")
print()

print("=== Diagnostic 2: Hindrance Factor Logic ===")
N_low = np.ones(len(test_bins)) * 1e9
N_high = np.ones(len(test_bins)) * 1e11

TSS_low = compute_total_tss(test_bins, N_low, floc_props)
TSS_high = compute_total_tss(test_bins, N_high, floc_props)

results_low = compute_bin_settling_velocities(
    test_bins, N_low, floc_props, settling_calc,
    X_influent=0.1, return_intermediate=True
)

results_high = compute_bin_settling_velocities(
    test_bins, N_high, floc_props, settling_calc,
    X_influent=0.1, return_intermediate=True
)

print(f"Low concentration:")
print(f"  TSS = {TSS_low:.6f} kg/m³ = {TSS_low*1000:.1f} mg/L")
print(f"  Hindrance factor = {results_low['hindrance_factor']:.6f}")
print(f"High concentration:")
print(f"  TSS = {TSS_high:.6f} kg/m³ = {TSS_high*1000:.1f} mg/L")
print(f"  Hindrance factor = {results_high['hindrance_factor']:.6f}")
print()

print("=== Diagnostic 3: Primary vs Secondary Parameters ===")
X_influent = 0.2

vs_primary = compute_bin_settling_velocities(
    test_bins, realistic_dist, floc_props, settling_calc,
    X_influent=X_influent, takacs_params=PRIMARY_PARAMS,
    return_intermediate=True
)

vs_secondary = compute_bin_settling_velocities(
    test_bins, realistic_dist, floc_props, settling_calc,
    X_influent=X_influent, takacs_params=BSM2_PARAMS,
    return_intermediate=True
)

print(f"TSS = {vs_primary['TSS_total']*1000:.1f} mg/L")
print(f"Primary clarifier (rh=0.0003):")
print(f"  Hindrance factor = {vs_primary['hindrance_factor']:.6f}")
print(f"  vs[0] = {vs_primary['vs_hindered'][0]:.8f} m/day")
print(f"Secondary clarifier (rh=0.000576):")
print(f"  Hindrance factor = {vs_secondary['hindrance_factor']:.6f}")
print(f"  vs[0] = {vs_secondary['vs_hindered'][0]:.8f} m/day")
print()

print("=== Diagnostic 4: Very Dilute Case ===")
N_dilute = np.ones(len(test_bins)) * 1e6
TSS_dilute = compute_total_tss(test_bins, N_dilute, floc_props)

results_dilute = compute_bin_settling_velocities(
    test_bins, N_dilute, floc_props, settling_calc,
    X_influent=0.2, return_intermediate=True
)

print(f"TSS = {TSS_dilute:.6f} kg/m³ = {TSS_dilute*1000:.3f} mg/L")
print(f"Hindrance factor = {results_dilute['hindrance_factor']:.6f}")
print(f"vs[0] = {results_dilute['vs_hindered'][0]:.8f} m/day")
