from django import template
from django.utils.translation import get_language

register = template.Library()

@register.filter
def get_current_language(meaning_dict):
    lang = get_language()
    # キーの正規化（zh-hans/zh_Hans、en等）
    lang = lang.replace('_', '-').lower()
    if isinstance(meaning_dict, dict):
        # 完全一致
        if lang in meaning_dict:
            return meaning_dict[lang]
        # zh-hans <-> zh_Hansなどflexible対応
        for key in meaning_dict.keys():
            if key.replace('_', '-').lower() == lang:
                return meaning_dict[key]
        if 'en' in meaning_dict:
            return meaning_dict['en']
        return next(iter(meaning_dict.values()))
    else:
        return meaning_dict  # 元々strだった場合や旧データ
