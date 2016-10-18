class AbcModel:

    """ABCModel class.

    should contain I think just a simulator of some sort
    and probably a distance function that compares the data
    and maybe a data thing, and if the data is not set then it gets it
    at point of calculation?

    """

    def __init__(self,
                 name,  # just a string
                 # nspecies, #  number of initial conditions required - shouldnt be needed
                 # x0prior,  # again should not be needed, combined with nparameters?
                 # source,  # like a file name, shouldnt be needed
                 # type,  # SDE, ODE, not needed again
                 # fit,  # again not needed
                 # dt,   # not for now
                 # atol, rtol, logp,  # again not sure these are needed.
                 simulationFn,
                 distanceFn,
                 prior,  # array of length nparameters
                 nparameters,  # including initial conditions, etc
                 parameterNames=None,
                 ):
        self.name = name
        self.simulationFn = simulationFn
        self.distanceFn   = distanceFn
        self.nparameters  = nparameters
        self.prior        = prior  # this is stupid, should be an array, so really should be called priors!
        if parameterNames is None:
            parameterNames = ['P%d' % x for x in range(self.nparameters)]
        self.parameterNames = parameterNames

    def simulate(self, params):

        simulatedData = apply(self.simulationFn, (params,))
        return simulatedData

    def distance(self, simulatedData, targetData, params, _unusedModel):
        d = apply(self.distanceFn, (simulatedData, targetData, params, self))
        return d
