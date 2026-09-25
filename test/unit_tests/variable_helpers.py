import numpy as np

from newsegsmodelframework.newsegsvariable.variable import Variable

def one_of_every_variable() -> dict[str, Variable]:
    """Return a dictionary containing an instance of every type of variable and parameterisation"""
    odict = {}

    odict['constant_0'] = Variable(
        'constant_0',
        distribution='constant',
        parameterisation_index = 0,
        parameters = 'Any constant',
        interface_section = 'section_1',
        interface_key = 'value_1',
        interface_subindex = 0
    ) # pyright: ignore[reportAbstractUsage]

    odict['numeric_constant_0'] = Variable(
        'numeric_constant_0',
        distribution = 'numeric_constant',
        parameterisation_index = 0,
        parameters = 42,
        interface_section = 'section_1',
        interface_key = 'value_2',
        interface_subindex = 0
    ) # pyright: ignore[reportAbstractUsage]

    odict['binomial_0'] = Variable(
        'binomial_0',
        label = 'Binomial: probility / trials form',
        distribution = 'binomial',
        parameterisation_index = 0,
        parameters = (0.4, 5),
        interface_section = 'section_1',
        interface_key = 'value_3',
        interface_subindex = 0,
    ) # pyright: ignore[reportAbstractUsage]

    odict['binomial_1'] = Variable(
        'binomial_1',
        label = 'Binomial: expected / trials form',
        distribution = 'binomial',
        parameterisation_index = 1,
        parameters = (2, 5),
        interface_section = 'section_1',
        interface_key = 'value_3',
        interface_subindex = 1,
    ) # pyright: ignore[reportAbstractUsage]

    odict['normal_0'] = Variable(
        'normal_0',
        label = 'Normal: mean / sd form',
        distribution = 'normal',
        parameterisation_index = 0,
        parameters = (2, 0.5),
        interface_section = 'section_1',
        interface_key = 'value_4',
        interface_subindex = 0
    ) # pyright: ignore[reportAbstractUsage]

    odict['normal_1'] = Variable(
        'normal_1',
        label = 'Lognormal: mu / sigma form',
        distribution = 'normal',
        parameterisation_index = 1,
        transform = 'ln',
        parameters = (0, 0.25),
        interface_section = 'section_1',
        interface_key = 'value_4',
        interface_subindex = 1
    ) # pyright: ignore[reportAbstractUsage]

    odict['normal_2'] = Variable(
        'normal_2',
        label = 'Lognormal: mean / sd form',
        distribution = 'normal',
        parameterisation_index = 2,
        transform = 'ln',
        parameters = (1, 0.25),
        interface_section = 'section_1',
        interface_key = 'value_4',
        interface_subindex = 2,
    ) # pyright: ignore[reportAbstractUsage]

    odict['beta_0'] = Variable(
        'beta_0',
        label = 'Beta: a / b form',
        distribution = 'beta',
        parameterisation_index = 0,
        parameters = (1, 3),
        interface_section = 'section_1',
        interface_key = 'value_5',
        interface_subindex = 0,
    ) # pyright: ignore[reportAbstractUsage]

    odict['beta_1'] = Variable(
        'beta_1',
        label = 'Beta: mean / sd form',
        distribution = 'beta',
        parameterisation_index = 1,
        parameters = (0.25, 0.1),
        interface_section = 'section_1',
        interface_key = 'value_5',
        interface_subindex = 1,
    ) # pyright: ignore[reportAbstractUsage]

    odict['beta_2'] = Variable(
        'beta_2',
        label = 'Logbeta: alog / blog form',
        distribution = 'beta',
        parameterisation_index = 2,
        transform = 'ln',
        parameters = (1, 3),
        interface_section = 'section_1',
        interface_key = 'value_5',
        interface_subindex = 2,
    ) # pyright: ignore[reportAbstractUsage]

    odict['gamma_0'] = Variable(
        'gamma_0',
        label = 'Gamma: shape / scale form',
        distribution = 'gamma',
        parameterisation_index = 0,
        parameters = (1.5, 0.8),
        interface_section = 'section_1',
        interface_key = 'value_6',
        interface_subindex = 0
    ) # pyright: ignore[reportAbstractUsage]

    odict['gamma_1'] = Variable(
        'gamma1',
        label = 'Gamma: mean / sd form',
        distribution = 'gamma',
        parameterisation_index = 1,
        parameters = (3, 1.5),
        interface_section = 'section_1',
        interface_key = 'value_6',
        interface_subindex = 1
    ) # pyright: ignore[reportAbstractUsage]

    odict['gamma_2'] = Variable(
        'gamma_2',
        label = 'LogGamma: shapelog / scalelog form',
        distribution = 'gamma',
        transform = 'ln',
        parameterisation_index = 2,
        parameters = (0.8, 2.0),
        interface_section = 'section_1',
        interface_key = 'value_6',
        interface_subindex = 2
    ) # pyright: ignore[reportAbstractUsage]

    odict['constant_vector_0'] = Variable(
        'constant_vector_0',
        label = 'Constant vector: default form',
        distribution = 'constant_vector',
        parameterisation_index = 0,
        parameters = tuple((np.array([42, 96, 128.1]),)),
        interface_section = 'section_2',
        interface_key = 'value_1',
        interface_subindex = 0
    ) # pyright: ignore[reportAbstractUsage]

    odict['mvn_0'] = Variable(
        'mvn_0',
        label = 'MVN: mean / vcv form',
        distribution = 'mvn',
        parameterisation_index = 0,
        parameters = (np.array([3.0, 5.0]), np.asarray([[1.5, -0.2],[-0.2, 1.8]])),
        interface_section = 'section_2',
        interface_key = 'value_2',
        interface_subindex = 0
    ) # pyright: ignore[reportAbstractUsage]

    odict['mvn_1'] = Variable(
        'mvn_1',
        label = 'MVLN: mu / vcv form',
        distribution = 'mvn',
        parameterisation_index = 1,
        transform = 'ln',
        parameters = (np.array([3.0, 5.0]), np.asarray([[1.5, -0.2],[-0.2, 1.8]])),
        interface_section = 'section_2',
        interface_key = 'value_2',
        interface_subindex = 1
    ) # pyright: ignore[reportAbstractUsage]

    odict['mvn_2'] = Variable(
        'mvn_2',
        label = 'MVLN: mean / vcv form',
        distribution = 'mvn',
        parameterisation_index = 1,
        transform = ('ln', 'identity'),
        parameters = (np.array([3.0, 5.0]), np.asarray([[1.5, -0.2],[-0.2, 1.8]])),
        interface_section = 'section_2',
        interface_key = 'value_2',
        interface_subindex = 2
    ) # pyright: ignore[reportAbstractUsage]

    odict['dirichlet_0'] = Variable(
        'dirichlet_0',
        label = 'Dirichlet: alpha vector form',
        distribution = 'dirichlet',
        parameterisation_index = 0,
        parameters = tuple((np.array([5,3,2]),)),
        interface_section = 'section_2',
        interface_key = 'value_3',
        interface_subindex = 0,
    ) # pyright: ignore[reportAbstractUsage]

    odict['dirichlet_1'] = Variable(
        'dirichlet_1',
        label = 'Dirichlet: mean / vcv form',
        distribution = 'dirichlet',
        parameterisation_index = 1,
        parameters = (np.asarray([0.5, 0.5]), np.matrix([[0.25/3, -1/3], [-1/3, 0.25/3]])),
        interface_section = 'section_2',
        interface_key = 'value_3',
        interface_subindex = 1
    ) # pyright: ignore[reportAbstractUsage]

    return odict
