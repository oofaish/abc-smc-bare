from __future__ import print_function
import os
import pickle
import datetime


class InputOutput:

    """Setup the output folders, save data for restart, etc.

    blah blah
    """

    def __init__(self, folder, restart, addTime=True):
        # if we are restarting then dont add the date as it probably already has it
        if restart or not addTime:
            self.folder = folder
        else:
            self.folder = '%s%s' % (folder, datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))

        # Hold all data here for plotting purposes.
        # May want to remove this as could get large
        self.all_results = []

        if restart:
            self.folder += '_restart'

        print('top folder name is %s\n(useful e.g. if you are restarting because in such cases this is the folder name you should pass in)' % self.folder)

    # write rates, distances, trajectories
    def create_output_folders(self, num_outputs, pickling):
        try:
            os.mkdir(self.folder)
        except OSError:
            print("\nThe folder " + self.folder + " already exists!\nContinuing anyway")

        os.chdir(self.folder)

        os.chdir('..')

        if pickling:
            try:
                os.chdir(self.folder)
                os.mkdir('copy')
            except OSError:
                print("\nThe folder \'copy\' already exists!\nContinuing anyway")
            os.chdir('..')
            out_file = open(self.folder + '/copy/algorithm_parameter.dat', "w")
            pickle.dump(num_outputs, out_file)
            out_file.close()

    # read the stored data
    def read_pickled(self, location):
        # pickle numbers selected model of previous population
        # pickle population of selected model of previous population pop_pickled[selected_model][n][vectpos]
        # pickle weights of selected model of previous population weights_pickled[selected_model][n][vectpos]
        in_file = open(location + '/copy/model_last.dat', "r")
        model_pickled = pickle.load(in_file)
        in_file.close()
        in_file = open(location + '/copy/weights_last.dat', "r")
        weights_pickled = pickle.load(in_file)
        in_file.close()
        in_file = open(location + '/copy/params_last.dat', "r")
        parameters_pickled = pickle.load(in_file)
        in_file.close()
        in_file = open(location + '/copy/margins_last.dat', "r")
        margins_pickled = pickle.load(in_file)
        in_file.close()
        in_file = open(location + '/copy/kernels_last.dat', "r")
        kernel = pickle.load(in_file)
        in_file.close()

        return [model_pickled, weights_pickled, parameters_pickled, margins_pickled, kernel]

    # write the stored data
    def write_pickled(self, nmodel, model_prev, weights_prev, parameters_prev, margins_prev, kernel, allResults):

        pickle.dump(model_prev[:], open(self.folder + '/copy/model_last.dat', "w"))
        pickle.dump(weights_prev[:], open(self.folder + '/copy/weights_last.dat', "w"))
        pickle.dump(parameters_prev, open(self.folder + '/copy/params_last.dat', "w"))
        pickle.dump(margins_prev[:], open(self.folder + '/copy/margins_last.dat', "w"))
        x = []
        for mod in range(nmodel):
            x.append(kernel[mod])
        pickle.dump(x, open(self.folder + '/copy/kernels_last.dat', "w"))
        pickle.dump(allResults, open(self.folder + '/allResults.dat', 'w'))
