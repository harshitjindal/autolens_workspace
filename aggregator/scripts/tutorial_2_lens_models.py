from pathlib import Path

import autofit as af
import autolens as al
import autolens.plot as aplt

import numpy as np
import matplotlib.pyplot as plt

# This tutorial builds on tutorial_1 of the aggregator autolens_workspace. Here, we use the aggregator to load
# models from a non-linear search and visualize and interpret results.

# First, we set up the aggregator as we did in the previous tutorial.
workspace_path = Path(__file__).parent.parent
output_path = workspace_path / "output"
aggregator_results_path = output_path / "aggregator_sample_beginner"

af.conf.instance = af.conf.Config(
    config_path=str(workspace_path / "config"), output_path=str(aggregator_results_path)
)

aggregator = af.Aggregator(directory=str(aggregator_results_path))

# Next, lets create a list of instances of the most-likely models of the final phase of each fit.
pipeline_name = "pipeline__lens_sie__source_inversion"
phase_name = "phase_3__source_inversion"

multi_nest_outputs = aggregator.filter(phase=phase_name).output

most_likely_model_instances = [
    out.most_probable_model_instance for out in multi_nest_outputs
]

# A model instance is a Galaxy instance of the pipeline's GalaxyModel. So, its just a list of galaxies which we
# can pass to functions in PyAutoLens. Lets create the most-likely tracer of every fit and then plot their subplots.
most_likely_tracers = [
    al.Tracer.from_galaxies(galaxies=instance.galaxies)
    for instance in most_likely_model_instances
]

[aplt.tracer.subplot_tracer(tracer=tracer) for tracer in most_likely_tracers]

# Because instances are just lists of galaxies we can directly extract attributes of the Galaxy class. Lets print
# the Einstein mass of each of our most-likely lens galaxies.

# The model instance uses the model defined by a pipeline. In this pipeline, we called the lens galaxy 'lens'.
print("Most Likely Lens Einstein Masses:")
print(
    [
        instance.galaxies.lens.mass.einstein_mass
        for instance in most_likely_model_instances
    ]
)
print()

# Lets next do something a bit more ambitious. Lets create a plot of the einstein_radius vs axis_ratio of each
# SIE mass profile, including error bars at 3 sigma confidence.

most_probable_model_instances = [
    out.most_probable_model_instance for out in multi_nest_outputs
]
upper_error_instances = [
    out.model_errors_instance_at_upper_sigma_limit(sigma_limit=3.0)
    for out in multi_nest_outputs
]
lower_error_instances = [
    out.model_errors_instance_at_lower_sigma_limit(sigma_limit=3.0)
    for out in multi_nest_outputs
]

einstein_radii = [
    instance.galaxies.lens.mass.einstein_radius
    for instance in most_probable_model_instances
]
einstein_radii_upper = [
    instance.galaxies.lens.mass.einstein_radius for instance in upper_error_instances
]
einstein_radii_lower = [
    instance.galaxies.lens.mass.einstein_radius for instance in lower_error_instances
]
axis_ratios = [
    instance.galaxies.lens.mass.axis_ratio for instance in most_probable_model_instances
]
axis_ratios_upper = [
    instance.galaxies.lens.mass.axis_ratio for instance in upper_error_instances
]
axis_ratios_lower = [
    instance.galaxies.lens.mass.axis_ratio for instance in lower_error_instances
]

plt.errorbar(
    x=einstein_radii, y=axis_ratios, xerr=einstein_radii_upper, yerr=axis_ratios_upper
)

# Finally, lets compute the errors on an attribute that wasn't a free parameter in our model fit. For example, getting
# the errors on an axis_ratio is simple, because it was sampled by MultiNest during the fit. Thus, to get errors on the
# axis ratio we simply marginalizes over all over parameters to produce the 1D Probability Density Function (PDF).

# But what if we want the errors on the Einstein Mass? This wasn't a free parameter in our model so we can't just
# marginalize over all other parameters.

# Instead, we need to compute the Einstein mass of every lens model sampled by MultiNest and from this determine the
# PDF of the Einstein mass. When combining the different Einstein mass we weight each value by its MultiNest sampling
# probablity. This means that models which gave a poor fit to the data are downweighted appropriately.

# Below, we get an instance of every MultiNest sample using the MultiNestOutput, compute that models einstein mass,
# store them in a list and find the weighted median value with errors.

# This function takes the list of Einstein mass values with their sample weights and computed the weighted mean and
# standard deviation of these values.


def weighted_mean_and_standard_deviation(values, weights):
    """
    Return the weighted average and standard deviation.
    values, weights -- Numpy ndarrays with the same shape.
    """
    values = np.asarray(values)
    weights = np.asarray(weights)
    average = np.average(values, weights=weights)
    # Fast and numerically precise:
    variance = np.average((values - average) ** 2, weights=weights)
    return (average, np.sqrt(variance))


# Now, we iterate over each MultiNestOutput, extracting all samples and computing ther masses and weights and compute
# the weighted mean of these samples.

einstein_masses = []
einstein_mass_errors = []

for multi_nest_output in multi_nest_outputs:

    sample_masses = []
    sample_weights = []

    for sample_index in range(multi_nest_output.total_samples):
        instance = multi_nest_output.sample_model_instance_from_sample_index(
            sample_index=sample_index
        )
        sample_masses.append(instance.galaxies.lens.einstein_mass)
        sample_weights.append(
            multi_nest_output.sample_weight_from_sample_index(sample_index=sample_index)
        )

    value, error = weighted_mean_and_standard_deviation(
        values=sample_masses, weights=sample_weights
    )
    einstein_masses.append(value)
    einstein_mass_errors.append(value)

print("Einstein Mass:")
print(einstein_masses)
print("Einstein Mass Errors")
print(einstein_mass_errors)
