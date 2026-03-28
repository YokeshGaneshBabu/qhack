# qrisc_arch_diagram.py
"""Q-RISC++ Architecture Block Diagram — clean textbook style"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

def save_architecture_diagram(path: str):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    
    fig, ax = plt.subplots(figsize=(16, 10))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.axis('off')
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    
    def rect(ax, x, y, w, h, label, sub='', fs=9):
        ax.add_patch(mpatches.Rectangle((x, y), w, h,
                     linewidth=1.5, edgecolor='black', facecolor='white', zorder=2))
        ty = y + h/2 + (0.15 if sub else 0)
        ax.text(x+w/2, ty, label, ha='center', va='center',
                fontsize=fs, fontweight='bold', color='black', zorder=3)
        if sub:
            ax.text(x+w/2, y+h/2-0.22, sub, ha='center', va='center',
                    fontsize=6.5, color='black', zorder=3)
    
    def harrow(ax, x0, x1, y, label='', up=True):
        ax.annotate('', xy=(x1, y), xytext=(x0, y),
                    arrowprops=dict(arrowstyle='->', color='black', lw=1.2), zorder=4)
        if label:
            ax.text((x0+x1)/2, y + (0.12 if up else -0.18),
                    label, ha='center', fontsize=6, color='black')
    
    def varrow(ax, x, y0, y1, label='', right=True):
        ax.annotate('', xy=(x, y1), xytext=(x, y0),
                    arrowprops=dict(arrowstyle='->', color='black', lw=1.2), zorder=4)
        if label:
            ax.text(x + (0.12 if right else -0.12), (y0+y1)/2,
                    label, ha='left' if right else 'right', va='center',
                    fontsize=6, color='black')
    
    def hline(ax, x0, x1, y):
        ax.plot([x0, x1], [y, y], color='black', lw=1.2, zorder=3)
    
    def vline(ax, x, y0, y1):
        ax.plot([x, x], [y0, y1], color='black', lw=1.2, zorder=3)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Title
    # ─────────────────────────────────────────────────────────────────────────────
    ax.text(8, 9.65, 'Q-RISC++ Quantum Processor — Architecture',
            ha='center', va='center', fontsize=14, fontweight='bold', color='black')
    ax.text(8, 9.35, 'RISC-V Inspired  |  4-Stage Pipeline  |  Linear Qubit Topology  |  IBM Eagle Noise Model',
            ha='center', va='center', fontsize=8, color='black')
    
    # ─────────────────────────────────────────────────────────────────────────────
    # ROW 1 — Pipeline stages (main data path)
    # ─────────────────────────────────────────────────────────────────────────────
    # Boxes: IF | ID | EX | WB
    STAGE_Y = 6.5
    STAGE_H = 1.8
    stages = [
        (1.0,  'IF',  'Fetch'),
        (4.0,  'ID',  'Decode'),
        (7.0,  'EX',  'Execute'),
        (10.0, 'WB',  'Write-Back'),
    ]
    SW = 2.2
    for (sx, abbr, name) in stages:
        rect(ax, sx, STAGE_Y, SW, STAGE_H, abbr, name, fs=13)
    
    # Arrows between stages (instruction flow)
    for i in range(len(stages)-1):
        x0 = stages[i][0] + SW
        x1 = stages[i+1][0]
        harrow(ax, x0, x1, STAGE_Y + STAGE_H/2, '32-bit instr', up=True)
    
    # Label above pipeline
    ax.text(6.1, STAGE_Y + STAGE_H + 0.15, 'Instruction Pipeline (IF → ID → EX → WB)',
            ha='center', fontsize=8, style='italic', color='black')
    
    # ─────────────────────────────────────────────────────────────────────────────
    # ROW 2 — Supporting units below pipeline
    # ─────────────────────────────────────────────────────────────────────────────
    UNIT_Y = 4.2
    UNIT_H = 1.5
    
    # PC
    rect(ax, 1.0, UNIT_Y, 1.6, UNIT_H, 'PC', 'Program\nCounter', fs=9)
    varrow(ax, 1.8, UNIT_Y+UNIT_H, STAGE_Y, 'pc++')
    
    # ISA / Assembler
    rect(ax, 3.2, UNIT_Y, 2.2, UNIT_H, 'ISA', '32-bit Encoding\nR/I/U/M/F types', fs=9)
    varrow(ax, 4.3, UNIT_Y+UNIT_H, STAGE_Y)
    
    # Register File
    rect(ax, 6.0, UNIT_Y, 2.2, UNIT_H, 'Reg File', 'QR0–QR7\nCR0–CR7', fs=9)
    varrow(ax, 7.1, UNIT_Y+UNIT_H, STAGE_Y)
    
    # Hazard / Forwarding
    rect(ax, 8.8, UNIT_Y, 2.8, UNIT_H, 'Hazard Unit', 'RAW / CONTROL\nForwarding', fs=9)
    varrow(ax, 10.2, UNIT_Y+UNIT_H, STAGE_Y)
    # Forwarding bypass arrow (horizontal arc over pipeline)
    ax.annotate('', xy=(7.3, STAGE_Y+0.4), xytext=(10.2, STAGE_Y+0.4),
                arrowprops=dict(arrowstyle='->', color='black', lw=1.0,
                                connectionstyle='arc3,rad=-0.35'), zorder=4)
    ax.text(8.75, STAGE_Y-0.2, 'forward bypass', ha='center', fontsize=6.5, style='italic')
    
    # Noise Model
    rect(ax, 12.2, UNIT_Y, 2.5, UNIT_H, 'Noise Model', 'IBM Eagle r3\nT1/T2/Readout', fs=9)
    harrow(ax, 14.7, 15.5, UNIT_Y + UNIT_H/2)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # ROW 3 — Compiler + Topology + Backend + Output
    # ─────────────────────────────────────────────────────────────────────────────
    BOT_Y = 1.8
    BOT_H = 1.5
    
    # Topology
    rect(ax, 1.0, BOT_Y, 2.2, BOT_H, 'Topology', 'Q0—Q1—Q2—Q3\nLinear Chain', fs=9)
    # Draw mini chain inside
    for i in range(4):
        cx = 1.2 + i*0.42
        ax.add_patch(mpatches.Rectangle((cx-0.13, BOT_Y+0.18), 0.26, 0.38,
                     lw=1.0, edgecolor='black', facecolor='white', zorder=5))
        ax.text(cx, BOT_Y+0.37, f'Q{i}', ha='center', va='center',
                fontsize=5.5, fontweight='bold', zorder=6)
        if i < 3:
            hline(ax, cx+0.13, cx+0.29, BOT_Y+0.37)
    
    varrow(ax, 2.1, BOT_Y+BOT_H, UNIT_Y, 'topology\ncheck')
    
    # Compiler / Router
    rect(ax, 3.8, BOT_Y, 2.5, BOT_H, 'Compiler', 'SWAP Router\n10→16 instrs', fs=9)
    harrow(ax, 3.8, 3.2+2.2, BOT_Y+BOT_H/2)   # Compiler → ISA
    varrow(ax, 5.05, BOT_Y+BOT_H, UNIT_Y+UNIT_H/2)
    
    # Qiskit Backend
    rect(ax, 7.0, BOT_Y, 2.8, BOT_H, 'Backend', 'AerSimulator\nNoisy + Ideal', fs=9)
    harrow(ax, 6.3, 7.0, BOT_Y+BOT_H/2)       # Noise → Backend
    varrow(ax, 8.4, BOT_Y+BOT_H, UNIT_Y, 'simulate')
    
    # Outputs
    rect(ax, 10.4, BOT_Y, 2.5, BOT_H, 'Outputs', 'Circuit PNG\nHistogram\nResults JSON', fs=9)
    harrow(ax, 9.8, 10.4, BOT_Y+BOT_H/2)
    
    # Metrics
    rect(ax, 13.3, BOT_Y, 2.5, BOT_H, 'Metrics', 'CPI  Stalls\nForwards  Fidelity', fs=9)
    harrow(ax, 12.9, 13.3, BOT_Y+BOT_H/2)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Right side: Qiskit backend box (tall)
    # ─────────────────────────────────────────────────────────────────────────────
    rect(ax, 13.5, STAGE_Y, 2.2, STAGE_H, 'Qiskit\nBackend', 'Fidelity 93.7%', fs=9)
    harrow(ax, 10.0+SW, 13.5, STAGE_Y+STAGE_H/2, 'circuit')
    harrow(ax, 13.5+2.2, 15.9, STAGE_Y+STAGE_H/2, 'results')
    
    # Noise model connects up to backend
    vline(ax, 13.45, UNIT_Y+UNIT_H, STAGE_Y)
    harrow(ax, 13.45, 13.5, STAGE_Y+0.4)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Global data bus (top horizontal bus line)
    # ─────────────────────────────────────────────────────────────────────────────
    BUS_Y = 8.9
    hline(ax, 0.8, 15.8, BUS_Y)
    ax.text(0.5, BUS_Y+0.1, 'Data / Control Bus', fontsize=6.5,
            va='bottom', ha='left', style='italic')
    # Taps from pipeline stages to bus
    for (sx, _, _) in stages:
        vline(ax, sx + SW/2, STAGE_Y+STAGE_H, BUS_Y)
        ax.annotate('', xy=(sx+SW/2, BUS_Y), xytext=(sx+SW/2, STAGE_Y+STAGE_H),
                    arrowprops=dict(arrowstyle='->', color='black', lw=0.8), zorder=4)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Legend box (bottom right)
    # ─────────────────────────────────────────────────────────────────────────────
    rect(ax, 13.3, 0.2, 2.6, 1.4, '', '')
    ax.text(14.6, 1.4, 'Legend', ha='center', fontsize=7.5, fontweight='bold')
    ax.plot([13.4, 13.9], [1.15, 1.15], 'k-', lw=1.2)
    ax.annotate('', xy=(13.9,1.15), xytext=(13.4,1.15),
                arrowprops=dict(arrowstyle='->', color='black', lw=1.2))
    ax.text(14.0, 1.15, 'Data flow', va='center', fontsize=7)
    
    ax.plot([13.4, 13.9], [0.85, 0.85], 'k--', lw=1.0)
    ax.text(14.0, 0.85, 'Control signal', va='center', fontsize=7)
    
    ax.plot([13.4, 13.9], [0.55, 0.55], 'k-', lw=0.8)
    ax.text(14.0, 0.55, 'Bus tap', va='center', fontsize=7)
    
    plt.tight_layout(pad=0.2)
    fig.savefig(path, dpi=160, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        print(f'  [ARCH] Architecture diagram saved → {path}')
    

if __name__ == '__main__':
    save_architecture_diagram('qrisc_architecture.png')
