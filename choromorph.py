# core.py

import numpy as np
from typing import Union

def choromorph(
    grid: np.ndarray,
    pois: np.ndarray,
    edges: np.ndarray,
    *,
    alpha: float = 0.05,
    beta: float = 0.2,
    threshold: float = 1e-3,
    max_iter: int = 250,
    max_step: Union[float, None] = 0.05,
) -> tuple[np.ndarray, int]:
    """
    Esegue il morph con forze di attrazione POI + coesione fra vicini.
    """
    N = grid.shape[0]
    neighbors = [[] for _ in range(N)]
    for a, b in edges:
        neighbors[a].append(b)
        neighbors[b].append(a)

    g = grid.copy()

    for it in range(max_iter):
        move = np.zeros_like(g)
        max_min_d = 0.0

        for i, n in enumerate(g):
            diffs = pois - n
            dists = np.linalg.norm(diffs, axis=1)
            j = np.argmin(dists)
            d = dists[j]
            max_min_d = max(max_min_d, d)
            v_poi = alpha * d * (diffs[j] / d) if d > 0 else np.zeros(2)

            v_coh = np.zeros(2)
            if neighbors[i]:
                centroid = g[neighbors[i]].mean(axis=0)
                v_coh = beta * (centroid - n)

            v = v_poi + v_coh
            if max_step is not None:
                norm_v = np.linalg.norm(v)
                if norm_v > max_step:
                    v *= max_step / norm_v
            move[i] = v

        g += move
        if max_min_d < threshold:
            return g, it + 1

    return g, max_iter
