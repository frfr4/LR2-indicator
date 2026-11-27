"""Fit the monotone physical summary on the training families."""
import numpy as np
from scipy.optimize import minimize
from baseline import d, h, ok, clean


def design(scores):
    ranked = np.sort(scores, axis=1)[:, ::-1]
    cube_sum = np.cbrt((scores ** 3).sum(axis=1))
    inputs = np.column_stack([scores, ranked, cube_sum])
    hinges = [np.maximum(0., inputs - onset) for onset in (250., 500., 750., 1000.)]
    return np.column_stack([inputs, *hinges]) / 500.


def fit_compound(scores, training):
    features = design(scores)
    use = training & ok & clean
    x = features[use]
    target = h[use] / 500.
    bands = np.digitize(d.hard_reference.to_numpy()[use], [3, 5, 10, 15, 20, 23, 24, 25, 26])
    _, band_index, band_count = np.unique(bands, return_inverse=True, return_counts=True)
    _, family_index, family_count = np.unique(d.family.to_numpy()[use], return_inverse=True, return_counts=True)
    weights = (np.maximum(20, band_count[band_index]) / 100.) ** (-.5)
    weights *= np.maximum(1, family_count[family_index]) ** (-.5)
    weights /= weights.sum()

    def loss(coefficients):
        error = x @ coefficients - target
        radius = np.hypot(error, .13)
        value = weights @ radius + .002 * np.dot(coefficients, coefficients)
        gradient = x.T @ (weights * error / radius) + .004 * coefficients
        return value, gradient

    count = features.shape[1]
    fit = minimize(loss, np.zeros(count), method='L-BFGS-B', jac=True,
                   bounds=[(0., None)] * count, options={'maxiter': 500, 'ftol': 1e-12})
    return features @ fit.x * 500., fit.x
