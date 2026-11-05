"""Wind roses, energy roses and wind speed profiles of a site (matplotlib and seaborn), from the wind resource helpers
of the framework (`newsegsmodelframework.util.wind_resource_helpers`).
"""
import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import seaborn as sns

from newsegsmodelframework.util.wind_resource_helpers import BEARING_POLAR_ANGLES, bearing_to_category

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