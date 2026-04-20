from django.apps import AppConfig


class ProvidersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.providers"
    verbose_name = "Prestadores"

    def ready(self) -> None:
        import apps.providers.signals  # noqa: F401 — registra os signals
