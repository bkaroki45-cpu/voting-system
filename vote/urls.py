from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.student_register, name='register'),
    path('login/', views.student_login, name='login'),
    path('vote/', views.vote_page, name='vote_page'),
    path('vote/success/', views.vote_page, name='vote_success'),
    path('thank-you/', views.thank_you, name='thank_you'),
    path('already-voted/', views.already_voted, name='already_voted'),
    path('results/', views.results_page, name='results_page'),
]