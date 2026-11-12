## The Sprake Location-Aware Energy Model

This energy model is derived from the one developed by Dr David Sprake in support of his PhD thesis "Large Housing Estates of the Future and the use of Smart Grids, Renewables and Storage to Meet 2050 Carbon Reduction Targets" [2023](https://wrexham.ac.uk/staff-profiles/david-sprake/).

The model adheres to the general NewSEGS structure; however, there are some notable simplifications:

- The wider environment server, providing weather conditions impacting the wider price of electricity, is not used. This restricts the model to scenarios where the price of imported and exported grid energy is not dependent on the weather.

- The Grid module is not used at all. Due to the simple pricing assumptions for import/export electricity and simple storage charge and dispatch rules, there is no requirement for pricing signals from the wider grid.

- Generated electricity is consumed by site consumers before it can influence the control strategy of the storage unit. Due to the single, simple storage charge and dispatch algorithm in use, this is adequate, as the only signal required by the storage unit for control is the quantity of over/under production, and not the absolute rate of production or any price signalling from the Grid module.

### Key information

#### Model Type

The Generation Module is a discrete-time hindcasting power generation model, using historical weather data to estimate mean power production over 60 minute intervals.

The Consumption and Storage Module is a discrete-time top-down aggregated demand model with an idealised energy storage unit capable of storing or dispatching residual net energy over a 60 minute timestep.

The time horizon of the model is 10 years.

#### Generation Module

Generation occurs at two point generators 

- A point Wind Energy Converter at 15 m hub height.
- A point south-facing PV array pitched at 35° from horizontal.

These point generators are assumed able to scale arbitrarily with proportional energy yield increases.

#### Consumption and Storage Module

Consumption modelling consists of scaling four aggregated demand profiles:

- Domestic hot water demand.
- Space heating demand.
- Other (appliance) demand.
- Electric Vehicle charging demand.
