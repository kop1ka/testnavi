#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask Blueprint для "Парад Звёзд"
Интегрируется с основным приложением testnavi/app.py как дополнительный модуль
Обслуживает статические файлы и предоставляет API для управления данными
"""

import os
import json
from flask import Blueprint, request, jsonify, send_from_directory, current_app
from werkzeug.utils import secure_filename

# Создание Blueprint для интеграции с основным приложением
# url_prefix определяет путь, по которому будет доступен проект
parad_zvezd_bp = Blueprint(
    'parad_zvezd',
    __name__,
    static_folder='.',
    static_url_path=''  # Пустой путь, чтобы файлы обслуживались напрямую по префиксу blueprint
)

# Папка для хранения данных
DATA_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# Файлы данных
NOMINATIONS_FILE = os.path.join(DATA_FOLDER, 'nominations.json')
SCENARIOS_FILE = os.path.join(DATA_FOLDER, 'scenarios.json')

# Данные для авторизации
ADMIN_CREDENTIALS = {
    'username': 'admin',
    'password': 'anosov.museum'
}


def load_nominations():
    """Загрузка данных номинаций из файла"""
    if os.path.exists(NOMINATIONS_FILE):
        with open(NOMINATIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_nominations(data):
    """Сохранение данных номинаций в файл"""
    with open(NOMINATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_scenarios():
    """Загрузка данных сценариев из файла"""
    if os.path.exists(SCENARIOS_FILE):
        with open(SCENARIOS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_scenarios(data):
    """Сохранение данных сценариев в файл"""
    with open(SCENARIOS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==================== Статические файлы ====================

@parad_zvezd_bp.route('/')
def index():
    """Главная страница"""
    return send_from_directory('.', 'index.html')


@parad_zvezd_bp.route('/<path:filename>')
def serve_static(filename):
    """Обслуживание статических файлов"""
    return send_from_directory('.', filename)


# ==================== API Авторизация ====================

@parad_zvezd_bp.route('/api/login', methods=['POST'])
def login():
    """Вход для администратора"""
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')
    
    if username == ADMIN_CREDENTIALS['username'] and password == ADMIN_CREDENTIALS['password']:
        return jsonify({'success': True, 'message': 'Авторизация успешна'})
    else:
        return jsonify({'success': False, 'message': 'Неверный логин или пароль'}), 401


# ==================== API Номинации ====================

@parad_zvezd_bp.route('/api/nominations', methods=['GET'])
def get_all_nominations():
    """Получить все номинации"""
    data = load_nominations()
    return jsonify(data)


@parad_zvezd_bp.route('/api/nominations/<nomination_id>', methods=['GET'])
def get_nomination(nomination_id):
    """Получить записи конкретной номинации"""
    data = load_nominations()
    entries = data.get(nomination_id, [])
    return jsonify(entries)


@parad_zvezd_bp.route('/api/nominations/<nomination_id>', methods=['POST'])
def add_nomination_entry(nomination_id):
    """Добавить запись в номинацию"""
    data = load_nominations()
    
    if nomination_id not in data:
        data[nomination_id] = []
    
    entry = request.get_json()
    entry['id'] = str(len(data[nomination_id]) + 1)
    
    data[nomination_id].append(entry)
    save_nominations(data)
    
    return jsonify({'success': True, 'entry': entry})


@parad_zvezd_bp.route('/api/nominations/<nomination_id>/<entry_id>', methods=['PUT'])
def update_nomination_entry(nomination_id, entry_id):
    """Обновить запись в номинации"""
    data = load_nominations()
    
    if nomination_id not in data:
        return jsonify({'success': False, 'message': 'Номинация не найдена'}), 404
    
    entries = data[nomination_id]
    for i, entry in enumerate(entries):
        if entry.get('id') == entry_id:
            update_data = request.get_json()
            entries[i] = {
                'id': entry_id,
                'photo': update_data.get('photo', ''),
                'description': update_data.get('description', '')
            }
            save_nominations(data)
            return jsonify({'success': True, 'entry': entries[i]})
    
    return jsonify({'success': False, 'message': 'Запись не найдена'}), 404


@parad_zvezd_bp.route('/api/nominations/<nomination_id>/<entry_id>', methods=['DELETE'])
def delete_nomination_entry(nomination_id, entry_id):
    """Удалить запись из номинации"""
    data = load_nominations()
    
    if nomination_id not in data:
        return jsonify({'success': False, 'message': 'Номинация не найдена'}), 404
    
    entries = data[nomination_id]
    data[nomination_id] = [e for e in entries if e.get('id') != entry_id]
    save_nominations(data)
    
    return jsonify({'success': True})


# ==================== API Сценарии ====================

@parad_zvezd_bp.route('/api/scenarios', methods=['GET'])
def get_scenarios():
    """Получить все сценарии"""
    data = load_scenarios()
    return jsonify(data)


@parad_zvezd_bp.route('/api/scenarios', methods=['POST'])
def add_scenario():
    """Добавить сценарий"""
    data = load_scenarios()
    
    scenario = request.get_json()
    scenario['id'] = str(len(data) + 1)
    
    data.append(scenario)
    save_scenarios(data)
    
    return jsonify({'success': True, 'scenario': scenario})


@parad_zvezd_bp.route('/api/scenarios/<scenario_id>', methods=['DELETE'])
def delete_scenario(scenario_id):
    """Удалить сценарий"""
    data = load_scenarios()
    data = [s for s in data if s.get('id') != scenario_id]
    save_scenarios(data)
    
    return jsonify({'success': True})
