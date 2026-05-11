"""Утилиты для работы с данными"""
import os
import json
from datetime import datetime


def ensure_data_dir(data_dir):
    os.makedirs(data_dir, exist_ok=True)


def load_json_file(file_path, default=None):
    if default is None:
        default = {}
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default


def save_json_file(file_path, data):
    ensure_data_dir(os.path.dirname(file_path))
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_current_timestamp():
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def get_full_timestamp():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
