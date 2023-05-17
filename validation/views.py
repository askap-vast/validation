import csv
from itertools import groupby
from operator import itemgetter
from typing import Any, Dict, List
from bokeh.embed import components
from bokeh.layouts import row
import bokeh.resources
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import ListView, TemplateView
from django.views.generic.edit import UpdateView
import django_filters.rest_framework
from rest_framework import viewsets
from validation.filters import ObservationFilter
from validation.forms import ValidationForm
from validation.models import Observation
from validation.plots import (
    make_crossmatch_plots,
    make_psf_plot,
    make_user_validation_progress_plot,
)
from validation.serializers import ObservationSerializer


# The default project code, used as a column when generating a CSV in the
# ObservationListCSVView class.
DEFAULT_PROJ_CODE = "AS207"


def login(request):
    return render(request, "validation/login.html")


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "validation/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Count the number of observations grouped by obs epoch and data quality.
        # The .order_by() is required to clear the fields automatically added due to the
        # Observation.Meta.ordering setting.
        qs = (
            Observation.objects.order_by()
            .values("observation_epoch", "data_quality")
            .annotate(count=Count("pk"))
            .order_by("-observation_epoch")
        )
        count_by_epoch_quality: Dict[int, List[Dict[str, Any]]] = {}
        for epoch, grouper in groupby(qs, key=itemgetter("observation_epoch")):
            # sort the results by the order of the choices defined in
            # Observation.ValidationState
            count_by_epoch_quality[epoch] = sorted(
                grouper,
                key=lambda d: Observation.ValidationState.values.index(
                    d["data_quality"]
                ),
            )
            # count total obs in epoch
            epoch_total_obs: int = sum(
                d["count"] for d in count_by_epoch_quality[epoch]
            )
            # add display colors and percentages to each data quality count result
            for epoch_quality_result in count_by_epoch_quality[epoch]:
                epoch_quality_result[
                    "color"
                ] = Observation.ValidationState.get_color_class(
                    epoch_quality_result["data_quality"]
                )
                epoch_quality_result["percentage"] = round(
                    epoch_quality_result["count"] / epoch_total_obs * 100, 1
                )
        """Example data for count_by_epoch_quality dict. Key is observation_epoch.
        {
            1: [
                {'data_quality': 'N', 'count': 4, 'color': 'yellow', 'percentage': 33},
                {'data_quality': 'U', 'count': 8, 'color': 'grey', 'percentage': 66},
            ],
        }
        """

        # get the progress plot
        num_validated = Observation.objects.exclude(
            data_quality=Observation.ValidationState.NOT_VALIDATED
        ).count()
        prog_plot_script, prog_plot_divs = (
            components(
                row(
                    make_user_validation_progress_plot(
                        plot_width=None, plot_height=400
                    ),
                    sizing_mode="stretch_width",
                )
            )
            if num_validated > 0
            else "No validated observations in database."
        )

        context["validation_count_by_epoch_quality"] = count_by_epoch_quality
        context["max_display_epochs"] = settings.DASHBOARD_MAX_DISPLAY_EPOCHS
        context["num_epochs_overflow"] = (
            len(count_by_epoch_quality) - context["max_display_epochs"]
        )
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
    paginate_by = settings.DEFAULT_PAGINATE_BY
    filterset_class = ObservationFilter

    def get_queryset(self):
        queryset = super().get_queryset()
        self.prefilter_count = queryset.count()
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = context["page_obj"]
        context["page_range"] = page.paginator.get_elided_page_range(
            page.number, on_ends=1, on_each_side=1
        )
        context["page_title"] = "VAST Validation - Observations"
        context["filterset"] = self.filterset
        context["prefilter_count"] = self.prefilter_count
        return context


class ObservationListCSVView(LoginRequiredMixin, ListView):
    """A View exporting and corresponding to the ObservationListView."""

    model = Observation
    paginate_by = settings.DEFAULT_PAGINATE_BY
    filterset_class = ObservationFilter

    def get_queryset(self):
        queryset = super().get_queryset()
        self.prefilter_count = queryset.count()
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = context["page_obj"]
        context["page_range"] = page.paginator.get_elided_page_range(
            page.number, on_ends=1, on_each_side=1
        )
        context["page_title"] = "VAST Validation - Observations"
        context["filterset"] = self.filterset
        context["prefilter_count"] = self.prefilter_count
        return context

    def get(self, *args, **kwargs):
        """Replaces the as_view() method to return an HTTP -> text/csv response
        rather than a webpage. Exports the current query set (as filtered
        through ObservationListView) to CSV, which is downloaded upon accessing
        this view.
        """
        # Assume the observation epoch is the epoch of the first observation in
        # the filtered queryset (change naming convention for future
        # implementations?)
        epoch = getattr(list(self.get_queryset())[0], "observation_epoch")
        filename = "_".join(["epoch", str(epoch), "validation.csv"])

        # Define the returned HTTP response to be in CSV text format
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="' + filename + '"'

        # The headers of the data table
        headers = ["SBID", "Project Code", "Quality Level", "Validation Notes"]

        # Write the headers to CSV
        writer = csv.writer(response)
        writer.writerow(headers)

        # Iterate over each observation in the filtered query set as found in
        # the ObservationListView
        for observation in self.get_queryset():
            # Create list representing one Observation to be written as a row in
            # a CSV with data corresponding to desired headers
            row = [
                getattr(observation, "sbid"),
                (
                    DEFAULT_PROJ_CODE
                    if kwargs.get("proj_code") is None
                    else kwargs["proj_code"]
                ),
                observation.get_data_quality_display().upper(),
                getattr(observation, "validation_comment").replace(",", ";"),
            ]

            # Write the populated row to the response CSV
            writer.writerow(row)

        # Return the CSV response - this sends the file to be downloaded
        return response


class PendingValidationListView(ObservationListView):
    queryset = Observation.objects.filter(
        data_quality=Observation.ValidationState.NOT_VALIDATED
    )
    ordering = "start_datetime"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Pending Validation List"
        context["page_title"] = "VAST Validation - Pending"

        context["user_pending_count"] = (
            self.get_queryset().filter(assigned_validator=self.request.user).count()
        )
        return context


class PendingValidationAssignedListView(PendingValidationListView):
    def get_queryset(self):
        return super().get_queryset().filter(assigned_validator=self.request.user)


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

        context["other_obs"] = observation.field.observation_set.exclude(
            pk=observation.pk
        ).order_by("observation_epoch")
        return context

    def form_valid(self, form):
        form.instance.validator = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        next_observation = (
            Observation.objects.filter(
                data_quality=Observation.ValidationState.NOT_VALIDATED,
                assigned_validator=self.request.user,
            )
            .order_by("start_datetime")
            .first()
        )
        if next_observation is None:
            url = reverse("pending-list-all")
            messages.success(
                self.request,
                "Well done! You have finished validating all pending observations that"
                " were assigned to you.",
            )
        else:
            url = next_observation.get_absolute_url()
        return url


class ObservationViewSet(viewsets.ModelViewSet):
    queryset = Observation.objects.all()
    serializer_class = ObservationSerializer
    filter_backends = [django_filters.rest_framework.DjangoFilterBackend]
    filterset_class = ObservationFilter
