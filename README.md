
This is a really simplified version of ``abc-sysbio`` (http://www.theosysbio.bio.ic.ac.uk/resources/abc-sysbio/) for python.

It's actually a fork (fork is a strong word, call it a hack) of the copy being worked on by JSB at https://github.com/jamesscottbrown/abc-sysbio.

It can do Model Selection and Parameter Inference.

See the example jupyter notebook included to see how you can get started. good luck!


``abc-sysbio`` implements likelihood free parameter inference and model selection in dynamical systems.
so ``abc-smc-bare``  also implements likelihood free parameter inference and model selection. However, the big differences are:

* You do NOT need to call it via various scripts, etc.
* It does NOT assume you are using biological systems.
* It does NOT assume you need to use SBML interface.
* It does NOT assume your system is using ODEs or SDEs or anything like that.
* You can just call it from another python script by setting up your own simulation and distance function and get on with it.

However, on the downside:
* It does NOT have GPU support, or any parallelisation, not yet anyway. But should be easy enough to implement quickly using MPI or something.


``abc-smc-bare`` combines three algorithms: ABC rejection sampler, ABC SMC for parameter inference and ABC SMC for model selection.

# Prerequisites

Before trying to install and use abc-sysbio you must
first install the following packages

    numpy
    matplotlib
    scipy
    seaborn

You really should know how to install these things if you are here, but a quick http://duckduckgo.com will get you there too. Seaborn and scipy are not really essential, but useful. Specially seaborn, why whould you not have seaborn installed?

# installation
Because I want this to be a quick hacking library, there is no real installation. Just copy the abcsmcbare directory whereever you want to use it and just import it:

import abcsmcbare

look at the included iPython/jupyter notebook for a full example.

#Usual nonsense
As I said at the top the original copy of this work is taken from https://github.com/jamesscottbrown/abc-sysbio, which itself is taken from http://www.theosysbio.bio.ic.ac.uk/resources/abc-sysbio/. The code is I am sure very buggy, etc, etc, and I provide no guarantees that it's not.

Play with it, enjoy it, learn from it, but dont come running to me if it lets you down :p.
