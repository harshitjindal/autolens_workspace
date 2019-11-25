import os

# Before reading this script, you should checkout the 'galaxy_fit_surface_density.py' script first, which shows you
# how to simulate a convergence profile and fit it with a galaxy. In this script, we'll do the same thing with
# deflection angles and using multiple galaxies. There a few benefits to fitting deflection angles instead of a surface
# density profile (or gravitational potential):

# 1) In terms of lensing, the deflection-angle map is closest thing to what we *actually* observe when we image and
#    model a strong lens. Thus fitting deflection angle maps is the best way we can compare the results of a lens model
#    to a theoretical quantity.

# 2) As we do in this example, we can simulator our deflecton angle map using multi-plane lens ray-tracing, and thus
#    investigate the impact assuming a single-lens plane has on the inferred lens model.

### AUTOFIT + CONFIG SETUP ###

import autofit as af

# Setup the path to the autolens_workspace, using a relative directory name.
workspace_path = "{}/../../".format(os.path.dirname(os.path.realpath(__file__)))

# Use this path to explicitly set the config path and output path.
af.conf.instance = af.conf.Config(
    config_path=workspace_path + "config", output_path=workspace_path + "output"
)

### AUTOLENS + DATA SETUP ###

import autolens as al

# First, we'll setup the grid we use to simulate a deflection profile.
grid = al.grid.uniform(shape_2d=(250, 250), pixel_scales=0.05, sub_size=4)

# Now lets create two galaxies, using singular isothermal spheres. We'll put the two galaxies at different redshifts,
# and the second galaxy will be much lower mass as if it is a 'perturber' of the main lens galaxy.
lens_galaxy = al.Galaxy(
    redshift=0.5, mass=al.mp.SphericalIsothermal(centre=(0.0, 0.0), einstein_radius=1.0)
)

perturber = al.Galaxy(
    redshift=0.2, mass=al.mp.SphericalIsothermal(centre=(0.5, 0.5), einstein_radius=0.1)
)

# We only need the source galaxy to have a redshift - given we're not fitting an image it doens't need a light profile.
source_galaxy = al.Galaxy(redshift=1.0)

# We'll use a tracer to compute our multi-plane deflection angles.
tracer = al.Tracer.from_galaxies(galaxies=[lens_galaxy, perturber, source_galaxy])

# We'll now extract the deflection angles from the tracer - we will extract the two deflection angle maps (y and x)
# separately.
deflections_y = tracer.deflections_from_grid(grid=grid).in_2d_binned[:, :, 0]
deflections_y = al.array.manual_2d(
    array=deflections_y, pixel_scales=grid.pixel_scales, sub_size=1
)

deflections_x = tracer.deflections_from_grid(grid=grid).in_2d_binned[:, :, 1]
deflections_x = al.array.manual_2d(
    array=deflections_x, pixel_scales=grid.pixel_scales, sub_size=1
)

# Next we create each deflection angle map as its own GalaxyData object. A somewhat arbritary noise-map is required by
# the fit.
noise_map = al.array.full(
    fill_value=0.1, shape_2d=grid.shape_2d, pixel_scales=grid.pixel_scales
)
data_y = al.galaxy_data(
    image=deflections_y, noise_map=noise_map, pixel_scales=grid.pixel_scales
)
data_x = al.galaxy_data(
    image=deflections_x, noise_map=noise_map, pixel_scales=grid.pixel_scales
)

# The fit will use a mask, which we setup like any other fit. Lets use a circular mask of 2.0"
def mask_function_circular(shape_2d, pixel_scales):
    return al.mask.circular(
        shape_2d=shape_2d, pixel_scales=pixel_scales, sub_size=1, radius=2.5
    )


# Again, we'll use a special phase, called a 'PhaseGalaxy', to fit the deflections with our model galaxies. We'll
# fit it with two singular isothermal spheres at the same lens-plane, thus we should see how the absence of multi-plane
# ray tracing impacts the mass of the subhalo.


class DeflectionFitPhaseGalaxy(al.PhaseGalaxy):
    def customize_priors(self, results):

        # You may wish to fix the first galaxy to its true centre / einstein radius

        #  self.galaxies.lens.mass.centre_0 = 0.0
        #  self.galaxies.lens.mass.centre_1 = 0.0
        #  self.galaxies.lens.mass.einstein_radius = 1.0

        # Adjusting the priors on the centre of galaxies away from (0.0", 0.0") is also a good idea.

        self.galaxies.subhalo.mass.centre_0 = af.GaussianPrior(mean=0.5, sigma=0.3)
        self.galaxies.subhalo.mass.centre_1 = af.GaussianPrior(mean=0.5, sigma=0.3)


phase = DeflectionFitPhaseGalaxy(
    phase_name="phase_galaxy_deflections_fit",
    galaxies=dict(
        lens=al.GalaxyModel(redshift=0.5, mass=al.mp.SphericalIsothermal),
        subhalo=al.GalaxyModel(redshift=0.5, mass=al.mp.SphericalIsothermal),
    ),
    use_deflections=True,
    sub_size=4,
    mask_function=mask_function_circular,
    optimizer_class=af.MultiNest,
)


# Finally, when we run the phase, we now pass both deflection angle dataset_label's separately.
phase.run(galaxy_data=[data_y, data_x])

# If you check your output folder, you should see that this fit has been performed and visualization specific to a
# deflections fit is output.
