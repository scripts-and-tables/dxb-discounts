from django.urls import path

from . import views


app_name = "discounts"

urlpatterns = [
    path("", views.program_list, name="list"),
    path("<slug:slug>/", views.program_detail, name="detail"),
]
