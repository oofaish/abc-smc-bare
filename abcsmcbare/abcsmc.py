from __future__ import print_function
import numpy as np
from numpy import random as rnd

import copy
import time
import sys
from abcsmcbare import kernels
from abcsmcbare import statistics
from .KernelType import KernelType
from .PriorType import PriorType


"""
priors:
              a 2D list.
              priors[model_number][parameter_number] is a NamedTuple of type prior.
              The .type attribute is a PriorType object (one of PriorType.constant, PriorType.uniform, PriorType.normal,
              PriorType.lognormal).
              The other attributes store the appropriate parameters.

fit:
              a 2D list of strings.
              This list contains the fitting instructions and therefore defines how to fit the
              experimental data to the systems variables. The first dimension represents the
              models to be investigated, the second dimension represents the amount of data.

              Example:
              1 model with 7 species, 3 data series
              fit = [ ['species1+species2' , 'species5' , '3*species4-species7'], ]
              2 models with each 7 species, 2 data series
              fit = [ ['species1' , 'species2*species3'] , ['species1' , 'species2*species4'] ]

              The default value is 'None', i.e. the order of data series corresponds exactly
              to the order of species.
"""


# distances are stored as [nparticle][nbeta][d1, d2, d3 .... ]
# trajectories are stored as [nparticle][nbeta][ species ][ times ]

class AbcsmcResults:

    """ABCSmcResults class.

    Does what it says on the tin

    """

    def __init__(self,
                 naccepted,
                 sampled,
                 rate,
                 trajectories,
                 distances,
                 margins,
                 models,
                 weights,
                 parameters,
                 epsilon):
        self.naccepted = naccepted
        self.sampled = sampled
        self.rate = rate
        self.trajectories = trajectories  # cant convert to array as they could be different sizes for different models
        self.distances = np.array(distances)
        self.margins = np.array(margins)
        self.models = np.array(models)
        self.weights = np.array(weights)
        self.parameters = np.array(parameters)
        self.epsilon = epsilon


class Abcsmc:

    """ABCSmc class.

    Does what it says on the tin

    """

    def __init__(self,
                 models,  # array of model objects
                 nparticles,  # number of particles e.g. 100
                 modelprior,  # model priors
                 data,
                 # beta,
                 nbatch,
                 model_kernel,
                 debug,
                 timing,
                 io,
                 kernel_type=KernelType.component_wise_uniform,
                 kernelfn=kernels.get_kernel,
                 kernelpdffn=kernels.get_parameter_kernel_pdf,
                 perturbfn=kernels.perturb_particle):
        self.io = io

        self.nmodel = len(models)
        self.models = copy.copy(models)

        self.nparticles = nparticles

        self.model_prev = [0] * nparticles
        self.weights_prev = [0] * nparticles
        self.parameters_prev = [[] for _ in range(self.nparticles)]
        self.margins_prev = [0] * self.nmodel

        self.model_curr = [0] * nparticles
        self.weights_curr = [0] * nparticles
        self.parameters_curr = [[] for _ in range(self.nparticles)]
        self.margins_curr = [0] * self.nmodel

        self.b = [0] * nparticles
        self.distances = []
        self.trajectories = []

        # self.distancefn = distancefn
        self.kernel_type = kernel_type
        self.kernelfn = kernelfn
        self.kernelpdffn = kernelpdffn
        self.perturbfn = perturbfn

        # self.beta = 1
        self.dead_models = []
        self.nbatch = nbatch
        self.debug = debug
        self.timing = timing

        self.data = data

        self.modelprior = modelprior[:]
        self.modelKernel = model_kernel
        self.kernel_aux = [0] * nparticles

        self.kernels = list()
        # self.kernels is a list of length the number of models
        # self.kernels[i] is a list of length 2 such that :
        # self.kernels[i][0] contains the index of the non constant parameters for the model i
        # self.kernels[i][1] contains the information required to build the kernel and given by the input_file
        # self.kernels[i][2] is filled in during the kernelfn step and contains values/matrix etc depending on kernel
        kernel_option = list()
        for i in range(self.nmodel):
            if self.kernel_type == KernelType.multivariate_normal_nn:
                # Option for K nearest neigbours - user should be able to specify
                kernel_option.append(int(nparticles / 4))
            else:
                kernel_option.append(0)

        # get the list of parameters with non constant prior
        for i in range(self.nmodel):
            ind = list()
            for j in range(self.models[i].nparameters):
                if not (self.models[i].prior[j].type == PriorType.constant):
                    ind.append(j)
            # kernel info will get set after first population
            self.kernels.append([ind, kernel_option[i], 0])

            # get
        self.special_cases = [0] * self.nmodel
        if self.kernel_type == KernelType.component_wise_uniform:

            for m in range(self.nmodel):
                all_uniform = True
                for j in range(self.models[m].nparameters):
                    if self.models[m].prior[j].type not in [PriorType.constant, PriorType.uniform]:
                        all_uniform = False
                if all_uniform:
                    self.special_cases[m] = 1
                    print("### Found special kernel case 1 for model ", m, "###")

        self.hits = []
        self.sampled = []
        self.rate = []
        self.dead_models = []
        self.sample_from_prior = True

    def run_schedule(self, epsilonSchedule, adaptiveEpsilon=False, adaptiveEpsilonQuantile=None):
        all_start_time = time.time()
        allResults = []
        results = None
        for pop, thisEpsilon in enumerate(epsilonSchedule):
            if pop > 0 and adaptiveEpsilon:
                adaptiveEpsilon, quantile = self.nextAdaptiveEpsilon(results.distances, epsilonSchedule[-1], adaptiveEpsilonQuantile)
                if self.debug >= 1:
                    print('### Adapting epsilon to %f (Quantile=%f) instead of %f' % (adaptiveEpsilon, quantile, thisEpsilon))
                    epsilonToUse = adaptiveEpsilon
            else:
                epsilonToUse = thisEpsilon

            start_time = time.time()
            if pop == 0 and self.sample_from_prior:
                results = self.iterate_one_population(epsilonToUse, prior=True)
            else:
                results = self.iterate_one_population(epsilonToUse, prior=False)
            end_time = time.time()

            allResults.append(results)

            self.io.write_pickled(self.nmodel, self.model_prev, self.weights_prev, self.parameters_prev, self.margins_prev, self.kernels, allResults)

            if self.debug >= 1:
                print("### iter:%d, eps=%0.2f, sampled=%d, accepted=%.2f" % (pop + 1, epsilonToUse, self.sampled[pop], self.rate[pop]))
                #   print "\t sampling steps / acceptance rate (%d/%):", self.sampled[pop], "/", self.rate[pop]
                print("model marginals:", self.margins_prev)

                if len(self.dead_models) > 0:
                    print("\t dead models                      :", self.dead_models)
                if self.timing:
                    print("\t timing:                          :", end_time - start_time)

                sys.stdout.flush()

        if self.timing:
            print("#### final time:", time.time() - all_start_time)

        return allResults

    def nextAdaptiveEpsilon(self, lastArrayOfDistances, lastEpsilon, adaptiveEpsilonQuantile=None):
        """Drovandi & Pettitt 2011.

        use qth quantile of the distance for t iterations
        unless we hit the tmin requested
        """
        if adaptiveEpsilonQuantile is None:
            adaptiveEpsilonQuantile = 75

        new_tol = np.percentile(lastArrayOfDistances, adaptiveEpsilonQuantile)

        if new_tol < lastEpsilon:
            new_tol = lastEpsilon
        return new_tol, adaptiveEpsilonQuantile

    def iterate_one_population(self, next_epsilon, prior):
        if self.debug == 2:
            print("\n\n****iterate_one_population: next_epsilon, prior", next_epsilon, prior)

        naccepted = 0
        sampled = 0

        while naccepted < self.nparticles:
            if self.debug == 2:
                print("\t****batch")
            if not prior:
                sampled_models_indexes = self.sample_model()
                sampled_params = self.sample_parameters(sampled_models_indexes)
            else:
                sampled_models_indexes = self.sample_model_from_prior()
                sampled_params = self.sample_parameters_from_prior(sampled_models_indexes)

            accepted_index, distances, traj = self.simulate_and_compare_to_data(sampled_models_indexes, sampled_params,
                                                                                next_epsilon)
            for i in range(self.nbatch):
                if naccepted < self.nparticles:
                    sampled += 1

                if naccepted < self.nparticles and accepted_index[i] > 0:

                    self.model_curr[naccepted] = sampled_models_indexes[i]
                    if self.debug == 2:
                        print("\t****accepted", i, accepted_index[i], sampled_models_indexes[i])

                    for p in range(self.models[sampled_models_indexes[i]].nparameters):
                        self.parameters_curr[naccepted].append(sampled_params[i][p])

                    self.b[naccepted] = accepted_index[i]
                    self.trajectories.append(traj[i])
                    self.distances.append(distances[i])

                    naccepted += 1
            if self.debug == 2:
                print("#### current naccepted:", naccepted)

            if self.debug > 1:
                print("\t****end  batch naccepted/sampled:", naccepted, sampled)

        # Finished loop over particles
        if self.debug == 2:
            print("**** end of population naccepted/sampled:", naccepted, sampled)

        if not prior:
            self.compute_particle_weights()
        else:
            for i in range(self.nparticles):
                self.weights_curr[i] = self.b[i]

        self.normalize_weights()
        self.update_model_marginals()

        if self.debug == 2:
            print("**** end of population: particles")
            for i in range(self.nparticles):
                print(i, self.weights_curr[i], self.model_curr[i], self.parameters_curr[i])
            print(self.margins_curr)

        # Prepare for next population
        self.margins_prev = self.margins_curr[:]
        self.weights_prev = self.weights_curr[:]
        self.model_prev = self.model_curr[:]
        self.parameters_prev = []
        for i in range(self.nparticles):
            self.parameters_prev.append(self.parameters_curr[i][:])

        self.model_curr = [0] * self.nparticles
        self.weights_curr = [0] * self.nparticles
        self.parameters_curr = [[] for _ in range(self.nparticles)]
        self.margins_curr = [0] * self.nmodel

        self.b = [0] * self.nparticles

        # Check for dead models
        self.dead_models = []
        for j in range(self.nmodel):
            if self.margins_prev[j] < 1e-6:
                self.dead_models.append(j)

        # Compute kernels
        for model_index in range(self.nmodel):
            this_model_particles = np.arange(self.nparticles)[np.array(self.model_prev) == model_index]

            this_population = np.zeros([len(this_model_particles), self.models[model_index].nparameters])
            this_weights = np.zeros(len(this_model_particles))
            # if we have just sampled from the prior we shall initialise the kernels using all available particles
            if prior:
                # quick sanity check - on step 1 we should really have all the models
                if len(set(self.model_prev)) is not self.nmodel:
                    raise RuntimeError('Something is very wrong - in my first population I failed to sample all models - are you sure your distance function is working?')

                for it in range(len(this_model_particles)):
                    if len(this_population[it, :]) != len(self.parameters_prev[this_model_particles[it]][:]):
                        print('>>>', this_population[it, :])
                        print('>>>', self.parameters_prev[this_model_particles[it]][:])

                    this_population[it, :] = self.parameters_prev[this_model_particles[it]][:]
                    this_weights[it] = self.weights_prev[this_model_particles[it]]

                tmp_kernel = self.kernelfn(self.kernel_type, self.kernels[model_index], this_population, this_weights)
                self.kernels[model_index] = tmp_kernel[:]

            else:
                # only update the kernels if there are > 5 particles
                if len(this_model_particles) > 5:
                    for it in range(len(this_model_particles)):
                        this_population[it, :] = self.parameters_prev[this_model_particles[it]][:]
                        this_weights[it] = self.weights_prev[this_model_particles[it]]
                    tmp_kernel = self.kernelfn(self.kernel_type, self.kernels[model_index], this_population, this_weights)
                    self.kernels[model_index] = tmp_kernel[:]

        # Kernel auxilliary information
        self.kernel_aux = kernels.get_auxilliary_info(self.kernel_type, self.model_prev, self.parameters_prev,
                                                      self.models, self.kernels)[:]

        self.hits.append(naccepted)
        self.sampled.append(sampled)
        self.rate.append(naccepted / float(sampled))

        results = AbcsmcResults(naccepted,
                                sampled,
                                naccepted / float(sampled),
                                self.trajectories,
                                self.distances,
                                self.margins_prev,
                                self.model_prev,
                                self.weights_prev,
                                self.parameters_prev,
                                next_epsilon)

        self.trajectories = []
        self.distances = []

        return results

    def fill_values(self, particle_data):
        """Save particle data from pickled array into the corresponding attributes of this abc_smc object.

        Parameters
        ----------
        particle_data : particle data, in form:
         [model_pickled, weights_pickled, parameters_pickled, margins_pickled, kernel]

        """
        self.model_prev = particle_data[0][:]

        self.weights_prev = particle_data[1][:]

        self.parameters_prev = []
        for it in range(len(particle_data[2])):
            self.parameters_prev.append(particle_data[2][it][:])

        self.margins_prev = particle_data[3][:]

        self.kernels = []
        for i in range(self.nmodel):
            self.kernels.append([])
            for j in range(len(particle_data[4][i])):
                self.kernels[i].append(particle_data[4][i][j])

        self.sample_from_prior = False

        # you gotta fill the dead models too
        self.dead_models = []
        nonDeadModelNumbers = list(set(self.model_prev))
        assert len(self.dead_models) == 0, ValueError('Oh no, I had some existing dead models! %s' % self.dead_models)
        for j in range(self.nmodel):
            isDead = False
            if self.margins_prev[j] < 1e-6:
                self.dead_models.append(j)
                isDead = True
            assert (isDead or j in nonDeadModelNumbers), RuntimeError('Model %d is neither dead nor alive' % j)

    def simulate_and_compare_to_data(self, sampled_models_indexes, sampled_params, epsilon, do_comp=True):
        """
        Perform simulations:

        Parameters
        ----------
        sampled_models : list of sampled model numbers
        sampled_params : a list, each element of which is a list of sampled parameters
        epsilon : value of epsilon
        do_comp : if False, do not actually calculate distance between simulation results and experimental data, and
            instead assume this is 0.

        Returns
        -------
        accepted
        distances
        traj
        """

        if self.debug == 2:
            print('\t\t\t***simulate_and_compare_to_data')

        accepted = [0] * self.nbatch
        traj = [[] for _ in range(self.nbatch)]
        distances = [0 for _ in range(self.nbatch)]

        model_indexes = np.array(sampled_models_indexes)

        for model_index in range(self.nmodel):

            # create a list of indexes for the simulations corresponding to this model
            mapping = np.arange(self.nbatch)[model_indexes == model_index]
            if self.debug == 2:
                print("\t\t\tmodel / mapping:", model_index, mapping)

            num_simulations = len(mapping)
            if num_simulations == 0:
                # I really dont think you should be breaking here like you used to
                # continue so you try the next model!
                continue

            this_model_parameters = []
            for i in range(num_simulations):
                this_model_parameters.append(sampled_params[mapping[i]])
            try:
                sims = self.models[model_index].simulate(this_model_parameters)
                doh_fail = False
                if self.debug == 2:
                    print('\t\t\tsimulation dimensions:', sims.shape)

            except:
                print('SIMULATION FAILEDD!')
                sims = None
                doh_fail = True

            for i in range(num_simulations):
                # store the trajectories and distances in a list of length beta
                simulation_number = mapping[i]

                if doh_fail:
                    dist = False
                    distance = np.inf
                else:
                    sample_points = sims[i]#ABC not sure I need to explicity define the second dimension of this guy
                    if do_comp:
                        model = self.models[model_index]

                        distance = model.distance(sample_points, self.data, this_model_parameters[i], None)
                        dist = check_below_threshold(distance, epsilon)
                    else:
                        distance = 0
                        dist = True

                if dist:
                    accepted[simulation_number] += 1

                if self.debug == 2:
                    print('\t\t\tdistance/this_epsilon/mapping/b:', distance, epsilon, \
                        simulation_number, accepted[simulation_number])

                traj[simulation_number] = sample_points
                distances[simulation_number] = distance

        return accepted, distances, traj

    def sample_model_from_prior(self):
        """
        Returns a list of model numbers, of length self.nbatch, drawn from a categorical distribution with probabilities
         self.modelprior

        """
        models = [0] * self.nbatch
        if self.nmodel > 1:
            for i in range(self.nbatch):
                models[i] = statistics.w_choice(self.modelprior)

        return models

    def sample_model(self):
        """
        Returns a list of model numbers, of length self.nbatch, obtained by sampling from a categorical distribution
        with probabilities self.modelprior, and then perturbing with a uniform model perturbation kernel.
        """

        models = [0] * self.nbatch

        if self.nmodel > 1:
            # Sample models from prior distribution
            for i in range(self.nbatch):
                models[i] = statistics.w_choice(self.margins_prev)

            # perturb models
            if len(self.dead_models) < self.nmodel - 1:

                for i in range(self.nbatch):
                    u = rnd.uniform(low=0, high=1)

                    if u > self.modelKernel:
                        # sample randomly from other (non dead) models
                        not_available = set(self.dead_models[:])
                        not_available.add(models[i])

                        available_indexes = np.array(list(set(range(self.nmodel)) - not_available))
                        rnd.shuffle(available_indexes)
                        perturbed_model = available_indexes[0]

                        models[i] = perturbed_model

        return models[:]

    def sample_parameters_from_prior(self, sampled_models_indexes):
        """
        For each model whose index is in sampled_models, draw a sample of the corresponding parameters.

        Parameters
        ----------
        sampled_models : a list of model indexes, of length self.nbatch

        Returns
        -------
        a list of length self.nbatch, each entry of which is a list of parameter samples (whose length is
                model.nparameters for the corresponding model)

        """
        samples = []

        for i in range(self.nbatch):
            model = self.models[sampled_models_indexes[i]]
            sample = [0] * model.nparameters

            for param in range(model.nparameters):
                if model.prior[param].type == PriorType.constant:
                    sample[param] = model.prior[param].value

                if model.prior[param].type == PriorType.normal:
                    sample[param] = rnd.normal(loc=model.prior[param].mean, scale=np.sqrt(model.prior[param].variance))

                if model.prior[param].type == PriorType.uniform:
                    sample[param] = rnd.uniform(low=model.prior[param].lower_bound, high=model.prior[param].upper_bound)

                if model.prior[param].type == PriorType.lognormal:
                    sample[param] = rnd.lognormal(mean=model.prior[param].mu, sigma=np.sqrt(model.prior[param].sigma))

            samples.append(sample[:])

        return samples

    def sample_parameters(self, sampled_models_indexes):
        """
        For each model index in sampled_models_indexes, sample a set of parameters by sampling a particle from
        the corresponding model (with probability biased by the particle weights), and then perturbing using the
        parameter perturbation kernel; if this gives parameters with probability <=0 the process is repeated.

        Parameters
        ----------
        sampled_models_indexes : a list of model indexes, of length self.nbatch


        Returns
        -------
        a list of length self.nbatch, each entry of which is a list of parameter samples (whose length is
            model.nparameters for the corresponding model)

        """
        if self.debug == 2:
            print("\t\t\t***sampleTheParameter")
        samples = []

        for i in range(self.nbatch):
            model = self.models[sampled_models_indexes[i]]
            model_num = sampled_models_indexes[i]

            num_params = model.nparameters
            sample = [0] * num_params

            prior_prob = -1
            while prior_prob <= 0:

                # sample putative particle from previous population
                particle = sample_particle_from_model(self.nparticles, model_num, self.margins_prev, self.model_prev,
                                                      self.weights_prev)

                # Copy this particle's params into a new array, then perturb this in place using the parameter
                #  perturbation kernel ALI
                for param in range(num_params):
                    sample[param] = self.parameters_prev[particle][param]

                prior_prob = self.perturbfn(sample, model.prior, self.kernels[model_num],
                                            self.kernel_type, self.special_cases[model_num])

                if self.debug == 2:
                    print("\t\t\tsampled p prob:", prior_prob)
                    print("\t\t\tnew:", sample)
                    print("\t\t\told:", self.parameters_prev[particle])

            samples.append(sample)

        return samples

    def compute_particle_weights(self):
        r"""Calculate the weight of each particle.

        This is given by $w_t^i = \frac{\pi(M_t^i, \theta_t^i) P_{t-1}(M_t^i = M_{t-1}) }{S_1 S_2 }$, where
        $S_1 = \sum_{j \in M} P_{t-1}(M^j_{t-1}) KM_t(M_t^i | M^j_{t-1})$ and
        $S_2 = \sum_{k \in M_t^i = M_{t-1}} w^k_{t-1} K_{t, M^i}(\theta_t^i | \theta_{t-1}^k)$

        (See p.4 of SOM to 'Bayesian design of synthetic biological systems', except that here we have moved model
        marginal out of s2 into a separate term)
        """
        if self.debug == 2:
            print("\t***computeParticleWeights")

        for k in range(self.nparticles):
            model_num = self.model_curr[k]
            model = self.models[model_num]

            this_param = self.parameters_curr[k]

            model_prior = self.modelprior[model_num]

            particle_prior = 1
            for n in range(len(self.parameters_curr[k])):
                x = 1.0
                this_prior = model.prior[n]

                if this_prior.type == PriorType.constant:
                    x = 1

                if this_prior.type == PriorType.normal:
                    x = statistics.get_pdf_gauss(this_prior.mean, np.sqrt(this_prior.variance), this_param[n])

                if this_prior.type == PriorType.uniform:
                    x = statistics.get_pdf_uniform(this_prior.lower_bound, this_prior.upper_bound, this_param[n])

                if this_prior.type == PriorType.lognormal:
                    x = statistics.get_pdf_lognormal(this_prior.mu, np.sqrt(this_prior.sigma), this_param[n])
                particle_prior = particle_prior * x

            # self.b[k] is a variable indicating whether the simulation corresponding to particle k was accepted
            numerator = self.b[k] * model_prior * particle_prior

            s1 = 0
            for i in range(self.nmodel):
                s1 += self.margins_prev[i] * get_model_kernel_pdf(model_num, i, self.modelKernel, self.nmodel,
                                                                  self.dead_models)
            s2 = 0
            for j in range(self.nparticles):
                if int(model_num) == int(self.model_prev[j]):

                    if self.debug == 2:
                        print("\tj, weights_prev, kernelpdf", j, self.weights_prev[j],)
                        self.kernelpdffn(this_param, self.parameters_prev[j], model.prior,
                                         self.kernels[model_num], self.kernel_aux[j], self.kernel_type)

                    kernel_pdf = self.kernelpdffn(this_param, self.parameters_prev[j], model.prior,
                                                  self.kernels[model_num], self.kernel_aux[j], self.kernel_type)
                    s2 += self.weights_prev[j] * kernel_pdf

                if self.debug == 2:
                    print("\tnumer/s1/s2/m(t-1) : ", numerator, s1, s2, self.margins_prev[model_num])

            self.weights_curr[k] = self.margins_prev[model_num] * numerator / (s1 * s2)

    def normalize_weights(self):
        """Normalize weights by dividing each by the total."""
        n = sum(self.weights_curr)
        for i in range(self.nparticles):
            self.weights_curr[i] /= float(n)

    def update_model_marginals(self):
        """Re-calculate the marginal probability of each model as the sum of the weights of the corresponding particles."""
        for model in range(self.nmodel):
            self.margins_curr[model] = 0
            for particle in range(self.nparticles):
                if int(self.model_curr[particle]) == int(model):
                    self.margins_curr[model] += self.weights_curr[particle]


def sample_particle_from_model(nparticle, selected_model, margins_prev, model_prev, weights_prev):
    """Select a particle from those in the previous generation whose model was the currently selected model, weighted by their previous weight.

    Parameters
    ----------
    nparticle : number of particles
    selected_model : index of the currently selected model
    margins_prev : the marginal probability of the selected model at the previous iteration (nb. this is the sum of the
        weights of the corresponding particles)
    model_prev : list recording the model index corresponding to each particle from the previous iteration
    weights_prev : list recording the weight of each particle from the previous iteration

    Returns
    -------
    the index of the selected particle
    """

    u = rnd.uniform(low=0, high=margins_prev[selected_model])
    f = 0

    for i in range(nparticle):
        if int(model_prev[i]) == int(selected_model):
            f = f + weights_prev[i]
            if f > u:
                return i
    return nparticle - 1


def get_model_kernel_pdf(new_model, old_model, model_k, num_models, dead_models):
    """Return the probability of model number m0 being perturbed into model number m (assuming neither is dead).

    This assumes a uniform model perturbation kernel: with probability modelK the model is not perturbed; with
    probability (1-modelK) it is replaced by a model randomly chosen from the non-dead models (including the current
    model).

    Parameters
    ----------
    new_model : index of next model
    old_model : index of previous model
    model_k : model (non)-perturbation probability
    num_models : total number of models
    dead_models : number of models which are 'dead'
    """
    num_dead_models = len(dead_models)

    if num_dead_models == num_models - 1:
        return 1.0
    else:
        if new_model == old_model:
            return model_k
        else:
            return (1 - model_k) / (num_models - num_dead_models)


def check_below_threshold(distance, epsilon):
    """Return true if each element of distance is less than the corresponding entry of epsilon (and non-negative).

    Parameters
    ----------
    distance : list of distances
    epsilon : list of maximum acceptable distances
    """
    return distance < epsilon
