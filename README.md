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

The NewSEGS model consists of four modules

- **Module 1 - Generation**
- **Module 2 - Grid**
- **Module 3 - Consumption**
- **Module 4 - Storage**

These four modules must be defined for a coincident time period, as one of the key considerations of the model is that short-term local environmental conditions determine the value of both generation and consumption, and may impact storage performance; correlated wider environmental conditions determine the cost of imported energy from the grid, and the sale price of electricity to the grid.

As such, wrapping these four modules is an overall Model configuration, which includes access to environmental data.

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
