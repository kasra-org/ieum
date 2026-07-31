"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
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
from main.apis import api
from main.views import nicepay_callback

from django.conf import settings

urlpatterns = [
    path('api/', api.urls),
    # NicePay posts the authentication result here from the payer's browser.
    # Kept outside the Ninja API because it is a cross-site, CSRF-exempt,
    # form-encoded POST that responds with a redirect rather than JSON.
    path('nicepay/callback', nicepay_callback, name='nicepay_callback'),
    path(f'{settings.ADMIN_PAGE_NAME}/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('_allauth/', include('allauth.headless.urls')),
]
