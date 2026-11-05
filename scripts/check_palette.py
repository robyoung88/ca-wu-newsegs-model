"""Check the colours of the configurations (components/colours.py) for colour-blind users.

For each configuration colour: its lightness (CIELAB L*) and its contrast with the page background. Then, with normal
vision and simulated protanopia, deuteranopia and tritanopia (Machado, Oliveira & Fernandes, 2009, full severity), the
two most similar pairs of configuration colours and their CIEDE2000 difference. Differences below about 10 are hard to
tell apart in a small icon or a thin line.

Run after changing the configuration colours:

    python scripts/check_palette.py
"""

import itertools
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from newsegsmodelapp.components import colours  # noqa: E402

# Machado, Oliveira & Fernandes (2009), severity 1.0, in linear RGB
CVD = {
    'normal': np.eye(3),
    'protan': np.array([[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]]),
    'deutan': np.array([[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]]),
    'tritan': np.array([[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]]),
}


def lin(h):
    c = np.array([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)])
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lab(rgb_lin):
    rgb_lin = np.clip(rgb_lin, 0, 1)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = m @ rgb_lin / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def de2000(l1, l2):
    L1, a1, b1 = l1
    L2, a2, b2 = l2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    dh = h2p - h1p
    if C1p * C2p == 0:
        dh = 0
    elif dh > 180:
        dh -= 360
    elif dh < -180:
        dh += 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dh / 2))
    Lbp, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    hs = h1p + h2p
    if C1p * C2p == 0:
        hbp = hs
    elif abs(h1p - h2p) > 180:
        hbp = (hs + 360) / 2 if hs < 360 else (hs - 360) / 2
    else:
        hbp = hs / 2
    T = 1 - 0.17 * math.cos(math.radians(hbp - 30)) + 0.24 * math.cos(math.radians(2 * hbp)) \
        + 0.32 * math.cos(math.radians(3 * hbp + 6)) - 0.20 * math.cos(math.radians(4 * hbp - 63))
    dth = 30 * math.exp(-((hbp - 275) / 25) ** 2)
    Rc = 2 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / math.sqrt(20 + (Lbp - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cbp, 1 + 0.015 * Cbp * T
    Rt = -math.sin(math.radians(2 * dth)) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def lum(rgb_lin):
    return float(np.array([0.2126, 0.7152, 0.0722]) @ np.clip(rgb_lin, 0, 1))


def contrast(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse = True)
    return (la + 0.05) / (lb + 0.05)


def main():
    cols = colours.CONFIG_COLOURS
    bg = lin(colours.BACKGROUND)
    print(f'{"":8} {"L*":>5} {"hue":>5} {"vs bg":>6}')
    for c in cols:
        L, a, b = lab(lin(c))
        print(f'{c:8} {L:5.1f} {math.degrees(math.atan2(b, a)) % 360:5.0f} {contrast(lin(c), bg):6.2f}')
    for name, m in CVD.items():
        labs = [lab(m @ lin(c)) for c in cols]
        pairs = sorted(
            (de2000(labs[i], labs[j]), cols[i], cols[j]) for i, j in itertools.combinations(range(len(cols)), 2)
        )
        print(
            f'{name:7} min dE {pairs[0][0]:5.1f} ({pairs[0][1]}/{pairs[0][2]}); '
            f'next {pairs[1][0]:5.1f} ({pairs[1][1]}/{pairs[1][2]})'
        )

if __name__ == '__main__':
    main()
