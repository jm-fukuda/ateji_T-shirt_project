# generator/admin.py

from . import translation  # ← これが必須で一番最初！
from django.contrib import admin
from .models import PronounceName, KanjiAteji,KanjiMeaning, Order, TshirtSetting, PrintJob, BadWord
from modeltranslation.admin import TranslationAdmin

@admin.register(PronounceName)
class PronounceNameAdmin(TranslationAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)

@admin.register(KanjiAteji)
class KanjiAtejiAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)

@admin.register(KanjiMeaning)
class KanjiMeaningAdmin(TranslationAdmin):
    list_display = ('char', 'meaning',)
    search_fields = ('char', 'meaning')

@admin.register(Order)
class OrderAdmin(TranslationAdmin):
    list_display = ("id", "kanji", "reading", "mode", "size", "body_color", "text_color", "created_at")
    search_fields = ("kanji", "reading", "meaning")

@admin.register(TshirtSetting)
class TshirtSettingAdmin(admin.ModelAdmin):
    list_display = ("id", "price", "updated_at")

@admin.register(PrintJob)
class PrintJobAdmin(TranslationAdmin):
    list_display = ("order_no", "kanji", "reading", "mode", "size", "body_color", "text_color", "created_at")
    search_fields = ("kanji", "reading", "meaning", "order_no")

@admin.register(BadWord)
class BadWordAdmin(admin.ModelAdmin):
    list_display = ("word", "source", "created_at", "updated_at")
