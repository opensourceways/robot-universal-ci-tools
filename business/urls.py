from django.urls import path
from business.views import HealthCheckView, CommunityPRCIView


urlpatterns = [
    path('health', HealthCheckView.as_view()),
    path('review/', CommunityPRCIView.as_view()),
]
