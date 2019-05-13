from autofit.tools import path_util
from autofit.optimize import non_linear as nl
from autofit.mapper import model_mapper as mm
from autolens.data.array import mask as msk
from autolens.model.galaxy import galaxy_model as gm
from autolens.pipeline import phase as ph
from autolens.pipeline import pipeline
from autolens.pipeline import tagging as tag
from autolens.model.profiles import light_profiles as lp
from autolens.model.profiles import mass_profiles as mp

# In this pipeline, we'll perform a basic analysis which fits a source galaxy using a parametric light profile and a
# lens galaxy where its light is included and fitted, using three phases:

# Phase 1:

# Description: Initializes the lens light model to subtract the foreground lens
# Lens Light: EllipticalSersic
# Lens Mass: EllipitcalIsothermal + ExternalShear
# Source Light: EllipticalSersic
# Previous Pipelines: None
# Prior Passing: None
# Notes: None

# Phase 2:

# Description: Initializes the lens mass model and source light profile.
# Lens Light: EllipticalSersic
# Lens Mass: EllipitcalIsothermal + ExternalShear
# Source Light: EllipticalSersic
# Previous Pipelines: None
# Prior Passing: None
# Notes: Uses the lens subtracted image from phase 1.

# Phase 3:

# Description: Refine the lens light and mass models and source light model.
# Lens Light: EllipticalSersic
# Lens Mass: EllipitcalIsothermal + ExternalShear
# Source Light: EllipticalSersic
# Previous Pipelines: None
# Prior Passing: Lens light (variable -> phase 1), lens mass and source light (variable -> phase 2).
# Notes: None

def make_pipeline(
        phase_folders=None, tag_phases=True,
        redshift_lens=0.5, redshift_source=1.0,
        sub_grid_size=2, bin_up_factor=None, positions_threshold=None, inner_mask_radii=None, interp_pixel_scale=None):

    ### SETUP PIPELINE AND PHASE NAMES, TAGS AND PATHS ###

    # We setup the pipeline name using the tagging module. In this case, the pipeline name is not given a tag and
    # will be the string specified below However, its good practise to use the 'tag.' function below, incase
    # a pipeline does use customized tag names.

    pipeline_name = 'pl__lens_sersic_sie_shear_source_x1_sersic'
    pipeline_name = tag.pipeline_name_from_name_and_settings(pipeline_name=pipeline_name)

    # This function uses the phase folders and pipeline name to set up the output directory structure,
    # e.g. 'autolens_workspace/output/phase_folder_1/phase_folder_2/pipeline_name/phase_name/'
    phase_folders = path_util.phase_folders_from_phase_folders_and_pipeline_name(phase_folders=phase_folders,
                                                                                pipeline_name=pipeline_name)

    ### PHASE 1 ###

    # In phase 1, we will fit only the lens galaxy's light, where we:

    # 1) Set our priors on the lens galaxy (y,x) centre such that we assume the image is centred around the lens galaxy.
    # 2) Use a circular mask which therefore also includes the source's light.

    # Whereas in the howtolens tutorial I used an anti-annular mask in this phase to remove the source galaxy, here I
    # use the default 3.0"  circular mask. In general, I haven't found the choice of mask to make a big difference,
    # albeit this does depend on how much off the lens galaxy's light the lensed source galaxy's light obstructs.

    class LensPhase(ph.LensPlanePhase):

        def pass_priors(self, results):

            self.lens_galaxies.lens.light.centre_0 = mm.GaussianPrior(mean=0.0, sigma=0.1)
            self.lens_galaxies.lens.light.centre_1 = mm.GaussianPrior(mean=0.0, sigma=0.1)

    phase1 = LensPhase(
        phase_name='phase_1_lens_sersic', phase_folders=phase_folders, tag_phases=tag_phases,
        lens_galaxies=dict(lens=gm.GalaxyModel(redshift=redshift_lens, light=lp.EllipticalSersic)),
        sub_grid_size=sub_grid_size, bin_up_factor=bin_up_factor, inner_mask_radii=inner_mask_radii,
        optimizer_class=nl.MultiNest)

    # You'll see these lines throughout all of the example pipelines. They are used to make MultiNest sample the \
    # non-linear parameter space faster (if you haven't already, checkout 'tutorial_7_multinest_black_magic' in
    # 'howtolens/chapter_2_lens_modeling'.

    phase1.optimizer.const_efficiency_mode = True
    phase1.optimizer.n_live_points = 30
    phase1.optimizer.sampling_efficiency = 0.3

    ### PHASE 2 ###

    # In phase 2, we will fit the lens galaxy's mass and source galaxy's light, where we:

    # 1) Use a lens-subtracted image generated by subtracting model lens galaxy image from phase 1.
    # 2) Use a circular annular mask to only include the source-galaxy.
    # 3) Initialize the priors on the centre of the lens galaxy's mass-profile by linking them to those inferred for \
    #    its light profile in phase 1.

    def mask_function(image):
        return msk.Mask.circular_annular(shape=image.shape, pixel_scale=image.pixel_scale,
                                         inner_radius_arcsec=0.3, outer_radius_arcsec=3.0)

    class LensSubtractedPhase(ph.LensSourcePlanePhase):

        def modify_image(self, image, results):
            return image - results[-1].unmasked_model_image

        def pass_priors(self, results):

            self.lens_galaxies.lens.mass.centre_0 = results.from_phase('phase_1_lens_sersic').\
                variable.lens_galaxies.lens.light.centre_0

            self.lens_galaxies.lens.mass.centre_1 = results.from_phase('phase_1_lens_sersic').\
                variable.lens_galaxies.lens.light.centre_1

    phase2 = LensSubtractedPhase(
        phase_name='phase_2_lens_sie_shear_source_sersic', phase_folders=phase_folders, tag_phases=tag_phases,
        lens_galaxies=dict(lens=gm.GalaxyModel(redshift=redshift_lens, mass=mp.EllipticalIsothermal,
                                               shear=mp.ExternalShear)),
        source_galaxies=dict(source=gm.GalaxyModel(redshift=redshift_source, light=lp.EllipticalSersic)),
        mask_function=mask_function,
        sub_grid_size=sub_grid_size, bin_up_factor=bin_up_factor, positions_threshold=positions_threshold,
        inner_mask_radii=inner_mask_radii, interp_pixel_scale=interp_pixel_scale,
        optimizer_class=nl.MultiNest)

    phase2.optimizer.const_efficiency_mode = True
    phase2.optimizer.n_live_points = 60
    phase2.optimizer.sampling_efficiency = 0.2

    ### PHASE 3 ###

    # In phase 3, we will fit simultaneously the lens and source galaxies, where we:

    # 1) Initialize the lens's light, mass, shear and source's light using the results of phases 1 and 2.

    class LensSourcePhase(ph.LensSourcePlanePhase):

        def pass_priors(self, results):

            ## Lens Light, Sersic -> Sersic ###

            self.lens_galaxies.lens.light = results.from_phase('phase_1_lens_sersic').\
                variable.lens_galaxies.lens.light

            ## Lens Mass, SIE -> SIE ###

            self.lens_galaxies.lens.mass = results.from_phase('phase_2_lens_sie_shear_source_sersic').\
                variable.lens_galaxies.lens.mass

            ## Lens Mass, Shear -> Shear ###

            self.lens_galaxies.lens.shear = results.from_phase('phase_2_lens_sie_shear_source_sersic').\
                variable.lens_galaxies.lens.shear

            ### Source Inversion, Inv -> Inv ###

            self.source_galaxies.source = results.from_phase('phase_2_lens_sie_shear_source_sersic').\
                variable.source_galaxies.source

    phase3 = LensSourcePhase(
        phase_name='phase_3_lens_sersic_sie_shear_source_sersic', phase_folders=phase_folders, tag_phases=tag_phases,
        lens_galaxies=dict(lens=gm.GalaxyModel(redshift=redshift_lens, light=lp.EllipticalSersic,
                                               mass=mp.EllipticalIsothermal, shear=mp.ExternalShear)),
        source_galaxies=dict(source=gm.GalaxyModel(redshift=redshift_source, light=lp.EllipticalSersic)),
        sub_grid_size=sub_grid_size, bin_up_factor=bin_up_factor, positions_threshold=positions_threshold,
        inner_mask_radii=inner_mask_radii, interp_pixel_scale=interp_pixel_scale,
        optimizer_class=nl.MultiNest)

    phase3.optimizer.const_efficiency_mode = True
    phase3.optimizer.n_live_points = 75
    phase3.optimizer.sampling_efficiency = 0.3

    return pipeline.PipelineImaging(pipeline_name, phase1, phase2, phase3)