# generator/apps.py

from django.apps import AppConfig

class GeneratorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'generator'

    def ready(self):
        import generator.translation  # ここでimportして確実に読み込ませる
