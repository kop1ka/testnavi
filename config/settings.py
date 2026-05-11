"""Конфигурация приложения"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

CATALOG_FILE = os.path.join(DATA_DIR, 'catalog.json')
PERMANENT_FILE = os.path.join(DATA_DIR, 'permanent_items.json')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
PARSER_IMAGES_FILE = os.path.join(DATA_DIR, 'parser_images.json')

FTP_BASE_URL = 'https://vm-ftp.anosov.ru/vm/'
PARSER_MAX_DEPTH = 10
PARSER_TIMEOUT = 30

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

SESSION_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
PERMANENT_SESSION_LIFETIME = 3600

WTF_CSRF_ENABLED = True
WTF_CSRF_TIME_LIMIT = 3600

RATELIMIT_STORAGE_URI = "memory://"
RATELIMIT_DEFAULT = ["1000 per hour", "100 per minute"]
RATELIMIT_LOGIN = "10 per minute"
RATELIMIT_ENABLED = True

LOGIN_VIEW = 'login'
LOGIN_MESSAGE = 'Пожалуйста, войдите для доступа к этой странице'
SESSION_PROTECTION = 'strong'
