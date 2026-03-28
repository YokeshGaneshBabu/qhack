"""
Level - 3: Orthogonality & Expectation Values via Density Matrices
===================================================================
NO statevectors. Proof using ρ = ½(I + r·σ) only.
"""

import os
import numpy as np
import qutip as qt
import matplotlib.pyplot as plt

OUT = r"C:\Users\Yokesh G\qutip-da2\outputs"
os.makedirs(OUT, exist_ok=True)

# ── Density matrices (written directly, no statevectors) ──────
rho1 = qt.Qobj(np.array([[0.5,  0.5], [ 0.5, 0.5]]))
rho2 = qt.Qobj(np.array([[0.5, -0.5], [-0.5, 0.5]]))

sx, sy, sz = qt.sigmax(), qt.sigmay(), qt.sigmaz()

# ── Orthogonality: Tr(ρ₁ ρ₂) = 0 ────────────────────────────
overlap = (rho1 * rho2).tr().real
print(f"Tr(ρ₁ρ₂) = {overlap:.6f}  →  orthogonal ✓" if abs(overlap) < 1e-10
      else f"Tr(ρ₁ρ₂) = {overlap:.6f}  →  NOT orthogonal ✗")

# ── Expectation values ────────────────────────────────────────
def expect_vals(rho):
    return {
        'x': (rho * sx).tr().real,
        'y': (rho * sy).tr().real,
        'z': (rho * sz).tr().real,
    }

e1 = expect_vals(rho1)
e2 = expect_vals(rho2)

print("\n  State       ⟨σx⟩    ⟨σy⟩    ⟨σz⟩")
print(f"  ρ₁         {e1['x']:+.3f}   {e1['y']:+.3f}   {e1['z']:+.3f}  ← equator, +x axis")
print(f"  ρ₂         {e2['x']:+.3f}   {e2['y']:+.3f}   {e2['z']:+.3f}  ← equator, −x axis")

# ── FIGURE ────────────────────────────────────────────────────
fig = plt.figure(figsize=(14, 5))

# Panel 1: Bloch sphere
ax1 = fig.add_subplot(131, projection='3d')
b = qt.Bloch(axes=ax1)
b.add_states([rho1, rho2])
b.vector_color = ['royalblue', 'tomato']
b.vector_width  = 4
b.sphere_alpha  = 0.08
b.frame_alpha   = 0.2
b.render()
ax1.set_title('Bloch Sphere\nBoth on equator (rz = 0)', fontweight='bold', fontsize=10)

# Panel 2: Expectation values bar chart
ax2 = fig.add_subplot(132)
ops   = [r'$\langle\sigma_x\rangle$', r'$\langle\sigma_y\rangle$', r'$\langle\sigma_z\rangle$']
v1    = [e1['x'], e1['y'], e1['z']]
v2    = [e2['x'], e2['y'], e2['z']]
x     = np.arange(3)
b1    = ax2.bar(x - 0.2, v1, 0.35, color='royalblue', alpha=0.85, label=r'$\rho_1$')
b2    = ax2.bar(x + 0.2, v2, 0.35, color='tomato',    alpha=0.85, label=r'$\rho_2$')
for bar in list(b1) + list(b2):
    h = bar.get_height()
    if abs(h) > 0.01:
        ax2.text(bar.get_x() + bar.get_width()/2, h + 0.05*np.sign(h),
                 f'{h:+.1f}', ha='center', fontsize=11, fontweight='bold')
ax2.axhline(0, color='black', lw=1)
ax2.set_xticks(x); ax2.set_xticklabels(ops, fontsize=12)
ax2.set_ylim(-1.4, 1.4)
ax2.set_ylabel('Expectation value')
ax2.set_title('Expectation Values\nSame ⟨σy⟩=⟨σz⟩=0, opposite ⟨σx⟩', fontweight='bold')
ax2.legend(fontsize=10)
ax2.grid(True, alpha=0.3)

# Panel 3: Orthogonality proof  Tr(ρ₁ρ₂) = 0
ax3 = fig.add_subplot(133)
product_matrix = (rho1 * rho2).full().real
im = ax3.imshow(product_matrix, cmap='RdBu_r', vmin=-0.3, vmax=0.3, aspect='auto')
fig.colorbar(im, ax=ax3)
for i in range(2):
    for j in range(2):
        ax3.text(j, i, f'{product_matrix[i,j]:.3f}',
                 ha='center', va='center', fontsize=13, fontweight='bold')
ax3.set_xticks([0,1]); ax3.set_yticks([0,1])
ax3.set_xticklabels(['|0⟩','|1⟩']); ax3.set_yticklabels(['⟨0|','⟨1|'])
ax3.set_title(f'ρ₁·ρ₂ matrix\nTr(ρ₁ρ₂) = {overlap:.1f}  →  Orthogonal ✓', fontweight='bold')

fig.suptitle('Proof: ρ₁ and ρ₂ are Orthogonal yet look similar on the Bloch Sphere\n'
             'Both equatorial (rz=0), 180° apart in azimuth',
             fontsize=12, fontweight='bold')
fig.tight_layout()
fig.savefig(os.path.join(OUT, 'proof_ortho_expect.png'), bbox_inches='tight', dpi=150)
plt.close(fig)
print("\nSaved: proof_ortho_expect.png")
