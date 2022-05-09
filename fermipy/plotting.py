# Licensed under a 3-clause BSD style license - see LICENSE.rst
from __future__ import absolute_import, division, print_function
import copy
import os
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patheffects as PathEffects
from matplotlib.patches import Circle, Ellipse, Rectangle
from matplotlib.colors import LogNorm, Normalize, PowerNorm
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
import matplotlib.mlab as mlab

from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import numpy as np
from scipy.stats import norm
from scipy.stats import chi2
from scipy import interpolate
from gammapy.maps import WcsNDMap, HpxNDMap, MapCoord

import fermipy
import fermipy.config
import fermipy.utils as utils
import fermipy.wcs_utils as wcs_utils
import fermipy.hpx_utils as hpx_utils
import fermipy.defaults as defaults
import fermipy.catalog as catalog
from fermipy.utils import merge_dict
from fermipy.logger import Logger
from fermipy.logger import log_level


def truncate_colormap(cmap, minval=0.0, maxval=1.0, n=256):
    """Function that extracts a subset of a colormap.
    """
    if minval is None:
        minval = 0.0
    if maxval is None:
        maxval = 0.0

    name = "%s-trunc-%.2g-%.2g" % (cmap.name, minval, maxval)
    return LinearSegmentedColormap.from_list(
        name, cmap(np.linspace(minval, maxval, n)))


def get_xerr(sed):
    delo = sed['e_ctr'] - sed['e_min']
    dehi = sed['e_max'] - sed['e_ctr']
    xerr = np.vstack((delo, dehi))
    return xerr


def make_counts_spectrum_plot(o, roi, energies, imfile, **kwargs):

    figsize = kwargs.get('figsize', (8.0, 6.0))
    weighted = kwargs.get('weighted', False)

    fig = plt.figure(figsize=figsize)

    gs = gridspec.GridSpec(2, 1, height_ratios=[1.4, 1])
    ax0 = fig.add_subplot(gs[0, 0])
    ax1 = fig.add_subplot(gs[1, 0], sharex=ax0)

    #    axes = axes_grid.Grid(fig,111,
    #                          nrows_ncols=(2,1),
    #                          axes_pad=0.05,
    #                          add_all=True)
    #    ax = axes[0]

    x = 0.5 * (energies[1:] + energies[:-1])
    xerr = 0.5 * (energies[1:] - energies[:-1])

    count_str = 'counts'
    model_counts_str = 'model_counts'
    npred_str = 'npred'

    if weighted:
        count_str += '_wt'
        model_counts_str += '_wt'
        npred_str += '_wt'

    y = o[count_str]
    ym = o[model_counts_str]

    ax0.errorbar(x, y, yerr=np.sqrt(y), xerr=xerr, color='k',
                 linestyle='None', marker='s',
                 label='Data')

    ax0.errorbar(x, ym, color='k', linestyle='-', marker='None',
                 label='Total')

    for s in sorted(roi.sources,
                    key=lambda t: t[npred_str], reverse=True)[:6]:
        ax0.errorbar(x, s[model_counts_str], linestyle='-', marker='None',
                     label=s['name'])

    for s in sorted(roi.sources,
                    key=lambda t: t[npred_str], reverse=True)[6:]:
        ax0.errorbar(x, s[model_counts_str], color='gray',
                     linestyle='-', marker='None',
                     label='__nolabel__')

    ax0.set_yscale('log')
    ax0.set_ylim(0.1, None)
    ax0.set_xlim(energies[0], energies[-1])
    ax0.legend(frameon=False, loc='best', prop={'size': 8}, ncol=2)

    ax1.errorbar(x, (y - ym) / ym, xerr=xerr, yerr=np.sqrt(y) / ym,
                 color='k', linestyle='None', marker='s',
                 label='Data')

    ax1.set_xlabel('Energy [log$_{10}$(E/MeV)]')
    ax1.set_ylabel('Fractional Residual')
    ax0.set_ylabel('Counts')

    ax1.set_ylim(-0.4, 0.4)
    ax1.axhline(0.0, color='k')

    plt.savefig(imfile)
    plt.close(fig)


def load_ds9_cmap():
    # http://tdc-www.harvard.edu/software/saoimage/saoimage.color.html
    ds9_b = {
        'red': [[0.0, 0.0, 0.0],
                [0.25, 0.0, 0.0],
                [0.50, 1.0, 1.0],
                [0.75, 1.0, 1.0],
                [1.0, 1.0, 1.0]],
        'green': [[0.0, 0.0, 0.0],
                  [0.25, 0.0, 0.0],
                  [0.50, 0.0, 0.0],
                  [0.75, 1.0, 1.0],
                  [1.0, 1.0, 1.0]],
        'blue': [[0.0, 0.0, 0.0],
                 [0.25, 1.0, 1.0],
                 [0.50, 0.0, 0.0],
                 [0.75, 0.0, 0.0],
                 [1.0, 1.0, 1.0]]
    }

    try:
        plt.cm.ds9_b = plt.cm.get_cmap('ds9_b')

    except ValueError:
        ds9_cmap=LinearSegmentedColormap(name = 'ds9_b', segmentdata = ds9_b )
        plt.register_cmap(cmap = ds9_cmap)
        plt.cm.ds9_b = plt.cm.get_cmap('ds9_b')

    return plt.cm.ds9_b


def load_bluered_cmap():
    bluered = {'red': ((0.0, 0.0, 0.0),
                       (0.5, 0.0, 0.0),
                       (1.0, 1.0, 1.0)),

               'green': ((0.0, 0.0, 0.0),
                         (1.0, 0.0, 0.0)),

               'blue': ((0.0, 0.0, 1.0),
                        (0.5, 0.0, 0.0),
                        (1.0, 0.0, 0.0))
               }

    try:
        plt.cm.bluered = plt.cm.get_cmap('bluered')

    except ValueError:
        bluered_cmap=LinearSegmentedColormap(name = 'bluered', segmentdata = bluered )
        plt.register_cmap(cmap = bluered_cmap)
        plt.cm.bluered = plt.cm.get_cmap('bluered')
    
    return plt.cm.bluered


def annotate_name(data, xy=(0.05, 0.93), **kwargs):

    if not 'name' in data:
        return

    ax = kwargs.pop('ax', plt.gca())
    ax.annotate(data['name'],
                xy=xy,
                xycoords='axes fraction', fontsize=12,
                xytext=(-5, 5), textcoords='offset points',
                ha='left', va='center')


def annotate(**kwargs):
    ax = kwargs.pop('ax', plt.gca())
    loge_bounds = kwargs.pop('loge_bounds', None)
    src = kwargs.pop('src', None)

    text = []

    if src:

        if 'ASSOC1' in src['assoc'] and src['assoc']['ASSOC1']:
            text += ['%s (%s)' % (src['name'], src['assoc']['ASSOC1'])]
        else:
            text += [src['name']]

    if loge_bounds:
        text += ['E = %.3f - %.3f GeV' % (10 ** loge_bounds[0] / 1E3,
                                          10 ** loge_bounds[1] / 1E3)]

    if not text:
        return

    ax.annotate('\n'.join(text),
                xy=(0.05, 0.93),
                xycoords='axes fraction', fontsize=12,
                xytext=(-5, 5), textcoords='offset points',
                ha='left', va='top')


def plot_markers(lon, lat, **kwargs):

    transform = kwargs.get('transform', 'icrs')
    path_effects = kwargs.get('path_effects', None)
    p = plt.gca().plot(lon, lat,
                       marker=kwargs.get('marker', '+'),
                       color=kwargs.get('color', 'w'),
                       label=kwargs.get('label', '__nolabel__'),
                       linestyle='None',
                       transform=plt.gca().get_transform(transform))

    if path_effects:
        plt.setp(p, path_effects=path_effects)


def plot_error_ellipse(fit, xy, cdelt, **kwargs):

    ax = kwargs.pop('ax', plt.gca())
    colname = kwargs.pop('colname', 'r68')
    color = kwargs.pop('color', 'k')
    sigma = fit['pos_err']
    sigmax = fit['pos_err_semimajor']
    sigmay = fit['pos_err_semiminor']
    theta = fit['pos_angle']
    radius = fit[colname]
    e0 = Ellipse(xy=(float(xy[0]), float(xy[1])),
                 width=2.0 * sigmax / cdelt[0] * radius / sigma,
                 height=2.0 * sigmay / cdelt[1] * radius / sigma,
                 angle=-theta,
                 facecolor='None', **kwargs)
    ax.add_artist(e0)


class ImagePlotter(object):

    def __init__(self, img, mapping=None):

        if isinstance(img, WcsNDMap):
            self._projtype = 'WCS'
            img = copy.deepcopy(img)
            self._geom = img.geom
        elif isinstance(img, HpxNDMap):
            self._projtype = 'HPX'
            raise ValueError
        else:
            raise ValueError("Can't plot map of unknown type %s" % type(proj))

        self._img = img

    @property
    def projtype(self):
        return self._projtype

    @property
    def geom(self):
        return self._geom

    def plot(self, subplot=111, cmap='magma', **kwargs):

        kwargs_contour = {'levels': None, 'colors': ['k'],
                          'linewidths': 1.0}

        kwargs_imshow = {'interpolation': 'nearest',
                         'origin': 'lower', 'norm': None}

        zscale = kwargs.get('zscale', 'lin')
        gamma = kwargs.get('gamma', 0.5)
        transform = kwargs.get('transform', None)

        if zscale == 'pow':
            kwargs_imshow['norm'] = PowerNorm(gamma=gamma)
        elif zscale == 'sqrt':
            kwargs_imshow['norm'] = PowerNorm(gamma=0.5)
        elif zscale == 'log':
            kwargs_imshow['norm'] = LogNorm()
        elif zscale == 'lin':
            kwargs_imshow['norm'] = Normalize()
        else:
            kwargs_imshow['norm'] = Normalize()

        fig = plt.gcf()

        ax = fig.add_subplot(subplot, projection=self._geom.wcs)

        load_ds9_cmap()
        try:
            colormap = plt.cm.get_cmap(cmap).copy()
        except:
            colormap = plt.cm.get_cmap('ds9_b').copy()

        colormap.set_under(colormap(0))

        data = copy.copy(self._img.data)

        if transform == 'sqrt':
            data = np.sqrt(data)

        kwargs_imshow = merge_dict(kwargs_imshow, kwargs)
        kwargs_contour = merge_dict(kwargs_contour, kwargs)

        im = ax.imshow(data, **kwargs_imshow)
        im.set_cmap(colormap)

        if kwargs_contour['levels']:
            cs = ax.contour(data, **kwargs_contour)
            cs.levels = ['%.0f' % val for val in cs.levels]
            plt.clabel(cs, inline=1, fontsize=8)

        frame = self._geom.frame
        if frame == 'icrs':
            ax.set_xlabel('RA')
            ax.set_ylabel('DEC')
        elif frame == 'galactic':
            ax.set_xlabel('GLON')
            ax.set_ylabel('GLAT')

        xlabel = kwargs.get('xlabel', None)
        ylabel = kwargs.get('ylabel', None)
        if xlabel is not None:
            ax.set_xlabel(xlabel)
        if ylabel is not None:
            ax.set_ylabel(ylabel)

        # plt.colorbar(im,orientation='horizontal',shrink=0.7,pad=0.15,
        #                     fraction=0.05)
        ax.coords.grid(color='white', linestyle=':',
                       linewidth=0.5)  # , alpha=0.5)
        #       ax.locator_params(axis="x", nbins=12)

        return im, ax


def make_cube_slice(map_in, loge_bounds):
    """Extract a slice from a map cube object.
    """
    # FIXME: This functionality should be moved into a slice method of
    # gammapy.maps
    axis = map_in.geom.axes[0]
    i0 = utils.val_to_edge(axis.edges, 10**loge_bounds[0])[0]
    i1 = utils.val_to_edge(axis.edges, 10**loge_bounds[1])[0]
    new_axis = map_in.geom.axes[0].slice(slice(i0, i1))
    geom = map_in.geom.to_image()
    geom = geom.to_cube([new_axis])
    map_out = WcsNDMap(geom, map_in.data[slice(i0, i1), ...].copy())
    return map_out


class ROIPlotter(fermipy.config.Configurable):
    defaults = {
        'loge_bounds': (None, '', list),
        'catalogs': (None, '', list),
        'graticule_radii': (None, '', list),
        'label_ts_threshold': (0.0, '', float),
        'cmap': ('ds9_b', '', str),
    }

    def __init__(self, data_map, hpx2wcs=None, **kwargs):
        self._roi = kwargs.pop('roi', None)
        super(ROIPlotter, self).__init__(None, **kwargs)

        self._catalogs = []
        for c in self.config['catalogs']:
            if utils.isstr(c):
                self._catalogs += [catalog.Catalog.create(c)]
            else:
                self._catalogs += [c]

        self._loge_bounds = self.config['loge_bounds']

        if isinstance(data_map, WcsNDMap):
            self._projtype = 'WCS'
            self._data_map = copy.deepcopy(data_map)
        elif isinstance(data_map, HpxNDMap):
            self._projtype = 'HPX'
            self._data_map = data_map.to_wcs(normalize=False, hpx2wcs=hpx2wcs)
        else:
            raise Exception(
                "Can't make ROIPlotter of unknown projection type %s" % type(data_map))

        if self._loge_bounds:
            self._data_map = make_cube_slice(self._data_map, self._loge_bounds)

        self._implot = ImagePlotter(self._data_map.sum_over_axes(keepdims=False))

    @property
    def data(self):
        return self._data_map.data

    @property
    def geom(self):
        return self._data_map.geom

    @property
    def map(self):
        return self._data_map

    @property
    def projtype(self):
        return self._projtype

    @property
    def proj(self):
        return self._proj

    @classmethod
    def create_from_fits(cls, fitsfile, roi, **kwargs):
        map_in = Map.read(fitsfile)
        return cls(map_in, roi, **kwargs)

    def plot_projection(self, iaxis, **kwargs):

        data_map = kwargs.pop('data', self._data_map)
        noerror = kwargs.pop('noerror', False)
        xmin = kwargs.pop('xmin', -1)
        xmax = kwargs.pop('xmax', 1)

        axes = wcs_utils.wcs_to_axes(self.geom.wcs,
                                     self._data_map.data.shape[-2:])
        x = utils.edge_to_center(axes[iaxis])
        xerr = 0.5 * utils.edge_to_width(axes[iaxis])

        y = self.get_data_projection(data_map, axes, iaxis,
                                     loge_bounds=self._loge_bounds,
                                     xmin=xmin, xmax=xmax)

        if noerror:
            plt.errorbar(x, y, **kwargs)
        else:
            plt.errorbar(x, y, yerr=y ** 0.5, xerr=xerr, **kwargs)

    @staticmethod
    def get_data_projection(data_map, axes, iaxis, xmin=-1, xmax=1, loge_bounds=None):

        s0 = slice(None, None)
        s1 = slice(None, None)
        s2 = slice(None, None)

        if iaxis == 0:
            if xmin is None:
                xmin = axes[1][0]
            if xmax is None:
                xmax = axes[1][-1]
            i0 = utils.val_to_edge(axes[iaxis], xmin)[0]
            i1 = utils.val_to_edge(axes[iaxis], xmax)[0]
            s1 = slice(i0, i1)
            saxes = [1, 2]
        else:
            if xmin is None:
                xmin = axes[0][0]
            if xmax is None:
                xmax = axes[0][-1]
            i0 = utils.val_to_edge(axes[iaxis], xmin)[0]
            i1 = utils.val_to_edge(axes[iaxis], xmax)[0]
            s0 = slice(i0, i1)
            saxes = [0, 2]

        if loge_bounds is not None:
            j0 = utils.val_to_edge(
                data_map.geom.axes[0].edges, 10**loge_bounds[0])[0]
            j1 = utils.val_to_edge(
                data_map.geom.axes[0].edges, 10**loge_bounds[1])[0]
            s2 = slice(j0, j1)

        c = np.apply_over_axes(np.sum, data_map.data.T[s0, s1, s2], axes=saxes)
        c = np.squeeze(c)
        return c

    @staticmethod
    def setup_projection_axis(iaxis, loge_bounds=None):

        plt.gca().legend(frameon=False, prop={'size': 10})
        plt.gca().set_ylabel('Counts')
        if iaxis == 0:
            plt.gca().set_xlabel('LON Offset [deg]')
        else:
            plt.gca().set_xlabel('LAT Offset [deg]')

    def plot_sources(self, skydir, labels,
                     plot_kwargs, text_kwargs, **kwargs):

        ax = plt.gca()

        nolabels = kwargs.get('nolabels', False)
        label_mask = kwargs.get('label_mask',
                                np.ones(len(labels), dtype=bool))
        if nolabels:
            label_mask.fill(False)

        pixcrd = wcs_utils.skydir_to_pix(skydir, self._implot.geom.wcs)
        path_effect = PathEffects.withStroke(linewidth=2.0,
                                             foreground="black")

        for i, (x, y, label, show_label) in enumerate(zip(pixcrd[0], pixcrd[1],
                                                          labels, label_mask)):

            if show_label:
                t = ax.annotate(label, xy=(x, y),
                                xytext=(5.0, 5.0), textcoords='offset points',
                                **text_kwargs)
                plt.setp(t, path_effects=[path_effect])

            t = ax.plot(x, y, **plot_kwargs)
            plt.setp(t, path_effects=[path_effect])

    def plot_roi(self, roi, **kwargs):

        src_color = 'w'

        label_ts_threshold = kwargs.get('label_ts_threshold', 0.0)
        plot_kwargs = dict(linestyle='None', marker='+',
                           markerfacecolor='None', mew=0.66, ms=8,
                           #                           markersize=8,
                           markeredgecolor=src_color, clip_on=True)

        text_kwargs = dict(color=src_color, size=8, clip_on=True,
                           fontweight='normal')

        ts = np.array([s['ts'] for s in roi.point_sources])

        if label_ts_threshold is None:
            m = np.zeros(len(ts), dtype=bool)
        elif label_ts_threshold <= 0:
            m = np.ones(len(ts), dtype=bool)
        else:
            m = ts > label_ts_threshold

        skydir = roi._src_skydir
        labels = [s.name for s in roi.point_sources]
        self.plot_sources(skydir, labels, plot_kwargs, text_kwargs,
                          label_mask=m, **kwargs)

    def plot_catalog(self, catalog):

        color = 'lime'

        plot_kwargs = dict(linestyle='None', marker='x',
                           markerfacecolor='None',
                           markeredgecolor=color, clip_on=True)

        text_kwargs = dict(color=color, size=8, clip_on=True,
                           fontweight='normal')

        skydir = catalog.skydir

        if 'NickName' in catalog.table.columns:
            labels = catalog.table['NickName']
        else:
            labels = catalog.table['Source_Name']

        separation = skydir.separation(self.map.skydir).deg
        m = separation < max(self.map.width)

        self.plot_sources(skydir[m], labels[m], plot_kwargs, text_kwargs,
                          nolabels=True)

    def plot(self, **kwargs):

        zoom = kwargs.get('zoom', None)
        graticule_radii = kwargs.get('graticule_radii',
                                     self.config['graticule_radii'])
        label_ts_threshold = kwargs.get('label_ts_threshold',
                                        self.config['label_ts_threshold'])

        im_kwargs = dict(cmap=self.config['cmap'],
                         interpolation='nearest', transform=None,
                         vmin=None, vmax=None, levels=None,
                         zscale='lin', subplot=111, colors=['k'])

        cb_kwargs = dict(orientation='vertical', shrink=1.0, pad=0.1,
                         fraction=0.1, cb_label=None)

        im_kwargs = merge_dict(im_kwargs, kwargs)
        cb_kwargs = merge_dict(cb_kwargs, kwargs)

        im, ax = self._implot.plot(**im_kwargs)

        self._ax = ax

        for c in self._catalogs:
            self.plot_catalog(c)

        if self._roi is not None:
            self.plot_roi(self._roi,
                          label_ts_threshold=label_ts_threshold)

        self._extent = im.get_extent()
        ax.set_xlim(self._extent[0], self._extent[1])
        ax.set_ylim(self._extent[2], self._extent[3])

        self.zoom(zoom)

        cb_label = cb_kwargs.pop('cb_label', None)
        cb = plt.colorbar(im, **cb_kwargs)
        if cb_label:
            cb.set_label(cb_label)

        for r in graticule_radii:
            self.draw_circle(r)

    def draw_circle(self, radius, **kwargs):

        # coordsys = wcs_utils.get_coordsys(self.proj)
        skydir = kwargs.get('skydir', None)
        path_effects = kwargs.get('path_effects', None)

        if skydir is None:
            pix = self.map.geom.center_pix[:2]
        else:
            pix = skydir.to_pixel(self.map.geom.wcs)[:2]

        kw = dict(facecolor='none', edgecolor='w', linestyle='--',
                  linewidth=0.5, label='__nolabel__')
        kw = merge_dict(kw, kwargs)

        pix_radius = radius / max(np.abs(self.map.geom.wcs.wcs.cdelt))
        c = Circle(pix, pix_radius, **kw)

        if path_effects is not None:
            plt.setp(c, path_effects=path_effects)

        self._ax.add_patch(c)

    def zoom(self, zoom):

        if zoom is None:
            return

        extent = self._extent

        xw = extent[1] - extent[0]
        x0 = 0.5 * (extent[0] + extent[1])
        yw = extent[1] - extent[0]
        y0 = 0.5 * (extent[0] + extent[1])

        xlim = [x0 - 0.5 * xw / zoom, x0 + 0.5 * xw / zoom]
        ylim = [y0 - 0.5 * yw / zoom, y0 + 0.5 * yw / zoom]

        self._ax.set_xlim(xlim[0], xlim[1])
        self._ax.set_ylim(ylim[0], ylim[1])


class SEDPlotter(object):

    def __init__(self, sed):

        self._sed = copy.deepcopy(sed)

    @property
    def sed(self):
        return self._sed

    @staticmethod
    def get_ylims(sed):

        fmin = np.log10(np.nanmin(sed['e2dnde_ul95'])) - 0.5
        fmax = np.log10(np.nanmax(sed['e2dnde_ul95'])) + 0.5
        fdelta = fmax - fmin
        if fdelta < 2.0:
            fmin -= 0.5 * (2.0 - fdelta)
            fmax += 0.5 * (2.0 - fdelta)

        return fmin, fmax

    @staticmethod
    def plot_lnlscan(sed, **kwargs):

        ax = kwargs.pop('ax', plt.gca())
        llhcut = kwargs.pop('llhcut', -2.70)
        cmap = kwargs.pop('cmap', 'BuGn')
        cmap_trunc_lo = kwargs.pop('cmap_trunc_lo', None)
        cmap_trunc_hi = kwargs.pop('cmap_trunc_hi', None)

        ylim = kwargs.pop('ylim', None)

        if ylim is None:
            fmin, fmax = SEDPlotter.get_ylims(sed)
        else:
            fmin, fmax = np.log10(ylim)

        fluxEdges = np.arange(fmin, fmax, 0.01)
        fluxCenters = 0.5*(fluxEdges[1:] + fluxEdges[:-1])
        fbins = len(fluxCenters)
        llhMatrix = np.zeros((len(sed['e_ctr']), fbins))

        # loop over energy bins
        for i in range(len(sed['e_ctr'])):
            m = sed['norm_scan'][i] > 0
            e2dnde_scan = sed['norm_scan'][i][m] * sed['ref_e2dnde'][i]
            flux = np.log10(e2dnde_scan)
            logl = sed['dloglike_scan'][i][m]
            logl -= np.max(logl)
            try:
                fn = interpolate.interp1d(flux, logl, fill_value='extrapolate')
                logli = fn(fluxCenters)
            except:
                logli = np.interp(fluxCenters, flux, logl)
            llhMatrix[i, :] = logli

        cmap = copy.deepcopy(plt.cm.get_cmap(cmap))
        # cmap.set_under('w')

        if cmap_trunc_lo is not None or cmap_trunc_hi is not None:
            cmap = truncate_colormap(cmap, cmap_trunc_lo, cmap_trunc_hi, 1024)

        xedge = 10**np.insert(sed['loge_max'], 0, sed['loge_min'][0])
        yedge = 10**fluxEdges
        xedge, yedge = np.meshgrid(xedge, yedge)
        im = ax.pcolormesh(xedge, yedge, llhMatrix.T,
                           vmin=llhcut, vmax=0, cmap=cmap,
                           linewidth=0, shading='auto') 
        cb = plt.colorbar(im)
        cb.set_label('Delta LogLikelihood')

        plt.gca().set_ylim(10 ** fmin, 10 ** fmax)
        plt.gca().set_yscale('log')
        plt.gca().set_xscale('log')
        plt.gca().set_xlim(sed['e_min'][0], sed['e_max'][-1])

    @staticmethod
    def plot_flux_points(sed, **kwargs):

        ax = kwargs.pop('ax', plt.gca())

        ul_ts_threshold = kwargs.pop('ul_ts_threshold', 4)

        kw = {}
        kw['marker'] = kwargs.get('marker', 'o')
        kw['linestyle'] = kwargs.get('linestyle', 'None')
        kw['color'] = kwargs.get('color', 'k')

        fmin, fmax = SEDPlotter.get_ylims(sed)

        m = sed['ts'] < ul_ts_threshold
        x = sed['e_ctr']
        y = sed['e2dnde']
        yerr = sed['e2dnde_err']
        yerr_lo = sed['e2dnde_err_lo']
        yerr_hi = sed['e2dnde_err_hi']
        yul = sed['e2dnde_ul95']

        delo = sed['e_ctr'] - sed['e_min']
        dehi = sed['e_max'] - sed['e_ctr']
        xerr0 = np.vstack((delo[m], dehi[m]))
        xerr1 = np.vstack((delo[~m], dehi[~m]))

        plt.errorbar(x[~m], y[~m], xerr=xerr1,
                     yerr=(yerr_lo[~m], yerr_hi[~m]), **kw)
        plt.errorbar(x[m], yul[m], xerr=xerr0,
                     yerr=yul[m] * 0.2, uplims=True, **kw)

        ax.set_yscale('log')
        ax.set_xscale('log')
        ax.set_xlim(sed['e_min'][0], sed['e_max'][-1])
        ax.set_ylim(10 ** fmin, 10 ** fmax)

    @staticmethod
    def plot_resid(src, model_flux, **kwargs):

        ax = kwargs.pop('ax', plt.gca())

        sed = src['sed']

        m = sed['ts'] < 4

        x = sed['e_ctr']
        y = sed['e2dnde']
        yerr = sed['e2dnde_err']
        yul = sed['e2dnde_ul95']
        delo = sed['e_ctr'] - sed['e_min']
        dehi = sed['e_max'] - sed['e_ctr']
        xerr = np.vstack((delo, dehi))

        ym = np.interp(sed['e_ctr'], model_flux['log_energies'],
                       10 ** (2 * model_flux['log_energies']) *
                       model_flux['dnde'])

        ax.errorbar(x, (y - ym) / ym, xerr=xerr, yerr=yerr / ym, **kwargs)

    @staticmethod
    def plot_model(model_flux, **kwargs):

        ax = kwargs.pop('ax', plt.gca())

        color = kwargs.pop('color', 'k')
        noband = kwargs.pop('noband', False)

        e2 = 10 ** (2 * model_flux['log_energies'])

        ax.plot(10 ** model_flux['log_energies'],
                model_flux['dnde'] * e2, color=color)

        ax.plot(10 ** model_flux['log_energies'],
                model_flux['dnde_lo'] * e2, color=color,
                linestyle='--')
        ax.plot(10 ** model_flux['log_energies'],
                model_flux['dnde_hi'] * e2, color=color,
                linestyle='--')

        if not noband:
            ax.fill_between(10 ** model_flux['log_energies'],
                            model_flux['dnde_lo'] * e2,
                            model_flux['dnde_hi'] * e2,
                            alpha=0.5, color=color, zorder=-1)

    @staticmethod
    def plot_sed(sed, showlnl=False, **kwargs):
        """Render a plot of a spectral energy distribution.

        Parameters
        ----------
        showlnl : bool        
            Overlay a map of the delta-loglikelihood values vs. flux
            in each energy bin.

        cmap : str        
            Colormap that will be used for the delta-loglikelihood
            map.

        llhcut : float
            Minimum delta-loglikelihood value.

        ul_ts_threshold : float        
            TS threshold that determines whether the MLE or UL
            is plotted in each energy bin.

        """

        ax = kwargs.pop('ax', plt.gca())
        cmap = kwargs.get('cmap', 'BuGn')

        annotate_name(sed, ax=ax)
        SEDPlotter.plot_flux_points(sed, **kwargs)

        if np.any(sed['ts'] > 9.):

            if 'model_flux' in sed:
                SEDPlotter.plot_model(sed['model_flux'],
                                      noband=showlnl, **kwargs)

        if showlnl:
            SEDPlotter.plot_lnlscan(sed, **kwargs)

        ax.set_yscale('log')
        ax.set_xscale('log')
        ax.set_xlabel('Energy [MeV]')
        ax.set_ylabel('E$^{2}$dN/dE [MeV cm$^{-2}$ s$^{-1}$]')

    def plot(self, showlnl=False, **kwargs):
        return SEDPlotter.plot_sed(self.sed, showlnl, **kwargs)


class ExtensionPlotter(object):

    def __init__(self, src, roi, suffix, workdir, loge_bounds=None):

        self._src = copy.deepcopy(src)

        name = src['name'].lower().replace(' ', '_')

        self._file0 = os.path.join(workdir,
                                   'mcube_%s_noext%s.fits' % (name, suffix))
        self._file1 = os.path.join(workdir,
                                   'mcube_%s_ext_bkg%s.fits' % (name, suffix))
        self._file2 = os.path.join(workdir, 'ccube%s.fits' % suffix)

        self._files = []
        self._width = src['extension']['width']
        for i, w in enumerate(src['extension']['width']):
            self._files += [os.path.join(workdir, 'mcube_%s_ext%02i%s.fits' % (
                name, i, suffix))]
        self._roi = roi
        self._loge_bounds = loge_bounds

    def plot(self, iaxis):

        p0 = ROIPlotter.create_from_fits(self._file2, roi=self._roi,
                                         loge_bounds=self._loge_bounds)
        p1 = ROIPlotter.create_from_fits(self._file1, roi=self._roi,
                                         loge_bounds=self._loge_bounds)
        p0.plot_projection(iaxis, color='k', label='Data', marker='s',
                           linestyle='None')
        p1.plot_projection(iaxis, color='b', noerror=True, label='Background')

        n = len(self._width)
        step = max(1, int(n / 5.))

        fw = zip(self._files, self._width)[::step]

        for i, (f, w) in enumerate(fw):
            cf = float(i) / float(len(fw) - 1.0)
            cf = 0.2 + cf * 0.8

            p = ROIPlotter.create_from_fits(f, roi=self._roi,
                                            loge_bounds=self._loge_bounds)
            p._data += p1.data
            p.plot_projection(iaxis, color=matplotlib.cm.Reds(cf),
                              noerror=True, label='%.4f$^\circ$' % w)


class AnalysisPlotter(fermipy.config.Configurable):
    defaults = dict(defaults.plotting.items(),
                    fileio=defaults.fileio,
                    logging=defaults.logging)

    def __init__(self, config, **kwargs):
        fermipy.config.Configurable.__init__(self, config, **kwargs)

        matplotlib.rcParams['font.size'] = 12
        matplotlib.interactive(self.config['interactive'])

        self._catalogs = []
        for c in self.config['catalogs']:
            self._catalogs += [catalog.Catalog.create(c)]

    def run(self, gta, mcube_map, **kwargs):
        """Make all plots."""

        prefix = kwargs.get('prefix', 'test')
        format = kwargs.get('format', self.config['format'])

        loge_bounds = [None] + self.config['loge_bounds']
        for x in loge_bounds:
            self.make_roi_plots(gta, mcube_map, loge_bounds=x,
                                **kwargs)

        imfile = utils.format_filename(self.config['fileio']['workdir'],
                                       'counts_spectrum', prefix=[prefix],
                                       extension=format)

        make_counts_spectrum_plot(gta._roi_data, gta.roi,
                                  gta.log_energies,
                                  imfile, **kwargs)

    def make_residmap_plots(self, maps, roi=None, **kwargs):
        """Make plots from the output of
        `~fermipy.gtanalysis.GTAnalysis.residmap`.

        Parameters
        ----------
        maps : dict
            Output dictionary of
            `~fermipy.gtanalysis.GTAnalysis.residmap`.

        roi : `~fermipy.roi_model.ROIModel`
            ROI Model object.  Generate markers at the positions of
            the sources in this ROI.

        zoom : float
            Crop the image by this factor.  If None then no crop is
            applied.

        """

        fmt = kwargs.get('format', self.config['format'])
        figsize = kwargs.get('figsize', self.config['figsize'])
        workdir = kwargs.pop('workdir', self.config['fileio']['workdir'])
        use_weights = kwargs.pop('use_weights', False)
        # FIXME, how to set this:
        no_contour = False
        zoom = kwargs.get('zoom', None)

        kwargs.setdefault('graticule_radii', self.config['graticule_radii'])
        kwargs.setdefault('label_ts_threshold',
                          self.config['label_ts_threshold'])
        cmap = kwargs.setdefault('cmap', self.config['cmap'])
        cmap_resid = kwargs.pop('cmap_resid', self.config['cmap_resid'])
        kwargs.setdefault('catalogs', self.config['catalogs'])
        if no_contour:
            sigma_levels = None
        else:
            sigma_levels = [-5, -3, 3, 5, 7] + list(np.logspace(1, 3, 17))

        load_bluered_cmap()

        prefix = maps['name']
        mask = maps['mask']
        if use_weights:
            sigma_hist_data = maps['sigma'].data[maps['mask'].data.astype(
                bool)]
            maps['sigma'].data *= maps['mask'].data
            maps['data'].data *= maps['mask'].data
            maps['model'].data *= maps['mask'].data
            maps['excess'].data *= maps['mask'].data
        else:
            sigma_hist_data = maps['sigma'].data

        fig = plt.figure(figsize=figsize)
        p = ROIPlotter(maps['sigma'], roi=roi, **kwargs)
        p.plot(vmin=-5, vmax=5, levels=sigma_levels,
               cb_label='Significance [$\sigma$]', interpolation='bicubic',
               cmap=cmap_resid, zoom=zoom)
        plt.savefig(utils.format_filename(workdir,
                                          'residmap_sigma',
                                          prefix=[prefix],
                                          extension=fmt))
        plt.close(fig)

        # make and draw histogram
        fig, ax = plt.subplots(figsize=figsize)
        nBins = np.linspace(-6, 6, 121)
        data = np.nan_to_num(sigma_hist_data)
        # find best fit parameters
        mu, sigma = norm.fit(data.flatten())
        # make and draw the histogram
        data[data > 6.0] = 6.0
        data[data < -6.0] = -6.0

        n, bins, patches = ax.hist(data.flatten(), nBins, density=True,
                                   histtype='stepfilled',
                                   facecolor='green', alpha=0.75)
        # make and draw best fit line
        y = norm.pdf(bins, mu, sigma)
        ax.plot(bins, y, 'r--', linewidth=2)
        y = norm.pdf(bins, 0.0, 1.0)
        ax.plot(bins, y, 'k', linewidth=1)

        # labels and such
        ax.set_xlabel(r'Significance ($\sigma$)')
        ax.set_ylabel('Probability')
        paramtext = 'Gaussian fit:\n'
        paramtext += '$\\mu=%.2f$\n' % mu
        paramtext += '$\\sigma=%.2f$' % sigma
        ax.text(0.05, 0.95, paramtext, verticalalignment='top',
                horizontalalignment='left', transform=ax.transAxes)

        plt.savefig(utils.format_filename(workdir,
                                          'residmap_sigma_hist',
                                          prefix=[prefix],
                                          extension=fmt))
        plt.close(fig)

        vmax = max(np.max(maps['data'].data), np.max(maps['model'].data))
        vmin = min(np.min(maps['data'].data), np.min(maps['model'].data))

        fig = plt.figure(figsize=figsize)
        p = ROIPlotter(maps['data'], roi=roi, **kwargs)
        p.plot(cb_label='Counts', interpolation='bicubic',
               cmap=cmap, zscale='sqrt', vmin=vmin, vmax=vmax)
        plt.savefig(utils.format_filename(workdir,
                                          'residmap_data',
                                          prefix=[prefix],
                                          extension=fmt))
        plt.close(fig)

        fig = plt.figure(figsize=figsize)
        p = ROIPlotter(maps['model'], roi=roi, **kwargs)
        p.plot(cb_label='Counts', interpolation='bicubic',
               cmap=cmap, zscale='sqrt', vmin=vmin, vmax=vmax)
        plt.savefig(utils.format_filename(workdir,
                                          'residmap_model',
                                          prefix=[prefix],
                                          extension=fmt))
        plt.close(fig)

        fig = plt.figure(figsize=figsize)
        p = ROIPlotter(maps['excess'], roi=roi, **kwargs)
        p.plot(cb_label='Counts', interpolation='bicubic',
               cmap=cmap_resid)
        plt.savefig(utils.format_filename(workdir,
                                          'residmap_excess',
                                          prefix=[prefix],
                                          extension=fmt))
        plt.close(fig)

    def make_tsmap_plots(self, maps, roi=None, **kwargs):
        """Make plots from the output of
        `~fermipy.gtanalysis.GTAnalysis.tsmap` or
        `~fermipy.gtanalysis.GTAnalysis.tscube`.  This method
        generates a 2D sky map for the best-fit test source in
        sqrt(TS) and Npred.

        Parameters
        ----------
        maps : dict
            Output dictionary of
            `~fermipy.gtanalysis.GTAnalysis.tsmap` or
            `~fermipy.gtanalysis.GTAnalysis.tscube`.

        roi : `~fermipy.roi_model.ROIModel`
            ROI Model object.  Generate markers at the positions of
            the sources in this ROI.

        zoom : float
            Crop the image by this factor.  If None then no crop is
            applied.
        """
        kwargs.setdefault('graticule_radii', self.config['graticule_radii'])
        kwargs.setdefault('label_ts_threshold',
                          self.config['label_ts_threshold'])
        kwargs.setdefault('cmap', self.config['cmap'])
        kwargs.setdefault('catalogs', self.config['catalogs'])
        fmt = kwargs.get('format', self.config['format'])
        figsize = kwargs.get('figsize', self.config['figsize'])
        workdir = kwargs.pop('workdir', self.config['fileio']['workdir'])
        suffix = kwargs.pop('suffix', 'tsmap')
        zoom = kwargs.pop('zoom', None)

        if 'ts' not in maps:
            return

        sigma_levels = [3, 5, 7] + list(np.logspace(1, 3, 17))
        prefix = maps['name']
        fig = plt.figure(figsize=figsize)
        p = ROIPlotter(maps['sqrt_ts'], roi=roi, **kwargs)
        p.plot(vmin=0, vmax=5, levels=sigma_levels,
               cb_label='Sqrt(TS) [$\sigma$]', interpolation='bicubic',
               zoom=zoom)
        plt.savefig(utils.format_filename(workdir,
                                          '%s_sqrt_ts' % suffix,
                                          prefix=[prefix],
                                          extension=fmt))
        plt.close(fig)

        fig = plt.figure(figsize=figsize)
        p = ROIPlotter(maps['npred'], roi=roi, **kwargs)
        p.plot(vmin=0, cb_label='NPred [Counts]', interpolation='bicubic',
               zoom=zoom)
        plt.savefig(utils.format_filename(workdir,
                                          '%s_npred' % suffix,
                                          prefix=[prefix],
                                          extension=fmt))
        plt.close(fig)

        # make and draw histogram
        fig, ax = plt.subplots(figsize=figsize)
        bins = np.linspace(0, 25, 101)

        data = np.nan_to_num(maps['ts'].data.T)
        data[data > 25.0] = 25.0
        data[data < 0.0] = 0.0
        n, bins, patches = ax.hist(data.flatten(), bins, density=True,
                                   histtype='stepfilled',
                                   facecolor='green', alpha=0.75)
        # ax.plot(bins,(1-chi2.cdf(x,dof))/2.,**kwargs)
        ax.plot(bins, 0.5 * chi2.pdf(bins, 1.0), color='k',
                label=r"$\chi^2_{1} / 2$")
        ax.set_yscale('log')
        ax.set_ylim(1E-4)
        ax.legend(loc='upper right', frameon=False)

        # labels and such
        ax.set_xlabel('TS')
        ax.set_ylabel('Probability')
        plt.savefig(utils.format_filename(workdir,
                                          '%s_ts_hist' % suffix,
                                          prefix=[prefix],
                                          extension=fmt))
        plt.close(fig)

    def make_roi_plots(self, gta, mcube_tot, **kwargs):
        """Make various diagnostic plots for the 1D and 2D
        counts/model distributions.

        Parameters
        ----------

        prefix : str
            Prefix that will be appended to all filenames.

        """

        fmt = kwargs.get('format', self.config['format'])
        figsize = kwargs.get('figsize', self.config['figsize'])
        prefix = kwargs.get('prefix', '')
        loge_bounds = kwargs.get('loge_bounds', None)
        weighted = kwargs.get('weighted', False)

        roi_kwargs = {}
        roi_kwargs.setdefault('loge_bounds', loge_bounds)
        roi_kwargs.setdefault(
            'graticule_radii', self.config['graticule_radii'])
        roi_kwargs.setdefault('label_ts_threshold',
                              self.config['label_ts_threshold'])
        roi_kwargs.setdefault('cmap', self.config['cmap'])
        roi_kwargs.setdefault('catalogs', self._catalogs)

        if loge_bounds is None:
            loge_bounds = (gta.log_energies[0], gta.log_energies[-1])
        esuffix = '_%.3f_%.3f' % (loge_bounds[0], loge_bounds[1])

        mcube_diffuse = gta.model_counts_map('diffuse')
        counts_map = gta.counts_map()

        if weighted:
            wmap = gta.weight_map()
            counts_map = copy.deepcopy(counts_map)
            mcube_tot = copy.deepcopy(mcube_tot)
            counts_map.data *= wmap.data
            mcube_tot.data *= wmap.data
            mcube_diffuse.data *= wmap.data

        # colors = ['k', 'b', 'g', 'r']
        data_style = {'marker': 's', 'linestyle': 'None'}

        fig = plt.figure(figsize=figsize)

        if gta.projtype == "WCS":
            xmin = -1
            xmax = 1
        elif gta.projtype == "HPX":
            hpx2wcs = counts_map.make_wcs_mapping(proj='CAR', oversample=2)
            counts_map = counts_map.to_wcs(hpx2wcs=hpx2wcs)
            mcube_tot = mcube_tot.to_wcs(hpx2wcs=hpx2wcs)
            mcube_diffuse = mcube_diffuse.to_wcs(hpx2wcs=hpx2wcs)
            xmin = None
            xmax = None

        fig = plt.figure(figsize=figsize)
        rp = ROIPlotter(mcube_tot, roi=gta.roi, **roi_kwargs)
        rp.plot(cb_label='Counts', zscale='pow', gamma=1. / 3.)
        plt.savefig(os.path.join(gta.config['fileio']['workdir'],
                                 '%s_model_map%s.%s' % (
                                     prefix, esuffix, fmt)))
        plt.close(fig)

        rp = ROIPlotter(counts_map, roi=gta.roi, **roi_kwargs)

        rp.plot(cb_label='Counts', zscale='sqrt')
        plt.savefig(os.path.join(gta.config['fileio']['workdir'],
                                 '%s_counts_map%s.%s' % (
                                     prefix, esuffix, fmt)))
        plt.close(fig)

        for iaxis, xlabel, psuffix in zip([0, 1],
                                          ['LON Offset [deg]', 'LAT Offset [deg]'],
                                          ['xproj', 'yproj']):

            fig = plt.figure(figsize=figsize)
            rp.plot_projection(iaxis, label='Data', color='k',
                               xmin=xmin, xmax=xmax, **data_style)
            rp.plot_projection(iaxis, data=mcube_tot, label='Model', xmin=xmin, xmax=xmax,
                               noerror=True)
            rp.plot_projection(iaxis, data=mcube_diffuse, label='Diffuse', xmin=xmin, xmax=xmax,
                               noerror=True)
            plt.gca().set_ylabel('Counts')
            plt.gca().set_xlabel(xlabel)
            plt.gca().legend(frameon=False)
            annotate(loge_bounds=loge_bounds)
            plt.savefig(os.path.join(gta.config['fileio']['workdir'],
                                     '%s_counts_map_%s%s.%s' % (prefix, psuffix,
                                                                esuffix, fmt)))
            plt.close(fig)

    def make_sed_plots(self, sed, **kwargs):

        prefix = kwargs.get('prefix', '')
        name = sed['name'].lower().replace(' ', '_')
        fmt = kwargs.get('format', self.config['format'])
        figsize = kwargs.get('figsize', self.config['figsize'])
        p = SEDPlotter(sed)
        fig = plt.figure(figsize=figsize)
        p.plot()

        outfile = utils.format_filename(self.config['fileio']['workdir'],
                                        'sed', prefix=[prefix, name],
                                        extension=fmt)

        plt.savefig(outfile)
        plt.close(fig)

        fig = plt.figure(figsize=figsize)
        p.plot(showlnl=True)

        outfile = utils.format_filename(self.config['fileio']['workdir'],
                                        'sedlnl', prefix=[prefix, name],
                                        extension=fmt)
        plt.savefig(outfile)
        plt.close(fig)

    def make_localization_plots(self, loc, roi=None, **kwargs):

        fmt = kwargs.get('format', self.config['format'])
        figsize = kwargs.get('figsize', self.config['figsize'])
        prefix = kwargs.get('prefix', '')
        skydir = kwargs.get('skydir', None)
        cmap = kwargs.get('cmap', self.config['cmap'])
        name = loc.get('name', '')
        name = name.lower().replace(' ', '_')

        tsmap = loc['tsmap']
        fit_init = loc['fit_init']
        tsmap_renorm = copy.deepcopy(tsmap)
        tsmap_renorm.data -= np.max(tsmap_renorm.data)

        skydir = loc['tsmap_peak'].geom.get_coord().flat
        frame = loc['tsmap_peak'].geom.frame
        skydir = MapCoord.create(skydir, frame=frame).skycoord

        path_effect = PathEffects.withStroke(linewidth=2.0,
                                             foreground="black")

        p = ROIPlotter(tsmap_renorm, roi=roi)
        fig = plt.figure(figsize=figsize)

        vmin = max(-100.0, np.min(tsmap_renorm.data))

        p.plot(levels=[-200, -100, -50, -20, -9.21, -5.99, -2.3, -1.0],
               cmap=cmap, vmin=vmin, colors=['k'],
               interpolation='bicubic', cb_label='2$\\times\Delta\ln$L')

        cdelt0 = np.abs(tsmap.geom.wcs.wcs.cdelt[0])
        cdelt1 = np.abs(tsmap.geom.wcs.wcs.cdelt[1])
        cdelt = [cdelt0, cdelt1]

        peak_skydir = SkyCoord(fit_init['ra'], fit_init['dec'],
                               frame='icrs', unit='deg')
        scan_skydir = SkyCoord(loc['ra'], loc['dec'],
                               frame='icrs', unit='deg')

        peak_pix = peak_skydir.to_pixel(tsmap_renorm.geom.wcs)
        scan_pix = scan_skydir.to_pixel(tsmap_renorm.geom.wcs)

        if 'ra_preloc' in loc:
            preloc_skydir = SkyCoord(loc['ra_preloc'], loc['dec_preloc'],
                                     frame='icrs', unit='deg')
            plot_markers(preloc_skydir.ra.deg, preloc_skydir.dec.deg,
                         marker='+', color='w', path_effects=[path_effect],
                         label='Old Position')

        plot_markers(peak_skydir.ra.deg, peak_skydir.dec.deg,
                     marker='x', color='lime', path_effects=[path_effect])

        plot_markers(scan_skydir.ra.deg, scan_skydir.dec.deg,
                     marker='x', color='w', path_effects=[path_effect],
                     label='New Position')

        if skydir is not None:
            pix = skydir.to_pixel(tsmap_renorm.geom.wcs)
            xmin = np.min(pix[0])
            ymin = np.min(pix[1])
            xwidth = np.max(pix[0]) - xmin
            ywidth = np.max(pix[1]) - ymin
            r = Rectangle((xmin, ymin), xwidth, ywidth,
                          edgecolor='w', facecolor='none', linestyle='--')
            plt.gca().add_patch(r)

        plot_error_ellipse(fit_init, peak_pix, cdelt, edgecolor='lime',
                           color='lime', colname='pos_r68')
        plot_error_ellipse(fit_init, peak_pix, cdelt, edgecolor='lime',
                           color='lime', colname='pos_r99', linestyle=':')

        plot_error_ellipse(loc, scan_pix, cdelt, edgecolor='w',
                           color='w', colname='pos_r68', label='68% Uncertainty')
        plot_error_ellipse(loc, scan_pix, cdelt, edgecolor='w',
                           color='w', colname='pos_r99', label='99% Uncertainty',
                           linestyle='--')

        handles, labels = plt.gca().get_legend_handles_labels()
        h0 = Line2D([], [], color='w', marker='None',
                    label='68% Uncertainty', linewidth=1.0)
        h1 = Line2D([], [], color='w', marker='None',
                    label='99% Uncertainty', linewidth=1.0,
                    linestyle='--')
        plt.legend(handles=handles + [h0, h1])

        outfile = utils.format_filename(self.config['fileio']['workdir'],
                                        'localize', prefix=[prefix, name],
                                        extension=fmt)

        plt.savefig(outfile)
        plt.close(fig)

        tsmap = loc['tsmap_peak']
        tsmap_renorm = copy.deepcopy(tsmap)
        tsmap_renorm.data -= np.max(tsmap_renorm.data)

        p = ROIPlotter(tsmap_renorm, roi=roi)
        fig = plt.figure(figsize=figsize)

        vmin = max(-50.0, np.min(tsmap_renorm.data))

        p.plot(levels=[-200, -100, -50, -20, -9.21, -5.99, -2.3, -1.0],
               cmap=cmap, vmin=vmin, colors=['k'],
               interpolation='bicubic', cb_label='2$\\times\Delta\ln$L')

        cdelt0 = np.abs(tsmap.geom.wcs.wcs.cdelt[0])
        cdelt1 = np.abs(tsmap.geom.wcs.wcs.cdelt[1])
        cdelt = [cdelt0, cdelt1]
        scan_pix = scan_skydir.to_pixel(tsmap_renorm.geom.wcs)

        if 'ra_preloc' in loc:
            preloc_skydir = SkyCoord(loc['ra_preloc'], loc['dec_preloc'],
                                     frame='icrs', unit='deg')
            plot_markers(preloc_skydir.ra.deg, preloc_skydir.dec.deg,
                         marker='+', color='w', path_effects=[path_effect],
                         label='Old Position')

        plot_markers(scan_skydir.ra.deg, scan_skydir.dec.deg,
                     marker='x', color='w', path_effects=[path_effect],
                     label='New Position')

        plot_error_ellipse(loc, scan_pix, cdelt, edgecolor='w',
                           color='w', colname='pos_r68', label='68% Uncertainty')
        plot_error_ellipse(loc, scan_pix, cdelt, edgecolor='w',
                           color='w', colname='pos_r99', label='99% Uncertainty',
                           linestyle='--')

        handles, labels = plt.gca().get_legend_handles_labels()
        h0 = Line2D([], [], color='w', marker='None',
                    label='68% Uncertainty', linewidth=1.0)
        h1 = Line2D([], [], color='w', marker='None',
                    label='99% Uncertainty', linewidth=1.0,
                    linestyle='--')
        plt.legend(handles=handles + [h0, h1])

        outfile = utils.format_filename(self.config['fileio']['workdir'],
                                        'localize_peak', prefix=[prefix, name],
                                        extension=fmt)

        plt.savefig(outfile)
        plt.close(fig)

    def make_extension_plots(self, ext, roi=None, **kwargs):

        if ext.get('tsmap') is not None:
            self._plot_extension_tsmap(ext, roi=roi, **kwargs)

        if ext.get('ebin_ts_ext') is not None:
            self._plot_extension_ebin(ext, roi=roi, **kwargs)

    def _plot_extension_ebin(self, ext, roi=None, **kwargs):

        fmt = kwargs.get('format', self.config['format'])
        figsize = kwargs.get('figsize', self.config['figsize'])
        prefix = kwargs.get('prefix', '')
        name = ext.get('name', '')
        name = name.lower().replace(' ', '_')

        m = ext['ebin_ts_ext'] > 4.0

        fig = plt.figure(figsize=figsize)

        ectr = ext['ebin_e_ctr']
        delo = ext['ebin_e_ctr'] - ext['ebin_e_min']
        dehi = ext['ebin_e_max'] - ext['ebin_e_ctr']
        xerr0 = np.vstack((delo[m], dehi[m]))
        xerr1 = np.vstack((delo[~m], dehi[~m]))

        ax = plt.gca()

        ax.errorbar(ectr[m], ext['ebin_ext'][m], xerr=xerr0,
                    yerr=(ext['ebin_ext_err_lo'][m],
                          ext['ebin_ext_err_hi'][m]),
                    color='k', linestyle='None', marker='o')
        ax.errorbar(ectr[~m], ext['ebin_ext_ul95'][~m], xerr=xerr1,
                    yerr=0.2 * ext['ebin_ext_ul95'][~m], uplims=True,
                    color='k', linestyle='None', marker='o')
        ax.set_xlabel('Energy [log$_{10}$(E/MeV)]')
        ax.set_ylabel('Extension [deg]')
        ax.set_xscale('log')
        ax.set_yscale('log')

        annotate_name(ext)

        ymin = min(10**-1.5, 0.8 * ext['ext_ul95'])
        ymax = max(10**-0.5, 1.2 * ext['ext_ul95'])
        if np.any(np.isfinite(ext['ebin_ext_ul95'])):
            ymin = min(ymin, 0.8 * np.nanmin(ext['ebin_ext_ul95']))
            ymax = max(ymax, 1.2 * np.nanmax(ext['ebin_ext_ul95']))

        if ext['ts_ext'] > 4.0:
            plt.axhline(ext['ext'], color='k')
            ext_lo = ext['ext'] - ext['ext_err_lo']
            ext_hi = ext['ext'] + ext['ext_err_hi']
            ax.fill_between([ext['ebin_e_min'][0], ext['ebin_e_max'][-1]],
                            [ext_lo, ext_lo], [ext_hi, ext_hi],
                            alpha=0.5, color='k', zorder=-1)

            ymin = min(ymin, 0.8 * (ext['ext'] - ext['ext_err_lo']))
            ymax = max(ymax, 1.2 * (ext['ext'] + ext['ext_err_hi']))

        else:
            plt.axhline(ext['ext_ul95'], color='k', linestyle='--')

        ax.set_ylim(ymin, ymax)
        ax.set_xlim(ext['ebin_e_min'][0], ext['ebin_e_max'][-1])

        outfile = utils.format_filename(self.config['fileio']['workdir'],
                                        'extension_ebin', prefix=[prefix, name],
                                        extension=fmt)

        plt.savefig(outfile)
        plt.close(fig)

    def _plot_extension_tsmap(self, ext, roi=None, **kwargs):

        fmt = kwargs.get('format', self.config['format'])
        figsize = kwargs.get('figsize', self.config['figsize'])
        prefix = kwargs.get('prefix', '')
        cmap = kwargs.get('cmap', self.config['cmap'])
        name = ext.get('name', '')
        name = name.lower().replace(' ', '_')

        p = ROIPlotter(ext['tsmap'], roi=roi)
        fig = plt.figure(figsize=figsize)

        sigma_levels = [3, 5, 7] + list(np.logspace(1, 3, 17))

        p.plot(cmap=cmap, interpolation='bicubic', levels=sigma_levels,
               transform='sqrt')
        c = SkyCoord(ext['ra'], ext['dec'], unit='deg')

        path_effect = PathEffects.withStroke(linewidth=2.0,
                                             foreground="black")

        if ext['ts_ext'] > 9.0:
            p.draw_circle(ext['ext'], skydir=c, edgecolor='lime', linestyle='-',
                          linewidth=1.0, label='R$_{68}$', path_effects=[path_effect])
            p.draw_circle(ext['ext'] + ext['ext_err'], skydir=c, edgecolor='lime', linestyle='--',
                          linewidth=1.0, label='R$_{68}$ $\pm 1 \sigma$', path_effects=[path_effect])
            p.draw_circle(ext['ext'] - ext['ext_err'], skydir=c, edgecolor='lime', linestyle='--',
                          linewidth=1.0, path_effects=[path_effect])
        else:
            p.draw_circle(ext['ext_ul95'], skydir=c, edgecolor='lime', linestyle='--',
                          linewidth=1.0, label='R$_{68}$ 95% UL',
                          path_effects=[path_effect])
        leg = plt.gca().legend(frameon=False, loc='upper left')

        for text in leg.get_texts():
            text.set_color('lime')

        outfile = utils.format_filename(self.config['fileio']['workdir'],
                                        'extension', prefix=[prefix, name],
                                        extension=fmt)

        plt.savefig(outfile)
        plt.close(fig)

    def _plot_extension(self, gta, prefix, src, loge_bounds=None, **kwargs):
        """Utility function for generating diagnostic plots for the
        extension analysis."""

        # format = kwargs.get('format', self.config['plotting']['format'])

        if loge_bounds is None:
            loge_bounds = (self.energies[0], self.energies[-1])

        name = src['name'].lower().replace(' ', '_')

        esuffix = '_%.3f_%.3f' % (loge_bounds[0], loge_bounds[1])

        p = ExtensionPlotter(src, self.roi, '',
                             self.config['fileio']['workdir'],
                             loge_bounds=loge_bounds)

        fig = plt.figure()
        p.plot(0)
        plt.gca().set_xlim(-2, 2)
        ROIPlotter.setup_projection_axis(0)
        annotate(src=src, loge_bounds=loge_bounds)
        plt.savefig(os.path.join(self.config['fileio']['workdir'],
                                 '%s_%s_extension_xproj%s.png' % (
                                     prefix, name, esuffix)))
        plt.close(fig)

        fig = plt.figure()
        p.plot(1)
        plt.gca().set_xlim(-2, 2)
        ROIPlotter.setup_projection_axis(1)
        annotate(src=src, loge_bounds=loge_bounds)
        plt.savefig(os.path.join(self.config['fileio']['workdir'],
                                 '%s_%s_extension_yproj%s.png' % (
                                     prefix, name, esuffix)))
        plt.close(fig)

        for i, c in enumerate(self.components):
            suffix = '_%02i' % i

            p = ExtensionPlotter(src, self.roi, suffix,
                                 self.config['fileio']['workdir'],
                                 loge_bounds=loge_bounds)

            fig = plt.figure()
            p.plot(0)
            ROIPlotter.setup_projection_axis(0, loge_bounds=loge_bounds)
            annotate(src=src, loge_bounds=loge_bounds)
            plt.gca().set_xlim(-2, 2)
            plt.savefig(os.path.join(self.config['fileio']['workdir'],
                                     '%s_%s_extension_xproj%s%s.png' % (
                                         prefix, name, esuffix, suffix)))
            plt.close(fig)

            fig = plt.figure()
            p.plot(1)
            plt.gca().set_xlim(-2, 2)
            ROIPlotter.setup_projection_axis(1, loge_bounds=loge_bounds)
            annotate(src=src, loge_bounds=loge_bounds)
            plt.savefig(os.path.join(self.config['fileio']['workdir'],
                                     '%s_%s_extension_yproj%s%s.png' % (
                                         prefix, name, esuffix, suffix)))
            plt.close(fig)
