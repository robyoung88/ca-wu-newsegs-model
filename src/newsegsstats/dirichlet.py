import numpy as np
import numpy.typing as npt

def fit_dirichlet(mean: npt.ArrayLike, vcv: npt.ArrayLike):
    """
    Find dirichlet alphas using method of moments
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
