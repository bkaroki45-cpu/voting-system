from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.student_register, name='register'),
    path('login/', views.student_login, name='login'),
    path('vote/', views.vote_page, name='vote_page'),
    path('results/', views.results_page, name='results_page'),
    path('close/', views.close, name='close'),
    path('final_results/', views.final_results_page, name='final_results_page'),
]