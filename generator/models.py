# generator/models.py

from django.db import models
import uuid

class PronounceName(models.Model):
    name = models.CharField(max_length=100, unique=True)
    reading = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class KanjiAteji(models.Model):
    name = models.CharField(max_length=100, unique=True)
    kanji_candidates_json = models.TextField()  # JSON文字列として保存
    meaning_parts = models.JSONField(default=list, blank=True)  # ["樹","志","天"] のように保持
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class KanjiMeaning(models.Model):
    char = models.CharField(max_length=10, unique=True, verbose_name="部品漢字")
    meaning = models.CharField(max_length=255, blank=True, verbose_name="意味（多言語化）")

    def __str__(self):
        return self.char


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kanji = models.CharField(max_length=32)
    reading = models.CharField(max_length=64, blank=True)
    meaning = models.TextField(blank=True)
    mode = models.CharField(max_length=10)
    font = models.CharField(max_length=50)
    size = models.CharField(max_length=10)                      # 追加: Tシャツサイズ (例: 'L')
    body_color = models.CharField(max_length=20, default='white')   # 追加: ボディカラー
    text_color = models.CharField(max_length=20, default='black')   # 追加: プリントカラー
    price = models.PositiveIntegerField(default=5000)            # 追加: 価格（円／税込）
    jan_code = models.CharField(max_length=13, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Order #{self.id}: {self.kanji}'


class TshirtSetting(models.Model):
    # ex. "XS (Chest 78cm)", "S (Chest 84cm)", etc
    size_choices = models.JSONField(default=list)  # 例: [{"code":"XS","label":"XS (Chest 78cm)"}]
    body_color_choices = models.JSONField(default=list)  # 例: ["white", "black", "red"]
    text_color_choices = models.JSONField(default=list)  # 例: ["black", "red", "blue"]
    price = models.PositiveIntegerField(default=5500)    # 税込金額
    jan_code_const = models.CharField(max_length=13, default="4901234567894")  # ★JANコード定数
    updated_at = models.DateTimeField(auto_now=True)


class PrintJob(models.Model):
    order_no = models.CharField(max_length=64, unique=True)
    kanji = models.CharField(max_length=32)
    reading = models.CharField(max_length=64)
    meaning = models.TextField()
    mode = models.CharField(max_length=10)
    font = models.CharField(max_length=50)
    size = models.CharField(max_length=32)
    body_color = models.CharField(max_length=20)
    text_color = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)


class BadWord(models.Model):
    word = models.CharField(max_length=64, unique=True)
    source = models.CharField(max_length=128, blank=True, default="internal")  # 取得元（手動/自動/AI等）
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
