from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),

    # AUTH
    path('register/', views.student_register, name='register'),
    path('login/', views.student_login, name='login'),

    # VOTING
    path('vote/', views.vote_page, name='vote_page'),
    path('voice-vote/', views.voice_vote_view, name='voice_vote'),
    path('results/', views.results_page, name='results_page'),

    # FINAL RESULTS
    path('final-results/', views.final_results_page, name='final_results_page'),
    path('final-results/download/', views.download_final_results_pdf, name='download_final_results_pdf'),

    # SESSION CLOSED PAGE
    path('close/', views.close, name='close'),

    # USSD CALLBACK (IMPORTANT)
    path('ussd/', views.ussd_callback, name='ussd'),
]
