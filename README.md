# behavior models

This is the readme for the behavioral models. We developped a series of models, for the moment there are 3:
- the exponential smoothing model based on the previous actions (called `expSmoothing_prevAction`)
- the exponential smoothing model based on the previous stimulus sides (called `expSmoothing_stimside`)
- the optimal Bayesian model. This model performs inference in the generative Bayesian process with the correct parameters (mean block size=50, lower bound=20, upper bound=100, p(stimulus on left side | left block) = 0.8)
- the biased Bayesian model. This model performs inference in the generative Bayesian process with parameters fitted to the behavior. The additional parameters fitted are the mean block size, the lower bound, the upper bound and the p(stimulus on left side | left block).

See the `main.py` file for an example on prior generation

In the `models` folder, you will find a file called `model.py` from which all models inherits. In this file, you will find all the methods to which you have access. The other files defines the specificities for each model.

The inference takes some minutes but once it has run (and has been saved automatically), computing the prior is very fast (which means you can run this prior computation on a lot of pseudoblocks)
