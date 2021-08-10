from typing import Optional, Tuple
from astropy.coordinates import SkyCoord
from astropy.io.fits import getheader
from bokeh.palettes import Magma256
from bokeh.plotting import figure, Figure
from bokeh.models import (
    BoxAnnotation,
    ColumnDataSource,
    ColorBar,
    DataRange1d,
    Label,
    Span,
    Slope,
    Whisker,
)
from bokeh.transform import log_cmap
import pandas as pd
import numpy as np

from validation.models import Crossmatch

DEFAULT_TOOLS = ["pan,box_zoom,wheel_zoom,box_select,lasso_select,save,reset"]


def _make_astrometry_plot(
    source: ColumnDataSource,
    hue_column: Optional[str] = "ASKAP_flux",
    pixel_size: Optional[Tuple[float, float]] = None,
    plot_width: int = 400,
    plot_height: int = 400,
):
    coords_vast = SkyCoord(ra=source.data["RA"], dec=source.data["DEC"], unit="deg")
    coords_racs = SkyCoord(
        ra=source.data["RA_comp"], dec=source.data["DEC_comp"], unit="deg"
    )
    dra, ddec = coords_vast.spherical_offsets_to(coords_racs)
    source.data["dra_arcsec"] = dra.arcsec
    source.data["ddec_arcsec"] = ddec.arcsec

    # set the data range such that (0, 0) is centered and the aspect ratio is 1
    max_offset = max(
        abs(min(source.data["dra_arcsec"].min(), source.data["ddec_arcsec"].min())),
        abs(max(source.data["dra_arcsec"].max(), source.data["ddec_arcsec"].max())),
    )
    # if a pixel size is given, make sure the data range is set to always include it
    if pixel_size:
        max_offset = max(max_offset, *[x / 2 for x in pixel_size])
    max_offset = max_offset + (max_offset * 0.05)
    data_range = DataRange1d(start=-max_offset, end=max_offset)

    fig_pos = figure(
        frame_width=plot_width,
        frame_height=plot_height,
        toolbar_location="above",
        x_range=data_range,
        y_range=data_range,
        x_axis_label="RA offset (arcsec)",
        y_axis_label="Dec offset (arcsec)",
        tools=DEFAULT_TOOLS,
    )
    # color points by flux on a log scale if flux if requested (not possible for ICRF)
    if hue_column:
        cmap = log_cmap(
            "ASKAP_flux",
            list(reversed(Magma256)),
            low=source.data["ASKAP_flux"].min(),
            high=source.data["ASKAP_flux"].max(),
        )
        style = {"color": cmap}
    else:
        style = {}
    fig_pos.dot(x="dra_arcsec", y="ddec_arcsec", size=20, source=source, **style)

    # add median annotation
    dra_median = np.median(source.data["dra_arcsec"])
    ddec_median = np.median(source.data["ddec_arcsec"])
    ann_dra_median = Whisker(
        dimension="width",
        base=ddec_median,
        lower=dra_median - source.data["dra_arcsec"].std(),
        upper=dra_median + source.data["dra_arcsec"].std(),
        level="annotation",
        line_width=2,
    )
    ann_ddec_median = Whisker(
        dimension="height",
        base=dra_median,
        lower=ddec_median - source.data["ddec_arcsec"].std(),
        upper=ddec_median + source.data["ddec_arcsec"].std(),
        level="annotation",
        line_width=2,
    )
    fig_pos.add_layout(ann_dra_median)
    fig_pos.add_layout(ann_ddec_median)

    # add stats labels
    label_stats = Label(
        text=(
            f"({dra_median:.1f} ± {source.data['dra_arcsec'].std():.1f},"
            f" {ddec_median:.1f} ± {source.data['ddec_arcsec'].std():.1f})"
        ),
        x=plot_width,
        y=plot_height,
        x_units="screen",
        y_units="screen",
        text_align="right",
        text_baseline="top",
        x_offset=-plot_width * 0.05,
        y_offset=-plot_height * 0.05,
        background_fill_color="white",
        background_fill_alpha=0.8,
        level="overlay",
    )
    fig_pos.add_layout(label_stats)

    # add a crosshair at (0, 0) to guide the eye
    ann_crosshair_ra = Span(
        location=0, dimension="width", line_color="#333", line_width=0.5
    )
    ann_crosshair_dec = Span(
        location=0, dimension="height", line_color="#333", line_width=0.5
    )
    fig_pos.add_layout(ann_crosshair_ra)
    fig_pos.add_layout(ann_crosshair_dec)

    # add the ASKAP pixel annotation
    if pixel_size:
        x, y = pixel_size
        x /= 2
        y /= 2
        ann_pixel = BoxAnnotation(
            left=-x,
            right=x,
            bottom=-y,
            top=y,
            line_color="black",
            line_width=2,
            line_dash="dashed",
            line_alpha=1.0,
            fill_color=None,
        )
        fig_pos.add_layout(ann_pixel)

    # add a colorbar
    if hue_column:
        cbar = ColorBar(
            color_mapper=cmap["transform"],
            title="Flux density (mJy)",
            title_standoff=-120,
        )
        fig_pos.add_layout(cbar, "right")
    return fig_pos


def _make_flux_plot(
    source: ColumnDataSource, crossmatch: Crossmatch, alpha: float = -0.8, plot_width: int = 400,
    plot_height: int = 400,
):
    # calculate the plot range such that the aspect ratio is 1 and the min/max are the
    # nearest powers of 10
    min_flux = min(source.data["ASKAP_flux"].min(), source.data["Comp_flux"].min())
    max_flux = max(source.data["ASKAP_flux"].max(), source.data["Comp_flux"].max())
    data_range = DataRange1d(
        start=10 ** np.floor(np.log10(min_flux)), end=10 ** np.ceil(np.log10(max_flux))
    )

    fig_flux = figure(
        frame_width=plot_width,
        frame_height=plot_height,
        toolbar_location="above",
        x_range=data_range,
        y_range=data_range,
        x_axis_label="ASKAP flux (mJy)",
        y_axis_label=f"{crossmatch.reference_catalog.name} flux (mJy)",
        x_axis_type="log",
        y_axis_type="log",
        tools=DEFAULT_TOOLS,
    )
    fig_flux.dot(x="ASKAP_flux", y="Comp_flux", size=20, source=source)

    # add the y=x slope to guide the eye
    ann_equality = Slope(
        gradient=1, y_intercept=0, line_color="#333", line_width=0.5, line_dash="dashed"
    )
    fig_flux.add_layout(ann_equality)

    # add a spectral index correction slope
    ann_alpha = Slope(
        gradient=(
            crossmatch.observation.field.frequency_MHz
            / crossmatch.reference_catalog.frequency_MHz
        )
        ** -alpha,
        y_intercept=0,
        line_color="red",
        line_width=1,
    )
    fig_flux.add_layout(ann_alpha)
    # label the slope
    label_slope = Label(
        text=f"alpha = {alpha:.2f}",
        x=plot_width,
        y=plot_height,
        x_units="screen",
        y_units="screen",
        text_align="right",
        text_baseline="top",
        text_color="red",
        x_offset=-plot_width * 0.05,
        y_offset=-plot_height * 0.05,
        background_fill_color="white",
        background_fill_alpha=0.8,
        level="overlay",
    )
    fig_flux.add_layout(label_slope)

    return fig_flux


def make_crossmatch_plots(catalog: Crossmatch) -> Tuple[Figure, ...]:
    source = ColumnDataSource(data=pd.read_csv(catalog.file_path))
    do_flux_plot = catalog.reference_catalog.frequency_MHz is not None
    hue_column = "ASKAP_flux" if do_flux_plot else None

    # get pixel size
    fits_header = getheader(catalog.observation.image_path)
    pix_ra_arcsec = fits_header["CDELT1"] * 3600
    pix_dec_arcsec = fits_header["CDELT2"] * 3600
    astrometry_plot = _make_astrometry_plot(
        source, hue_column=hue_column, pixel_size=(pix_ra_arcsec, pix_dec_arcsec)
    )
    if do_flux_plot:
        flux_plot = _make_flux_plot(source, catalog)
        return (astrometry_plot, flux_plot)
    else:
        return (astrometry_plot,)
