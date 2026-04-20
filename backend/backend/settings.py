import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path, encoding="utf-8-sig", override=True)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'security_app',

    'rest_framework',
    'django_extensions',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'threatdb'),
        'USER': os.getenv('DB_USER', 'admin'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'admin'),
        'HOST': os.getenv('DB_HOST', 'postgres'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

KAFKA_CONFIG = {
    'BOOTSTRAP_SERVERS': os.getenv('KAFKA_SERVERS', 'localhost:9092').split(','),
    'TOPIC_INCIDENTS': 'incidents-source',
    'TOPIC_GENERATED': 'incidents-generated',
}

TIME_ZONE = 'Europe/Moscow'
USE_TZ = True
LANGUAGE_CODE = 'ru-ru'