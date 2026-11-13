# Assumptions

## Environmental Conditions

- Site weather conditions for Generation and Consumption are assumed to be homogenous and independent; i.e. all generators, buildings and storage devices are assumed subject to weather conditions experienced at the same latitude and longitude at the modelled time, but have no interactive effects such as self-shading, wake losses, or explicitly modelled sheltering.

- Location-dependent ten year timeseries are used.

- Wind data are sourced from the New European Wind Atlas at [mesoscale](https://wps.neweuropeanwindatlas.eu/api/mesoscale-atlas/v1/docs#/) and [microscale](https://wps.neweuropeanwindatlas.eu/api/microscale-atlas/v1/docs#/). See the documentation of [`get_wind_at_site`](/documentation/framework/util.html#newsegsmodelframework.util.wind_resource_helpers.get_wind_at_site).

- Horizontal solar flux and air temperature are sourced from [PVGIS](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/api-non-interactive-service_en)

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

-	Electrical power production is characterised by a power curve describing mean net electrical output power over mean hub height wind speeds. Discrepancies between averaging periods and measurement technologies for input hub height wind speed is permitted. Extrapolation of hub height wind speed from measurements or estimates at other heights and/or locations is permitted.

-   The power curve used is that for a Proven 12 kW wind turbine, assumed to be at 15 m hub height.

-	Array effects are not modelled.

-	Effects of local micro-geography upon wind speed, e.g. ridgeline speed-up, are not be explicitly modelled, though may be captured by input data if the features are of large enough scale. Effects of land use upon wind shear profile are be represented by wind direction, speed and stability conditional power law exponents.

-	These power law exponents and the implied surface roughness lengths are not time-varying, and cannot describe the effect of growing trees or crops, or of the varying roughness of the sea surface.

-	Wind shear profiles use the power law and so assume a neutral atmosphere at all times.

-	Variations around a mean wind speed within an averaging period are not considered.

-	Decorrelation of power production due to (local) geographical dispersion of WTGs is not modelled (and due to timescale of averaging, would not be influential over a single site).

-	The impact of wind speed variation on electrical power production is not modelled.

-	Loss of performance of the WTG due to component aging is not modelled.

-	No catastrophic failure of any WTG component leading to loss of generation is possible, either due to manufacturing defect or acquired damage.

-	Loss of conversion efficiency due to controller error (e.g. yaw misalignment) is not explicitly modelled, but may inform the WTG Cp curve.

-	Parasitic losses during still or pre-cut-in conditions are not modelled; net electrical energy transfer is assumed to always flow from the turbine to the take-off point.

-	Any necessary voltage transformation from generation voltage to distribution / storage voltage will be expected to incur an additional energy loss at the WTG transformer, but this is assumed captured by the Cp curve of the nominated turbine.

-	No maintenance windows are modelled.

-	Routine service of WTGs is notassumed to have any impact on WTG performance.

-	Reactive service and replacement of WTG components is not modelled.

-	The IEC wind classification of the generation site is not assumed known, and validated extrapolative models or local measurements should be used to ensure the wind conditions are suitable for any specific model of generator selected, particularly as this may affect the device warrantee.

### Solar PV generation systems:

-	Electrical power is characterised by module efficiency in response to horizontal plane irradiation, based upon assumptions of direct/diffuse ratio and attenuation due to humidity content and considerate of module azimuth and elevation.

-	Estimation of the diffuse to global irradiation ratio is per the model of Munoz et al.[Muñoz, Ballantyne, and Stone 2022](https://www.sciencedirect.com/science/article/pii/S0360544221030693)

-	Estimation of the diffuse irradiative flux on an inclined plane under an anisotropic sky dome is per the model of Muneer.[Muneer 1990](https://journals.sagepub.com/doi/10.1177/014362449001100405)

-	Shallow-angle losses are estimated per the model of Martin and Ruiz.[Martin and Ruiz 2001](https://www.sciencedirect.com/science/article/abs/pii/S0927024800004086)

-	Losses in module efficiency/maximum power as a result of elevated module temperature and/or low irradiance are estimated per the model of Huld et al. [Huld et al. 2011](https://www.sciencedirect.com/science/article/abs/pii/S0927024811004442).

-	Module temperature is estimated using the model of Faiman [David Faiman 2008](https://onlinelibrary.wiley.com/doi/10.1002/pip.813) as fitted by Koehl et al [Koehl et al. 2011](https://www.sciencedirect.com/science/article/abs/pii/S0927024811000304).

-	Module aging is not modelled.

-	No impact of changes in spectrum from STC conditions is modelled.

-	Maximum power point tracking is assumed to apply at the module level; combined control of multiple modules with heterogenous MPPs is not be modelled.

-	Modules are grouped to a single inverter for the calculation of inverter losses and minimum power for inverter power export.

-	Parasitic losses due to inverters are modelled as a constant rate during night-time hours and a secondary constant rate during daytime hours, until net export occurs.

-	Inverter losses under net export conditions sare modelled as a function of electrical input power and air temperature.

-	Module shading is modelled using horizon files indicating occulusion directions and solar elevation angles, which will be applied assuming that the sun is a point source and the modules are point receivers.

-	Module array self-shading is not modelled.

-	Module occlusion due to precipitation or dirt is not modelled.

-	The impact of cleaning cycles on performance is not modelled.

-	Local thermal conditions around the modules is not modelled directly, but the efficiency function is dependent upon air temperature, and wind speed.

-	The peak capacity of the modules is not modified by aging.

-	The impact of sub-module shading on performance or lifespan (i.e. hotspotting) is not modelled.

## Consumption

-	Housing stock is newbuild to standards appropriate for Welsh Social Housing. As such, it must comply with the Welsh Building Regulations,(Welsh Government 2025) Welsh Development Quality Requirements 2021,(Welsh Government 2021) and Planning Policy Wales edition 12 (Welsh Government 2024b), and thus Welsh Government Technical Advice Note 12 (Design) (Welsh Government 2018b) and Practice Guidance for Planning for Sustainable Buildings.(Welsh Government 2018a)

-	The five seasonal mean residential electrical load profiles (split further into weekday and two weekend profiles) used by Elexon for settlement (Elexon 2025c) are appropriate for estimation of after-diversity household electricity demand. This assumption contains the following assumptions:

-	The profile class selected (i.e. sampled domestic unrestricted customers) is representative of the domestic electrical requirements of the modelled dwellings. This requires that appliances be of similar energy efficiency and load profile, and that their usage rates be similar.

-	The geographic dispersion of the sample has negligible impact on the load diversity versus that from a single site.

-	The change in number of consumers from the Elexon sample (~2,500 customers across 8 profile classes) to the site (20 - 125 households) has negligible impact on the load diversity.

-	The inter-day variability of diversity has no impact on model outcomes.

 	The validity of the above contained assumptions will be tested using bottom-up models of household electricity demand.

-	Domestic demand will not evolve substantially within a single household, except as due to changes in occupancy pattern (i.e. change of tenancy) over the model time horizon. Scenarios may investigate decrease in demand due to increasing energy efficiency of appliances, or increases in demand due to faster-than-expected aging of components, particularly heat pumps.
