import os
import itertools
import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import seaborn as sns

from newa import get_newa_micro_point, get_newa_meso_ts_point
from scipy.stats import weibull_min
from config import settings

_bearing_names = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
_bearing_max_angle = np.arange(len(_bearing_names)) * 360.0 / len(_bearing_names) + 0.5 * (360.0 / len(_bearing_names))
BEARING_DICT = dict(zip(_bearing_names,_bearing_max_angle))
_WS_BINS = [0,1,2,3,4,5,10,15,20,25,30,50]

BEARING_POLAR_ANGLES = (pd.DataFrame.from_dict(BEARING_DICT,
                                               orient='index',
                                               columns=['max_angle'])
                        .assign(theta=lambda df:2.*np.pi*(df['max_angle']-df['max_angle'].min())/360.0)
                        .reset_index()
                        .rename(columns={'index':'bearing_cat'})
                        .loc[:,['bearing_cat','theta']]
                        )

#wind_res_dir = settings.get('SiteResourceWindDirectory')

# 15 m height for 6kW (e.g. SD6) or 12 kW (e.g. SD12) turbine
# 35 m height for 50 - 250 kW (e.g. Norvento nED 100)
EVAL_HEIGHTS = [15, 35]

def get_cp(file_name):
    cp_file = pd.read_excel(file_name)
    def interpolant(x):
        return np.interp(x, cp_file['wind_speed'], cp_file['coeff_power'], left=0.0, right=0.0)
    return interpolant

#_cp_small = get_cp(os.path.join('data','power-curve-proven-6.xlsx'))
#_cp_med = get_cp(os.path.join('data','power-curve-ned-100.xlsx'))

#CPS = (_cp_small, _cp_med)

def bearing_to_category(bearings,
                        categories=BEARING_DICT,
                        offset=None):
    if offset is None:
        offset = (360.0 / len(categories)) / 2.0
    
    b = (bearings + 360.0 + offset)%360.0 
    o = np.zeros_like(b, dtype=str)
    for cat, max_angle in reversed(categories.items()):
        ma = max_angle + offset
        o = np.where(b < ma, cat, o)
    o = pd.Categorical(o,categories=list(categories.keys()),ordered=True)
    return o

def expand_grid(data_dict):
    rows = itertools.product(*data_dict.values())
    return pd.DataFrame.from_records(rows, columns=data_dict.keys())

def get_alpha_distribution(newa_meso_data):
    """Get the value of the Prandtl log-law scaling parameter from NEWA mesoscale data"""
    z_ref = newa_meso_data.height.unique()
    assert len(z_ref) == 1, "Please provide only a single wind speed height in NEWA data"
    z_ref = z_ref[0]

    # Remove unstable atmospheres, leaving neutral and stable
    idf = newa_meso_data.query('inverse_obukhov_length >= 0.0')

    # Categorise wind speed and direction
    idf = (
        idf
        .assign(
            wd_10_cat=lambda df: bearing_to_category(df['wind_from_direction_10m']),
            ws_10_cat=lambda df: pd.cut(df['wind_speed_10m'], _WS_BINS)
        )
    )

    # Calculate alpha
    denom = np.log(z_ref) - np.log(10.0)
    idf = (
        idf
        .assign(
            alpha = lambda df: (np.log(df['wind_speed']) - np.log(df['wind_speed_10m']))/denom
        )
    )
    
    o1 = idf.groupby(['wd_10_cat','ws_10_cat'])['alpha'].mean()

    all_cats = expand_grid({'wd_10_cat':BEARING_DICT.keys(),
                            'ws_10_cat':pd.cut([], _WS_BINS).categories})
    o2 = (
        pd.merge(
            all_cats,
            o1,
            on=['wd_10_cat','ws_10_cat'],
            how='left'
        )
        .ffill()
        .set_index(['wd_10_cat','ws_10_cat'])
    )

    return o2

def get_alphas(wd_10, ws_10, alpha_dist):
    idf = (
        pd.DataFrame({
            'wd_10': wd_10,
            'ws_10': ws_10
            })
        .assign(
            wd_10_cat=lambda df: bearing_to_category(df['wd_10']),
            ws_10_cat=lambda df: pd.cut(df['ws_10'], _WS_BINS)
        )
    )

    return (idf.set_index(['wd_10_cat','ws_10_cat']).join(alpha_dist)['alpha'].values)

def get_wind_at_site(lat, lon,
                     rng,
                     meso_reference_height=50,
                     micro_reference_height=50,
                     dt_start='2005-01-01T00:00:00',
                     dt_stop='2022-12-31T23:30:00',
                     site_heights = EVAL_HEIGHTS,
                     #site_cps = CPS,
                     return_working = False
                     ):
    
    meso_data = get_newa_meso_ts_point(lat, lon,
                                       height=meso_reference_height, 
                                       dt_start=dt_start, 
                                       dt_stop=dt_stop,
                                       variables=['wind_speed',
                                                  'wind_from_direction_10m',
                                                  'wind_speed_10m',
                                                  'inverse_obukhov_length'])
    
    alpha_dist = get_alpha_distribution(meso_data)

    micro_data = get_newa_micro_point(lat, lon,
                                      height=micro_reference_height,
                                      variables=['weib_A_combined',
                                                 'weib_k_combined',
                                                 'air_dens'])
    
    rho = micro_data['air_dens'].values[0]

    # Our reference wind time series is the mesoscale at ref height.
    ref_ts = meso_data.loc[:,['time','wind_speed','wind_speed_10m','wind_from_direction_10m']]

    # First, let's sort the wind speeds, as will need to do so regardless
    ref_ts = (
        ref_ts
        .sample(frac=1,random_state=rng)
        .sort_values('wind_speed')
    )

    # Determine Weibull parameters for this ts
    # Now get the reference Weibull parameters
    ws_ref_wb_pars = weibull_min.fit(ref_ts['wind_speed'],floc=0.0)
    ws_ref_wb_pars = dict(zip(('c','loc','scale'), ws_ref_wb_pars))
    # Based on this, we can find the empirical maximum value of the CDF achieved
    max_cdf = weibull_min.cdf(x=ref_ts['wind_speed'].max(),**ws_ref_wb_pars)

    # Generate the wind speeds across the probability distribution at micro reference height
    ws_site_ref = weibull_min.ppf(q=np.linspace(0,max_cdf,len(ref_ts)),
                                  c=micro_data['weib_k_combined'].values[0],
                                  loc=0.0,
                                  scale=micro_data['weib_A_combined'].values[0])
    
    # Augment ref ts with the local 50 m wind speed and the alpha parameter
    ref_ts = (
        ref_ts
        .assign(
            ws_ref_local=ws_site_ref,
            alpha=lambda df:get_alphas(df['wind_from_direction_10m'].values, df['wind_speed_10m'].values, alpha_dist)
        )
    )

    # Extrapolation function
    def get_wind_speed_at_height(z):
        return (
            ref_ts
            .copy()
            .assign(
                ws_hub = lambda df: df['ws_ref_local'] * (z / micro_reference_height) ** df['alpha'],
            )
            .sort_values('time')
            .assign(hub_height=z)
    )

    #def get_specific_wind_power_at_height(z, cp_func):
    #    return (
    #        ref_ts
    #        .copy()
    #        .assign(
    #            ws_hub = lambda df: df['ws_ref_local'] * (z / micro_reference_height) ** df['alpha'],
    #            sp_power = lambda df: 0.001 * 0.5 * rho * cp_func(df['ws_hub']) * df['ws_hub']**3
    #        )
    #        .sort_values('time')
    #        .assign(hub_height=z)
    #)

    olist = []
    for z in site_heights:
        olist.append(get_wind_speed_at_height(z))


    odata = pd.concat(olist)

    if return_working:
        return {
            'site_ts': odata,
            'ref_ts': ref_ts,
            'alpha_dist': alpha_dist,
            'micro_weibull_pars': micro_data,
            'meso_weibull_pars': ws_ref_wb_pars
        }
    else :
        return odata

WIND_ROSE_BINS = [0,3,6,9,12,18,24,50]
clrs = sns.color_palette("husl", len(WIND_ROSE_BINS)-1)
ws_cats = pd.cut([], WIND_ROSE_BINS).categories
windrose_catcols = dict(zip(ws_cats, clrs))

def draw_wind_rose(wind_speeds, wind_directions, height_agl=None, figsize=(6.5,4)):
    """Draw a landscape wind rose with legend to the right and a note box.

    Parameters
    - wind_speeds: array-like of wind speeds
    - wind_directions: array-like of wind directions (degrees)
    - height_agl: optional height above ground level (m) to report in note box
    - figsize: tuple for figure size (width, height)
    """
    idf = pd.DataFrame({
        'speed': wind_speeds,
        'direction': wind_directions
    }) \
        .assign(ws_bin = lambda df: pd.cut(df['speed'], WIND_ROSE_BINS),
                wd_bin = lambda df: bearing_to_category(df['direction']))

    mean_speed = idf['speed'].mean()

    pdf = idf.groupby(['wd_bin','ws_bin'])['speed'].agg('count')/len(idf)
    pdf = pdf.to_frame().rename(columns={'speed':'prop'}) \
        .reset_index()\
        .assign(cumprop=lambda df: df.groupby('wd_bin')['prop'].cumsum())\
        .set_index('wd_bin')\
        .join(BEARING_POLAR_ANGLES.set_index('bearing_cat'))

    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(1,3,(1,2), projection='polar')
    ax_leg = fig.add_subplot(1,3,3)
    ax_leg.axis('off')

    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)

    width = 2.0*np.pi / len(BEARING_POLAR_ANGLES)

    for cat in reversed(ws_cats):
        pdata = pdf.loc[pdf['ws_bin']==cat,:]
        if (len(pdata)>0):
            ax.bar(pdata['theta'],
                   pdata['cumprop'],
                   width=width,
                   linewidth=1,
                   edgecolor='k',
                   color=windrose_catcols[cat],
                   alpha=0.7)

    ax.set_xticks(np.linspace(0, 2*np.pi, len(BEARING_POLAR_ANGLES), endpoint=False))
    ax.set_xticklabels(BEARING_POLAR_ANGLES['bearing_cat'].values)

    ax_leg.text(0.5, 0.95, "Proportion of year with wind from direction", ha='center', va='center', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    # Build legend on the right-hand axis
    legend_patches = [Patch(facecolor=windrose_catcols[cat], edgecolor='k', label=str(cat)) for cat in ws_cats]
    ax_leg.legend(handles=legend_patches, title='Wind speed bin', frameon=False,
                  loc='center')

    # Add note box with height and mean wind speed
    note_lines = []
    if height_agl is not None:
        note_lines.append(f"Height AGL: {height_agl} m")
    note_lines.append(f"Mean wind speed: {mean_speed:.2f} m/s")
    note_text = "\n".join(note_lines)
    ax_leg.text(0.5, 0.05, note_text, ha='center', va='center', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()
    return fig

POWER_BINS = [0,0.001,0.25,0.5,0.75,0.999, 1.0]
clrs = sns.color_palette("husl", len(POWER_BINS)-1)
power_cats = pd.cut([], POWER_BINS).categories
power_cat_labels = dict(zip(power_cats,['< Cut-in',r'0%-25%',r'25%-50%',r'50%-75%',r'75%-100%','Max/Rated'] ))
power_catcols = dict(zip(power_cats, clrs))

def draw_energy_rose(wind_powers,
                     wind_directions,
                     height_agl=None, 
                     figsize=(6.5,4)):
    """Draw a landscape energy rose with legend to the right and a note box.

    Parameters
    - wind_powers: array-like of specific power per half hour
    - wind_directions: array-like of wind directions (degrees)
    - height_agl: optional height above ground level (m) to report in note box
    - figsize: tuple for figure size (width, height)
    """
    idf = pd.DataFrame({
        'power': wind_powers,
        'direction': wind_directions
    })

    max_power = idf.power.max()

    idf = idf.assign(
        norm_power = lambda df: df['power'] / max_power,
        power_bin = lambda df: pd.cut(df['norm_power'], POWER_BINS),
        wd_bin = lambda df: bearing_to_category(df['direction']),
        energy = lambda df: 0.5 * df['power'] # Assume half-hourly and in kW
        )

    n_years = len(idf) / (2 * 8760)
    total_energy = idf.energy.sum()
    ann_energy = total_energy / n_years
    
    pdf = idf.groupby(['wd_bin','power_bin'])['energy'].agg('sum')/total_energy
    pdf = pdf.to_frame().rename(columns={'energy':'prop'}) \
        .reset_index()\
        .assign(cumprop=lambda df: df.groupby('wd_bin')['prop'].cumsum())\
        .set_index('wd_bin')\
        .join(BEARING_POLAR_ANGLES.set_index('bearing_cat'))

    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(1,3,(1,2), projection='polar')
    ax_leg = fig.add_subplot(1,3,3)
    ax_leg.axis('off')

    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)

    width = 2.0*np.pi / len(BEARING_POLAR_ANGLES)

    for cat in reversed(power_cats):
        pdata = pdf.loc[pdf['power_bin']==cat,:]
        if (len(pdata)>0):
            ax.bar(pdata['theta'],
                   pdata['cumprop'],
                   width=width,
                   linewidth=1,
                   edgecolor='k',
                   color=power_catcols[cat],
                   alpha=0.7)

    ax.set_xticks(np.linspace(0, 2*np.pi, len(BEARING_POLAR_ANGLES), endpoint=False))
    ax.set_xticklabels(BEARING_POLAR_ANGLES['bearing_cat'].values)

    ax_leg.text(0.5, 0.95, "Proportion of energy from direction", ha='center', va='center', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    # Build legend on the right-hand axis
    legend_patches = [Patch(facecolor=power_catcols[cat], edgecolor='k', label=power_cat_labels[cat]) for cat in power_cats]
    ax_leg.legend(handles=legend_patches, title='Normalised power', loc='center', frameon=False)

    # Add note box with height and mean wind speed
    note_lines = []
    if height_agl is not None:
        note_lines.append(f"Height AGL: {height_agl} m")
    note_lines.append(f"Annual specific energy: {ann_energy:.2f} kWh/m²")
    note_text = "\n".join(note_lines)
    ax_leg.text(0.5, 0.05, note_text, ha='center', va='center', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()
    return fig

# Variation of wind speed with height
SOURCE_DICT = {
    'meso': 'NEWA Meso-scale',
    'micro': 'NEWA Micro-scale',
    'extrap': 'Vertically extrapolated'
}

def wind_speed_profile_box(profile_data, figsize=(6,4)):
    """Create a transposed box plot of wind speed versus height.

    - y axis is height (m)
    - x axis is speed (m/s)
    - boxes are coloured by `source` and dodged to avoid overlap.
    - legend entries are relabelled using ``SOURCE_DICT``.
    """
    # use gridspec-like spacing by reducing top margin to keep legend clear
    fig, ax = plt.subplots(figsize=figsize)
    fig.subplots_adjust(top=0.2)  # reserve upper ~1/6 for legend
    # ensure consistent ordering of sources using SOURCE_DICT keys
    hue_order = list(SOURCE_DICT.keys())
    sns.boxplot(
        data=profile_data,
        x='speed',
        y='height',
        hue='source',
        dodge=True,
        ax=ax,
        orient='h',
        showmeans=True,
        hue_order=hue_order
    )
    ax.set_ylabel('Height (m)')
    ax.invert_yaxis()
    ax.set_xlabel('Wind speed (m/s)')

    # relabel legend entries
    handles, labels = ax.get_legend_handles_labels()
    new_labels = [SOURCE_DICT.get(lbl, lbl) for lbl in labels]
    # place legend above the axes, centred, outside plot
    ax.legend(handles, new_labels, title='Source', loc='upper center',
              bbox_to_anchor=(0.5, 1.15), ncol=len(new_labels), frameon=False)

    plt.tight_layout()
    return fig