from typing import Any, Dict
from bokeh.embed import components
import bokeh.resources
from django.views.generic import ListView, DetailView
from validation.models import Observation
from validation.plots import make_crossmatch_plots


class ObservationListView(ListView):
    model = Observation
    ordering = "-start_datetime"
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = context["page_obj"]
        context["page_range"] = page.paginator.get_elided_page_range(
            page.number, on_ends=1, on_each_side=1
        )
        return context


class ObservationDetailView(DetailView):
    model = Observation

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        observation = self.get_object()
        bokeh_version = bokeh.resources.__version__
        context["bokeh_version"] = bokeh_version
        context["bokeh_sri_hash"] = bokeh.resources.get_sri_hashes_for_version(
            bokeh_version
        )[f"bokeh-{bokeh_version}.min.js"]

        crossmatch_plots: Dict[str, Dict[str, Any]] = {}
        for crossmatch in observation.crossmatch_set.all():
            script, divs = components(make_crossmatch_plots(crossmatch))
            crossmatch_plots[crossmatch.reference_catalog] = {
                "script": script,
                "divs": divs,
            }
        context["crossmatch_plots"] = crossmatch_plots
        return context
