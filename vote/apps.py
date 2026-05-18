from django.apps import AppConfig

class VoteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vote'

    def ready(self):
        from .background import start_results_notifier

        start_results_notifier()
