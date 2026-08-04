# Assumptions

## Environmental Conditions

- Site weather conditions for Generation and Consumption are assumed to be homogenous and independent; i.e. all generators, buildings and storage devices are assumed subject to weather conditions experienced at the same latitude and longitude at the modelled time, but have no interactive effects such as self-shading, wake losses, or explicitly modelled sheltering.

- Fixed ten-year timeseries of weather data are used.

- The price of electricity sold to and purchased from the grid is time-invariant and uncorrelated with environmental conditions.

## Generation

### All generators

-	No electrical losses over the (private) distribution network to the point of common coupling with the regional distribution network are modelled except as incurred over voltage transformation.
-	Electrical and network supplies for supervisory control and data acquisition (SCADA) are assumed backed-up and are not explicitly modelled as requiring energy flows or incurring system costs.
-	All generators are assumed to be unaffected by power quality impositions of other generators.
-	All electrical machines, power electronics, circuit breakers and necessary safety equipment is assumed appropriately rated for the current drawn during both transient and steady-state operation of the generators.
-	All generators are assumed connected to the same AC electrical bus (i.e. at the same RMS voltage, with matching frequency and in phase) for connection to the site storage / distribution network.
-	All generators are assumed to be using the same earth potential if single-phase or Y-connected.

### Wind Turbine Generators

-	Electrical power production will be characterised by power curve describing mean net electrical output power over mean hub height wind speeds. Discrepancies between averaging periods and measurement technologies for input hub height wind speed will be permitted. Extrapolation of hub height wind speed from measurements or estimates other heights and/or locations will be permitted.
-	Array effects will not be explicitly modelled, but may be expressed by a loss function conditional upon mean wind direction and speed applied per WTG.
-	Effects of local micro-geography upon wind speed, e.g. ridgeline speed-up, will not be explicitly modelled, though may be captured by input data. Effects of land use upon wind shear profile may be represented by a single aerodynamic roughness length per wind direction sector.
-	These roughness lengths are not time-varying, and cannot describe the effect of growing trees or crops, or of the varying roughness of the sea surface.
-	Wind shear profiles will assume a neutral atmosphere at all times.
-	Variations around a mean wind speed within an averaging period may be represented by a Markov-chain process (Ma, Fouladirad, and Grall 2018).
-	Decorrelation of power production due to (local) geographical dispersion of WTGs will not be modelled.
-	The impact of wind speed variation on electrical power production may be modelled by a first-order dynamic model of spinning mass within the WTG under the assumption of locally linear torque response to wind speed.
-	Loss of performance of the WTG due to component aging may be represented by a single scalar reduction in conversion efficiency at all wind speeds (nb - rated capacity may be reached, but at a higher wind speed, under these conditions). This performance loss is to be conditional only upon the number of hours since commissioning of the WTG. It may have stochastic components, but must be monotonically decreasing or stable.
-	No catastrophic failure of any WTG component leading to loss of generation will be possible, either due to manufacturing defect or acquired damage.
-	Loss of conversion efficiency due to controller error (e.g. yaw misalignment) will not be explicitly modelled, but may inform the WTG aging performance loss coefficient.
-	Parasitic losses during still or pre-cut-in conditions will not be modelled; net electrical energy transfer will be assumed to always flow from the turbine to the take-off point.
-	Any necessary voltage transformation from generation voltage to distribution / storage voltage will incur an additional energy loss at the WTG transformer. Losses will be assumed proportional to the rate of electrical energy export. No parasitic losses will be modelled at zero export or (unmodelled) net import. Metering of WTG output will occur across the output terminals of this transformer, if present.
-	Maintenance windows may be pre-specified per WTG, with a priority order assigned to each WTG and a number of available maintenance and inspection crews. Once the maintenance window opens, wind turbines will be shut down and serviced in priority order in post-hoc evaluated periods of wind speeds below a nominated threshold.
-	Routine service of WTGs will not be assumed to have any direct impact on WTG performance beyond the shut-down period.
-	Reactive service and replacement of WTG components will not be possible within the model, but may be pre-specified as deterministic service windows outside of the normal service season. Loss of production waiting for a weather window cannot be explicitly modelled; in order to approximate the impact of such a failure, an initial service to “remove” the WTG from the modelled system with a very high weather window threshold should be scheduled, followed by scheduling of a new service window with a more realistic window criterion to represent reactive maintenance, during which a “new” WTG should be installed. A function allowing for the transfer of service life from one WTG to another across this window will be provided, allowing for the new WTG to have the same aging as the previous. This method will be particularly useful for modelling the impact on total energy production of electrical trips requiring on-site reset. Partial failure of a WTG requiring reactive maintenance cannot be modelled.
-	The IEC wind classification of the generation site is not assumed known, and validated extrapolative models or local measurements should be used to ensure the wind conditions are suitable for any specific model of generator selected, particularly as this may affect the device warrantee.

### Solar PV generation systems:

-	Electrical power will be characterised by module efficiency in response to horizontal plane irradiation, based upon assumptions of direct/diffuse ratio and attenuation due to humidity content and considerate of module azimuth and elevation.
-	Estimation of the diffuse to global irradiation ratio will be per the model of Munoz et al.(Muñoz, Ballantyne, and Stone 2022)
-	Estimation of the diffuse irradiative flux on an inclined plane under an anisotropic sky dome will be per the model of Muneer.(Muneer 1990)
-	Shallow-angle losses shall be estimated per the model of Martin and Ruiz.(Martin and Ruiz 2001)
-	Losses in module efficiency/maximum power as a result of elevated module temperature and/or low irradiance shall be estimated per the model of Huld et al.(Huld et al. 2011) These models may be superceded by information from manufacturer datasheets.
-	Module temperature shall be estimated using the model of Faiman(David Faiman 2008) as fitted by Koehl et al (Koehl et al. 2011).
-	Module aging shall be modelled by assuming a monotonic decrease in peak power production under STC.
-	No impact of changes in spectrum from STC conditions shall be modelled unless using PVGIS module output estimates.
-	Maximum power point tracking is assumed to apply at the module level; combined control of multiple modules with heterogenous MPPs will not be modelled.
-	Modules may be grouped to a single inverter for the calculation of inverter losses and minimum power for inverter power export.
-	Parasitic losses due to inverters shall be modelled as a constant rate during night-time hours and a secondary constant rate during daytime hours, until net export occurs.
-	Inverter losses under net export conditions shall be modelled as a function of electrical input power and (optionally) air temperature.
-	Module shading shall be modelled using horizon files indicating occulusion directions and solar elevation angles, which will be applied assuming that the sun is a point source and the modules are point receivers.
-	Module array self-shading shall not be modelled.
-	Module occlusion due to precipitation or dirt shall not be modelled.
-	The impact of cleaning cycles on performance will not be modelled directly, but should be reflected in the long-term degredation of performance and costs included in ongoing O&M costs.
-	Local thermal conditions around the modules shall not be modelled directly, but the efficiency function can be made dependent upon air temperature, wind speed and direction.
-	The peak capacity of the modules may be modified by an aging function dependent only upon time from connection of the module to the supply system.
-	The impact of sub-module shading on performance or lifespan (i.e. hotspotting) will not be modelled.

## Consumption

-	Housing stock is newbuild to standards appropriate for Welsh Social Housing. As such, it must comply with the Welsh Building Regulations,(Welsh Government 2025) Welsh Development Quality Requirements 2021,(Welsh Government 2021) and Planning Policy Wales edition 12 (Welsh Government 2024b), and thus Welsh Government Technical Advice Note 12 (Design) (Welsh Government 2018b) and Practice Guidance for Planning for Sustainable Buildings.(Welsh Government 2018a)
-	The five seasonal mean residential electrical load profiles (split further into weekday and two weekend profiles) used by Elexon for settlement (Elexon 2025c) are appropriate for estimation of after-diversity household electricity demand. This assumption contains the following assumptions:
-	The profile class selected (i.e. sampled domestic unrestricted customers) is representative of the domestic electrical requirements of the modelled dwellings. This requires that appliances be of similar energy efficiency and load profile, and that their usage rates be similar.
-	The geographic dispersion of the sample has negligible impact on the load diversity versus that from a single site.
-	The change in number of consumers from the Elexon sample (~2,500 customers across 8 profile classes) to the site (20 - 125 households) has negligible impact on the load diversity.
-	The inter-day variability of diversity has no impact on model outcomes.
 	The validity of the above contained assumptions will be tested using bottom-up models of household electricity demand.
-	Domestic demand will not evolve substantially within a single household, except as due to changes in occupancy pattern (i.e. change of tenancy) over the model time horizon. Scenarios may investigate decrease in demand due to increasing energy efficiency of appliances, or increases in demand due to faster-than-expected aging of components, particularly heat pumps.
