from typing import Any, Dict
from bokeh.embed import components
from bokeh.layouts import row
import bokeh.resources
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import ListView, TemplateView
from django.views.generic.edit import UpdateView
from validation.forms import ValidationForm
from validation.models import Observation
from validation.plots import (
    make_crossmatch_plots,
    make_psf_plot,
    make_user_validation_progress_plot,
)


def login(request):
    return render(request, "validation/login.html")


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "validation/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # count the number of observations grouped by data quality
        # the .order_by() is required to clear the fields automatically added due to the
        # Observation.Meta.ordering setting.
        count_by_quality = (
            Observation.objects.order_by()
            .values("data_quality")
            .annotate(count=Count("pk"))
        )
        total_observations = count_by_quality.aggregate(total=Sum("count"))
        # sort the results by the order of the choices defined in Observation.ValidationState
        count_by_quality = sorted(
            count_by_quality,
            key=lambda d: Observation.ValidationState.values.index(d["data_quality"]),
        )

        # add the display colors and fractions
        for result in count_by_quality:
            result["color"] = Observation.ValidationState.get_color_class(
                result["data_quality"]
            )
            result["percentage"] = int(
                round(result["count"] / total_observations["total"] * 100)
            )

        # get the progress plot
        prog_plot_script, prog_plot_divs = components(
            row(
                make_user_validation_progress_plot(plot_width=None, plot_height=400),
                sizing_mode="stretch_width",
            )
        ) if len(count_by_quality) > 0 else "No observations in database.", ""

        context["observation_validation_counts"] = count_by_quality
        context["page_title"] = "VAST Validation - Dashboard"
        bokeh_version = bokeh.resources.__version__
        context["bokeh_version"] = bokeh_version
        context["bokeh_sri_hash"] = bokeh.resources.get_sri_hashes_for_version(
            bokeh_version
        )[f"bokeh-{bokeh_version}.min.js"]
        context["prog_plot"] = {
            "script": prog_plot_script,
            "divs": prog_plot_divs,
        }
        return context


class ObservationListView(LoginRequiredMixin, ListView):
    model = Observation
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = context["page_obj"]
        context["page_range"] = page.paginator.get_elided_page_range(
            page.number, on_ends=1, on_each_side=1
        )
        context["page_title"] = "VAST Validation - Observations"
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
            script, divs = components(
                make_crossmatch_plots(crossmatch, plot_width=300, plot_height=300)
            )
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
        context[
            "page_title"
        ] = f"VAST Validation - {observation.field.name} - SB{observation.sbid}"
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
    ordering = "start_datetime"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Pending Validation List"
        context["page_title"] = "VAST Validation - Pending"
        return context
