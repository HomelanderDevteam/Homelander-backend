from django.urls import path

from . import views

app_name = "waitlist"

urlpatterns = [
    path("", views.WaitlistView.as_view(), name="join"),

]