"""Isolated tests: never connect to the configured MySQL database."""
from .settings import *  # noqa: F403

# 테스트 전용 비밀 키
SECRET_KEY = 'test-only-secret-key'
# 테스트용 메모리 DB (MySQL 분리)
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
# 테스트 전용 고속 해시 (운영 사용 금지)
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
