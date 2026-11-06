# Finance model

The NewSEGS Finance model (Finance) transforms the configuration and results of a previously `run` NewSEGS Energy Model into financial values and statistics relevant to comparing the performance of NewSEGS schemes from the perspective of a System Owner (SO).

## Perspectives

There are a number of perspectives that can be considered for cost-benefit analysis (CBA) of a NewSEGS scheme.

### System Owner

The System Owner (SO) perspective encapsulates the generation, storage, distribution, metering, energy purchase and resale aspects of the scheme and is conceptually easy to value, as the majority of aspects have a direct monetary cost and the majority of benefits are also direct.

**Costs**

- Generation
    - One-off costs of planning
    - Capital cost of equipment
    - One-off or ongoing costs of site leases
    - One-off costs of installation and commissioning
    - Ongoing costs of operation and maintenance
    - Periodic costs of replacement or decomissioning
    - One-off costs of environmental impact mitigation
    - Ongoing costs of environmental impact mitigation
- Storage
    - One-off costs of planning
    - Capital cost of equipment
    - One-off or ongoing costs of site leases
    - One-off costs of installation and commissioning
    - Ongoing costs of operation and maintenance
    - Periodic costs of replacement or decomissioning
    - One-off costs of environmental impact mitigation
    - Ongoing costs of environmental impact mitigation
- Distribution
    - One-off costs of planning
    - Capital cost of equipment
    - One-off costs of installation and commissioning
    - Ongoing costs of operation and maintenance
    - Periodic costs of replacement or decomissioning
    - One-off costs of environmental impact mitigation
    - Ongoing costs of environmental impact mitigation
- Metering and Billing
    - Capital cost of equipment
    - One-off costs of installation and commissioning
    - Ongoing costs of operation and maintenance
    - Periodic costs of replacement
    - Ongoing costs of meter reading and billing
    - Ongoing costs of customer service
- Electricity purchase
    - One-off costs of site connection planning
    - One-off costs of site connection installation and commissioning
    - Periodic cost of access to supply
    - Variable periodic cost of electricity consumed
    - Variable periodic cost of power factor compensation
    - Periodic cost of contract (re)negotiation
- Electricity market participation
    - One-off costs to enrol in relevant markets
    - Periodic cost to administer market participation and control storage charging/dispatch

**Benefits**
- Residential sales
    - Periodic revenue from fixed (standing) charges
    - Periodic variable revenue per unit electricity sold
- Export sales
    - Periodic variable revenue per unit electricity sold
    - Periodic variable revenue per unit capacity provided (capacity markets)
- Residuals
    - Value of generation equipment
    - Value of storage equipment
    - Value of distribution equipment
    - Value of metering equipment
- Grants
    - Grants for installation of renewables on social housing

The quantity of residential sales is not necessarily fixed for a site under fixed environmental conditions; there may exist "rebound" effects tending to increase the quantity of electrical energy units used in response to a decrease in unit price or perceived reduction in environmental cost for each unit produced. These effects may be nonlinear, time-varying and subject to saturation points; e.g. resident behaviour changing to demand a higher mean internal temperature of their household in response to lower energy prices will have a hard threshold at a temperature beyond which any increases would become uncomfortable, and a soft threshold at a temperature beyond which any increases have no effect on comfort (i.e. the bounds of the "Goldilocks zone"). Changes in residential consumer behaviour will almost always result in a change to the marginal price of electricity supplied, as the proportion of imported versus on-site generated energy, and the quantity of energy available for export, will vary, even if the generation and storage scheme is varied proportionally due to the variable nature of the generation resource and the non-uniform application of the demand rebound.

The rebound effect, whilst being complex, is capable of representation within the NewSEGS model.

### Resident

The Resident perspective considers only the consumption of electricity within the site. It does not encompass other costs of accommodation, including rent, as there is not a feasible mechanism whereby benefits accrued by the SO can be translated directly into rent corrections; i.e. all other costs are assumed fixed.

The primary benefit of a NewSEGS scheme to a resident is the supply of electrical energy. Under the assumptions of this model, this supply is invariant regardless of generation and storage composition or electricity market participation. In addition, it is assumed that there is no impact on any other benefit to the residential consumer, such as:

- Reliability of supply.
- Efficacy and flexibility of billing and payment.
- Provision of customer service.
- Ethical benefits from participation in a community-level low-carbon energy project.
   
Therefore CBA from the resident perspective cannot be fully defined and is a simple problem of cost minimisation, which may be achieved through two vectors:

- Reduction in residential demand
- Reduction in fixed and/or variable costs of supply

Reduction in demand can itself be achieved through changes to multiple factors, such as:

- Behavioural (i.e. energy intensity of occupation)
- Occupational (i.e. quantity of building-time occupied)
- Appliance (i.e. reduction of energy intensity of tasks through equipment)
- Building fabric (i.e. reduction of energy intensity of occupation through reduced heat loss/gain)

At least a proportion of all of these factors can be influenced by actions of the Landlord; however, the costs incurred by such action at not encapsulated within the Resident perspective. The costs of Resident actions to reduce demand are considered out of scope for the NewSEGS model, though they may have an impact on the marginal cost of electricity under a NewSEGS scheme, which may be reflected in the price of electricity to the residents after mediation by the SO. As these actions are not costed, from the Resident perspective within this model, demand modifying changes cannot be considered part of any optimisation problem.

Reduction in fixed and/or variable costs of supply are determined by the pricing structure and valuation of supply from the SO. Dependent on the financial requirements of the SO, these may be more or less decoupled from the marginal cost of supply to the SO; however, in the limit of minimum cost to the resident, price will be set to cover this cost only.

Therefore, within this model, optimisation of the NewSEGS system for cost minimisation to the resident requires minimisation of the cost to the SO of supply to residents. The problem is therefore best tackled from the SO perspective. After optimisation and assuming no further price-responsive changes in demand, the final cost to residents can be determined by choosing price values that satisfy the minimum financial requirements of the SO.

### Landlord

The Landlord perspective considers the costs and benefits associated with the building assets and rent. The Landlord may also be SO, but even if they are not, the value of the NewSEGS scheme to the SO might be expected (under ideal competitive scenarios) to be reflected as a benefit to the Landlord through the price of compensation to the landlord; e.g. the price of the lease for generation siting.

Registered Social Landlords (RSLs) do not operate within an idealised competitive environment. Rent cannot increase and decrease in response to resident competition for residences, demand exceeds supply such that less desirable residences are not less valuable due to lower occupancy, and geography is not a commodity, so it is impossible to consider residences fully exchangeable. As such, it is a challenge to incorporate the Landlord perspective in a CBA without making substantial assumptions.

**Costs**

- Buildings
    - One-off cost of materials for construction
    - One-off cost of labour for construction
    - Ongoing cost of maintenance
- Appliances
    - One-off cost for purchase
    - Ongoing cost of maintenance
    - Periodic cost of replacement
- Administration
    - Ongoing cost of support of residents interacting with NewSEGS

**Benefits**

- NewSEGS value
    - Via lease or directly from net revenue
- Rent
    - Successfully paid rent (not modelled)
- Grants
    - Grants for energy-efficient building

The quantity of successfully paid rent might be considered to be influenced by several factors:

- Resident income
- Resident cost of living (including energy costs)
- Occupancy (number of units, proportion of units occupied - itself dependent upon demand level for property types in a location, and the turn-around time for a property which may partially depend on its ease of maintenance)

This model is principally concerned with the second factor, though the potential impact of any modelled technologies on the third should be considered. Reductions to the resident cost of living may be achieved by improvements to the building fabric or appliances (at cost to the landlord) or lower pricing of electricity supply, which may be achieved by lowering the marginal cost of supply, or reduction in the operating margin of the supplier and thus profitability of the SO.

However, the response of the proportion of rent successfully paid is expected to be highly non-linear in response to changes in the cost of energy at an individual household level, with a strong threshold effect between the rent being considered "affordable" and "not affordable". The impact of the NewSEGS scheme on the quantity of successfully paid rent is not modelled.

In the absence of this dependent variable, the only aspects determining the financial performance of the NewSEGS scheme from the perspective of the Landlord are the costs of building, the profitability of the SO, and any grants that might be incurred.

Less efficient buildings with higher energy requirements will tend to scale the profitability of a NewSEGS scheme to a SO provided that there is space available, grid access, and regulatory permission for sufficient generation and storage; i.e. if a small scheme is already profitable, then provision of a greater quantity of electricity to demand within that captive market will increase profitability. This may not always be true if the demand increases occurs disproportionately at times when the generation/storage system is not providing energy or if generator or storage cost does not increase linearly, but may be considered an approximate rule-of-thumb.

Therefore, it can be seen that under this framework, the Landlord perspective contains a perverse incentive to lower building costs by decreasing the energy efficiency of the buildings, which is then subject to a positive reinforcement by increasing value to the SO (and therefore the landlord) of supply of a greater number of units of electricity to residents. The effect of this on residents does not feed through to the Landlord under the present assumptions.

Even if they were, due to the expected nonlinearity in the rent payment response, an optimal system from the Landlord point of view would be one in which all tenants were spending their individual maximum possible amount on rent and energy.

It should therefore be considered that there are other non-monetary incentives and benefits to lowering the cost of living for tenants, not least the social obligations of a RSL.

To avoid these perverse incentives, the Landlord perspective is not to be considered a traditional Benefits-Cost opimisation problem. Rather, an appropriate problem to solve would be:

>  "What is the most cost-effective way for a Landlord to achieve a specified cost of energy for its tenants?"

As an example, a target level of affordability may be to consider buildings constructed to Passivhaus standard being supplied by regulated domestic electricity suppliers on standard tariffs. If the Landlord was to instead construct to a lower insulation standard, then tenants would be subject to higher energy costs, but a NewSEGS scheme could be used to supply electricity at a rate low enough to negate the difference. A cost-effective NewSEGS scheme at this rate would be self-sufficient and could attract funding if presented to a suitable SO; if not cost-effective, then the Landlord would have to part-fund the scheme, returning their costs towards or above the level of building to the higher insulation standard, in order to maintain the same level of energy affordability for their tenants.

#### Example of resident affordability threshold analysis

*Please note that these numbers are indicative only, using a generic site composition and resource profile*.

Consider a site of 50 units, with mean GFA of 90 m² and mean heat loss parameter (HLP) of 0.3 W/m²/K. Over ten years, it is estimated by the model that these consume 3,463,550 units of electricity at a cost of £1,101,755 from registered domestic suppliers. There is no generation or storage on site.

If instead the units were built to a HLP of 0.8 W/m²/K, the consumption would increase to 4,718,337 units and costs would increase by 36% to £1,500,900. By applying a discount of 26.5% (i.e 1 - 1,101,755/1,500,900) to electricity sold on site, costs to residents will return to £1,101,755, but the SO would have to cover that cost - assuming that the discount also applies to EV charging prices, then the undiscounted NPV to the SO decreases to -£410,312.

From a simple financial perspective to this limited ten-year horizon, if the money saved by the Landlord by building to the 0.8 HLP standard instead of the 0.3 standard exceeds £8,206 per unit, then they could take that money, fund the SO to make-up the difference in energy bills, and still be in profit; however, after the ten years have expired, they still have lower standard housing stock, and their tenants will continue to require subsidy to keep energy bills at the existing level.

A more sustainable alternative would be to invest in self-generation instead; investment in a 300 kWp solar array and 466 kWh BESS might increase the NPV to -£128,283, reducing the necessary subsidy to £2,566 per housing unit over the first ten years, assuming that the Landlord receives full SO benefits. However, this relatively high NPV does come at the expense of increased capital expenditure - approximately £480,000 for the generators and BESS (the majority of which for the PV generators, which would cover only 17.5% of winter consumption, but 94.5% of summer consumption), or £9,600 per housing unit; a higher lump-sum than the £8,206 spread out over ten years required for the without-NewSEGS project, and still requiring £2,566 per housing unit over ten years additional subsidy.

As a general rule for renewable energy generators, once installed, it is cost-effective to keep them running until maintenance costs become prohibitive, as the economics of them are dominated by the up-front cost and the marginal cost of generation is virtually nil. Therefore, up to the lifespan of the generator, increases in financial time horizon will tend to increase the NPV of a generation project. "Subsidy" of supply with active generation may therefore be considered just another aspect of project finance from this perspective, provided that a positive NPV occurs when considering a horizon of the project lifetime. Sale of electricity at heavy discount can occur, even if that electricity has had to be purchased at a higher rate, under the assumption that future profits will recoup these losses. For this reason, the system is sensitive to assumptions regarding discounting the future value of benefits or costs.

The low marginal cost of generation suggests that almost any level of price discount could be sustained provided that the equipment lasts long enough and maintenance is cheap enough. If the sale price to residents drops below the sale price to the grid, then this does not necessarily imply any great change in the system control strategy - the SO will incur large losses whenever it has to import electricity to sell at the heavily reduced rate, and so self-consumption is always preferred.

Practically, however, the limited lifespan of project assets and the dimishing future value of money does impose a relatively high limit on the lowest possible price for supply under a NewSEGS scheme.

Under the assumption that PV may be installed at a rate of £1,365 / kWp (see the initial site report and [Department for Energy Security and Net Zero](https://www.gov.uk/government/statistics/solar-pv-cost-data)) with ongoing costs 1% of initial costs per year and a mean capacity factor of 12% over a lifetime of 25 years and ignoring inverter replacement, the mean sale price of electricity could not be below £0.06493 for break-even; with a 3.5% discount rate, this increases to £0.08911. If requiring pay-back within 10 years, a mean price of £0.1428 is required, or £0.1638 with 3.5% discounting for both costs and benefits. These latter numbers are substantially greater than the expected sale rate for site exports, making storage particularly valuable for PV as peak production rarely occurs with peak consumption.

For small/medium scale wind, assuming a cost of £5,400 per kW of installed capacity (see the initial site report and [Energy Saving Trust 2024](https://energysavingtrust.org.uk/advice/wind-turbines/)) with ongoing costs 4% of initial costs per year and a mean capacity factor of 25% over a lifetime of 25 years, the mean sale price of electricity could not be below £0.1973 / kWh for break-even, and with a 3.5% discount on both costs and benefits, this increases to £0.2432 / kWh, higher than the target residential price in our HLP = 0.8 example. Under a 10 year horizon, payback requires £0.3452 / kWh, or £0.3851 / kWh with discounting at 3.5%. This is substantially higher than the price of electricity available from public supply; even with perfect storage capable of ensuring that all wind generation was consumed on site (by default, a higher proportion than PV due to the correlation of generation and load, but still imperfect) it would not have achieved payback within ten years if selling with *no* discount to the residents.

What this implies from the Landlord perspective is that trading between energy efficiency and NewSEGS project value is not unlimited or without compromise.

- High insulation, no NewSEGS:
    - Higher one-off costs to Landlord for building.
    - Low level of consumption by residents, but high per-unit cost, resulting in moderate energy costs. Asymptotic lower limit to consumption due to appliance, hot water, lighting use.
    - No one-off costs for SO for generation/storage construction.
    - No ongoing costs for SO.
    - High residual value of building due to fabric quality.
    - No residual value of NewSEGS.
- Low insulation, no NewSEGS:
    - Lower one-off costs to Landlord for building
    - High level of consumption by residents, but moderated per-unit cost, financed by savings from building but with no long-term recovery mechanism and with potential to exceed savings.
    - No one-off costs for SO for generation/storage construction.
    - No ongoing costs for SO.
    - Low residual value of building due to fabric quality.
    - No residual value of NewSEGS. 
- Low insulation, NewSEGS:
    - Lower one-off costs to Landlord for building
    - High level of consumption by residents, but moderated per-unit cost. Dependent on relative savings from building and one-off costs from NewSEGS (if SO), moderated cost may be part-funded by savings or additional finance. Long-term recovery by sale of generated electricity, limited by lifespan of generation equipment and required level of tariff. Buildings will require several generations of NewSEGS equipment over lifespan.
    - High one-off costs for SO for generation/storage construction.
    - Ongoing costs for SO
    - Low residual value of building due to fabric quality.
    - Residual value of NewSEGS up to lifespan of project.
- High insulation, NewSEGS:
    - High one-off costs to Landlord for building
    - Low level of consumption by residents, lightly moderated per-unit cost.
    - High one-off costs for SO for generation/storage construction.
    - Ongoing costs for SO
    - High residual value of building due to fabric quality.
    - Residual value of NewSEGS up to lifespan of project.

It should also be considered that, in the case of a separate Landlord and SO, the enticement for the SO to participate in the more heavily subsidised schemes is weaker. It is envisaged that in these scenarios, the SO is offered the opportunity to lease generation and storage sites and access the private wire network in order to supply the residents of the scheme, under obligation to price energy supplied at a discount relative to other suppliers, as necessary to meet the resident affordability criterion and therefore higher in less-efficient buildings. As demonstrated above, the higher the discount, the longer the payback period for generation equipment. Once all costs to the SO are considered and after considering the number of units required to be imported, it may be economically unattractive or even infeasible for the SO to undertake the project without some additional funding (i.e. from the Landlord, sourced from savings made in the building fabric, potentially even after waiving any lease fees).

## Provisions

A Finance Model provides the following values, both undiscounted and after application of a cost or benefit discount rate:

- Timeseries:
    - Resident receipts
    - EV charging receipts
    - Exported electricity receipts
    - All receipts
    - Import costs
    - Generation O&M costs
    - Storage O&M costs
    - Billing O&M costs
    - Other O&M costs
    - Generation Capex
    - Storage Capex
    - Distribution Capex
    - Metering Capex
    - Other Capex
    - All Capex
    - All costs
- Present Values:
    - Total benefits
    - Total costs
    - Benefit:Cost ratio
    - Net Present Value
- Other statistics:
    - Simple payback time
