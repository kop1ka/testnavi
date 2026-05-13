"""
Flask приложение для управления мультимедийным контентом
с парсером FTP-каталога и возможностью сохранения постоянных элементов
С системой авторизации и защиты

Структура проекта:
- app.py: Основной файл приложения (маршруты, контроллеры)
- config/: Конфигурация приложения
    - settings.py: Все настройки и константы приложения
- utils/: Утилиты и вспомогательные функции
    - data_utils.py: Работа с данными (загрузка/сохранение JSON)
    - parser_utils.py: Парсинг FTP-каталога
    - auth_utils.py: Аутентификация и пользователи
    - catalog_utils.py: Работа с каталогом (поиск, обновление, удаление)
"""

import os
import json
import re
import threading
import requests
from datetime import datetime, timedelta
from urllib.parse import unquote, urlparse
from flask import Flask, render_template_string, request, jsonify, send_from_directory, redirect, url_for, session, flash, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Импорт конфигурации из модуля settings
from config.settings import (
    DATA_DIR, CATALOG_FILE, PERMANENT_FILE, USERS_FILE, PARSER_IMAGES_FILE, SECRET_KEY,
    FTP_BASE_URL, PARSER_MAX_DEPTH, PARSER_TIMEOUT,
    RATELIMIT_STORAGE_URI, RATELIMIT_DEFAULT, RATELIMIT_LOGIN, RATELIMIT_ENABLED,
    LOGIN_VIEW, LOGIN_MESSAGE, SESSION_PROTECTION
)

# Директория для проектов
PROJECTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'projects')

# Словарь для хранения информации о проектах Flask
project_flask_info = {}

# Импорт утилит для работы с данными, парсингом, аутентификацией и каталогом
from utils.data_utils import (
    ensure_data_dir, load_json_file, save_json_file, get_current_timestamp, get_full_timestamp,
    load_users, save_users, load_catalog, save_catalog, load_permanent_items, save_permanent_items
)
from utils.parser_utils import extract_items_from_html, parse_folder
from utils.auth_utils import User, hash_password, verify_password, admin_required_decorator
from utils.catalog_utils import (
    get_item_path, mark_permanent_recursive, merge_with_permanent,
    find_item_by_path, delete_item_by_path, update_item_by_path
)

# Инициализация Flask приложения
# static_folder='.' указывает, что статические файлы находятся в корневой директории
# static_url_path='' позволяет обращаться к файлам напрямую по имени
app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = SECRET_KEY  # Использование секретного ключа из конфига для сессий

# Настройка CORS заголовков для всех ответов (необходимо для работы на render.com и других хостингах)
@app.after_request
def add_cors_headers(response):
    """Добавляет CORS заголовки для поддержки跨源 запросов"""
    # Разрешаем запросы с любых источников (можно ограничить при необходимости)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    
    # Добавляем правильные MIME-типы для статических файлов
    if response.headers.get('Content-Type', '').startswith('text/plain') or not response.headers.get('Content-Type'):
        if request.path.endswith('.css'):
            response.headers['Content-Type'] = 'text/css; charset=utf-8'
        elif request.path.endswith('.js'):
            response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
        elif request.path.endswith('.png'):
            response.headers['Content-Type'] = 'image/png'
        elif request.path.endswith('.jpg') or request.path.endswith('.jpeg'):
            response.headers['Content-Type'] = 'image/jpeg'
        elif request.path.endswith('.gif'):
            response.headers['Content-Type'] = 'image/gif'
        elif request.path.endswith('.webp'):
            response.headers['Content-Type'] = 'image/webp'
        elif request.path.endswith('.svg'):
            response.headers['Content-Type'] = 'image/svg+xml'
        elif request.path.endswith('.html'):
            response.headers['Content-Type'] = 'text/html; charset=utf-8'
    
    return response

# Инициализация расширений Flask
csrf = CSRFProtect(app)  # Защита от CSRF атак

# Отключаем rate limiting для статических файлов (изображения, CSS, JS) и API прокси
def limiter_enabled():
    """Проверка, включен ли rate limiting для текущего запроса"""
    # Не применяем rate limiting к статическим файлам и proxy-image endpoint
    if request.path.startswith('/page/') or request.path.startswith('/static/') or request.path.startswith('/projects/') or request.path.startswith('/css/') or request.path.startswith('/js/') or request.path == '/api/proxy-image':
        return False
    return RATELIMIT_ENABLED

limiter = Limiter(
    key_func=get_remote_address,  # Ограничение по IP адресу
    app=app,
    default_limits=RATELIMIT_DEFAULT,  # Ограничения по умолчанию из конфига
    storage_uri=RATELIMIT_STORAGE_URI,  # Хранилище счётчиков в памяти
    enabled=limiter_enabled  # Динамическое включение/отключение
)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = LOGIN_VIEW  # Маршрут для перенаправления неавторизованных
login_manager.login_message = LOGIN_MESSAGE  # Сообщение при перенаправлении
login_manager.session_protection = SESSION_PROTECTION  # Уровень защиты сессии

# Глобальная переменная для хранения статуса парсера
parser_status = {'running': False, 'last_run': None, 'message': 'Парсер не запущен', 'images': []}


@login_manager.user_loader
def load_user(user_id):
    """
    Callback функция для загрузки пользователя по ID (требуется Flask-Login)
    
    Вызывается автоматически Flask-Login при работе с сессиями.
    
    Args:
        user_id (str): Идентификатор пользователя из сессии
    
    Returns:
        User or None: Объект пользователя или None если не найден
    """
    users_data = load_users(USERS_FILE, hash_password)
    for user in users_data.get('users', []):
        if str(user['id']) == str(user_id):
            return User(user['id'], user['username'], user.get('is_admin', False))
    return None


def run_parser_task():
    """
    Фоновая задача парсинга FTP-каталога
    
    Выполняется в отдельном потоке для неблокирующей работы.
    Обновляет глобальную переменную parser_status для отображения прогресса.
    Сохраняет найденные изображения в файл для постоянного доступа.
    НЕ сбрасывает уже сохранённые изображения - добавляет только новые.
    """
    global parser_status
    try:
        parser_status['running'] = True
        parser_status['message'] = 'Парсинг запущен...'
        
        # Загрузить уже сохранённые изображения, чтобы не потерять их
        existing_images_data = load_json_file(PARSER_IMAGES_FILE, {'images': []})
        existing_images = set(existing_images_data.get('images', []))
        
        # Запустить парсинг FTP-каталога
        items = parse_folder(FTP_BASE_URL, max_depth=PARSER_MAX_DEPTH, timeout=PARSER_TIMEOUT)
        
        # Собрать все найденные изображения из парсера
        new_parser_images = []
        def collect_images(items_list):
            for item in items_list:
                # Проверяем, является ли элемент файлом изображения (у файлов children=None)
                if item.get('children') is None:
                    # Это файл - проверяем расширение
                    url = item.get('url', '')
                    if url and (url.lower().endswith('.png') or url.lower().endswith('.jpg') or 
                                url.lower().endswith('.jpeg') or url.lower().endswith('.gif') or 
                                url.lower().endswith('.webp')):
                        if url not in new_parser_images:
                            new_parser_images.append(url)
                else:
                    # Это папка - рекурсивно обрабатываем детей
                    if item.get('children'):
                        collect_images(item['children'])
        
        collect_images(items)
        
        # Объединить с существующими изображениями (сохраняем старые + добавляем новые)
        all_images = list(existing_images)
        for img_url in new_parser_images:
            if img_url not in existing_images:
                all_images.append(img_url)
        
        # Сохранить все изображения в файл для постоянного доступа
        save_json_file(PARSER_IMAGES_FILE, {'images': all_images})
        
        # Обновить статус парсера с новыми изображениями
        parser_status['images'] = all_images
        
        # Загрузить постоянные элементы
        permanent_items = load_permanent_items(PERMANENT_FILE)
        permanent_paths = set(permanent_items.get('permanent_items', []))
        
        # Загрузить существующий каталог
        existing_catalog = load_catalog(CATALOG_FILE)
        existing_children = existing_catalog.get('children', [])
        
        # Объединить новые данные с существующими, сохраняя постоянные элементы
        merged_children = merge_with_permanent(items, existing_children, permanent_paths)
        
        # Сохранить обновлённый каталог
        existing_catalog['children'] = merged_children
        existing_catalog['modified'] = get_current_timestamp()
        save_catalog(CATALOG_FILE, existing_catalog)
        
        # Обновить статус парсера
        parser_status['last_run'] = get_full_timestamp()
        parser_status['message'] = f'Парсинг завершён успешно. Найдено элементов: {len(items)}. Всего изображений: {len(all_images)}'
        
    except Exception as e:
        parser_status['message'] = f'Ошибка парсинга: {str(e)}'
    finally:
        parser_status['running'] = False


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit(RATELIMIT_LOGIN)  # Ограничение частоты запросов для защиты от брутфорса
def login():
    """
    Страница входа в систему
    
    Обрабатывает GET (отображение формы) и POST (аутентификация) запросы.
    
    Returns:
        Response: HTML страница входа или редирект на главную
    """
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        if not username or not password:
            error = 'Введите имя пользователя и пароль'
        else:
            users_data = load_users(USERS_FILE, hash_password)
            user_found = None
            for user in users_data.get('users', []):
                if user['username'] == username:
                    user_found = user
                    break
            
            if user_found and verify_password(password, user_found['password_hash']):
                user_obj = User(user_found['id'], user_found['username'], user_found.get('is_admin', False))
                login_user(user_obj, remember=remember)
                next_page = request.args.get('next')
                flash('Вы успешно вошли в систему', 'success')
                return redirect(next_page if next_page else url_for('admin'))
            else:
                error = 'Неверное имя пользователя или пароль'
    
    return render_template_string('''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Вход в систему</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            width: 100%;
            max-width: 400px;
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
            font-size: 24px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: bold;
        }
        input[type="text"],
        input[type="password"] {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 5px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input[type="text"]:focus,
        input[type="password"]:focus {
            outline: none;
            border-color: #667eea;
        }
        .checkbox-group {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
        }
        .checkbox-group input {
            margin-right: 10px;
        }
        .checkbox-group label {
            margin: 0;
            font-weight: normal;
            cursor: pointer;
        }
        .btn-submit {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn-submit:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        .error-message {
            background: #fee;
            color: #c00;
            padding: 12px;
            border-radius: 5px;
            margin-bottom: 20px;
            text-align: center;
            border: 1px solid #fcc;
        }
        .flash-messages {
            margin-bottom: 20px;
        }
        .flash-message {
            padding: 12px;
            border-radius: 5px;
            margin-bottom: 10px;
            text-align: center;
        }
        .flash-success {
            background: #efe;
            color: #0a0;
            border: 1px solid #cfc;
        }
        .flash-error {
            background: #fee;
            color: #c00;
            border: 1px solid #fcc;
        }
        .flash-info {
            background: #eef;
            color: #00a;
            border: 1px solid #ccf;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>Вход в систему</h1>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="flash-messages">
                    {% for category, message in messages %}
                        <div class="flash-message flash-{{ category }}">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        
        {% if error %}
            <div class="error-message">{{ error }}</div>
        {% endif %}
        
        <form method="POST" action="{{ url_for('login') }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            
            <div class="form-group">
                <label for="username">Имя пользователя</label>
                <input type="text" id="username" name="username" required autofocus>
            </div>
            
            <div class="form-group">
                <label for="password">Пароль</label>
                <input type="password" id="password" name="password" required>
            </div>
            
            <div class="checkbox-group">
                <input type="checkbox" id="remember" name="remember">
                <label for="remember">Запомнить меня</label>
            </div>
            
            <button type="submit" class="btn-submit">Войти</button>
        </form>
    </div>
</body>
</html>
''', error=error)


@app.route('/logout')
@login_required
def logout():
    """
    Выход из системы
    
    Завершает сессию пользователя и перенаправляет на главную страницу.
    
    Returns:
        Response: Редирект на главную страницу
    """
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """
    Страница изменения пароля пользователя
    
    Обрабатывает GET (отображение формы) и POST (смена пароля) запросы.
    
    Returns:
        Response: HTML страница смены пароля или редирект
    """
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not current_password or not new_password or not confirm_password:
            flash('Заполните все поля', 'error')
            return redirect(url_for('change_password'))
        
        if new_password != confirm_password:
            flash('Новые пароли не совпадают', 'error')
            return redirect(url_for('change_password'))
        
        if len(new_password) < 6:
            flash('Пароль должен быть не менее 6 символов', 'error')
            return redirect(url_for('change_password'))
        
        # Проверяем текущий пароль
        users_data = load_users(USERS_FILE, hash_password)
        user_found = None
        user_index = None
        for idx, user in enumerate(users_data.get('users', [])):
            if user['username'] == current_user.username:
                user_found = user
                user_index = idx
                break
        
        if not user_found or not verify_password(current_password, user_found['password_hash']):
            flash('Текущий пароль неверен', 'error')
            return redirect(url_for('change_password'))
        
        # Обновляем пароль
        users_data['users'][user_index]['password_hash'] = hash_password(new_password)
        save_users(USERS_FILE, users_data)
        
        flash('Пароль успешно изменён', 'success')
        return redirect(url_for('admin'))
    
    return render_template_string('''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Изменение пароля</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            width: 100%;
            max-width: 450px;
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
            font-size: 24px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: bold;
        }
        input[type="password"] {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 5px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input[type="password"]:focus {
            outline: none;
            border-color: #667eea;
        }
        .btn-submit {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn-submit:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        .btn-secondary {
            display: block;
            width: 100%;
            padding: 14px;
            background: #f0f0f0;
            color: #333;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            margin-top: 10px;
            text-align: center;
            text-decoration: none;
        }
        .btn-secondary:hover {
            background: #e0e0e0;
        }
        .flash-messages {
            margin-bottom: 20px;
        }
        .flash-message {
            padding: 12px;
            border-radius: 5px;
            margin-bottom: 10px;
            text-align: center;
        }
        .flash-success {
            background: #efe;
            color: #0a0;
            border: 1px solid #cfc;
        }
        .flash-error {
            background: #fee;
            color: #c00;
            border: 1px solid #fcc;
        }
        .password-requirements {
            background: #f8f9fa;
            padding: 12px;
            border-radius: 5px;
            margin-bottom: 20px;
            font-size: 14px;
            color: #666;
        }
        .password-requirements ul {
            margin-left: 20px;
            margin-top: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Изменение пароля</h1>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="flash-messages">
                    {% for category, message in messages %}
                        <div class="flash-message flash-{{ category }}">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        
        <div class="password-requirements">
            <strong>Требования к паролю:</strong>
            <ul>
                <li>Минимум 6 символов</li>
                <li>Подтверждение пароля должно совпадать</li>
            </ul>
        </div>
        
        <form method="POST" action="{{ url_for('change_password') }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            
            <div class="form-group">
                <label for="current_password">Текущий пароль</label>
                <input type="password" id="current_password" name="current_password" required autofocus>
            </div>
            
            <div class="form-group">
                <label for="new_password">Новый пароль</label>
                <input type="password" id="new_password" name="new_password" required>
            </div>
            
            <div class="form-group">
                <label for="confirm_password">Подтверждение нового пароля</label>
                <input type="password" id="confirm_password" name="confirm_password" required>
            </div>
            
            <button type="submit" class="btn-submit">Изменить пароль</button>
            <a href="{{ url_for('admin') }}" class="btn-secondary">Отмена</a>
        </form>
    </div>
</body>
</html>
''')


@app.route('/')
def index():
    """
    Главная страница приложения
    
    Отдаёт клиентский HTML файл интерфейса пользователя.
    
    Returns:
        Response: HTML файл index.html
    """
    response = send_from_directory('.', 'index.html')
    # Добавляем заголовки для предотвращения кэширования HTML страниц
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/admin')
@login_required
@admin_required_decorator  # Только для администраторов
def admin():
    """
    Панель администратора
    
    Доступна только авторизованным пользователям с правами администратора.
    
    Returns:
        Response: HTML файл admin.html
    """
    response = send_from_directory('.', 'admin.html')
    # Добавляем заголовки для предотвращения кэширования HTML страниц
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/video-player')
def video_player():
    """
    Страница просмотра видео
    
    Открывает HTML страницу видеоплеера для воспроизведения видеофайлов.
    
    Returns:
        Response: HTML файл video-player.html
    """
    response = send_from_directory('.', 'video-player.html')
    # Добавляем заголовки для предотвращения кэширования HTML страниц
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/api/catalog')
def get_catalog():
    """
    API endpoint для получения каталога
    
    Возвращает каталог с отмеченными постоянными элементами.
    
    Returns:
        Response: JSON объект каталога
    """
    catalog = load_catalog(CATALOG_FILE)
    permanent_items = load_permanent_items(PERMANENT_FILE)
    permanent_paths = set(permanent_items.get('permanent_items', []))
    mark_permanent_recursive(catalog.get('children', []), permanent_paths)
    
    # Добавляем проекты из папки projects напрямую в каталог (без создания папки projects)
    if os.path.exists(PROJECTS_DIR):
        # Собираем все проекты из файловой системы
        project_items = []
        for project_name in os.listdir(PROJECTS_DIR):
            project_path = os.path.join(PROJECTS_DIR, project_name)
            if os.path.isdir(project_path):
                # Ищем index.html в нескольких возможных местах
                possible_index_paths = [
                    os.path.join(project_path, 'index.html'),
                    os.path.join(project_path, 'templates', 'index.html'),
                    os.path.join(project_path, 'app', 'index.html')
                ]
                
                index_html_path = None
                for possible_path in possible_index_paths:
                    if os.path.exists(possible_path):
                        index_html_path = possible_path
                        break
                
                if index_html_path is None:
                    # Если нет index.html, но есть app.py (Flask проект), всё равно добавляем проект
                    flask_app_path = os.path.join(project_path, 'app.py')
                    if not os.path.exists(flask_app_path):
                        continue
                    # Используем app.py для определения времени модификации
                    index_html_path = flask_app_path
                
                # Проверяем, есть ли Flask приложение в проекте
                flask_app_path = os.path.join(project_path, 'app.py')
                has_flask = os.path.exists(flask_app_path)
                
                # Если это Flask приложение, сохраняем информацию о нём
                if has_flask:
                    project_flask_info[project_name] = {
                        'app_path': flask_app_path,
                        'loaded': False,
                        'error': None,
                        'is_blueprint': True  # Флаг для Blueprint проектов
                    }
                
                project_items.append({
                    'name': project_name,
                    'path': project_path,
                    'index_html_path': index_html_path,
                    'has_flask': has_flask
                })
        
        # Создаём словарь существующих проектов для быстрого поиска
        existing_project_indices = {}
        children = catalog.get('children') or []
        for idx, item in enumerate(children):
            if item and isinstance(item, dict):
                url_val = item.get('url')
                if url_val and str(url_val).startswith('/projects/'):
                    project_name_from_url = url_val.split('/')[2]
                    existing_project_indices[project_name_from_url.lower()] = idx
        
        # Сначала удаляем все существующие проекты из каталога (сохраняя их настройки)
        saved_project_settings = {}
        for proj_info in project_items:
            project_name = proj_info['name']
            existing_idx = existing_project_indices.get(project_name.lower())
            if existing_idx is not None:
                existing_project = children[existing_idx]
                # Сохраняем пользовательские настройки (иконку, имя)
                icon_to_use = "page/logo.png"
                if existing_project.get('icon'):
                    existing_icon = existing_project.get('icon', '')
                    if existing_icon and existing_icon.strip() != '' and existing_icon != 'page/logo.png':
                        icon_to_use = existing_icon
                
                saved_project_settings[project_name.lower()] = {
                    'icon': icon_to_use,
                    'name': existing_project.get('name', project_name)
                }
        
        # Удаляем старые записи проектов из каталога (начиная с конца, чтобы индексы не сдвигались)
        for project_name in sorted(existing_project_indices.keys(), key=lambda k: existing_project_indices[k], reverse=True):
            idx = existing_project_indices[project_name]
            children.pop(idx)
        
        # Добавляем все проекты в начало каталога в алфавитном порядке
        for proj_info in sorted(project_items, key=lambda x: x['name']):
            project_name = proj_info['name']
            settings = saved_project_settings.get(project_name.lower(), {})
            
            project_item = {
                "name": settings.get('name', project_name),
                "icon": settings.get('icon', "page/logo.png"),
                "children": None,
                "url": f"/projects/{project_name}/index.html",
                "modified": datetime.fromtimestamp(os.path.getmtime(proj_info['index_html_path'])).strftime('%Y-%m-%d %H:%M'),
                "permanent": True,
                "has_flask": proj_info['has_flask']
            }
            catalog["children"].insert(0, project_item)
    
    response = jsonify(catalog)
    # Добавляем заголовки для предотвращения кэширования API ответов
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/api/parser/status')
@login_required
@admin_required_decorator
def get_parser_status():
    """
    API endpoint для получения статуса парсера
    
    Returns:
        Response: JSON объект со статусом парсера
    """
    return jsonify(parser_status)


@app.route('/api/parser/start', methods=['POST'])
@login_required
@admin_required_decorator
@csrf.exempt  # Освободить от CSRF защиты
def start_parser():
    """
    API endpoint для запуска парсера
    
    Запускает парсинг в фоновом потоке если он ещё не запущен.
    
    Returns:
        Response: JSON объект со статусом операции
    """
    if not parser_status['running']:
        thread = threading.Thread(target=run_parser_task)
        thread.daemon = True
        thread.start()
        return jsonify({'status': 'started'})
    return jsonify({'status': 'already_running'})


@app.route('/api/import/json', methods=['POST'])
@login_required
@admin_required_decorator
@csrf.exempt  # Освободить от CSRF защиты
def import_json():
    """
    API endpoint для импорта JSON данных
    
    Принимает JSON файл или данные и добавляет их в каталог.
    
    Request Body:
        json_data: JSON строка с данными для импорта
        parent_path: Путь родительской папки (опционально)
    
    Returns:
        Response: JSON объект со статусом операции
    """
    try:
        data = request.json
        json_data = data.get('json_data')
        parent_path = data.get('parent_path', '')
        
        if not json_data:
            return jsonify({'error': 'JSON данные не предоставлены'}), 400
        
        # Парсинг JSON данных
        imported_items = json.loads(json_data)
        
        # Загрузка каталога
        catalog = load_catalog(CATALOG_FILE)
        
        # Определение целевого списка для добавления
        if not parent_path:
            target_list = catalog['children']
        else:
            parent_item = find_item_by_path(catalog['children'], parent_path)
            if parent_item and 'children' in parent_item:
                target_list = parent_item['children']
            else:
                return jsonify({'error': 'Родительская папка не найдена'}), 404
        
        # Функция для рекурсивного добавления элементов
        def add_imported_items(items, target):
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        target.append(item)
                    elif isinstance(item, list):
                        add_imported_items(item, target)
            elif isinstance(items, dict):
                target.append(items)
        
        add_imported_items(imported_items, target_list)
        save_catalog(CATALOG_FILE, catalog)
        
        return jsonify({'status': 'success', 'message': f'Импортировано элементов: {len(target_list)}'})
    
    except json.JSONDecodeError as e:
        return jsonify({'error': f'Ошибка парсинга JSON: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Ошибка импорта: {str(e)}'}), 500


@app.route('/api/permanent', methods=['GET', 'POST', 'DELETE'])
@login_required
@admin_required_decorator
@csrf.exempt  # Освободить от CSRF защиты
def permanent_api():
    """
    API endpoint для управления постоянными элементами
    
    Методы:
        GET: Получить список всех постоянных элементов
        POST: Добавить новый постоянный элемент
        DELETE: Удалить элемент из списка постоянных
    
    Returns:
        Response: JSON объект со статусом операции или списком элементов
    """
    permanent_data = load_permanent_items(PERMANENT_FILE)
    
    if request.method == 'POST':
        path = request.json.get('path')
        if path and path not in permanent_data['permanent_items']:
            permanent_data['permanent_items'].append(path)
            save_permanent_items(PERMANENT_FILE, permanent_data)
        return jsonify({'status': 'success'})
    
    elif request.method == 'DELETE':
        path = request.json.get('path')
        if path in permanent_data['permanent_items']:
            permanent_data['permanent_items'].remove(path)
            save_permanent_items(PERMANENT_FILE, permanent_data)
        return jsonify({'status': 'success'})
    
    return jsonify(permanent_data)


@app.route('/api/items', methods=['POST', 'PUT', 'DELETE'])
@login_required
@admin_required_decorator
@csrf.exempt  # Освободить от CSRF защиты
def items_api():
    """
    API endpoint для CRUD операций с элементами каталога
    
    Методы:
        POST: Создать новую папку
        PUT: Обновить существующий элемент
        DELETE: Удалить элемент
    
    Request Body:
        path: Путь элемента
        name: Имя элемента (для POST)
        parent_path: Путь родительской папки (для POST)
        updates: Словарь обновлений (для PUT)
    
    Returns:
        Response: JSON объект со статусом операции
    """
    catalog = load_catalog(CATALOG_FILE)
    data = request.json
    path = data.get('path', '')
    
    if request.method == 'POST':
        name = data.get('name')
        parent_path = data.get('parent_path', '')
        icon = data.get('icon', 'folder.png')
        url = data.get('url')
        
        # Определить целевой список для добавления
        if not parent_path:
            target_list = catalog['children']
        else:
            parent_item = find_item_by_path(catalog['children'], parent_path)
            if parent_item and 'children' in parent_item:
                target_list = parent_item['children']
            else:
                return jsonify({'error': 'Parent not found'}), 404
        
        # Создать новый элемент
        new_item = {'name': name, 'icon': icon, 'children': []}
        if url:
            new_item['url'] = url
        target_list.append(new_item)
        save_catalog(CATALOG_FILE, catalog)
        response = jsonify({'status': 'success'})
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    
    elif request.method == 'DELETE':
        if delete_item_by_path(catalog['children'], path):
            save_catalog(CATALOG_FILE, catalog)
            response = jsonify({'status': 'success'})
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return response
        return jsonify({'error': 'Not found'}), 404
    
    elif request.method == 'PUT':
        updates = data.get('updates', {})
        
        # Если в обновлениях есть icon, нужно также установить permanent=True
        if 'icon' in updates and updates['icon']:
            updates['permanent'] = True
        
        # Попытаться обновить существующий элемент
        if update_item_by_path(catalog['children'], path, updates):
            save_catalog(CATALOG_FILE, catalog)
            response = jsonify({'status': 'success'})
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return response
        
        # Элемент не найден - создать его автоматически
        # Разбить путь на части для определения родительской папки
        path_parts = path.split('/')
        if len(path_parts) > 1:
            parent_path = '/'.join(path_parts[:-1])
            item_name = path_parts[-1]
        else:
            parent_path = ''
            item_name = path
        
        # Определить целевой список для добавления
        if not parent_path:
            target_list = catalog['children']
        else:
            parent_item = find_item_by_path(catalog['children'], parent_path)
            if parent_item and 'children' in parent_item:
                target_list = parent_item['children']
            else:
                # Родительская папка не найдена - создать её рекурсивно
                # Для простоты создаём в корне
                target_list = catalog['children']
                parent_path = ''
        
        # Создать новый элемент с данными из updates
        new_item = {
            'name': updates.get('name', item_name.upper()),
            'icon': updates.get('icon', 'folder.png'),
            'children': []
        }
        if 'url' in updates:
            new_item['url'] = updates['url']
        if updates.get('permanent'):
            new_item['permanent'] = True
        
        target_list.append(new_item)
        save_catalog(CATALOG_FILE, catalog)
        response = jsonify({'status': 'created'})
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    
    return jsonify({'error': 'Invalid method'}), 400


@app.route('/api/images')
def get_images():
    """
    API endpoint для получения списка всех доступных изображений
    
    Возвращает изображения, найденные парсером (из файла parser_images.json).
    НЕ сканирует папки page/ и projects/ - используем только изображения от парсера.
    
    Returns:
        Response: JSON массив объектов с информацией об изображениях в UTF-8
    """
    images = []
    seen_paths = set()  # Для предотвращения дубликатов
    
    # Загрузить изображения из парсера (сохранённые в файле)
    parser_images_data = load_json_file(PARSER_IMAGES_FILE, default={'images': []})
    parser_images = parser_images_data.get('images', [])
    
    # Добавить изображения из парсера
    for icon_url in parser_images:
        if icon_url and icon_url not in seen_paths:
            # Извлечь имя файла из URL и декодировать URL-кодирование для корректного отображения кириллицы
            try:
                # Сначала декодируем весь URL, затем извлекаем имя файла
                decoded_url = unquote(icon_url)
                filename = decoded_url.split('/')[-1]
            except:
                filename = os.path.basename(icon_url)
            images.append({'name': filename, 'path': icon_url})
            seen_paths.add(icon_url)
    
    # Также добавить изображения из текущего статуса парсера (если он активен)
    if parser_status.get('images'):
        for icon_url in parser_status['images']:
            if icon_url and icon_url not in seen_paths:
                try:
                    decoded_url = unquote(icon_url)
                    filename = decoded_url.split('/')[-1]
                except:
                    filename = os.path.basename(icon_url)
                images.append({'name': filename, 'path': icon_url})
                seen_paths.add(icon_url)
    
    # Создаем response с явным указанием кодировки UTF-8
    response = Response(
        json.dumps(images, ensure_ascii=False),
        mimetype='application/json; charset=utf-8'
    )
    # Добавляем заголовки для предотвращения кэширования API ответов
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/page/<path:filename>')
def serve_page_image(filename):
    """
    API endpoint для раздачи изображений из папки page/
    
    Args:
        filename: Путь к файлу относительно папки page/
    
    Returns:
        Response: Файл изображения
    """
    page_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'page')
    return send_from_directory(page_dir, filename, max_age=86400)  # Кэширование на 24 часа


@app.route('/css/<path:filename>')
def serve_css(filename):
    """
    API endpoint для раздачи CSS файлов из папки css/
    
    Args:
        filename: Путь к файлу относительно папки css/
    
    Returns:
        Response: CSS файл
    """
    css_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'css')
    response = send_from_directory(css_dir, filename, max_age=86400)
    response.headers['Content-Type'] = 'text/css; charset=utf-8'
    return response


@app.route('/js/<path:filename>')
def serve_js(filename):
    """
    API endpoint для раздачи JS файлов из папки js/
    
    Args:
        filename: Путь к файлу относительно папки js/
    
    Returns:
        Response: JS файл
    """
    js_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'js')
    response = send_from_directory(js_dir, filename, max_age=86400)
    response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    return response



@app.route('/projects/<project_name>/static/<path:filename>')
def serve_project_static(project_name, filename):
    """
    API endpoint для раздачи статических файлов проектов из папки projects/<project>/static/
    
    Этот маршрут должен быть объявлен ДО общего маршрута /projects/<path:filename>,
    чтобы перехватывать запросы к статике до того, как они попадут в общий обработчик.

    Args:
        project_name: Имя проекта
        filename: Путь к файлу относительно папки static проекта

    Returns:
        Response: Статический файл проекта (css, js, images, etc.)
    """
    project_path = os.path.join(PROJECTS_DIR, project_name)
    static_folder = os.path.join(project_path, 'static')
    
    # Проверяем существование проекта и папки static
    if not os.path.exists(static_folder) or not os.path.isdir(static_folder):
        return jsonify({'error': f'Статика не найдена для проекта: {project_name}'}), 404
    
    return send_from_directory(static_folder, filename, max_age=86400)

@app.route('/projects/<path:filename>')
@app.route('/projects/<project_name>')
@app.route('/projects/<project_name>/')
def serve_project_file(filename=None, project_name=None):
    """
    API endpoint для раздачи файлов проектов из папки projects/
    
    Args:
        filename: Путь к файлу относительно папки projects/ (если указан)
        project_name: Имя проекта (если запрошен корень проекта)
    
    Returns:
        Response: Файл проекта (html, css, js, images, etc.) или ответ от Flask приложения проекта
    """
    # Определяем имя проекта и оставшийся путь
    if project_name is not None:
        # Запрошен корень проекта /projects/<project_name> или /projects/<project_name>/
        remaining_path = ''
    elif filename:
        # Запрошен конкретный файл /projects/<project_name>/<path>
        parts = filename.split('/', 1)
        if len(parts) < 2:
            project_name = parts[0]
            remaining_path = 'index.html'
        else:
            project_name, remaining_path = parts
    else:
        return jsonify({'error': 'Некорректный запрос'}), 400
    
    project_path = os.path.join(PROJECTS_DIR, project_name)
    
    # Проверяем существование проекта
    if not os.path.exists(project_path) or not os.path.isdir(project_path):
        return jsonify({'error': f'Проект не найден: {project_name}'}), 404
    
    # Проверяем, есть ли у этого проекта Flask приложение
    if project_name in project_flask_info:
        flask_info = project_flask_info[project_name]
        
        # Загружаем Flask приложение при первом запросе, если ещё не загружено
        if not flask_info.get('loaded') and flask_info.get('app_path'):
            try:
                import importlib.util
                import sys
                
                # Добавляем директорию проекта в sys.path для корректных импортов
                project_dir = os.path.dirname(flask_info['app_path'])
                if project_dir not in sys.path:
                    sys.path.insert(0, project_dir)
                
                spec = importlib.util.spec_from_file_location(f"{project_name}_app", flask_info['app_path'])
                if spec and spec.loader:
                    project_module = importlib.util.module_from_spec(spec)
                    # Добавляем проект в sys.modules для корректной работы импортов
                    sys.modules[f"{project_name}_app"] = project_module
                    spec.loader.exec_module(project_module)
                    
                    # Проверяем, является ли проект Blueprint
                    if flask_info.get('is_blueprint') and hasattr(project_module, 'parad_zvezd_bp'):
                        # Это Blueprint - регистрируем его в главном приложении
                        blueprint = project_module.parad_zvezd_bp
                        # Регистрируем Blueprint С url_prefix для проекта
                        # static_url_path уже настроен внутри Blueprint и будет работать корректно
                        app.register_blueprint(blueprint, url_prefix=f'/projects/{project_name}')
                        project_flask_info[project_name]['blueprint'] = blueprint
                        project_flask_info[project_name]['loaded'] = True
                        print(f"Blueprint '{project_name}' зарегистрирован с префиксом /projects/{project_name} (статика: {blueprint.static_url_path})")
                    elif hasattr(project_module, 'app'):
                        # Это обычное Flask приложение
                        flask_app = project_module.app
                        project_flask_info[project_name]['app'] = flask_app
                        project_flask_info[project_name]['loaded'] = True
                        print(f"Flask приложение '{project_name}' успешно загружено")
            except Exception as e:
                error_msg = f"Ошибка загрузки Flask приложения '{project_name}': {e}"
                print(error_msg)
                import traceback
                traceback.print_exc()
                project_flask_info[project_name]['error'] = error_msg
                # Если ошибка связана с БД или другими зависимостями, пробуем продолжить без загрузки Flask приложения
                # и отдавать статические файлы напрямую
                pass
        
        # Если Blueprint загружен, он уже зарегистрирован и будет обрабатывать запросы автоматически
        # Если Flask приложение загружено, пробуем обработать запрос через него
        if flask_info.get('loaded') and 'app' in flask_info and not flask_info.get('is_blueprint'):
            flask_app = flask_info['app']
            try:
                # Клонируем текущий запрос и передаём его во Flask приложение проекта
                environ = request.environ.copy()
                # Устанавливаем PATH_INFO для маршрута проекта
                # Для корня проекта устанавливаем '/', иначе путь к файлу
                if remaining_path == '' or remaining_path == 'index.html':
                    environ['PATH_INFO'] = '/'
                else:
                    environ['PATH_INFO'] = '/' + remaining_path
                environ['SCRIPT_NAME'] = f'/projects/{project_name}'
                
                # Создаём WSGI response iterator
                response_iter = flask_app(environ, lambda status, headers: None)
                
                # Если получили ответ, возвращаем его
                if response_iter:
                    # Конвертируем итератор в Response объект если нужно
                    from flask import Response
                    if isinstance(response_iter, Response):
                        return response_iter
                    # Если это итератор, читаем содержимое
                    body = b''.join(response_iter)
                    return Response(body, status='200 OK', content_type='text/html; charset=utf-8')
            except Exception as e:
                print(f"Ошибка обработки запроса Flask приложением '{project_name}': {e}")
                import traceback
                traceback.print_exc()
    
    # Стандартная обработка - пробуем найти файл в нескольких возможных местах
    # Сначала проверяем прямой путь
    if remaining_path:
        file_path = os.path.join(project_path, remaining_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return send_from_directory(project_path, remaining_path, max_age=86400)
        
        # Для проектов с шаблонами в templates/ (например, Flask проекты без загрузки)
        templates_path = os.path.join(project_path, 'templates', remaining_path)
        if os.path.exists(templates_path) and os.path.isfile(templates_path):
            return send_from_directory(os.path.join(project_path, 'templates'), remaining_path, max_age=86400)
        
        # Для статических файлов в static/ (универсальный путь для всех проектов)
        static_path = os.path.join(project_path, 'static', remaining_path)
        if os.path.exists(static_path) and os.path.isfile(static_path):
            return send_from_directory(os.path.join(project_path, 'static'), remaining_path, max_age=86400)
    
    # Специальная обработка для статики Blueprint проектов
    # Если запрос начинается с /projects/<project_name>/static/, перенаправляем в static папку проекта
    if project_name in project_flask_info and project_flask_info[project_name].get('loaded'):
        flask_info = project_flask_info[project_name]
        if flask_info.get('blueprint') and remaining_path.startswith('static/'):
            # Извлекаем путь к файлу относительно static папки
            static_file_path = remaining_path[7:]  # Убираем 'static/' из начала
            static_full_path = os.path.join(project_path, 'static', static_file_path)
            if os.path.exists(static_full_path) and os.path.isfile(static_full_path):
                return send_from_directory(os.path.join(project_path, 'static'), static_file_path, max_age=86400)
    
    # Файл не найден
    return jsonify({'error': f'Файл не найден: {project_name}/{remaining_path if remaining_path else ""}'}), 404


@app.route('/api/proxy-image')
def proxy_image():
    """
    API endpoint для проксирования изображений с внешних URL
    
    Используется для обхода CORS и rate limiting при загрузке изображений
    с FTP-сервера vm-ftp.anosov.ru
    
    Query params:
        url: Полный URL изображения
    
    Returns:
        Response: Изображение с appropriate Content-Type
    """
    image_url = request.args.get('url', '')
    
    if not image_url:
        return jsonify({'error': 'URL не указан'}), 400
    
    # Проверка, что URL принадлежит нашему доверенному домену
    parsed = urlparse(image_url)
    if parsed.netloc != 'vm-ftp.anosov.ru':
        return jsonify({'error': 'Недоверенный домен'}), 403
    
    try:
        # Загружаем изображение с внешнего сервера
        response = requests.get(image_url, timeout=10, stream=True)
        response.raise_for_status()
        
        # Определяем Content-Type
        content_type = response.headers.get('Content-Type', 'image/jpeg')
        
        # Создаём ответ с правильными заголовками
        proxy_response = Response(
            response.content,
            status=200,
            content_type=content_type
        )
        
        # Добавляем заголовки для кэширования
        proxy_response.headers['Cache-Control'] = 'public, max-age=86400'
        
        return proxy_response
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Ошибка загрузки: {str(e)}'}), 500


@app.route('/api/video-proxy')
def proxy_video():
    """
    API endpoint для проксирования видеофайлов с внешних URL
    
    Используется для открытия видео в браузере вместо скачивания.
    Устанавливает правильный Content-Type и убирает Content-Disposition: attachment.
    Поддерживает Range requests для потоковой передачи.
    
    Query params:
        url: Полный URL видеофайла
    
    Returns:
        Response: Видеофайл с правильным Content-Type для воспроизведения в браузере
    """
    video_url = request.args.get('url', '')
    
    if not video_url:
        return jsonify({'error': 'URL не указан'}), 400
    
    # Проверка, что URL принадлежит нашему доверенному домену
    parsed = urlparse(video_url)
    allowed_domains = ['vm-ftp.anosov.ru', 'testnavi.onrender.com']
    if parsed.netloc not in allowed_domains:
        return jsonify({'error': 'Недоверенный домен'}), 403
    
    try:
        # Определяем Content-Type по расширению файла
        video_content_types = {
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
            '.ogg': 'video/ogg',
            '.mov': 'video/quicktime',
            '.avi': 'video/x-msvideo',
            '.mkv': 'video/x-matroska',
            '.flv': 'video/x-flv',
            '.wmv': 'video/x-ms-wmv',
            '.m4v': 'video/x-m4v'
        }

        # Получаем расширение из URL (декодируем проценты и убираем пробелы)
        from urllib.parse import unquote
        decoded_url = unquote(video_url).strip()
        ext = os.path.splitext(decoded_url)[1].lower()
        content_type = video_content_types.get(ext, 'video/mp4')

        # Сначала получаем информацию о файле (размер) с правильным User-Agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive'
        }
        
        head_response = requests.head(video_url, headers=headers, timeout=30, allow_redirects=True)
        head_response.raise_for_status()
        file_size = int(head_response.headers.get('Content-Length', 0))
        
        # Проверяем поддержку Range запросов на удалённом сервере
        supports_ranges = head_response.headers.get('Accept-Ranges', '').lower() == 'bytes'
        
        # Обрабатываем Range запрос от браузера
        range_header = request.headers.get('Range', '')
        
        if range_header and supports_ranges and file_size > 0:
            # Браузер запрашивает часть файла (для перемотки)
            range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
            if range_match:
                start = int(range_match.group(1))
                end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
                end = min(end, file_size - 1)
                
                # Запрашиваем диапазон с удалённого сервера
                headers['Range'] = f'bytes={start}-{end}'
                response = requests.get(video_url, headers=headers, timeout=60, stream=True)
                response.raise_for_status()
                
                # Возвращаем частичный контент
                proxy_response = Response(
                    response.iter_content(chunk_size=8192),
                    status=206,  # Partial Content
                    mimetype=content_type
                )
                proxy_response.headers['Content-Length'] = str(end - start + 1)
                proxy_response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
                proxy_response.headers['Accept-Ranges'] = 'bytes'
                # КРИТИЧЕСКИ ВАЖНО: Устанавливаем inline и убираем любые следы attachment
                proxy_response.headers['Content-Disposition'] = f'inline; filename*=UTF-8\'\'{os.path.basename(decoded_url)}'
                # Убираем заголовки, которые могут вызвать скачивание в Edge
                proxy_response.headers.pop('X-Download-Options', None)
                return proxy_response
        
        # Если нет Range запроса или сервер не поддерживает ranges - отдаём всё видео
        response = requests.get(video_url, headers=headers, timeout=60, stream=True)
        response.raise_for_status()
        
        # Создаём ответ для клиента
        proxy_response = Response(
            response.iter_content(chunk_size=8192),
            status=response.status_code,
            mimetype=content_type
        )

        # Копируем важные заголовки от оригинального ответа
        if file_size > 0:
            proxy_response.headers['Content-Length'] = str(file_size)

        # Критически важные заголовки для воспроизведения вместо скачивания:
        # 1. Content-Disposition: inline - говорит браузеру отображать файл
        # Используем filename* для лучшей совместимости с UTF-8 именами
        proxy_response.headers['Content-Disposition'] = f'inline; filename*=UTF-8\'\'{os.path.basename(decoded_url)}'
        # 2. Accept-Ranges: bytes - поддержка перемотки
        proxy_response.headers['Accept-Ranges'] = 'bytes'
        # 3. Cache-Control - кэширование для лучшей производительности
        proxy_response.headers['Cache-Control'] = 'public, max-age=3600'
        # 4. Убираем заголовки, которые могут вызвать скачивание в Edge
        proxy_response.headers.pop('X-Download-Options', None)
        proxy_response.headers.pop('Content-Transfer-Encoding', None)

        return proxy_response

    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Ошибка загрузки видео: {str(e)}'}), 500


if __name__ == '__main__':
    # Убедиться, что директория данных существует
    ensure_data_dir(DATA_DIR)
    
    # Инициализировать файл пользователей если не существует
    load_users(USERS_FILE, hash_password)
    
    print("🚀 Запуск сервера...")
    app.run(debug=True, host='0.0.0.0', port=5000)
