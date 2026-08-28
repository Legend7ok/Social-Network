from django.apps import AppConfig


class ActionsConfig(AppConfig):
    name = "apps.actions"

    def ready(self):
        import apps.actions.signals  # noqa: F401
