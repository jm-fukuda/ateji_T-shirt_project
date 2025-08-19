from django import template
from generator.models import KanjiMeaning
from django.utils.translation import get_language
from generator.views import get_or_create_kanji_meaning

register = template.Library()

@register.simple_tag
def meaning_from_parts(parts):
    lang = get_language().replace('_', '-').lower()
    meaning_list = []
    for part in parts:
        value = get_or_create_kanji_meaning(part, lang)
        if value:
            meaning_list.append(f"'{part}':{value}")
    return ', '.join(meaning_list)