"""Deterministic k-means implemented with NumPy, without sklearn."""
import numpy as np

from nutrition import MACROS


def kmeans(values, k=3, seed=42, max_iter=100):
    """Return labels, standardized centers and iterations (Lloyd's algorithm)."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 2 or not len(values) or not np.isfinite(values).all():
        raise ValueError("Expected a finite, nonempty matrix")
    unique = np.unique(values, axis=0)
    if not 1 <= k <= len(unique) or max_iter < 1:
        raise ValueError("Invalid k or iteration limit")
    rng = np.random.default_rng(seed)
    centers = unique[rng.choice(len(unique), k, replace=False)].copy()
    for iteration in range(1, max_iter + 1):
        distances = ((values[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        labels = distances.argmin(axis=1)
        updated = centers.copy()
        for cluster in range(k):
            members = values[labels == cluster]
            if len(members):
                updated[cluster] = members.mean(axis=0)
            # An empty cluster keeps its previous center, avoiding NaN.
        converged = np.allclose(updated, centers, atol=1e-6, rtol=0)
        centers = updated
        if converged:
            break
    labels = ((values[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)
    return labels, centers, iteration


def cluster_recipes(df, k=3):
    """Standardize three macro features; return points and centers in grams."""
    values = df[MACROS].to_numpy(dtype=float)
    mean, scale = values.mean(axis=0), values.std(axis=0)
    scale = np.where(scale == 0, 1, scale)
    normalized = (values - mean) / scale
    labels, centers, iterations = kmeans(normalized, k=k)
    points = df[["Recipe_name", "Diet_type", *MACROS]].copy()
    points["cluster"] = labels
    centroids = [dict(cluster=i, **dict(zip(MACROS, row.tolist())))
                 for i, row in enumerate(centers * scale + mean)]
    return {
        "k": k, "features": MACROS, "standardized": True, "seed": 42,
        "iterations": iterations,
        "inertia": float(((normalized - centers[labels]) ** 2).sum()),
        "cluster_counts": {str(i): int((labels == i).sum()) for i in range(k)},
        "centroids": centroids, "points": points.to_dict(orient="records"),
    }
