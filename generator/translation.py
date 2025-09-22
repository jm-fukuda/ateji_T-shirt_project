# generator/translation.py

from modeltranslation.translator import translator, TranslationOptions
from .models import PronounceName, KanjiMeaning, Order, TshirtSetting, PrintJob

class PronounceNameTranslationOptions(TranslationOptions):
    fields = (
        'reading',
    )

class KanjiMeaningTranslationOptions(TranslationOptions):
    fields = (
        'meaning',
    )

class OrderTranslationOptions(TranslationOptions):
    fields = (
        'kanji',
        'reading',
        'meaning',
        'mode',
        'font',
        'size',
        'body_color',
        'text_color',
        # price等は数値なので不要
    )

class TshirtSettingTranslationOptions(TranslationOptions):
    # JSONFieldは多言語化しないのが一般的
    fields = ()

class PrintJobTranslationOptions(TranslationOptions):
    fields = (
        'kanji',
        'reading',
        'meaning',
        'mode',
        'font',
        'size',
        'body_color',
        'text_color',
        # order_no などID系は多言語不要
    )

translator.register(PronounceName, PronounceNameTranslationOptions)
translator.register(KanjiMeaning, KanjiMeaningTranslationOptions)
translator.register(Order, OrderTranslationOptions)
translator.register(TshirtSetting, TshirtSettingTranslationOptions)
translator.register(PrintJob, PrintJobTranslationOptions)
