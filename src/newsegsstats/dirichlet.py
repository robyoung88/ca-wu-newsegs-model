"""Provides a method for fitting a dirichlet distribution to observed data."""
import numpy as np
import numpy.typing as npt

def fit_dirichlet(mean: npt.ArrayLike, vcv: npt.ArrayLike) -> npt.ArrayLike:
    """Fit Dirichlet alpha parameters using the method of moments.

    Args:
        mean: Observed mean vector for the Dirichlet distribution.
        vcv: Variance-covariance matrix corresponding to the observed data.

    Returns:
        Alpha parameters for the fitted Dirichlet distribution.
    
    Raises:
        ValueError: if the alpha parameters cannot be identified (likely due to error in the vcv).
    """
    mean = np.asarray(mean).flatten()
    vcv = np.asarray(vcv).reshape((len(mean), len(mean)))
    variances = np.diag(vcv)

    ovector = np.zeros_like(mean)
    wch = mean > 0
    ovector[wch] = mean[wch] * ((mean[wch] * (1. - mean[wch]))/ variances[wch] - 1.)
    
    if np.all(ovector == 0):
        raise ValueError('Dirichlet alpha parameters cannot be identified - check your variances')

    return ovector
