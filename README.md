# NewSEGS Model

## Introduction 
The North Wales Social Housing Newbuild on-Site Energy Generation and Storage (NewSEGS) project aims to identify and optimise opportunities for self-supply of renewable energy in newbuild social housing in North Wales.

The NewSEGS-modelling project builds on the work of Dr David Sprake to produce estimates of the financial performance of a local energy system.

## Getting Started

## Supported platforms
This program has been tested on the following platforms:

- Python 3.13 running on Microsoft Windows 10

## Installing dependencies
In order to run this model, it is recommended that you set up a virtual execution environment. Using conda or miniconda, it is recommended you do so from the relevant `environment.yml` file using the command:

```
conda env create -f environment.yml
```

## Running calculations

**TODO**

## Model Concept

The NewSEGS model consists of four calculation modules, of which the latter two form a short-interval feedback loop and must be evaluated together.

- **Module 1 - Grid**
- **Module 2 - Generation**
- **Module 3a - Consumption**
- **Module 3b - Storage**

These four modules are described in more detail in their relevant sections. 

These four modules must be defined for a coincident time period, as one of the key considerations of the model is that short-term local environmental conditions determine the value of both generation and consumption, and may impact storage performance; correlated wider environmental conditions determine the cost of imported energy from the grid, and the sale price of electricity to the grid.

In order to provide for this requirement, a `NewsegsModel` is a container holding an instance of the first two calculation modules, and an instance of the consumption/storage joint calculation module, whilst providing an interface for access to environmental data.

#### Grid Module

- Requires: Wider environmental data
- Provides: Relative price of energy for input to or export from the site; Calls for bids for market participation; Indicators for grid access constraints.

The grid module represents the dynamics of the wider electricity supply; in particular, providing relative pricing signals for import and export, and signalling for participation in balancing markets. It is assumed to be dependent only on wider environmental conditions influencing the magnitude and location of power flows over the GB electrical transmission network and the consequent constraints at grid supply points; i.e. the site as a point load or generator is assumed to have no influence over the bulk electricity trading conditions.

Due to this constraining assumption, the grid module may be run in isolation of the other calculation modules and forms the head of the calculation chain.

Grid modules MAY be used to indicate dynamic network access constraints, e.g. indicating congestion at the local primary substation requiring a reduction in export capacity from the site. This information may be used by the generation module to constrain generator performance. This would be undertaken under the assumption that such constraints would be necessary regardless of on-site demand for grid safety; i.e. should the export capacity of the site be limited to 100 kVA, then the sum of generation and storage export power for the site should be dynamically configured to not exceed this in the case of a sudden (faulted) disconnection of the onsite load.

#### Generation Module

- Requires: Local environmental data, (Optional) Grid module results
- Provides: Electrical energy passing over various points on the local electrical grid, e.g. net export to the local microgrid grid within a timestep.

The generation module represents non-dispatchable generation on the local microgrid. This generation is assumed non-dispatchable beyond pre-defined respondent to model time, local environmental conditions, and local grid conditions. It is not necessary that all generators be responsive to all of these inputs, and operation without indicator of local grid condition should be possible (i.e. under the assumption of no dynamic constraint on import/export capacity).

Due to the optional use of Grid module results, this module should be run second; however, in many cases, the results may be independent of the Grid module and would not be made invalid by changes to the configuration of the Grid module.

#### Consumption Module

- Requires: Local environmental data, (Optional) Grid module results, (Optional) Generation module results, (Optional) Storage module results-to-date (Optional).
- Provides: Electrical energy demand by end consumers.

The consumption module represents residential electrical demand (including for space and water heating) on the local microgrid. This demand is assumed to be impacted by model time including time of year, day of week, holiday status, and daylight savings time. It is also assumed to be impacted by local environmental conditions; in particular, the local air temperature and solar irradiation; the first of which may impact space heating demand and the latter both space heating and lighting demand.

In some consumption modules, aspects of consumption may be deferred in time in response to demand-side management measures. Indication that these measures may be of value may be provided from the Grid module, the Generation module, or the Storage module. As such, the Consumption module should be run after the Grid and Generation module, and simultaneously with the Storage module.

##### Storage Module

- Requires: (Optional) Grid module results, Generation module results, Storage module results-to-date.
- Provides: Electrical energy import and export over site boundary; Electrical energy in storage; Electrical energy losses through storage.

The storage module represents the storage of electrical energy on site and its charging and dispatch. A typical application might be a site-scale battery energy storage system (BESS). It may be controlled considerate of the following parameters:
    - Model time
    - Current relative price of site electricity import/export (provided by Grid module)
    - Forecast relative price of site electricity import/export (provided by Grid module)
    - Current on-site generation status (provided by Generation module)
    - Forecast on-site generation status (provided by Generation module)
    - Current on-site consumption rates (provided by Consumption module)
    - Forecast on-site consumption rates (provided by Consumption module)

It provides the rate and quantity of electrical import and export over meters around the site; in particular, the point of common coupling with the local distribution network. In a simple controller configuration, the storage module may be set to always charge at a rate equal to the net generation of site electricity after removal of on-site consumption and discharge at a rate equal to the net consumption of site electricity after removal of on-site generation, until saturation of the available storage capacity. More complex strategies may involve import of electricity during periods of low variable pricing and export during periods of high export pricing.

As the control logic for the storage may be dependent upon the state of all of the other computational modules, it must be run subsequent to the Grid and Generation modules and simultaneously with the Consumption module. 


## Dash interface

The NewSEGS modelled may be accessed via a [Plotly Dash](https://dash.plotly.com/) interface. This multi-page app allows for configuration of multiple models, evaluation at fixed values, and both univariate and multivariate sensitivity analysis.

### The app callback chain

The app uses "Routing callback inputs" to transfer data between pages in the same session, and so allow the app to restore model states as the page is built. There are three `Store` variables which are transferred between the pages:

1. `selected-model` - A string holding the selected model type (e.g. `"sprake"`), used to determine which models are spawned by the app, and which interface is built.
2. `store-selected-configuration` - A json dictionary containing a reference to the current `NewsegsMetaModel` that is in focus; i.e. the one to which active input changes are being applied and from which focussed results are being shown. The dictionary also contains references to the `NewsegsModel` and `NewsegsFinance` that are held by the MetaModel, for convenience of access.
3. `store-configurations` - A json list of dictionaries, where each dictionary is a configuration as above.

When the app is first launched, the `model_selection_layout` (`newsegsbrowser.layouts.model_selection_layout.model_selection_layout`) is served. This is a static layout containing large buttons of id `{'type': 'btn-model-type-selector', 'label': ...}`.

A callback is assigned to watch buttons of this `id` `type` (`newsegsbrowser.callbacks.model_selection_callbacks.update_model_type`). When clicked, the `selected-model` is set to the `label` value of the button and the url is set to the `/{selected-model}/landing` page of the site. The app handles these page navigations by stripping out the `selected-model` from the url, and generating an appropriate form of the page layout when using that model.

For the live model pages, one of the last items added is a `div` with `id = {'type': 'onload-div', ...}`. This div serves the function of driving callbacks on page load; in particular the clientsite callback `attach_drawer` to enable the javascript behaviour of the results drawer, and the triggering of any `id = {'type': 'firstload-config-watcher', ...}`s with a simple data update of a string containing the current timestamp. Both of these callback functions are attached by `newsegsbrowser.callbacks.model_configuration_callbacks.add_initial_callbacks`

Any `firstload-config-watcher` stores that have been created are monitored by the `sync_config` callback function. This function handles changes in:

- The `firstload-config-watcher` (i.e. a change of page)
- `store-selected-configuration` (i.e. a change of focussed MetaModel)
- `store-configurations` (i.e. a change of other MetaModels)

These latter two `Store`s are "Routing callback inputs" and so are held by the app, rather than individual page layouts, and are universal to all pages.

The purpose of the `sync_config` function is primarily to update the page layout to correspond to the currently active configuration(s). It secondary purpose is to generate a new MetaModel if there are none corresponding to the app instance, set that to the selected configuration, and then update the page layout. Its primary purpose is accomplished by replacing the contents of divs with `id = {'type': 'input-container', ...}`

MetaModels are modified by one of several events.

- The changing of an input field, leading to a callback which results in a parameter update to a Variable within the MetaModel
- The running of the Model or Finance associated with the MetaModel.
- The loading of a MetaModel from an external source.
- The duplication of a MetaModel
- The deletion of a MetaModel



## Licence
This software is available under the [MIT License](LICENCE).
