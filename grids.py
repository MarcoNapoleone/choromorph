# grids.py
import numpy as np


def build_square_grid(n_side: int = 20) -> tuple[np.ndarray, np.ndarray]:
    x, y = np.meshgrid(np.linspace(0, 1, n_side),
                       np.linspace(0, 1, n_side))
    grid = np.column_stack([x.ravel(), y.ravel()])

    edges = []
    for r in range(n_side):
        for c in range(n_side):
            idx = r * n_side + c
            if c < n_side - 1:
                edges.append([idx, idx + 1])
            if r < n_side - 1:
                edges.append([idx, idx + n_side])
    return grid, np.asarray(edges, dtype=int)

def build_circle_grid(n_nodes: int = 20) -> tuple[np.ndarray, np.ndarray]:
    angles = np.linspace(0, 2 * np.pi, n_nodes, endpoint=False)
    radii = np.linspace(0.1, 1.0, n_nodes // 2 + 1)

    grid = np.array([
        (r * np.cos(a), r * np.sin(a))
        for r in radii for a in angles
    ])
    grid = np.vstack([[0, 0], grid])

    edges = []
    n_radii = len(radii)

    for i in range(n_radii):
        start_idx = 1 + i * n_nodes
        for j in range(n_nodes):
            edges.append([start_idx + j, start_idx + (j + 1) % n_nodes])

    for j in range(n_nodes):
        for i in range(n_radii - 1):
            edges.append([1 + i * n_nodes + j, 1 + (i + 1) * n_nodes + j])

    for j in range(n_nodes):
        edges.append([0, 1 + j])

    return grid, np.array(edges, dtype=int)

