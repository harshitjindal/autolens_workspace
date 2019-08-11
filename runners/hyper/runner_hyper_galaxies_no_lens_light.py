import autofit as af
from autolens.data.array import mask as msk
from autolens.data.instrument import ccd
from autolens.data.plotters import ccd_plotters
from autolens.pipeline import pipeline as pl
from autolens.model.inversion import pixelizations as pix
from autolens.model.inversion import regularization as reg

import os

# Welcome to the hyper_galaxy pipeline runner! This script is identical to the
# 'runners/simple/runner__lens_sersic_sie__source_sersic.py' script, except at the end when we add pipelines together. So,
# if you already know how the simple runners work, jump ahead to our pipeline imports. If you don't, I recommmend you
# checout the 'simple' pipelines, before using this script.

### The code between the dashed ---- lines is identical to 'runners/simple/runner__lens_sersic_sie__source_sersic.py' ###

# ----------------------------------------------------------------------------------------------------------

# Welcome to the pipeline runner. This tool allows you to load strong lens instrument, and pass it to pipelines for a
# PyAutoLens analysis. To show you around, we'll load up some example instrument and run it through some of the example
# pipelines that come distributed with PyAutoLens.

# The runner is supplied as both this Python script and a Juypter notebook. Its up to you which you use - I personally
# prefer the python script as provided you keep it relatively small, its quick and easy to comment out different lens
# names and pipelines to perform different analyses. However, notebooks are a tidier way to manage visualization - so
# feel free to use notebooks. Or, use both for a bit, and decide your favourite!

# The pipeline runner is fairly self explanatory. Make sure to checkout the pipelines in the
#  workspace/pipelines/examples/ folder - they come with detailed descriptions of what they do. I hope that you'll
# expand on them for your own personal scientific needs

# Setup the path to the workspace, using a relative directory name.
workspace_path = "{}/../../".format(os.path.dirname(os.path.realpath(__file__)))

# Use this path to explicitly set the config path and output path.
af.conf.instance = af.conf.Config(
    config_path=workspace_path + "config", output_path=workspace_path + "output"
)

# Create the path to the data folder in your workspace.
data_path = af.path_util.make_and_return_path_from_path_and_folder_names(
    path=workspace_path, folder_names=["data"]
)

# It is convenient to specify the instrument type and data name as a string, so that if the pipeline is applied to multiple
# images we don't have to change all of the path entries in the load_ccd_data_from_fits function below.
data_type = "example"
data_name = (
    "lens_sie__source_sersic"
)  # Example simulated image with lens light emission and a source galaxy.
pixel_scale = 0.1

# data_name = 'slacs1430+4105' # Example HST imaging of the SLACS strong lens slacs1430+4150.
# pixel_scale = 0.03

# Create the path where the instrument will be loaded from, which in this case is
# '/workspace/data/example/lens_light_and_x1_source/'
data_path = af.path_util.make_and_return_path_from_path_and_folder_names(
    path=data_path, folder_names=[data_type, data_name]
)

# This loads the CCD imaging data, as per usual.
ccd_data = ccd.load_ccd_data_from_fits(
    image_path=data_path + "image.fits",
    psf_path=data_path + "psf.fits",
    noise_map_path=data_path + "noise_map.fits",
    pixel_scale=pixel_scale,
)

# We need to define and pass our mask to the hyper_galaxy pipeline from the beginning.
mask = msk.Mask.circular(
    shape=ccd_data.shape, pixel_scale=ccd_data.pixel_scale, radius_arcsec=3.0
)

# Plot CCD before running.
ccd_plotters.plot_ccd_subplot(ccd_data=ccd_data, mask=mask)


# Running a pipeline is easy, we simply import it from the pipelines folder and pass the lens instrument to its run function.
# Below, we'll' use a 3 phase example pipeline to fit the instrument with a parametric lens light, mass and source light
# profile. Checkout 'workspace/pipelines/examples/lens_light_and_x1_source_parametric.py' for a full description of
# the pipeline.

# The phase folders input determines the output directory structure of the pipeline, for example the input below makes
# the directory structure:
# 'autolens_workspace/output/phase_folder_1/phase_folder_2/pipeline_name/' or
# 'autolens_workspace/output/example/lens_light_and_x1_source/lens_light_and_x1_source_parametric/'

# For large samples of images, we can therefore easily group lenses that are from the same sample or modeled using the
# same pipeline.

# --------------------------------------------------------------------------------------------------------

### HYPER FITTING ###

# Okay, so in this, the hyper_galaxy runner, we're going to use hyper_galaxy-galaxies. Whats a hyper_galaxy-galaxy? It's a galaxy which is
# also used to scale the noise-map of the observed image. This is necessary when there are regions of the image that
# are poorly fitted by the model, for example, because:

# - The lens galaxy's light has complex structures (nuclear star emission, a bar, etc.) that our analytic light profiles
#   cannot fit. This is often very problematic for the fitting, as these pixels are typically *very* high S/N, and
#   therefore overwhelm the chi-squared contribution (it is common to have single pixels with chi-squareds > 100s).
#   By increasing the noise, we bring this chi-squared down, and thus fit the image more equally.

# - The lens's' mass model is more complex than our simple analytic mass profiles, which means there are residuals in
#   the source reconstruction. Along a similar line to the lens light profile, these residuals will overwhelm the
#   model fitting if the noise isn't increased.

### HYPER PIPELINE SETTINGS ###

# In the advanced pipelines, we defined pipeline settings which controlled various aspects of the pipelines, such as
# the model complexity and assumtpions we made about the lens and source galaxy models.

# The pipeline settings we used in the advanced runners all still apply, but hyper_galaxy-fitting brings with it the following
# new settings:

# - If hyper_galaxy-galaxies are used to scale the noise in each component of the image (default True)

# - If the background sky is modeled throughout the pipeline (default False)

# - If the level of background noise is normal throughout the pipeline (default True)

# - The default Pixelization and Regularization are also now changed to VoronoiBrightnessImage and AdaptiveBrightness.

pipeline_settings = pl.PipelineSettingsHyper(
    hyper_galaxies=True,
    hyper_image_sky=False,
    hyper_background_noise=False,
    include_shear=True,
    pixelization=pix.VoronoiBrightnessImage,
    regularization=reg.AdaptiveBrightness,
)

### HYPER PIPELINES ###

from workspace.pipelines.hyper.no_lens_light.initialize import lens_sie__source_sersic
from workspace.pipelines.hyper.no_lens_light.inversion.from_initialize import (
    lens_sie__source_inversion,
)
from workspace.pipelines.hyper.no_lens_light.power_law.from_inversion import (
    lens_power_law__source_inversion,
)

pipeline_initialize = lens_sie__source_sersic.make_pipeline(
    pipeline_settings=pipeline_settings, phase_folders=[data_type, data_name]
)

pipeline_inversion = lens_sie__source_inversion.make_pipeline(
    pipeline_settings=pipeline_settings,
    phase_folders=[data_type, data_name],
    positions_threshold=1.0,
)

pipeline_power_law = lens_power_law__source_inversion.make_pipeline(
    pipeline_settings=pipeline_settings,
    phase_folders=[data_type, data_name],
    positions_threshold=1.0,
)

pipeline = pipeline_initialize + pipeline_inversion + pipeline_power_law

pipeline.run(data=ccd_data)
