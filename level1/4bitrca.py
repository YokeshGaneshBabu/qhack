import os
import pandas as pd
import matplotlib.pyplot as plt
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit.visualization import plot_histogram

OUT = r"C:\Users\Yokesh G\qiskit-project\outputs_qhack"
os.makedirs(OUT, exist_ok=True)
sim = AerSimulator()
def full_adder(qc, a, b, cin, sum_q, cout):
    qc.cx(a, sum_q)
    qc.cx(b, sum_q)
    qc.cx(cin, sum_q)
    qc.ccx(a, b, cout)
    qc.ccx(a, cin, cout)
    qc.ccx(b, cin, cout)
def ripple_carry_adder(A, B):
    """
    Qubit layout (17 qubits):
      q0–q3   : A (LSB→MSB)
      q4–q7   : B (LSB→MSB)
      q8–q11  : Sum outputs
      q12     : C0 (initial carry-in = 0)
      q13–q15 : Intermediate carries
      q16     : Final Cout
    Classical bits:
      c0–c3   : Sum bits (LSB→MSB)
      c4      : Cout
    """
    qc = QuantumCircuit(17, 5)
    for i in range(4):
        if A[i]: qc.x(i)
        if B[i]: qc.x(i + 4)
    qc.barrier(label="inputs ready")
    full_adder(qc, 0, 4, 12, 8,  13)   
    full_adder(qc, 1, 5, 13, 9,  14)   
    full_adder(qc, 2, 6, 14, 10, 15)   
    full_adder(qc, 3, 7, 15, 11, 16)  
    qc.barrier(label="measure")
    qc.measure([8, 9, 10, 11, 16], [0, 1, 2, 3, 4])
    return qc

def decode(out_str):
    # Qiskit: out_str[0]=c4(Cout) … out_str[4]=c0(S0), MSB-first already
    final = int(out_str, 2)
    cout  = int(out_str[0])
    s_int = int(out_str[1:], 2)   # S3 S2 S1 S0
    return final, cout, s_int
def run_rca(A, B, shots=1024):
    qc     = ripple_carry_adder(A, B)
    tqc    = transpile(qc, sim)
    result = sim.run(tqc, shots=shots).result()
    counts = result.get_counts()
    best   = max(counts, key=counts.get)
    return qc, counts, best

A = [1, 0, 1, 1]   # 11  (LSB first)
B = [1, 1, 0, 1]   # 13

a_int = int("".join(map(str, A[::-1])), 2)
b_int = int("".join(map(str, B[::-1])), 2)

qc, counts, best = run_rca(A, B)
final, cout, s_int = decode(best)

print("=" * 40)
print(f"  A        = {A}  ({a_int})")
print(f"  B        = {B}  ({b_int})")
print(f"  Expected = {a_int + b_int}")
print(f"  Got      = {final}  (Sum={s_int}, Cout={cout})")
print(f"  Correct  = {final == a_int + b_int}")
print("=" * 40)

#  Circuit diagram ─────────────────────────────────────────
fig = qc.draw("mpl", fold=40, style="iqp")
fig.suptitle("4-bit Ripple Carry Adder — Quantum Circuit", fontsize=13, fontweight="bold")
fig.savefig(f"{OUT}\\rca_circuit.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved: rca_circuit.png")

# ── Visualization 2: Measurement histogram ───────────────────────────────────
fig, ax = plt.subplots(figsize=(6, 4))
plot_histogram(counts, ax=ax, title=f"Measurement — A={a_int}, B={b_int}, Expected={a_int+b_int}")
fig.tight_layout()
fig.savefig(f"{OUT}\\rca_histogram.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved: rca_histogram.png")

# ── Visualization 3: Full truth table sweep ──────────────────────────────────
rows = []
for a_int_i in range(16):
    for b_int_i in range(16):
        A_i = [(a_int_i >> i) & 1 for i in range(4)]
        B_i = [(b_int_i >> i) & 1 for i in range(4)]
        _, _, best_i = run_rca(A_i, B_i)
        got, _, _ = decode(best_i)
        rows.append({
            "A": a_int_i,
            "B": b_int_i,
            "Expected": a_int_i + b_int_i,
            "Got": got,
            "Pass": got == a_int_i + b_int_i
        })

df = pd.DataFrame(rows)
df.to_csv(f"{OUT}\\rca_truth_table.csv", index=False)
acc = df["Pass"].mean() * 100
print(f"Saved: rca_truth_table.csv  |  Accuracy: {acc:.1f}%")

# ── Visualization 4: Accuracy heatmap ────────────────────────────────────────
pivot = df.pivot(index="A", columns="B", values="Pass").astype(int)
fig, ax = plt.subplots(figsize=(7, 6))
im = ax.imshow(pivot, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
ax.set_xticks(range(16)); ax.set_yticks(range(16))
ax.set_xticklabels(range(16)); ax.set_yticklabels(range(16))
ax.set_xlabel("B"); ax.set_ylabel("A")
ax.set_title(f"4-bit RCA — Pass/Fail Heatmap  (Accuracy: {acc:.1f}%)", fontweight="bold")
plt.colorbar(im, ax=ax, ticks=[0, 1], label="0=Fail  1=Pass")
fig.tight_layout()
fig.savefig(f"{OUT}\\rca_heatmap.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved: rca_heatmap.png")

print("\nDone. All outputs in:", OUT)
