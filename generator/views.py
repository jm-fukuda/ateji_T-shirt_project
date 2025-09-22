from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from .models import PronounceName, KanjiAteji, KanjiMeaning, Order, TshirtSetting, BadWord
from PIL import Image, ImageFont, ImageDraw
from django.http import HttpResponse
from urllib.parse import unquote
from io import BytesIO
import os
import openai
import json
import re
import qrcode
import base64
import barcode
import math
from barcode.writer import ImageWriter
from django.http import JsonResponse
from .models import PrintJob
from django.utils.translation import get_language, gettext as _
import ast
from django.contrib.auth.decorators import login_required
from kanji_name.settings import OPENAI_API_KEY
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.conf import settings



openai.api_key = OPENAI_API_KEY

PROMPT_TMPL = """
For the English name "{name}", create {count} patterns of Japanese kanji ateji (phonetic kanji representations) that mimic its pronunciation in Japanese Katakana.
For each ateji, provide:
- The kanji representation ("kanji")
- Its reading in Hiragana ("reading")
- A list of kanji parts ("parts"), containing each kanji character (or the original name for kana-only representations)

Format your response as the following JSON array:

[
  {"kanji": "kanji string", "reading": "hiragana reading", "parts": ["kanji1", "kanji2", ...]},
  ...
]

Example (for the name 'justin'):
[
  {"kanji": "じゃすてぃん", "reading": "じゃすてぃん", "parts": ["じゃすてぃん"]},
  {"kanji": "ジャスティン", "reading": "じゃすてぃん", "parts": ["ジャスティン"]},
  {"kanji": "樹志天", "reading": "じゃすてぃん", "parts": ["樹", "志", "天"]},
  ...
]
"""

FONT_CHOICES = {
    "ZenOldMincho": "ZenOldMincho-Black.ttf",                 # Google Fonts例
    "Kouzan": "衡山毛筆フォント.ttf",                          # 例：Kouzan font
    "YujiMai": "YujiMai-Regular.ttf",                    # Google Fonts例
}

FONT_DISPLAY_NAMES = {
    "ZenOldMincho": "1",
    "Kouzan": "2",
    "YujiMai": "3",
}

FONT_PATHS = {
    "Kouzan": "static/fonts/Kouzan.ttf",
    "ZenOldMincho": "static/fonts/ZenOldMincho-Black.ttf",
    "YujiMai": "static/fonts/YujiMai-Regular.ttf",
}

DEFAULT_FONT_PATH = "static/fonts/ZenOldMincho-Black.ttf"

DEFAULT_PRICE = 5500

DEFAULT_JAN_CODE = "4901234567894"

LANG_CHAR_RULES = {
    'ja': re.compile(r'^[\u3040-\u309f\u30a0-\u30ff\u3400-\u4dbf\u4e00-\u9fffー\- 　]+$'),  # ひらがな/カタカナ/漢字
    'en': re.compile(r"^[A-Za-z\-\' ]+$"),                  # ローマ字英字・アポストロフィ
    'fr': re.compile(r"^[A-Za-zÀ-ÿ\-\' ]+$"),               # フランス語名（拡張ラテン込み）
    'de': re.compile(r"^[A-Za-zÄÖÜäöüß\-\' ]+$"),           # ドイツ語名
    'es': re.compile(r"^[A-Za-zÁÉÍÓÚÜÑñáéíóúü\-\' ]+$"),    # スペイン語
    'it': re.compile(r"^[A-Za-zÀ-ÿ\-\' ]+$"),               # イタリア語
    'ko': re.compile(r"^[가-힣\-\' ]+$"),                   # 韓国語
    'ru': re.compile(r"^[А-Яа-яЁё\-\' ]+$"),                # ロシア語
    'zh-hans': re.compile(r"^[\u4e00-\u9fff]+$"),           # 汉字
    'zh-hant': re.compile(r"^[\u4e00-\u9fff]+$"),           # 漢字
    'sv': re.compile(r"^[A-Za-zÅÄÖåäö\-\' ]+$"),
    'nl': re.compile(r"^[A-Za-z\-\' ]+$"),
    'th': re.compile(r"^[\u0E00-\u0E7F\- ]+$"),             # タイ文字
}

LANG_NAME_LIMITS = {
    'ja': (1, 12),
    'en': (2, 12),
    'fr': (2, 12),
    'de': (2, 12),
    'es': (2, 12),
    'it': (2, 12),
    'ko': (1, 12),
    'nl': (2, 12),
    'ru': (2, 12),
    'sv': (2, 12),
    'th': (2, 12),
    'zh-hans': (1, 5),
    'zh-hant': (1, 5),
}

kana_type_dict = {
    "HIRAGANA": {
        "en": "HIRAGANA", "ja": "ひらがな", "fr": "HIRAGANA", "de": "HIRAGANA",
        "zh-hans": "平假名", "zh-hant": "平假名", "es": "hiragana", "it": "hiragana",
        "ru": "хирагана", "sv": "hiragana", "th": "ฮิรางานะ", "nl": "hiragana", "ko": "히라가나",
    },
    "KATAKANA": {
        "en": "KATAKANA", "ja": "カタカナ", "fr": "KATAKANA", "de": "KATAKANA",
        "zh-hans": "片假名", "zh-hant": "片假名", "es": "katakana", "it": "katakana",
        "ru": "катакана", "sv": "katakana", "th": "คาตากานะ", "nl": "katakana", "ko": "가타카나",
    }
}

def is_ng_word_ai_gpt(name):
    prompt = (
        f"Is the word/term '{name}' an inappropriate or offensive word in any language? "
        "Answer only yes or no. If yes, specify language and type (e.g., profanity, slur, insult, sexual, etc)."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an AI bad-word/profanity filter and language expert."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=20,
            temperature=0
        )
        answer = response['choices'][0]['message']['content'].lower()
        if "yes" in answer:
            return True, answer
        else:
            return False, ""
    except Exception as e:
        return False, ""

def smart_ng_check(name):
    if BadWord.objects.filter(word=name.lower()).exists():
        return True, "local"
    # AI・externalチェック
    is_bad, reason = is_ng_word_ai_gpt(name)
    if is_bad:
        BadWord.objects.create(word=name.lower(), source=f"gpt:{reason[:30]}")
        return True, "ai"
    # ローカル/外部リストの組み合わせで学習的に純化できる
    return False, ""

def validate_name(name):
    lang = get_language().replace('_','-').lower()
    lang = lang if lang in LANG_CHAR_RULES else 'en'

    # 1. NGワードチェック
    is_ng = smart_ng_check(name)[0]
    if is_ng:
        return True, _("The entered name contains an inappropriate word and cannot be used.")

    # 2. 文字数チェック
    min_len, max_len = LANG_NAME_LIMITS.get(lang, (2, 20))
    if not (min_len <= len(name) <= max_len):
        return True, _("Name must be between %(min)d and %(max)d characters for your language.") % {'min': min_len, 'max': max_len}

    # 3. 文字種チェック（選択された言語用パターン or 英語用パターンどちらかでOK）
    pattern_main = LANG_CHAR_RULES.get(lang, LANG_CHAR_RULES['en'])
    pattern_en = LANG_CHAR_RULES['en']
    # langがenの場合は1回、en以外なら両方チェック
    if not (pattern_main.fullmatch(name) or (lang != 'en' and pattern_en.fullmatch(name))):
        return True, _("Please use only allowed characters for your language (no symbols or inappropriate characters).")

    # 4. その他禁止（任意の追加ルール可）

    return False, ""  # エラーメッセージなし＝正常


@require_http_methods(["GET", "POST"])
def home(request):
    # トップページで言語切替だけ表示
    response = render(request, 'generator/home.html', {"on_top_page": False})
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response

import openai

LANG2LABEL = {
    'en': 'English',
    'ja': 'Japanese',
    'fr': 'French',
    'de': 'German',
    'zh-hans': 'Simplified Chinese',
    'zh-hant': 'Traditional Chinese',
    'es': 'Spanish',
    'it': 'Italian',
    'ko': 'Korean',
    'ru': 'Russian',
    'nl': 'Dutch',
    'sv': 'Swedish',
    'th': 'Thai',
}

def get_kana_from_name_by_gpt(name, lang):
    lang_label = LANG2LABEL.get(lang, lang)
    prompt = (
        f"Convert the name '{name}' to Japanese Hiragana, focusing on how a native {lang_label} speaker would pronounce it. "
        "Respond ONLY with the Japanese Hiragana (do not add any extra text)."
    )
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a Japanese linguist and name conversion expert."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=30,
        temperature=0
    )
    kana = response['choices'][0]['message']['content']
    kana = kana.strip().replace(' ', '')
    return kana

def get_kanji_candidates(name, num_candidates):
    lang = get_language().replace('_', '-').lower()
    field = f'reading_{lang.replace("-","_")}'
    pron, created = PronounceName.objects.get_or_create(name__iexact=name)
    reading_kana = getattr(pron, field, None)
    if not reading_kana:
        # ChatGPTで生成
        reading_kana = get_kana_from_name_by_gpt(name, lang)
        setattr(pron, field, reading_kana)
        pron.save(update_fields=[field])
    db_entry = KanjiAteji.objects.filter(name__iexact=reading_kana).first()
    if db_entry:
        candidates = json.loads(db_entry.kanji_candidates_json)
        cached = True
    else:
        prompt = PROMPT_TMPL.format(name=name, count=num_candidates)
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a naming assistant with extensive knowledge of the Japanese language."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1024,
            temperature=0.7
        )
        gpt_text = response['choices'][0]['message']['content']
        try:
            candidates = json.loads(gpt_text)
        except Exception:
            import re
            match = re.search(r'\[.*\]', gpt_text, re.DOTALL)
            if match:
                candidates = json.loads(match.group(0))
            else:
                candidates = []
        # ---- ここから補正処理 ----
        for c in candidates:
            if "parts" not in c:
                if all('\u3040' <= ch <= '\u309f' or ch in 'ー' for ch in c.get("kanji", "")):
                    # ひらがなonlyの場合
                    c["parts"] = [c.get("kanji", "")]
                elif all('\u30a0' <= ch <= '\u30ff' or ch in 'ー' for ch in c.get("kanji", "")):
                    # カタカナonlyの場合
                    c["parts"] = [c.get("kanji", "")]
                else:
                    # 漢字（やそれ以外）なら1文字ずつ分割
                    c["parts"] = list(c.get("kanji", ""))
        KanjiAteji.objects.create(
            name=name,
            kanji_candidates_json=json.dumps(candidates, ensure_ascii=False)
        )
        cached = False
    return candidates, cached


def kana_type_check(char):
    # 判定: ひらがな→"HIRAGANA"、カタカナ→"KATAKANA"
    if all('\u3040' <= c <= '\u309f' or c == 'ー' for c in char):  # ひらがな
        return "HIRAGANA"
    if all('\u30a0' <= c <= '\u30ff' or c == 'ー' for c in char):  # カタカナ
        return "KATAKANA"
    return None

def get_or_create_kanji_meaning(char, lang):
    kana_type = kana_type_check(char)
    if kana_type:
        # ひらがな or カタカナならローカライズラベルを返す
        return kana_type_dict[kana_type].get(lang, kana_type)    # lang→言語コード文字列（例："en"）
    field = f"meaning_{lang.replace('-', '_')}"
    try:
        m = KanjiMeaning.objects.get(char=char)
        value = getattr(m, field, "")
        if value:
            return value
    except KanjiMeaning.DoesNotExist:
        m = KanjiMeaning.objects.create(char=char)
    # なければChatGPTで取得
    gpt_meaning = ask_gpt_meaning(char, lang)
    setattr(m, field, gpt_meaning)
    m.save()
    return gpt_meaning

def ask_gpt_meaning(char, lang):
    lang_labels = {
        "en":"English",
        "ja":"Japanese",
        "fr":"French",
        "de":"German",
        "zh-hans":"Simplified Chinese",
        "zh-hant":"Traditional Chinese",
        "es":"Spanish", "it":"Italian",
        "ru":"Russian", "sv":"Swedish",
        "th":"Thai",
        "nl":"Dutch",
        "ko":"Korean",
    }
    system = "You are a professional Japanese kanji dictionary. Answer by giving only the short meaning for this single kanji in the requested language."
    prompt = f"What is a short, simple {lang_labels.get(lang, lang)} explanation of the Japanese character '{char}'? Respond only with the translation or meaning."
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=24,
        temperature=0
    )
    answer = response['choices'][0]['message']['content'].strip()
    return answer

"""
def get_meaning_dict(parts):
    # partsリストから全LANGUAGES分 meaning 辞書を組み立て
    from django.conf import settings
    LANGS = [lang[0] for lang in settings.LANGUAGES]
    meaning_dict = {}
    for lang in LANGS:
        field = f"meaning_{lang.replace('-','_')}"
        items = []
        for part in parts:
            try:
                mobj = KanjiMeaning.objects.get(char=part)
                label = getattr(mobj, field, "")
                if label:
                    items.append(f"'{part}':{label}")
            except KanjiMeaning.DoesNotExist:
                continue
        meaning_dict[lang] = ', '.join(items)
    return meaning_dict
"""

def get_meaning_string(parts, lang=None):
    if lang is None:
        lang = get_language().replace('_', '-').lower()
    meanings = []
    for part in parts:
        try:
            mobj = KanjiMeaning.objects.get(char=part)
            field = f"meaning_{lang.replace('-', '_')}"
            meaning = getattr(mobj, field, "")
            if meaning:
                meanings.append(f"'{part}':{meaning}")
        except KanjiMeaning.DoesNotExist:
            kana_type = kana_type_check(part)
            if kana_type:
                meanings.append(f"'{part}':{kana_type}")
            continue
    return ', '.join(meanings)

@require_http_methods(["GET", "POST"])
def ateji_form(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        num_candidates = request.POST.get('num_candidates', '3')
        mode = request.POST.get('mode', 'yoko')
        font = request.POST.get("font", "ZenOldMincho")
        return redirect(f"{request.path}?name={name}&num_candidates={num_candidates}&mode={mode}&font={font}")
    else:
        name = request.GET.get('name', '').strip()
        num_candidates = request.GET.get('num_candidates', '3')
        mode = request.GET.get('mode', 'yoko')
        font = request.GET.get("font", "ZenOldMincho")
    try:
        num_candidates = int(num_candidates) if num_candidates else 3
    except ValueError:
        num_candidates = 3
    error = None
    candidates = []
    cached = False
    if name:
        if validate_name(name)[0]:
            error = validate_name(name)[1]
        else:
            try:
                candidates, cached = get_kanji_candidates(name, num_candidates)
            except Exception as e:
                error = f'ERROR: {str(e)}'
    elif request.method == "POST":
        error = '名前を入力してください。'
    context = {
        'name': name,
        'num_candidates': num_candidates,
        'mode': mode,
        'font': font,
        'FONT_DISPLAY_NAMES': FONT_DISPLAY_NAMES,
        'candidates': candidates,
        'cached': cached,
        'error': error,
        'on_top_page': False,
    }
    response = render(request, "generator/ateji_form.html", context)
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


SMALL_KANA = (
    'ぁぃぅぇぉっゃゅょゎゕゖゝゞゟ'
    'ァィゥェォッャュョヮヵヶヽヾヿ'
)

def get_font_size_for_text(text, font_path, max_width, max_height, min_font_size=16, max_font_size=120, vertical=False):
    from PIL import Image, ImageDraw, ImageFont

    test_img = Image.new("RGB", (max_width, max_height))
    draw = ImageDraw.Draw(test_img)
    best_size = min_font_size
    left, right = min_font_size, max_font_size
    while left <= right:
        mid = (left + right) // 2
        font = ImageFont.truetype(font_path, mid)
        if not vertical:
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except Exception:
                w, h = draw.textsize(text, font=font)
        else:
            ws, hs = [], []
            for ch in text:
                if ch in ['ー', 'ｰ', '-']:
                    tmp_img = Image.new("RGBA", (max_width, max_height), (255,0,0,0))
                    tmp_draw = ImageDraw.Draw(tmp_img)
                    tmp_draw.text((0,0), ch, font=font, fill="black")
                    try:
                        bbox = tmp_draw.textbbox((0,0), ch, font=font)
                        w = bbox[3] - bbox[1]
                        h = bbox[2] - bbox[0]
                    except Exception:
                        w, h = draw.textsize(ch, font=font)
                        w, h = h, w
                    ws.append(w)
                    hs.append(h)
                else:
                    try:
                        bbox = draw.textbbox((0,0), ch, font=font)
                        ws.append(bbox[2] - bbox[0])
                        hs.append(bbox[3] - bbox[1])
                    except Exception:
                        w_, h_ = draw.textsize(ch, font=font)
                        ws.append(w_)
                        hs.append(h_)
            w = max(ws)
            h = sum(hs)
        if w <= max_width and h <= max_height:
            best_size = mid
            left = mid + 1
        else:
            right = mid - 1
    return best_size

def kanji_image(request):
    kanji = unquote(request.GET.get('kanji', '漢字'))
    width, height = 300, 300
    mode = request.GET.get('mode', 'yoko')
    font_code = request.GET.get('font', 'ZenOldMincho')
    bg_path = os.path.join('static', 'images', 'fashion_tshirt1_white.png')
    font_file = FONT_CHOICES.get(font_code, FONT_CHOICES["ZenOldMincho"])
    font_path = os.path.join('static', 'fonts', font_file)

    is_tate = mode == 'tate'
    chars = list(kanji)
    kanji_for_size = kanji

    font_size = get_font_size_for_text(kanji_for_size, font_path, width-190, height-190, 24, 120, vertical=is_tate)

    bg = Image.open(bg_path).convert("RGBA").resize((width, height))
    draw = ImageDraw.Draw(bg)
    font = ImageFont.truetype(font_path, font_size)

    if not is_tate:
        # 横書き
        try:
            bbox = draw.textbbox((0, 0), kanji, font=font)
            text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            text_width, text_height = draw.textsize(kanji, font=font)
        x = (width - text_width) // 2
        y = (height - text_height) // 3
        draw.text((x, y), kanji, font=font, fill="black")
    else:
        # 縦書き
        ws, hs, bboxes, small_indexes = [], [], [], []
        for ch in chars:
            try:
                bbox = draw.textbbox((0,0), ch, font=font)
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except Exception:
                w, h = draw.textsize(ch, font=font)
                bbox = (0, 0, w, h)
            # 長音符は事前に幅・高さを工夫（回転するため）
            if ch in ['ー', 'ｰ', '-']:
                ws.append(h)
                hs.append(w)
                small_indexes.append(False)
            else:
                ws.append(w)
                hs.append(h)
                small_indexes.append(ch in SMALL_KANA)
            bboxes.append(bbox)

        max_w = max(ws)
        total_h = sum(hs) + 10*(len(chars)-1)
        x = (width - max_w) // 2
        y = (height - total_h) // 3

        cursor_y = y
        for i, ch in enumerate(chars):
            w, h = ws[i], hs[i]
            bbox = bboxes[i]
            if ch in ['ー', 'ｰ', '-']:
                # 長音符は90度回転描画で中央
                base_w, base_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                char_img = Image.new('RGBA', (base_w, base_h), (0, 0, 0, 0))
                char_draw = ImageDraw.Draw(char_img)
                char_draw.text((-bbox[0], -bbox[1]), ch, font=font, fill="black")
                rotated_char_img = char_img.rotate(90, expand=True)
                rw, rh = rotated_char_img.size
                adjust_ratio = 1.95  # ここを1.5等で微調整可能
                rx = int((width - rw) / adjust_ratio)
                ry = cursor_y + int(hs[i] * 0.4)
                bg.paste(rotated_char_img, (rx, ry), rotated_char_img)
            elif small_indexes[i]:
                # 小書き文字: 右下寄せ
                sx = x + int(ws[i] * 0.2)
                sy = cursor_y - int(hs[i] * 0.4)
                draw.text((sx, sy), ch, font=font, fill="black")
            else:
                draw.text((x, cursor_y), ch, font=font, fill="black")
            cursor_y += h + 10

    response = HttpResponse(content_type="image/png")
    bg.save(response, "PNG")
    return response


@require_http_methods(["GET", "POST"])
def confirm_tshirt(request):
    from django.utils.translation import get_language
    if request.method == "POST":
        kanji = request.POST.get("kanji", "")
        reading = request.POST.get("reading", "")
        parts_str = request.POST.get("parts", "")    # "樹,志,天" のようなカンマ区切りかリスト

        # partsデータをリストにパース
        if parts_str.startswith('[') and parts_str.endswith(']'):
            # 文字列のリストの場合
            try:
                # まずjson.loadsでダメならliteral_eval
                try:
                    parts = json.loads(parts_str)
                except Exception:
                    parts = ast.literal_eval(parts_str)
            except Exception:
                parts = []
        elif ',' in parts_str:
            parts = [s.strip() for s in parts_str.split(',')]
        else:
            parts = [parts_str.strip()] if parts_str else []

        mode = request.POST.get("mode", "yoko")
        font = request.POST.get("font", "")
        name = request.POST.get("name", "")
        num_candidates = request.POST.get("num_candidates", "3")

        setting = TshirtSetting.objects.first()
        if not setting or not setting.size_choices:
            sizes = [["XS", "78"], ["S", "84"], ["M", "90"], ["L", "96"], ["XL", "102"], ["XXL", "108"]]
            body_colors = ["white", "black"]
            text_colors = ["black", "red"]
            price = 5000
        else:
            sizes = setting.size_choices
            body_colors = setting.body_color_choices
            text_colors = setting.text_color_choices
            price = setting.price

        # 現在言語
        lang = get_language().replace('_', '-').lower()
        meaning_str = get_meaning_string(parts, lang)

        context = {
            "kanji": kanji,
            "reading": reading,
            "parts": parts,
            "meaning_str": meaning_str,
            "mode": mode,
            "font": font,
            "name": name,
            "num_candidates": num_candidates,
            "sizes": sizes,
            "body_colors": body_colors,
            "text_colors": text_colors,
            "price": price,
            'on_top_page': False,
        }
        response = render(request, "generator/confirm_tshirt.html", context)
        response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
    else:
        return redirect('ateji_form')

@require_http_methods(["GET", "POST"])
def tshirt_order(request):
    if request.method == 'POST':
        kanji = request.POST.get('kanji', '')
        reading = request.POST.get('reading', '')
        parts_str = request.POST.get('parts', '')
        if parts_str.startswith('[') and parts_str.endswith(']'):
            try:
                # まずjson.loadsでダメならliteral_eval
                try:
                    parts = json.loads(parts_str)
                except Exception:
                    parts = ast.literal_eval(parts_str)
            except Exception:
                parts = ast.literal_eval(parts_str)
        elif ',' in parts_str:
            parts = [s.strip() for s in parts_str.split(',')]
        else:
            parts = [parts_str.strip()] if parts_str else []

        mode = request.POST.get('mode', '')
        font = request.POST.get('font', '')
        name = request.POST.get('name', '')
        num_candidates = request.POST.get('num_candidates', '3')
        size = request.POST.get('size', '')
        body_color = request.POST.get('body_color', '')
        text_color = request.POST.get('text_color', '')

        try:
            setting = TshirtSetting.objects.first()
            price = int(getattr(setting, "price", 5000))
        except:
            price = 5000

        lang = get_language().replace('_', '-').lower()  # ←現在の言語
        meaning_str = get_meaning_string(parts, lang)

        order = Order.objects.create(
            kanji=kanji,
            reading=reading,
            meaning=meaning_str,     # ←ここに「'樹':tree, '志':will/ambition, ...」が必ず入る
            mode=mode,
            font=font,
            size=size,
            body_color=body_color,
            text_color=text_color,
            price=price,
            jan_code=DEFAULT_JAN_CODE
        )

        order_url = f"{order.id}"

        # バーコード生成
        CODE = barcode.get('ean13', DEFAULT_JAN_CODE, writer=ImageWriter())
        barcode_buffer = BytesIO()
        CODE.write(
            barcode_buffer,
            options={
                'module_height': 15.0,
                'font_size': 10,
                'text_distance': 1,
                'module_width': 1.5,
                'write_text': False
            }
        )
        barcode_image_base64 = base64.b64encode(barcode_buffer.getvalue()).decode('utf-8')

        # QRコード内容にもmeaning_strを格納
        qr_content = {
            "order_no": order_url,
        }
        qr_json = json.dumps(qr_content, ensure_ascii=False)
        buf = BytesIO()
        qrcode.make(qr_json).save(buf, format='PNG')
        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        response = render(request, "generator/order_detail.html", {
            'order': order,
            'order_url': order_url,
            'qr_base64': img_base64,
            'qr_json': qr_json,
            'jan_code': DEFAULT_JAN_CODE,
            'barcode_base64': barcode_image_base64,
            'meaning_str': meaning_str,  # 表示用
            'parts': parts,              # テンプレで表示や確認用
            "on_top_page": False
        })
        response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
    else:
        return redirect('ateji_form')


@require_http_methods(["GET", "POST"])
@login_required
def admin_tshirt_settings(request):
    setting, created = TshirtSetting.objects.get_or_create(id=1)
    if request.method == 'POST':
        size_names = request.POST.getlist('size_name')
        chests = request.POST.getlist('chest')
        sizes = []
        for name, chest in zip(size_names, chests):
            # 空入力を除外
            if name.strip() and chest.strip():
                sizes.append([name.strip(), chest.strip()])
        body_colors = [c.strip() for c in request.POST.get('body_colors', '').split(',') if c.strip()]
        text_colors = [t.strip() for t in request.POST.get('text_colors', '').split(',') if t.strip()]
        price = int(request.POST.get('price', DEFAULT_PRICE))
        jan_code_const = request.POST.get('jan_code_const', DEFAULT_JAN_CODE)
        setting.size_choices = sizes
        setting.body_color_choices = body_colors
        setting.text_color_choices = text_colors
        setting.price = price
        setting.jan_code_const = jan_code_const
        setting.save()
        return redirect('admin_tshirt_settings')
    # ...デフォルト値セットは同様。最初は [["XS", "78"], ...] の形でsize_choicesを持つ...
    if not setting.size_choices:
        setting.size_choices = [["XS", "78"], ["S", "84"], ["M", "90"], ["L", "96"], ["XL", "102"], ["XXL", "108"]]
        setting.body_color_choices = ["white","black"]
        setting.text_color_choices = ["black","red"]
        setting.price = DEFAULT_PRICE
        setting.jan_code_const = DEFAULT_JAN_CODE
        setting.save()
    response = render(request, "admin_tshirt_settings.html", {
        "setting": setting,
        "on_top_page": False
        })
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


def get_best_font_size(text, font_path, img_w, img_h, vertical=False, margin=120, min_size=50, max_size=1000):
    # 二分探索で最大フォントサイズを求める
    left = min_size
    right = max_size
    best = min_size
    temp_img = Image.new("RGB", (img_w, img_h))
    draw = ImageDraw.Draw(temp_img)
    while left <= right:
        mid = (left + right) // 2
        font = ImageFont.truetype(font_path, mid)
        if not vertical:
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
            except AttributeError:
                bbox = (0, 0) + draw.textsize(text, font=font)
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
        else:
            widths = []
            heights = []
            for ch in text:
                try:
                    bbox = draw.textbbox((0, 0), ch, font=font)
                    w = bbox[2] - bbox[0]
                    h = bbox[3] - bbox[1]
                except AttributeError:
                    w, h = draw.textsize(ch, font=font)
                widths.append(w)
                heights.append(h)
            width = max(widths)
            height = sum(heights)
        # 上下左右margin px空ける
        if width <= img_w - 2*margin and height <= img_h - 2*margin:
            best = mid
            left = mid + 1
        else:
            right = mid - 1
    return best


SMALL_KANA = (
    'ぁぃぅぇぉっゃゅょゎゕゖゝゞゟ'
    'ァィゥェォッャュョヮヵヶヽヾヿ'
)

def get_best_font_size_tate(
    text, font_path, img_w, img_h, margin=120, min_size=50, max_size=1000, extra_ratio=0.2
):
    left = min_size
    right = max_size
    best = min_size
    temp_img = Image.new("RGB", (img_w, img_h))
    draw = ImageDraw.Draw(temp_img)
    while left <= right:
        mid = (left + right) // 2
        font = ImageFont.truetype(font_path, mid)
        heights = []
        max_width = 0
        for ch in text:
            try:
                bbox = draw.textbbox((0, 0), ch, font=font)
            except AttributeError:
                bbox = (0, 0) + draw.textsize(ch, font=font)
            if ch in ['ー', 'ｰ', '-']:
                h = bbox[2] - bbox[0]
                w = bbox[3] - bbox[1]
            else:
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
            heights.append(h)
            if w > max_width:
                max_width = w
        total_h = int(sum(h + math.ceil(h*extra_ratio) for h in heights))
        if max_width <= img_w - 2*margin and total_h <= img_h - 2*margin:
            best = mid
            left = mid + 1
        else:
            right = mid - 1
    return best

from io import BytesIO

@require_http_methods(["GET", "POST"])
@login_required
@csrf_exempt
def print_preview(request):
    if request.method == 'GET':
        response = render(request, 'print_preview.html', {"on_top_page": False})
        response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
    elif request.method == 'POST':
        try:
            reqdata = json.loads(request.body.decode())
            qr_json = reqdata.get("qr_json", "")
            qrdata = json.loads(qr_json)
            order_no = qrdata.get("order_no")
        except Exception as e:
            return JsonResponse({"error": "Invalid QR content or format."})

        # Orderデータをorder_no(=UUID)で検索
        try:
            order = Order.objects.get(id=order_no)  # もしくはorder_no=order_no等、該当モデルフィールドで
        except Order.DoesNotExist:
            return JsonResponse({"error": "Order data not found for the given QR code."})

        # 各値をorderから振り分けてqrdataへ
        qrdata = {
            "order_no": order_no,
            "kanji": order.kanji,
            "reading": order.reading,
            "meaning": order.meaning,
            "mode": order.mode,
            "font": order.font,
            "size": order.size,
            "body_color": order.body_color,
            "text_color": order.text_color,
            # partsや他フィールドも必要なら追加
        }

        # DB保存
        job, created = PrintJob.objects.update_or_create(
            order_no=qrdata["order_no"],
            defaults=dict(
                kanji=qrdata["kanji"],
                reading=qrdata["reading"],
                meaning=qrdata["meaning"],
                mode=qrdata["mode"],
                font=qrdata["font"],
                size=qrdata["size"],
                body_color=qrdata["body_color"],
                text_color=qrdata["text_color"],
            )
        )

        # 画像サイズと向き
        mode = qrdata.get("mode", "yoko")
        kanji = qrdata.get("kanji", "漢字")
        fontname = qrdata.get("font", "ZenOldMincho")
        font_path = FONT_PATHS.get(fontname, DEFAULT_FONT_PATH)
        text_color = qrdata.get("text_color","black")

        if mode == "tate":
            width, height = 2480, 3508  # 縦A4
            vertical = True
            best_font_size = get_best_font_size_tate(
                kanji, font_path, width, height, margin=100
            )
            font = ImageFont.truetype(font_path, best_font_size)
            img = Image.new("RGB", (width, height), "white")
            draw = ImageDraw.Draw(img)
            heights, widths, extra_spc, is_small, bboxes = [], [], [], [], []
            for ch in kanji:
                try:
                    bbox = draw.textbbox((0, 0), ch, font=font)
                except AttributeError:
                    bbox = (0, 0) + draw.textsize(ch, font=font)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                # 長音符は回転するためw,hを逆に記録
                if ch in ['ー', 'ｰ', '-']:
                    widths.append(h)
                    heights.append(w)
                else:
                    widths.append(w)
                    heights.append(h)
                extra_spc.append(math.ceil(h*0.2))
                is_small.append(ch in SMALL_KANA)
                bboxes.append(bbox)
            total_h = sum(h + sp for h,sp in zip(heights, extra_spc))

            # ====== 【ここ】上下マージンを十分設けて中央寄せ ======
            MARGIN_TOP = 0
            MARGIN_BOTTOM = 100  # 終端見切れ防止で多め
            usable_height = height - MARGIN_TOP - MARGIN_BOTTOM
            if total_h > usable_height:
                start_y = MARGIN_TOP
            else:
                start_y = MARGIN_TOP + int((usable_height - total_h) * 0.2)

            cursor_y = start_y
            for i, ch in enumerate(kanji):
                w, h, sp, bbox = widths[i], heights[i], extra_spc[i], bboxes[i]
                if ch in ['ー', 'ｰ', '-']:
                    # 長音符は90度回転
                    base_w, base_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    char_img = Image.new('RGBA', (base_w, base_h), (0, 0, 0, 0))
                    char_draw = ImageDraw.Draw(char_img)
                    char_draw.text((-bbox[0], -bbox[1]), ch, font=font, fill=text_color)
                    rotated_char_img = char_img.rotate(90, expand=True)
                    rw, rh = rotated_char_img.size
                    # 中央に配置（adjust_ratio微調整可）
                    adjust_ratio = 1.85
                    sx = int((width - rw) / adjust_ratio)
                    sy = cursor_y + int(rh * 0.3)
                    img.paste(rotated_char_img, (sx, sy), rotated_char_img)
                elif is_small[i]:
                    sx = (width - w) // 2 + int(w * 0.2)
                    sy = cursor_y - int(h * 0.4)
                    draw.text((sx, sy), ch, font=font, fill=text_color)
                else:
                    sx = (width - w) // 2
                    sy = cursor_y
                    draw.text((sx, sy), ch, font=font, fill=text_color)
                cursor_y += h + sp

            # --- 注文情報（90度回転）---
            info_font = ImageFont.truetype(font_path, 64)
            info_lines = [
                f"Order No: {qrdata.get('order_no','')}",
                f"Size: {qrdata.get('size','')} / Body: {qrdata.get('body_color','')} / Print: {qrdata.get('text_color','')}",
                f"Font: {qrdata.get('font','')}",
                f"Mode: {qrdata.get('mode','')}",
            ]
            info_text = "\n".join(info_lines)
            temp_img = Image.new("RGBA", (height, width), (255,255,255,0))
            temp_draw = ImageDraw.Draw(temp_img)
            padding = 50
            temp_draw.multiline_text((padding, padding), info_text, font=info_font, fill="gray", spacing=12)
            temp_img_rot = temp_img.rotate(90, expand=1)
            info_w, info_h = temp_img_rot.size
            pos_x = width - info_w - 40
            pos_y = height - info_h - 40
            img.paste(temp_img_rot, (pos_x, pos_y), temp_img_rot)
        else:
            width, height = 3508, 2480  # 横A4
            vertical = False
            best_font_size = get_best_font_size(kanji, font_path, width, height, vertical=vertical, margin=120)
            font = ImageFont.truetype(font_path, best_font_size)
            img = Image.new("RGB", (width, height), "white")
            draw = ImageDraw.Draw(img)
            try:
                bbox = draw.textbbox((0, 0), kanji, font=font)
            except AttributeError:
                bbox = (0, 0) + draw.textsize(kanji, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (width - text_width) // 2
            y = (height - text_height) * 0.3
            draw.text((x, y), kanji, font=font, fill=text_color)

            # 下部注文情報
            info_font = ImageFont.truetype(font_path, 64)
            info_lines = [
                f"Order No: {qrdata.get('order_no','')}",
                f"Size: {qrdata.get('size','')} / Body: {qrdata.get('body_color','')} / Print: {qrdata.get('text_color','')}",
                f"Font: {qrdata.get('font','')}",
                f"Mode: {qrdata.get('mode','')}",
            ]
            y_info = height - 400
            for line in info_lines:
                draw.text((160, y_info), line, font=info_font, fill="gray")
                y_info += 70

        buf = BytesIO()
        img.save(buf, format='PNG')
        preview_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return JsonResponse({"preview_base64": preview_base64})
    else:
        return JsonResponse({"error": "Method not allowed."})

@require_http_methods(["GET", "POST"])
@login_required
def store_dashboard(request):
    response=  render(request, "generator/store_dashboard.html", {"on_top_page": False})
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response
