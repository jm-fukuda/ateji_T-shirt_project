# generator/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  # トップ
    path('ateji/', views.ateji_form, name='ateji_form'),
    path('kanji_image/', views.kanji_image, name='kanji_image'),
    path('confirm_tshirt/', views.confirm_tshirt, name='confirm_tshirt'),
    path('tshirt_order/', views.tshirt_order, name='tshirt_order'),
    path('store/', views.store_dashboard, name='store_dashboard'),
    path('store/admin_tshirt_settings/', views.admin_tshirt_settings, name='admin_tshirt_settings'),
    path('store/print_preview/', views.print_preview, name='print_preview'),
    ]
