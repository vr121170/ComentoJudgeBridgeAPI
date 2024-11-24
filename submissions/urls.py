from django.urls import path
from .views import Judge0SubmissionView

urlpatterns = [
    path('submission', Judge0SubmissionView.as_view()),
]
