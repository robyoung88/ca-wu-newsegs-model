## The Sprake energy balance model

This energy model is derived from the one developed by Dr David Sprake in support of his PhD thesis "Large Housing Estates of the Future and the use of Smart Grids, Renewables and Storage to Meet 2050 Carbon Reduction Targets" [2023](https://wrexham.ac.uk/staff-profiles/david-sprake/).

The model adheres to the general NewSEGS structure; however, there are some notable simplifications:

- The wider environment server, providing weather conditions impacting the wider price of electricity, is not used. This restricts the model to scenarios where the price of imported and exported grid energy is not dependent on the weather.

- The Grid module is not used at all. Due to the simple pricing assumptions for import/export electricity and simple storage charge and dispatch rules, there is no requirement for pricing signals from the wider grid.

- Generated electricity is consumed by site consumers before it can influence the control strategy of the storage unit. Due to the single, simple storage charge and dispatch algorithm in use, this is adequate, as the only signal required by the storage unit for control is the quantity of over/under production, and not the absolute rate of production.

The "NewsegsMetaModel" is the encapsulation of a single model scenario, and is what the user creates and modifies. It consists of the three components:

1. The NewsegsModel itself.

2. A NewsegsFinance instance, which is a collection of functions which are applied to the energy flows predicted by the NewsegsModel in order to estimate financial costs and benefits of this energy. Its configuration consists of the fixed and ongoing per-unit prices for equipment and imported or sold energy, and the discount rates applied. Modifying these parameters is assumed not to impact the energy flows (price sensitivity is not modelled in the Sprake model, and is more generally represented by an abstract pricing signal produced by the Grid module).

3. A collection of variable Parameters. These may be fixed, but in general have systematic or probabilistic uncertainty associated with them, which may be explored on the Deterministic Sensitivity Analysis and Probabilistic Sensitivity Analysis pages, which vary these uncertain parameters and record their effect on key model outcomes.

### Subsection

Some more placeholder text.

