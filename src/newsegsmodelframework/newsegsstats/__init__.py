"""Statistics of the results of NewSEGS Energy Models: aggregate properties of meter data.

Nothing is imported here: use the modules directly.

Modules:
    core: Functions used by several of the procedures (indexing of timeseries by day, month, season...).
    agg_meters_daily: Sum meters to daily totals.
    basic_summary_stats: Summary statistics of generation or consumption.
    categorise_meter: Categorise energy timeseries by fractions of nominal capacity.
    locate_timeseries_extrema: Find the occurrence of the maximum and minimum values in a timeseries.
    seasonal_statistics: Summarise meter data by season.
    self_consumption: Summarise self-consumption.
    time_in_range: Time spent by meter readings within ranges.
    dirichlet: Fit a Dirichlet distribution to observed data.
"""
