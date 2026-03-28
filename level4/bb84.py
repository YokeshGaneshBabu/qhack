import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error

OUTPUT_DIR = "outputs_bb84"
os.makedirs(OUTPUT_DIR, exist_ok=True)

N_QUBITS      = 300
N_BATCHES     = 25
NOISE_PROB    = 0.03
SAFETY_MARGIN = 0.015
EVE_INITIAL_F = 0.30
EVE_STEP      = 0.04
QBER_THRESHOLD= 0.11
SAMPLE_FRAC   = 0.25
SEED          = 7

rng = np.random.default_rng(SEED)
simulator = AerSimulator()

noise_model = NoiseModel()
dep_error = depolarizing_error(NOISE_PROB, 1)
noise_model.add_all_qubit_quantum_error(dep_error, ['h', 'x', 'measure'])

def alice_encode(bit, basis):
    qc = QuantumCircuit(1, 1)
    if bit == 1: qc.x(0)
    if basis == 1: qc.h(0)
    return qc

def simulate_qubit(alice_bit, alice_basis, bob_basis, eve_intercepts=False, eve_basis=None):
    if eve_intercepts:
        if eve_basis == alice_basis:
            eve_bit = alice_bit
        else:
            eve_bit = rng.integers(0, 2)
        transmitted_bit, transmitted_basis = eve_bit, eve_basis
    else:
        transmitted_bit, transmitted_basis = alice_bit, alice_basis

    qc = alice_encode(transmitted_bit, transmitted_basis)
    if bob_basis == 1: qc.h(0)
    qc.measure(0, 0)
    job = simulator.run(qc, noise_model=noise_model, shots=1,
                        seed_simulator=int(rng.integers(1e6)))
    counts = job.result().get_counts()
    return int(list(counts.keys())[0])

def run_batch(n_qubits, eve_fraction):
    alice_bits  = rng.integers(0, 2, n_qubits)
    alice_bases = rng.integers(0, 2, n_qubits)
    bob_bases   = rng.integers(0, 2, n_qubits)
    n_intercept = int(n_qubits * eve_fraction)
    intercept_set = set(rng.choice(n_qubits, n_intercept, replace=False))
    eve_bases   = rng.integers(0, 2, n_qubits)

    bob_bits = np.array([
        simulate_qubit(alice_bits[i], alice_bases[i], bob_bases[i],
                       i in intercept_set, eve_bases[i])
        for i in range(n_qubits)
    ])

    matching = np.where(alice_bases == bob_bases)[0]
    sa, sb = alice_bits[matching], bob_bits[matching]
    n_sample = max(1, int(len(matching) * SAMPLE_FRAC))
    sidx = rng.choice(len(matching), n_sample, replace=False)
    qber = np.sum(sa[sidx] != sb[sidx]) / n_sample
    key_len = len(np.setdiff1d(np.arange(len(matching)), sidx))
    return {'qber': qber, 'sifted_len': len(matching),
            'raw_key_len': key_len, 'eve_fraction': eve_fraction}

# ── Run simulation ──
noise_floor = NOISE_PROB
eve_target  = noise_floor + SAFETY_MARGIN
eve_f       = EVE_INITIAL_F
results     = []
aborted     = False

print("Running simulation...")
for batch in range(1, N_BATCHES + 1):
    r = run_batch(N_QUBITS, eve_f)
    results.append(r)
    if r['qber'] > QBER_THRESHOLD:
        aborted = True
    if r['qber'] > eve_target:
        eve_f = max(0.0, eve_f - EVE_STEP)
    elif r['qber'] < eve_target - 0.01:
        eve_f = min(1.0, eve_f + EVE_STEP)
    print(f"  Batch {batch:02d} | QBER={r['qber']:.3f} | f={r['eve_fraction']:.2f}")

batches     = list(range(1, N_BATCHES + 1))
qbers       = [r['qber']          for r in results]
eve_fracs   = [r['eve_fraction']  for r in results]
key_lens    = [r['raw_key_len']   for r in results]
sifted_lens = [r['sifted_len']    for r in results]
expected    = [NOISE_PROB + r['eve_fraction'] / 4 for r in results]

# ── Style helpers ──
PURPLE='#9f7aea'; TEAL='#38b2ac'; AMBER='#ed8936'
RED='#fc8181'; GREEN='#68d391'; WHITE='#e2e8f0'; GRAY='#4a5568'
BG='#0f0f1a'; AX='#1a1a2e'

def style(ax, title):
    ax.set_facecolor(AX)
    ax.set_title(title, color=WHITE, fontsize=13, fontweight='bold', pad=12)
    ax.tick_params(colors=WHITE, labelsize=10)
    for sp in ax.spines.values(): sp.set_edgecolor(GRAY)
    ax.xaxis.label.set_color(WHITE)
    ax.yaxis.label.set_color(WHITE)
    ax.grid(True, color=GRAY, linestyle='--', linewidth=0.5, alpha=0.5)

def save(fig, name):
    path = os.path.join(OUTPUT_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved: {path}")
    return path

# ════════════════════════════════════════════
# PLOT 1 — QBER per batch
# ════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(9, 5))
fig.patch.set_facecolor(BG)
style(ax, 'Plot 1 — QBER per Batch')
ax.plot(batches, qbers, 'o-', color=TEAL, lw=2, ms=6, label='Observed QBER', zorder=3)
ax.axhline(QBER_THRESHOLD, color=RED,   lw=1.8, ls='--', label=f'Abort threshold (11%)')
ax.axhline(noise_floor,    color=GREEN, lw=1.8, ls='--', label=f'Noise floor (3%)')
ax.axhline(eve_target,     color=AMBER, lw=1.8, ls=':',  label=f"Eve's target (4.5%)")
ax.fill_between(batches, noise_floor, eve_target, alpha=0.15, color=AMBER, label='Stealth zone')
ax.fill_between(batches, eve_target, QBER_THRESHOLD, alpha=0.08, color=RED, label='Danger zone')
ax.set_xlabel('Batch Number', fontsize=11)
ax.set_ylabel('QBER', fontsize=11)
ax.set_ylim(0, 0.18)
ax.legend(fontsize=9, facecolor=AX, labelcolor=WHITE, framealpha=0.9,
          loc='upper right')
save(fig, 'plot1_qber.png')

# ════════════════════════════════════════════
# PLOT 2 — Eve's intercept fraction
# ════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(9, 5))
fig.patch.set_facecolor(BG)
style(ax, "Plot 2 — Eve's Adaptive Intercept Fraction (f)")
ax.step(batches, eve_fracs, where='post', color=PURPLE, lw=2.5, label='Intercept rate f')
ax.fill_between(batches, 0, eve_fracs, step='post', alpha=0.2, color=PURPLE)
ax.axhline(EVE_INITIAL_F, color=AMBER, lw=1.5, ls='--', alpha=0.7, label=f'Initial f = {EVE_INITIAL_F:.0%}')
# annotate first step down
for i in range(1, len(eve_fracs)):
    if eve_fracs[i] < eve_fracs[i-1]:
        ax.annotate('backs off ↓', xy=(batches[i], eve_fracs[i]),
                    xytext=(batches[i]+0.5, eve_fracs[i]+0.05),
                    color=RED, fontsize=8.5,
                    arrowprops=dict(arrowstyle='->', color=RED, lw=1.2))
        break
ax.set_xlabel('Batch Number', fontsize=11)
ax.set_ylabel('Fraction of qubits intercepted', fontsize=11)
ax.set_ylim(0, 0.55)
ax.legend(fontsize=9, facecolor=AX, labelcolor=WHITE, framealpha=0.9)
save(fig, 'plot2_eve_fraction.png')

# ════════════════════════════════════════════
# PLOT 3 — Expected vs Observed QBER
# ════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(9, 5))
fig.patch.set_facecolor(BG)
style(ax, 'Plot 3 — Expected vs Observed QBER  (QBER ≈ noise + f/4)')
ax.plot(batches, expected, 's--', color=AMBER, lw=1.8, ms=5, label='Expected: noise + f/4')
ax.plot(batches, qbers,    'o-',  color=TEAL,  lw=2,   ms=6, label='Observed QBER')
ax.fill_between(batches, expected, qbers, alpha=0.15, color=WHITE, label='Sampling noise gap')
ax.axhline(QBER_THRESHOLD, color=RED, lw=1.5, ls='--', alpha=0.7, label='Abort (11%)')
ax.axhline(noise_floor,    color=GREEN, lw=1.5, ls='--', alpha=0.7, label='Noise floor (3%)')
ax.set_xlabel('Batch Number', fontsize=11)
ax.set_ylabel('QBER', fontsize=11)
ax.set_ylim(0, 0.18)
ax.legend(fontsize=9, facecolor=AX, labelcolor=WHITE, framealpha=0.9)
save(fig, 'plot3_expected_vs_observed.png')

# ════════════════════════════════════════════
# PLOT 4 — Key bits generated
# ════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(9, 5))
fig.patch.set_facecolor(BG)
style(ax, 'Plot 4 — Sifted vs Usable Key Bits per Batch')
x = np.array(batches)
ax.bar(x - 0.2, sifted_lens, width=0.4, color=GRAY,  alpha=0.75, label='Sifted bits (post basis match)')
ax.bar(x + 0.2, key_lens,    width=0.4, color=GREEN, alpha=0.90, label='Usable key bits (after QBER sample)')
ax.axhline(np.mean(key_lens), color=TEAL, lw=1.5, ls='--',
           label=f'Avg key bits/batch = {np.mean(key_lens):.0f}')
ax.set_xlabel('Batch Number', fontsize=11)
ax.set_ylabel('Bits', fontsize=11)
ax.legend(fontsize=9, facecolor=AX, labelcolor=WHITE, framealpha=0.9)
total = sum(key_lens)
ax.set_title(f'Plot 4 — Key Bits per Batch  |  Total accumulated = {total} bits',
             color=WHITE, fontsize=12, fontweight='bold', pad=12)
save(fig, 'plot4_key_bits.png')

print("\nDone.")
