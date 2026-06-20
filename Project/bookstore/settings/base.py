import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from .env in the project root
load_dotenv(BASE_DIR / '.env')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'huey.contrib.djhuey',
    'books',
]

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

ROOT_URLCONF = 'bookstore.urls'

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
                'books.context_processors.cart_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'bookstore.wsgi.application'

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Auth
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/login/'

# Ollama (Bookie Chatbot)
OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen2.5:3b')
OLLAMA_TIMEOUT = float(os.environ.get('OLLAMA_TIMEOUT', '60'))
OLLAMA_CONTEXT_TURNS = int(os.environ.get('OLLAMA_CONTEXT_TURNS', '6'))
OLLAMA_MAX_TOKENS = int(os.environ.get('OLLAMA_MAX_TOKENS', '256'))
OLLAMA_TEMPERATURE = float(os.environ.get('OLLAMA_TEMPERATURE', '0.2'))
OLLAMA_NUM_CTX = int(os.environ.get('OLLAMA_NUM_CTX', '2048'))

# Chatbot API protection
CHATBOT_RATE_LIMIT_REQUESTS = int(os.environ.get('CHATBOT_RATE_LIMIT_REQUESTS', '20'))
CHATBOT_RATE_LIMIT_WINDOW = int(os.environ.get('CHATBOT_RATE_LIMIT_WINDOW', '60'))
REGISTER_RATE_LIMIT_REQUESTS = int(os.environ.get('REGISTER_RATE_LIMIT_REQUESTS', '5'))
REGISTER_RATE_LIMIT_WINDOW = int(os.environ.get('REGISTER_RATE_LIMIT_WINDOW', '300'))
COUPON_RATE_LIMIT_REQUESTS = int(os.environ.get('COUPON_RATE_LIMIT_REQUESTS', '10'))
COUPON_RATE_LIMIT_WINDOW = int(os.environ.get('COUPON_RATE_LIMIT_WINDOW', '60'))
CHECKOUT_RATE_LIMIT_REQUESTS = int(os.environ.get('CHECKOUT_RATE_LIMIT_REQUESTS', '5'))
CHECKOUT_RATE_LIMIT_WINDOW = int(os.environ.get('CHECKOUT_RATE_LIMIT_WINDOW', '300'))
LOGIN_RATE_LIMIT_FAILED_ATTEMPTS = int(os.environ.get('LOGIN_RATE_LIMIT_FAILED_ATTEMPTS', '5'))
LOGIN_RATE_LIMIT_LOCKOUT_WINDOW = int(os.environ.get('LOGIN_RATE_LIMIT_LOCKOUT_WINDOW', '900'))

# Security settings
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Low stock alert threshold
LOW_STOCK_THRESHOLD = int(os.environ.get('LOW_STOCK_THRESHOLD', '10'))

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '[{levelname}] {asctime} {module} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'books': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
