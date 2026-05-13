"""Утилиты для работы с данными"""
import os
import json
from datetime import datetime


def ensure_data_dir(data_dir):
    """Создать директорию если не существует"""
    os.makedirs(data_dir, exist_ok=True)


def load_json_file(file_path, default=None):
    """Загрузить JSON файл или вернуть значение по умолчанию"""
    if default is None:
        default = {}
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default


def save_json_file(file_path, data):
    """Сохранить данные в JSON файл"""
    ensure_data_dir(os.path.dirname(file_path))
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_current_timestamp():
    """Получить текущую дату и время в формате YYYY-MM-DD HH:MM"""
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def get_full_timestamp():
    """Получить полную дату и время в формате YYYY-MM-DD HH:MM:SS"""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def load_users(users_file, hash_password_func):
    """Загрузить пользователей из JSON файла"""
    return load_json_file(users_file, default={
        "users": [{
            "id": 1,
            "username": "admin",
            "password_hash": hash_password_func("admin123"),
            "is_admin": True,
            "created_at": datetime.now().isoformat()
        }]
    })


def save_users(users_file, data):
    """Сохранить пользователей в JSON файл"""
    save_json_file(users_file, data)


def load_catalog(catalog_file):
    """Загрузить каталог из JSON файла"""
    return load_json_file(catalog_file, default={
        "name": "ВЕБ-РЕСУРСЫ МУЛЬТИМЕДИЙНОГО КОНТЕНТА ПО НАПРАВЛЕНИЯМ",
        "icon": "folder.png",
        "children": []
    })


def save_catalog(catalog_file, data):
    """Сохранить каталог в JSON файл"""
    save_json_file(catalog_file, data)


def load_permanent_items(permanent_file):
    """Загрузить постоянные элементы из JSON файла"""
    return load_json_file(permanent_file, default={"permanent_items": []})


def save_permanent_items(permanent_file, data):
    """Сохранить постоянные элементы в JSON файл"""
    save_json_file(permanent_file, data)
