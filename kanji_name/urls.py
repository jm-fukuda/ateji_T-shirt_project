"""
URL configuration for kanji_name project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import set_language, i18n_patterns
from generator import views
from django.contrib.auth import views as auth_views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('generator.urls')),
    path('i18n/setlang/', set_language, name='set_language'),
    path('accounts/login/', auth_views.LoginView.as_view(next_page='store_dashboard'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='store_dashboard'), name='logout'),
]

urlpatterns += i18n_patterns(
    path('', views.home, name='home'),  # トップ
    path('ateji/', views.ateji_form, name='ateji_form'),
    path('kanji_image/', views.kanji_image, name='kanji_image'),
    path('confirm_tshirt/', views.confirm_tshirt, name='confirm_tshirt'),
    path('tshirt_order/', views.tshirt_order, name='tshirt_order'),
)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
