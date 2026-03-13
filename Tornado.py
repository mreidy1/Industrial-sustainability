import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# Baseline assumptions from the Excel sheet
assumptions = {
    'steel_volume': 11.1,            # Mt/year
    'slag_yield': 0.3,               # tonnes slag / tonne steel
    'ggbfs_utilization': 0.6,        # share of slag converted to GGBFS

    # CP3 cement parameters
    'cp3_ggbfs_per_tonne': 0.6, # % subsitution rate
    'cp3_price': 95, # $/tonne
    'cp3_opex': 50, # $/tonne
    'cp3_co2_saving': 0.468, #kgCO2e/tonne
    'cp3_capex': 150_000_000,  # M&A / facility acquisition


    # Clinker-free cement parameters
    'cf_ggbfs_per_tonne': 0.95, # % subsitution rate
    'cf_price': 130, # $/tonne
    'cf_opex': 80, # $/tonne
    'cf_co2_saving': 0.75, #kgCO2e/tonn
    'cf_capex': 150_000_000,  # M&A / facility acquisition

    # Shared financials
    'carbon_price': 50,
    'discount_rate': 0.1,
    'years': 25
}

n_simulations = 5000
np.random.seed(42)

steel_volume_dist = np.random.normal(loc=11.1, scale=0.5, size=n_simulations)
slag_yield_dist = np.clip(np.random.normal(0.3, 0.02, size=n_simulations), 0.25, 0.35)
carbon_price_dist = np.random.normal(50, 10, size=n_simulations)
cf_price_dist = np.random.normal(130, 10, size=n_simulations)
cf_opex_dist = np.random.normal(80, 5, size=n_simulations)
cf_capex_dist = np.random.normal(150_000_000, 5, size=n_simulations)
cp3_price_dist = np.random.normal(95, 5, size=n_simulations)
cp3_opex_dist = np.random.normal(50, 3, size=n_simulations)
cp3_capex_dist = np.random.normal(150_000_000, 5, size=n_simulations)

def clinker_free_ramp(year, max_share=0.5, ramp_start=5, ramp_end=20):
    """Return share of clinker-free cement in a given year"""
    if year < ramp_start:
        return 0
    elif year >= ramp_end:
        return max_share
    else:
        return max_share * ((year - ramp_start) / (ramp_end - ramp_start))
    
# Updated NPV function with CO2 savings
def calc_dual_npv(assumptions, use_clinker_free=True):
    slag_total = assumptions['steel_volume'] * assumptions['slag_yield'] * 1e6
    ggbfs_total = slag_total * assumptions['ggbfs_utilization']
    
    npv = -(assumptions['cf_capex']+ assumptions['cp3_capex']) if use_clinker_free else -assumptions['cp3_capex'] 
    
    for t in range(1, assumptions['years'] + 1):
        cf_share = clinker_free_ramp(t) if use_clinker_free else 0
        cf_ggbfs = cf_share * ggbfs_total
        cp3_ggbfs = ggbfs_total - cf_ggbfs
        
        # Constrained production volumes
        cf_volume = cf_ggbfs / assumptions['cf_ggbfs_per_tonne']
        cp3_volume = cp3_ggbfs / assumptions['cp3_ggbfs_per_tonne']
        
        # Cash flows
        cf_cashflow = (
            cf_volume * (assumptions['cf_price'] + assumptions['carbon_price'] * assumptions['cf_co2_saving'])
            - cf_volume * assumptions['cf_opex']
        )
        cp3_cashflow = (
            cp3_volume * (assumptions['cp3_price'] + assumptions['carbon_price'] * assumptions['cp3_co2_saving'])
            - cp3_volume * assumptions['cp3_opex']
        )
        
        total_cashflow = cf_cashflow + cp3_cashflow
        npv += total_cashflow / ((1 + assumptions['discount_rate']) ** t)
    
    return npv

npv_with_clinker_free = calc_dual_npv(assumptions, use_clinker_free=True)
npv_cp3_only = calc_dual_npv(assumptions, use_clinker_free=False)

print(f"NPV with clinker-free investment: ${npv_with_clinker_free:,.0f}")
print(f"NPV with CP3 cement only:         ${npv_cp3_only:,.0f}")

npv_results_cf = []

for i in range(n_simulations):
    sim_assumptions = assumptions.copy()
    sim_assumptions['steel_volume'] = steel_volume_dist[i]
    sim_assumptions['slag_yield'] = slag_yield_dist[i]
    sim_assumptions['carbon_price'] = carbon_price_dist[i]
    sim_assumptions['cf_price'] = cf_price_dist[i]
    sim_assumptions['cf_opex'] = cf_opex_dist[i]
    sim_assumptions['cp3_price'] = cp3_price_dist[i]
    sim_assumptions['cp3_opex'] = cp3_opex_dist[i]
    sim_assumptions['cf_capex'] = cf_capex_dist[i]
    sim_assumptions['cp3_capex'] = cp3_capex_dist[i]

    npv = calc_dual_npv(sim_assumptions, use_clinker_free=True)
    npv_results_cf.append(npv)

prob_negative = np.mean(np.array(npv_results_cf) < 0)
print(f"Probability of negative NPV: {prob_negative:.2%}")

npv_results_cp3 = []

for i in range(n_simulations):
    sim_assumptions = assumptions.copy()
    sim_assumptions['steel_volume'] = steel_volume_dist[i]
    sim_assumptions['slag_yield'] = slag_yield_dist[i]
    sim_assumptions['carbon_price'] = carbon_price_dist[i]
    sim_assumptions['cp3_price'] = cp3_price_dist[i]
    sim_assumptions['cp3_opex'] = cp3_opex_dist[i]
    sim_assumptions['cp3_capex'] = cp3_capex_dist[i]
    
    # Clinker-free values are irrelevant in this case
    npv = calc_dual_npv(sim_assumptions, use_clinker_free=False)
    npv_results_cp3.append(npv)

prob_negative_CP3 = np.mean(np.array(npv_results_cp3) < 0)
print(f"Probability of negative NPV: {prob_negative_CP3:.2%}")

p5 = np.percentile(npv_results_cf, 5)
p95 = np.percentile(npv_results_cf, 95)
print(f"90% confidence interval for NPV (Clinker-Free): ${p5:,.0f} to ${p95:,.0f}")

def generate_tornado_data(assumptions, use_clinker_free=True, variation=0.2):
    baseline_npv = calc_dual_npv(assumptions, use_clinker_free)
    impacts = {}

    for key in ['steel_volume', 'slag_yield', 'ggbfs_utilization', 
                'cp3_price', 'cp3_opex', 'cp3_co2_saving',
                'cf_price', 'cf_opex', 'cf_co2_saving',
                'carbon_price','cf_CAPEX','cp3_CAPEX']:

        low_input = assumptions.copy()
        high_input = assumptions.copy()

        # Apply variations
        low_input[key] *= (1 - variation)
        high_input[key] *= (1 + variation)

        npv_low = calc_dual_npv(low_input, use_clinker_free)
        npv_high = calc_dual_npv(high_input, use_clinker_free)

        # Percent change from baseline
        low_pct = 100 * (npv_low - baseline_npv) / baseline_npv
        high_pct = 100 * (npv_high - baseline_npv) / baseline_npv

        impacts[key] = (low_pct, high_pct)

    return impacts, baseline_npv

tornado_cf, baseline_cf = generate_tornado_data(assumptions, use_clinker_free=True)
tornado_cp3, baseline_cp3 = generate_tornado_data(assumptions, use_clinker_free=False)

df_cf = pd.DataFrame(tornado_cf, index=['Low', 'High']).T
df_cp3 = pd.DataFrame(tornado_cp3, index=['Low', 'High']).T

df_cf['Range'] = df_cf['High'] - df_cf['Low']
df_cp3['Range'] = df_cp3['High'] - df_cp3['Low']

df_cf = df_cf.sort_values('Range', ascending=True)
df_cp3 = df_cp3.sort_values('Range', ascending=True)

fig, axes = plt.subplots(2, 1, figsize=(14, 12), gridspec_kw={'height_ratios': [1, 2]})

# Top: Monte Carlo KDE
sns.kdeplot(npv_results_cf, fill=True, label='With Clinker-Free', color='skyblue', ax=axes[0])
sns.kdeplot(npv_results_cp3, fill=True, label='CP3 Only', color='orange', ax=axes[0])
axes[0].axvline(np.mean(npv_results_cf), color='blue', linestyle='--', label=f'Mean CF = ${np.mean(npv_results_cf):,.0f}')
axes[0].axvline(np.mean(npv_results_cp3), color='orange', linestyle='--', label=f'Mean CP3 = ${np.mean(npv_results_cp3):,.0f}')
axes[0].set_title('Monte Carlo: NPV Distribution Comparison')
axes[0].set_xlabel('NPV ($)')
axes[0].set_ylabel('Density')
axes[0].legend()
axes[0].grid(True)

# Bottom: Two side-by-side Tornado Charts
fig_tornado, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6), sharey=True)

# Clinker-Free
ax1.barh(df_cf.index, df_cf['Range'], left=df_cf['Low'], color='skyblue')
ax1.axvline(0, color='black', linestyle='--')
ax1.set_title('Clinker-Free: Sensitivity (% Change in NPV)')
ax1.set_xlabel('% Change in NPV')
ax1.grid(True)

# CP3 Only
ax2.barh(df_cp3.index, df_cp3['Range'], left=df_cp3['Low'], color='orange')
ax2.axvline(0, color='black', linestyle='--')
ax2.set_title('CP3 Only: Sensitivity (% Change in NPV)')
ax2.set_xlabel('% Change in NPV')
ax2.grid(True)

plt.tight_layout()
plt.show()