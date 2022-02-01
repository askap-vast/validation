"""vast_validation_site URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from rest_framework import routers
from validation.views import (
    DashboardView,
    ObservationListView,
    ObservationDetailView,
    ObservationViewSet,
    PendingValidationListView,
    PendingValidationAssignedListView,
    login,
)
import debug_toolbar


router = routers.DefaultRouter()
router.register(r"observations", ObservationViewSet)


urlpatterns = [
    path("", DashboardView.as_view()),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("observations/", ObservationListView.as_view(), name="observation-list"),
    path(
        "observations/<int:pk>/",
        ObservationDetailView.as_view(),
        name="observation-detail",
    ),
    path("pending/", PendingValidationAssignedListView.as_view(), name="pending-list"),
    path("pending/me", PendingValidationAssignedListView.as_view(), name="pending-list-me"),
    path("pending/all", PendingValidationListView.as_view(), name="pending-list-all"),
    path("login/", login, name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
    path("social-auth/", include("social_django.urls", namespace="social")),
    path("__debug__/", include(debug_toolbar.urls)),
    path("api/", include(router.urls)),
]
