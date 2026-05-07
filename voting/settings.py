"""
Django settings for voting project (Render-ready + Cloudinary media).
"""

import os
from pathlib import Path
import dj_database_url
import cloudinary

# ------------------------------
# Base directory
# ------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ------------------------------
# Security
# ------------------------------
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key')

DEBUG = True

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# ------------------------------
# Applications
# ------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'import_export',
    'vote.apps.VoteConfig',

    # Cloudinary (MEDIA STORAGE)
    'cloudinary',
    'cloudinary_storage',
]

# ------------------------------
# Middleware
# ------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'voting.urls'

# ------------------------------
# Templates
# ------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'voting.wsgi.application'

# ------------------------------
# DATABASE (POSTGRES ON RENDER / SQLITE LOCAL FALLBACK)
# ------------------------------
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

# ------------------------------
# PASSWORD VALIDATION
# ------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ------------------------------
# INTERNATIONALIZATION
# ------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# ------------------------------
# STATIC FILES
# ------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'vote' / 'static',
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ------------------------------
# MEDIA (CLOUDINARY - NO LOCAL MEDIA ISSUES)
# ------------------------------

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
}

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
)

# ------------------------------
# CSRF trusted origins
# ------------------------------
CSRF_TRUSTED_ORIGINS = [
    'https://voting-system-s9kz.onrender.com',
]

# ------------------------------
# AUTH BACKENDS
# ------------------------------
AUTHENTICATION_BACKENDS = [
    'vote.backends.AdmissionNumberBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# ------------------------------
# DEFAULT PK
# ------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'