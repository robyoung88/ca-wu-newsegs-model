# The NewSEGS Model

## Introduction

The North Wales Social Housing Newbuild on-Site Energy Generation and Storage (NewSEGS) project aims to identify and optimise opportunities for self-supply of renewable energy in newbuild social housing in North Wales.

The NewSEGS-modelling project builds on the work of Dr David Sprake to produce estimates of the financial performance of a local energy system.

## Model Concept

![Model diagram](metamodel-block-diagram-bw.svg)
*NewsegsMetamodel conceptual diagram*

A **metamodel** combines an **energy model** (generation, grid, and consumption and storage
modules acting on a site's environment) with a **finance model** and a set of **variables** that
characterise the uncertainty in the model's parameters. Metamodels are collected in a **project**.
A metamodel can be run deterministically, or analysed with deterministic (DSA) or probabilistic
(PSA) sensitivity analysis and optimisation.

## Software structure

The software is split into four groups of Python packages (all under `src/`):

| Package | Purpose | Documentation |
|---|---|---|
| `newsegsmodelframework` | The modelling framework: models, modules, finance, variables, metamodels, projects, sensitivity analysis and statistics. Has no dependency on the web app. | [Framework](framework/index.md) |
| `newsegsmodelapp` | The [Dash](https://dash.plotly.com) web application, the database it relies upon and the background workers that run the models. Depends on the framework. | [Application](app/index.md) |
| `newsegsmodelutils` | What the framework and the application share but neither owns: at present, the functions that draw figures from the framework's data. Uses the framework, but not the app. | [Plotting utilities](support/utils.md) |
| `newa`, `admdspenmw`, `config` | Supporting packages: New European Wind Atlas access, After Diversity Maximum Demand calculation and application settings. | [Supporting packages](support/newa.md) |

Both the framework and the application are extended by **plugins**: the framework with new
[project types](framework/plugins.md), and the application with new
[pages and models](app/plugins.md). See [Architecture](architecture.md) for how the pieces fit
together.

## Where to start

* To use the app: [User guide](user-guide.md).
* To understand how the pieces fit together: [Architecture](architecture.md).
* To add a new kind of model: [Framework plugins](framework/plugins.md), then [Application plugins](app/plugins.md).
* To understand what is stored by the app: [Database](app/database.md).
