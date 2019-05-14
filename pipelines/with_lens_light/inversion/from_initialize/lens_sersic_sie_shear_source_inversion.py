from autofit.tools import path_util
from autofit.optimize import non_linear as nl
from autolens.model.galaxy import galaxy_model as gm
from autolens.pipeline import phase as ph
from autolens.pipeline import pipeline
from autolens.pipeline import tagging as tag
from autolens.model.profiles import light_profiles as lp
from autolens.model.profiles import mass_profiles as mp
from autolens.model.inversion import pixelizations as pix
from autolens.model.inversion import regularization as reg

# In this pipeline, we'll perform an initializer analysis which fits an image with a source galaxy and a lens light
# component. This reconstructs the source using a pxielized inversion, and uses the light-profile source fit of a
# previous pipeline. The pipeline is as follows:

# Phase 1:

# Description: Initializes the inversion's pixelization and regularization hyper-parameters, using a previous lens
#              light and mass model.
# Lens Light: EllipticalSersic
# Lens Mass: EllipitcalIsothermal + ExternalShear
# Source Light: AdaptiveMagnification + Constant
# Previous Pipelines: initializers/lens_sie_shear_source_sersic_from_init.py
# Prior Passing: Lens Mass (variable -> previous pipeline).
# Notes: Uses the lens subtracted image corresponding to the light model of a previous pipeline.

# Phase 2:

# Description: Refine the lens light and mass model and source inversion.
# Lens Light: EllipticalSersic
# Lens Mass: EllipitcalIsothermal + ExternalShear
# Source Light: AdaptiveMagnification + Constant
# Previous Pipelines: initializers/lens_sie_shear_source_sersic_from_init.py
# Prior Passing: Lens light and mass (variable -> previous pipeline), source inversion (variable -> phase 1).
# Notes: None

# Phase 3:

# Description: Refine the source inversion using this lens light and mass model.
# Lens Light: EllipticalSersic
# Lens Mass: EllipitcalIsothermal + ExternalShear
# Source Light: AdaptiveMagnification + Constant
# Previous Pipelines: None
# Prior Passing: Lens light and mass (constant -> phase 2), source inversion (variable -> phase 1 & 2).
# Notes: Source inversion resolution varies.

def make_pipeline(
        pl_fix_lens_light=False,
        phase_folders=None, tag_phases=True,
        redshift_lens=0.5, redshift_source=1.0,
        sub_grid_size=2, bin_up_factor=None, positions_threshold=None, inner_mask_radii=None, interp_pixel_scale=None):

    ### SETUP PIPELINE AND PHASE NAMES, TAGS AND PATHS ###

    # We setup the pipeline name using the tagging module. In this case, the pipeline name is tagged according to
    # whether the lens light model is fixed throughout the pipeline.

    pipeline_name = 'pipeline_inv__lens_sersic_sie_shear_source_inversion'
    pipeline_name = tag.pipeline_name_from_name_and_settings(pipeline_name=pipeline_name,
                                                             fix_lens_light=pl_fix_lens_light)

    phase_folders = path_util.phase_folders_from_phase_folders_and_pipeline_name(phase_folders=phase_folders,
                                                                                pipeline_name=pipeline_name)


    ### PHASE 1 ###

    # In phase 1, we initialize the inversion's resolution and regularization coefficient, where we:

    # 1) Use a lens-subtracted image generated by subtracting model lens galaxy image from phase 3 of the initializer
    #    pipeline.
    # 2) Fix our mass model to the lens galaxy mass-model from phase 3 of the initializer pipeline.
    # 3) Use a circular mask which includes all of the source-galaxy light.

    class InversionPhase(ph.LensSourcePlanePhase):

        def pass_priors(self, results):

            ## Lens Light & Mass, Sersic -> Sersic, SIE -> SIE, Shear -> Shear ###

            self.lens_galaxies.lens = results.from_phase('phase_3_lens_sersic_sie_shear_source_sersic').\
                constant.lens_galaxies.lens

    phase1 = InversionPhase(
        phase_name='phase_1_initialize_inversion', phase_folders=phase_folders, tag_phases=tag_phases,
        lens_galaxies=dict(lens=gm.GalaxyModel(redshift=redshift_lens, light=lp.EllipticalSersic,
                                               mass=mp.EllipticalIsothermal, shear=mp.ExternalShear)),
        source_galaxies=dict(source=gm.GalaxyModel(redshift=redshift_source, pixelization=pix.AdaptiveMagnification,
                                                  regularization=reg.Constant)),
        sub_grid_size=sub_grid_size, bin_up_factor=bin_up_factor, positions_threshold=positions_threshold,
        inner_mask_radii=inner_mask_radii, interp_pixel_scale=interp_pixel_scale,
        optimizer_class=nl.MultiNest)

    phase1.optimizer.const_efficiency_mode = True
    phase1.optimizer.n_live_points = 20
    phase1.optimizer.sampling_efficiency = 0.8

    ### PHASE 2 ###

    # In phase 2, we fit the len galaxy light, mass and source galaxy simultaneously, using an inversion. We will:

    # 1) Initialize the priors of the lens galaxy and source galaxy from phase 3 of the previous pipeline and phase 1
    #    of this pipeline.
    # 2) Use a circular mask including both the lens and source galaxy light.

    class InversionPhase(ph.LensSourcePlanePhase):

        def pass_priors(self, results):

            ## Lens Light & Mass, Sersic -> Sersic, SIE -> SIE, Shear -> Shear ###

            self.lens_galaxies.lens = results.from_phase('phase_3_lens_sersic_sie_shear_source_sersic').\
                variable.lens_galaxies.lens

            # If the lens light is fixed, over-write the pass prior above to fix the lens light model.

            if pl_fix_lens_light:

                self.lens_galaxies.lens.light = results.from_phase('phase_3_lens_sersic_sie_shear_source_sersic').\
                    constant.lens_galaxies.lens.light

            ### Source Inversion, Inv -> Inv ###

            self.source_galaxies.source.pixelization = results.from_phase('phase_1_initialize_inversion').\
                constant.source_galaxies.source.pixelization

            self.source_galaxies.source.regularization = results.from_phase('phase_1_initialize_inversion').\
                variable.source_galaxies.source.regularization

    phase2 = InversionPhase(
        phase_name='phase_2_lens_sersic_sie_shear_source_inversion', phase_folders=phase_folders, tag_phases=tag_phases,
        lens_galaxies=dict(lens=gm.GalaxyModel(redshift=redshift_lens, light=lp.EllipticalSersic,
                                               mass=mp.EllipticalIsothermal, shear=mp.ExternalShear)),
        source_galaxies=dict(source=gm.GalaxyModel(redshift=redshift_source, pixelization=pix.AdaptiveMagnification,
                                                  regularization=reg.Constant)),
        sub_grid_size=sub_grid_size, bin_up_factor=bin_up_factor, positions_threshold=positions_threshold,
        inner_mask_radii=inner_mask_radii, interp_pixel_scale=interp_pixel_scale,
        optimizer_class=nl.MultiNest)

    phase2.optimizer.const_efficiency_mode = True
    phase2.optimizer.n_live_points = 75
    phase2.optimizer.sampling_efficiency = 0.2

    ### PHASE 3 ###

    # In phase 3, we refine the inversion's resolution and regularization coefficient, where we:

    # 1) Fix our mass model to the lens galaxy mass-model from phase 2.
    # 2) Use a circular mask which includes all of the source-galaxy light.

    class InversionPhase(ph.LensSourcePlanePhase):

        def pass_priors(self, results):

            ## Lens Light & Mass, Sersic -> Sersic, SIE -> SIE, Shear -> Shear ###

            self.lens_galaxies.lens = results.from_phase('phase_2_lens_sersic_sie_shear_source_inversion').\
                constant.lens_galaxies.lens

            ### Source Inversion, Inv -> Inv ###

            self.source_galaxies.source = results.from_phase('phase_2_lens_sersic_sie_shear_source_inversion').\
                variable.source_galaxies.source

    phase3 = InversionPhase(
        phase_name='phase_3_lens_sersic_sie_shear_refine_source_inversion', phase_folders=phase_folders, tag_phases=tag_phases,
        lens_galaxies=dict(lens=gm.GalaxyModel(redshift=redshift_lens, light=lp.EllipticalSersic,
                                               mass=mp.EllipticalIsothermal, shear=mp.ExternalShear)),
        source_galaxies=dict(source=gm.GalaxyModel(redshift=redshift_source, pixelization=pix.AdaptiveMagnification,
                                                  regularization=reg.Constant)),
        sub_grid_size=sub_grid_size, bin_up_factor=bin_up_factor, positions_threshold=positions_threshold,
        inner_mask_radii=inner_mask_radii, interp_pixel_scale=interp_pixel_scale,
        optimizer_class=nl.MultiNest)

    phase3.optimizer.const_efficiency_mode = True
    phase3.optimizer.n_live_points = 20
    phase3.optimizer.sampling_efficiency = 0.8

    return pipeline.PipelineImaging(pipeline_name, phase1, phase2)