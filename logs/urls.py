# logs/urls.py
from django.urls import path
from . import views

app_name = "logs"

urlpatterns = [
    path("upload/", views.upload_log, name="upload_log"),
    path("history/", views.upload_history, name="upload_history"),
]
