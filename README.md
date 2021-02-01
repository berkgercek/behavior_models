# behavior models

This is the readme for the behavioral models. We developped a series of models, for the moment there are 3:
- the exponential smoothing model based on the previous actions (called `expSmoothing_prevAction`)
- the exponential smoothing model based on the previous stimulus sides (called `expSmoothing_stimside`)
- the smoothing model with fitted kernel based on the previous stimulus sides (called `smoothing_stimside`)

See the `main.py` file for an example on prior generation

In the `models` folder, you will find a file called `model.py` from which all models inherits. In this file, you will find all the methods to which you have access. The other files defines the specificities for each model.

The inference takes a few minutes but once it has run (and has been saved automatically), computing the prior is very fast (which means you can run this prior computation on a lot of pseudoblocks)