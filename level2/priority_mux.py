import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit.visualization import plot_histogram

OUT = r"C:\Users\Yokesh G\qiskit-project\outputs_priority_mux"
os.makedirs(OUT, exist_ok=True)
sim = AerSimulator()

# ═══════════════════════════════════════════════════════════════════════════════
# PRIORITY ORDER: Medical (I3) > Fire (I0) > Gas (I1) > Intrusion (I2)
#
# MUX select encoding:
#   Medical   wins  →  S1=0, S0=0
#   Fire      wins  →  S1=0, S0=1
#   Gas       wins  →  S1=1, S0=0
#   Intrusion wins  →  S1=1, S0=1
#
# Encoder boolean expressions:
#   S1 = ~I3 & ~I0
#        (neither Medical nor Fire is active → Gas or Intrusion wins)
#
#   S0 = (~I3 & I0) | (~I3 & ~I0 & ~I1)
#        Term A: Fire wins       → ~I3 & I0
#        Term B: Intrusion wins  → ~I3 & ~I0 & ~I1
#        (Medical not active, AND [Fire active OR both Fire&Gas inactive])
#
# MUX output:
#   Y = (~S1 & ~S0 & I3)   Medical
#     | (~S1 &  S0 & I0)   Fire
#     | ( S1 & ~S0 & I1)   Gas
#     | ( S1 &  S0 & I2)   Intrusion
# ═══════════════════════════════════════════════════════════════════════════════

# ── Helpers ───────────────────────────────────────────────────────────────────
def compute_term(qc, a, b, c, term, anc):
    """term = a & b & c  using one clean ancilla. anc starts and ends at |0>."""
    qc.ccx(a, b, anc)
    qc.ccx(anc, c, term)
    qc.ccx(a, b, anc)

def uncompute_term(qc, a, b, c, term, anc):
    """Mirrors compute_term — resets term back to |0>."""
    qc.ccx(a, b, anc)
    qc.ccx(anc, c, term)
    qc.ccx(a, b, anc)

# ── Priority MUX (13 qubits) ──────────────────────────────────────────────────
def priority_mux(I):
    """
    Qubit layout:
      q0  → I0  Fire        (priority 1)
      q1  → I1  Gas         (priority 2)
      q2  → I2  Intrusion   (priority 3, lowest)
      q3  → I3  Medical     (priority 0, highest)
      q4  → S0  select LSB  (encoder output)
      q5  → S1  select MSB  (encoder output)
      q6  → Y   MUX output
      q7  → ancilla A       (scratch, always uncomputed)
      q8  → ancilla B       (scratch, always uncomputed)
      q9  → term0 register  (~S1 & ~S0 & I3)  Medical
      q10 → term1 register  (~S1 &  S0 & I0)  Fire
      q11 → term2 register  ( S1 & ~S0 & I1)  Gas
      q12 → term3 register  ( S1 &  S0 & I2)  Intrusion

    Encoder:
      S1 = ~I3 & ~I0
      S0 = (~I3 & I0) | (~I3 & ~I0 & ~I1)
    """
    qc = QuantumCircuit(13, 1, name="Priority MUX  M>F>G>I")

    # ── Load inputs ───────────────────────────────────────────────────────────
    for i in range(4):
        if I[i]: qc.x(i)
    qc.barrier(label="inputs")

    # ── Encoder: S1 = ~I3 & ~I0 ──────────────────────────────────────────────
    qc.x(3); qc.x(0)
    qc.ccx(3, 0, 5)           # S1 = ~I3 & ~I0
    qc.x(3); qc.x(0)

    qc.barrier(label="S1 ready")

    # ── Encoder: S0 = (~I3 & I0) | (~I3 & ~I0 & ~I1) ────────────────────────
    # Term A: ~I3 & I0
    qc.x(3)
    qc.ccx(3, 0, 4)           # S0 |= ~I3 & I0
    qc.x(3)

    # Term B: ~I3 & ~I0 & ~I1
    qc.x(3); qc.x(0); qc.x(1)
    qc.ccx(3, 0, 7)           # q7 = ~I3 & ~I0
    qc.ccx(7, 1, 4)           # S0 |= q7 & ~I1
    qc.ccx(3, 0, 7)           # uncompute q7
    qc.x(3); qc.x(0); qc.x(1)

    qc.barrier(label="S0 ready")

    # ── MUX: 4 terms into dedicated registers, OR into Y via CNOT ─────────────
    # Using dedicated term registers avoids XOR cancellation on Y directly.

    # Medical: ~S1 & ~S0 & I3
    qc.x(4); qc.x(5)
    compute_term(qc, 5, 4, 3, 9, 7)
    qc.cx(9, 6)
    uncompute_term(qc, 5, 4, 3, 9, 7)
    qc.x(4); qc.x(5)
    qc.barrier(label="Medical done")

    # Fire: ~S1 & S0 & I0
    qc.x(5)
    compute_term(qc, 5, 4, 0, 10, 7)
    qc.cx(10, 6)
    uncompute_term(qc, 5, 4, 0, 10, 7)
    qc.x(5)
    qc.barrier(label="Fire done")

    # Gas: S1 & ~S0 & I1
    qc.x(4)
    compute_term(qc, 5, 4, 1, 11, 7)
    qc.cx(11, 6)
    uncompute_term(qc, 5, 4, 1, 11, 7)
    qc.x(4)
    qc.barrier(label="Gas done")

    # Intrusion: S1 & S0 & I2
    compute_term(qc, 5, 4, 2, 12, 7)
    qc.cx(12, 6)
    uncompute_term(qc, 5, 4, 2, 12, 7)

    qc.barrier(label="measure")
    qc.measure(6, 0)
    return qc

# ── Classical reference  (M > F > G > I) ─────────────────────────────────────
SENSOR_NAMES = ["Fire", "Gas", "Intrusion", "Medical"]

def expected_output(I):
    # Priority: Medical(I3) > Fire(I0) > Gas(I1) > Intrusion(I2)
    if I[3]: return 3, 1   # Medical
    if I[0]: return 0, 1   # Fire
    if I[1]: return 1, 1   # Gas
    if I[2]: return 2, 1   # Intrusion
    return 2, 0            # all zero → Intrusion channel, signal=0

def expected_select(I):
    idx, _ = expected_output(I)
    # Encoding: Medical=00, Fire=01, Gas=10, Intrusion=11
    encoding = {3: (0,0), 0: (0,1), 1: (1,0), 2: (1,1)}
    return encoding[idx]   # (S1, S0)

# ── Run ───────────────────────────────────────────────────────────────────────
def run_priority_mux(I, shots=1024):
    qc     = priority_mux(I)
    tqc    = transpile(qc, sim)
    result = sim.run(tqc, shots=shots).result()
    counts = result.get_counts()
    best   = max(counts, key=counts.get)
    return qc, counts, best

# ════════════════════════════════════════════════════════════════════════════════
# MAIN — example: Fire=1, Medical=1 → Medical wins
# ════════════════════════════════════════════════════════════════════════════════
I = [1, 0, 0, 1]   # Fire=1, Medical=1 → Medical wins

sel_idx, exp_val = expected_output(I)
exp_S1,  exp_S0  = expected_select(I)
qc, counts, best = run_priority_mux(I)
got = int(best, 2)

print("=" * 48)
print(f"  Priority  = Medical > Fire > Gas > Intrusion")
print(f"  Inputs    = {dict(zip(SENSOR_NAMES, [I[0],I[1],I[2],I[3]]))}")
print(f"  Winner    = {SENSOR_NAMES[sel_idx]}")
print(f"  S1={exp_S1}, S0={exp_S0}  ->  channel {sel_idx}")
print(f"  Expected Y= {exp_val}")
print(f"  Got Y     = {got}")
print(f"  Correct   = {got == exp_val}")
print("=" * 48)

# ── Circuit diagram ───────────────────────────────────────────────────────────
fig = qc.draw("mpl", fold=50, style="iqp")

wire_labels = [
    "q0  - I0 Fire        (priority 1)",
    "q1  - I1 Gas         (priority 2)",
    "q2  - I2 Intrusion   (priority 3)",
    "q3  - I3 Medical     (priority 0 highest)",
    "q4  - S0 select LSB",
    "q5  - S1 select MSB",
    "q6  - Y  output",
    "q7  - ancilla A",
    "q8  - ancilla B",
    "q9  - term0 Medical  (~S1.~S0.I3)",
    "q10 - term1 Fire     (~S1.S0.I0)",
    "q11 - term2 Gas      (S1.~S0.I1)",
    "q12 - term3 Intrusion(S1.S0.I2)",
]
colors = [
    "#e05c3a","#e0c03a","#3aa0e0","#3ae07a",
    "#a06ae0","#c06ae0","#e03a7a",
    "#999999","#bbbbbb",
    "#3ae07a","#e05c3a","#e0c03a","#3aa0e0",
]
patches = [mpatches.Patch(color=c, label=l)
           for c, l in zip(colors, wire_labels)]
fig.legend(handles=patches, loc="lower center", ncol=2,
           fontsize=7, framealpha=0.9, bbox_to_anchor=(0.5, -0.08))
fig.suptitle(
    "Priority MUX  —  M > F > G > I  (13 Qubits)\n"
    "S1 = ~I3.~I0          (Gas or Intrusion wins)\n"
    "S0 = (~I3.I0) | (~I3.~I0.~I1)   (Fire or Intrusion wins)\n"
    "Y  = (~S1.~S0.I3)|(~S1.S0.I0)|(S1.~S0.I1)|(S1.S0.I2)",
    fontsize=9, fontweight="bold", y=1.04,
)
fig.savefig(f"{OUT}\\priority_mux_circuit.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved: priority_mux_circuit.png")

# ── Histogram ─────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(5, 4))
plot_histogram(counts, ax=ax, color="#5a7fe0",
               title=f"Winner: {SENSOR_NAMES[sel_idx]}  |  Y={exp_val}")
ax.set_xlabel("Output Y (c0)")
fig.tight_layout()
fig.savefig(f"{OUT}\\priority_mux_histogram.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved: priority_mux_histogram.png")

# ── Full truth table ───────────────────────────────────────────────────────────
rows = []
print("\nRunning all 16 combinations...")
for mask in range(16):
    I_i          = [(mask >> j) & 1 for j in range(4)]
    sel_i, exp_i = expected_output(I_i)
    es1, es0     = expected_select(I_i)
    _, _, best_i = run_priority_mux(I_i)
    got_i        = int(best_i, 2)
    rows.append({
        "I0_Fire"     : I_i[0],
        "I1_Gas"      : I_i[1],
        "I2_Intrusion": I_i[2],
        "I3_Medical"  : I_i[3],
        "Exp_S1"      : es1,
        "Exp_S0"      : es0,
        "Winner"      : SENSOR_NAMES[sel_i],
        "Expected_Y"  : exp_i,
        "Got_Y"       : got_i,
        "Pass"        : got_i == exp_i,
    })

df  = pd.DataFrame(rows)
df.to_csv(f"{OUT}\\priority_mux_truth_table.csv", index=False)
acc = df["Pass"].mean() * 100
print(f"Accuracy: {acc:.1f}%")

# ── Heatmap ───────────────────────────────────────────────────────────────────
pairs = [(0,0),(0,1),(1,0),(1,1)]
pivot_data = {}
for _, row in df.iterrows():
    kr = (int(row["I0_Fire"]),      int(row["I1_Gas"]))
    kc = (int(row["I2_Intrusion"]), int(row["I3_Medical"]))
    pivot_data[(kr, kc)] = int(row["Pass"])
matrix = [[pivot_data[((r0,r1),(c0,c1))] for (c0,c1) in pairs] for (r0,r1) in pairs]

fig, ax = plt.subplots(figsize=(6, 5))
im = ax.imshow(matrix, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
ax.set_xticks(range(4)); ax.set_yticks(range(4))
ax.set_xticklabels([f"I2={c0},I3={c1}" for c0,c1 in pairs],
                   rotation=30, ha="right", fontsize=9)
ax.set_yticklabels([f"I0={r0},I1={r1}" for r0,r1 in pairs], fontsize=9)
ax.set_title(f"Priority MUX  M>F>G>I  —  Pass/Fail  (Accuracy: {acc:.1f}%)",
             fontweight="bold")
for i in range(4):
    for j in range(4):
        ax.text(j, i, "+" if matrix[i][j] else "X",
                ha="center", va="center", fontsize=16,
                color="darkgreen" if matrix[i][j] else "darkred",
                fontweight="bold")
plt.colorbar(im, ax=ax, ticks=[0, 1], label="0=Fail  1=Pass")
fig.tight_layout()
fig.savefig(f"{OUT}\\priority_mux_heatmap.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved: priority_mux_heatmap.png")

# ── Encoder truth table ───────────────────────────────────────────────────────
print("\n-- Encoder truth table  (M > F > G > I) ---------------------------------")
print(f"  {'I3_M':>5} {'I0_F':>5} {'I1_G':>5} {'I2_I':>5}  |  "
      f"{'S1':>3} {'S0':>3}  |  Winner        Result")
print("  " + "-" * 56)
for _, row in df.iterrows():
    chk = "PASS" if row["Pass"] else "FAIL"
    print(f"  {int(row['I3_Medical']):>5} {int(row['I0_Fire']):>5} "
          f"{int(row['I1_Gas']):>5} {int(row['I2_Intrusion']):>5}  |  "
          f"{int(row['Exp_S1']):>3} {int(row['Exp_S0']):>3}  |  "
          f"{row['Winner']:<14}  {chk}")
print("-" * 58)
print(f"\n  Overall Accuracy: {acc:.1f}%")
print("\nDone. All outputs in:", OUT)
