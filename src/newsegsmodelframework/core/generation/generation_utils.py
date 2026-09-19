"""
Utility functions for the generator classes
"""
from pvlib.modelchain import ModelChain as PVLibModelChain

def huld_dcmodel_wrapper(
    mc: PVLibModelChain
) -> PVLibModelChain:
    """
    Use the Huld DC power model and assign it to mc.results.dc

    DC conversion model as per PVGIS.
    """
    from pvlib.pvarray import huld as pvlib_huld
    if mc.system.num_arrays == 1:
        effective_irrads = [mc.results.effective_irradiance]
    else:
        effective_irrads = mc.results.effective_irradiance

    # Note that for whatever reason it is the air temperature, not module
    # or cell temp which drives the Huld model.
    mc.results.dc = tuple(
        pvlib_huld(
            effective_irrad,
            mc.results.weather['temp_air'], # type: ignore
            array.module_parameters['pdc0'],
            k = array.module_parameters.get('k'),
            cell_type = array.module_parameters.get('cell_type'),
            k_version = array.module_parameters.get('k_version', 'pvgis5')
        )
        for effective_irrad, array
        in zip(effective_irrads, mc.system.arrays) # type: ignore
    )
    return mc

def fixed_percent_dc_loss(
    mc: PVLibModelChain
) -> PVLibModelChain:
    """
    Remove a fixed percentage of dc power
    """
    if isinstance(mc.results.dc, tuple):
        for dc in mc.results.dc:
            dc *= mc.system.losses_parameters.get('dc_efficiency', 1.0)
    else:
        mc.results.dc *=  mc.system.losses_parameters.get('dc_efficiency', 1.0)
    return mc
