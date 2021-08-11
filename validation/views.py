from typing import Any, Dict
from bokeh.embed import components
import bokeh.resources
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import ListView
from django.views.generic.edit import UpdateView
from validation.forms import ValidationForm
from validation.models import Observation
from validation.plots import make_crossmatch_plots, make_psf_plot


def login(request):
    return render(request, "validation/login.html")


class ObservationListView(LoginRequiredMixin, ListView):
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


class ObservationDetailView(LoginRequiredMixin, UpdateView):
    model = Observation
    form_class = ValidationForm
    template_name = "validation/observation_detail.html"

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

        psf_plot_script, psf_plot_divs = components(
            make_psf_plot(
                observation, min_data_range=2, plot_width=200, plot_height=200
            )
        )
        context["psf_plot"] = {
            "script": psf_plot_script,
            "divs": psf_plot_divs,
        }
        return context

    def form_valid(self, form):
        form.instance.validator = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        next_observation = (
            Observation.objects.filter(
                data_quality=Observation.ValidationState.NOT_VALIDATED
            )
            .order_by("start_datetime")
            .first()
        )
        if next_observation is None:
            url = reverse("pending-list")
        else:
            url = next_observation.get_absolute_url()
        return url


class PendingValidationListView(ObservationListView):
    queryset = Observation.objects.filter(
        data_quality=Observation.ValidationState.NOT_VALIDATED
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Pending Validation List"
        return context
