from django.apps import apps
from django.db import connection
from django.test.runner import DiscoverRunner


class UnmanagedTablesRunner(DiscoverRunner):
    """The farm tables are created by database/schema.sql (managed=False); create them for tests."""

    def setup_databases(self, **kwargs):
        cfg = super().setup_databases(**kwargs)
        with connection.schema_editor() as se:
            for model in apps.get_app_config("farm").get_models():
                se.create_model(model)
        return cfg
