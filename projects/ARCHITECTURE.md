# Архитектура масштабирования проектов на Flask Blueprint

## Обзор

Эта система позволяет легко добавлять новые проекты в основное приложение. Каждый проект изолирован и регистрируется автоматически через механизм Flask Blueprint.

## Структура проекта

```
/workspace/
├── app.py                          # Главное приложение (testnavi/app.py)
├── projects/                       # Директория со всеми проектами
│   ├── __init__.py                 # Модуль регистрации проектов
│   ├── TEMPLATE/                   # Шаблон для новых проектов
│   │   ├── app.py                  # Blueprint проекта
│   │   ├── templates/              # Шаблоны проекта
│   │   └── static/                 # Статика проекта
│   ├── ПарадЗвёзд!/               # Проект "ПарадЗвёзд"
│   │   └── app.py                  # Blueprint проекта
│   └── your_new_project/          # Ваш новый проект
│       └── app.py                  # Blueprint проекта
└── ...
```

## Как это работает

### 1. Автоматическое обнаружение проектов

Модуль `projects/__init__.py` предоставляет функцию `discover_projects()`, которая:
- Сканирует директорию `projects/`
- Находит все поддиректории с файлом `app.py`
- Возвращает словарь `{имя_проекта: путь}`

### 2. Загрузка Blueprint

Функция `load_project_blueprint()` динамически загружает каждый проект:
- Импортирует модуль `app.py` проекта
- Ищет функцию `create_blueprint()` или переменную Blueprint
- Возвращает объект Blueprint для регистрации

### 3. Регистрация в главном приложении

Функция `register_all_blueprints()`:
- Проходит по всем обнаруженным проектам
- Загружает каждый Blueprint
- Регистрирует его в главном приложении с префиксом `/projects/{project_name}/`

## Создание нового проекта

### Шаг 1: Создайте директорию

```bash
mkdir -p projects/my_new_project/templates
mkdir -p projects/my_new_project/static
```

### Шаг 2: Создайте app.py с функцией create_blueprint()

```python
from flask import Blueprint, render_template

def create_blueprint():
    """
    Фабрика Blueprint для проекта
    
    Returns:
        Blueprint: Настроенный Blueprint проекта
    """
    bp = Blueprint(
        'my_new_project',  # Уникальное имя
        __name__,
        template_folder='templates',
        static_folder='static'
    )
    
    @bp.route('/')
    def index():
        return render_template('index.html')
    
    @bp.route('/api/data')
    def api_data():
        from flask import jsonify
        return jsonify({'status': 'ok'})
    
    return bp
```

### Шаг 3: Добавьте шаблоны и статику

Создайте `templates/index.html` и другие файлы по необходимости.

### Шаг 4: Готово!

При запуске главного приложения проект будет автоматически зарегистрирован и доступен по URL:
```
/projects/my_new_project/
```

## Интеграция с главным приложением

### Вариант 1: Автоматическая регистрация (рекомендуется)

В главном `app.py` добавьте:

```python
from projects import register_all_blueprints

# После создания основного приложения
app = Flask(__name__)

# Автоматически регистрируем все проекты
register_all_blueprints(app, url_prefix='/projects')
```

### Вариант 2: Ручная регистрация отдельных проектов

```python
from projects import load_project_blueprint
from pathlib import Path

# Загружаем конкретный проект
bp, error = load_project_blueprint('my_project', Path('projects/my_project'))

if bp:
    app.register_blueprint(bp, url_prefix='/projects/my-project')
```

## Преимущества архитектуры

### 1. Изоляция
- Каждый проект имеет свои шаблоны и статику
- Отдельные пространства имён для маршрутов
- Независимые конфигурации

### 2. Масштабируемость
- Добавление проекта = создание новой папки
- Нет изменений в главном приложении
- Автоматическое обнаружение

### 3. Гибкость
- Проекты могут использовать разные БД
- Разные системы аутентификации
- Разные зависимости

### 4. Тестируемость
- Каждый проект можно тестировать отдельно
- Простой запуск в режиме standalone

## Примеры использования

### Проект с базой данных

```python
from flask import Blueprint, jsonify
import pymysql

def create_blueprint():
    bp = Blueprint('db_app', __name__, template_folder='templates')
    
    DB_CONFIG = {
        'host': 'localhost',
        'user': 'root',
        'password': '',
        'database': 'my_db'
    }
    
    @bp.route('/api/users')
    def get_users():
        conn = pymysql.connect(**DB_CONFIG)
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM users')
                return jsonify(cursor.fetchall())
        finally:
            conn.close()
    
    return bp
```

### API проект

```python
from flask import Blueprint, request, jsonify

def create_blueprint():
    bp = Blueprint('api_service', __name__)
    
    @bp.route('/api/v1/items', methods=['GET'])
    def get_items():
        return jsonify({'items': []})
    
    @bp.route('/api/v1/items', methods=['POST'])
    def create_item():
        data = request.json
        # Обработка данных
        return jsonify({'id': 1, **data}), 201
    
    return bp
```

### Проект с авторизацией

```python
from flask import Blueprint, session, redirect, url_for
from functools import wraps

def create_blueprint():
    bp = Blueprint('secure_app', __name__, template_folder='templates')
    
    def login_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get('is_admin'):
                return redirect(url_for('secure_app.login'))
            return f(*args, **kwargs)
        return decorated
    
    @bp.route('/login')
    def login():
        # Логика входа
        pass
    
    @bp.route('/dashboard')
    @login_required
    def dashboard():
        return render_template('dashboard.html')
    
    return bp
```

## URL структура

После регистрации все проекты доступны по единому префиксу:

```
Главное приложение:
/                           # Главная страница главного приложения
/admin                      # Админка главного приложения
/api/...                    # API главного приложения

Проекты:
/projects/TEMPLATE/         # Шаблон проекта
/projects/parad-zvezd/      # Проект ПарадЗвёзд (префикс преобразуется)
/projects/my-new-project/   # Ваш новый проект
```

## Важные замечания

### 1. Имена Blueprint должны быть уникальными

```python
# ПЛОХО: одинаковые имена
bp = Blueprint('app', __name__)  # В проекте 1
bp = Blueprint('app', __name__)  # В проекте 2 - КОНФЛИКТ!

# ХОРОШО: уникальные имена
bp = Blueprint('project_one', __name__)
bp = Blueprint('project_two', __name__)
```

### 2. Не указывайте url_prefix при создании Blueprint

```python
# ПЛОХО: префикс указан здесь
bp = Blueprint('app', __name__, url_prefix='/my-app')

# ХОРОШО: префикс добавится при регистрации
bp = Blueprint('app', __name__)
# При регистрации: app.register_blueprint(bp, url_prefix='/projects/my-app')
```

### 3. Используйте url_for с именем Blueprint

```python
# Доступ к маршрутам внутри проекта
url_for('my_blueprint.index')  # Вернёт /projects/my-project/

# Доступ к статике проекта
url_for('my_blueprint.static', filename='css/style.css')
```

### 4. Обработка ошибок при загрузке

Система продолжает работу даже если один из проектов не загрузился:

```python
registered = register_all_blueprints(app)

for project_name, info in registered.items():
    if not info['success']:
        print(f"Project {project_name} failed: {info.get('error')}")
        # Проект не зарегистрирован, но приложение работает
```

## Отладка и тестирование

### Тестирование проекта отдельно

```python
if __name__ == '__main__':
    from flask import Flask
    
    app = Flask(__name__)
    app.secret_key = 'dev-key'
    
    bp = create_blueprint()
    app.register_blueprint(bp)
    
    app.run(debug=True, port=5000)
```

### Просмотр зарегистрированных маршрутов

```python
from projects import get_project_info

projects = get_project_info(app)
for project in projects:
    print(f"Project: {project['name']}")
    print(f"  Routes: {project['routes']}")
```

## Миграция существующих проектов

Если у вас есть проект с прямой структурой Flask app:

### Было:
```python
# app.py
app = Flask(__name__)

@app.route('/')
def index():
    return 'Hello'
```

### Стало:
```python
# app.py
from flask import Blueprint

def create_blueprint():
    bp = Blueprint('my_app', __name__, template_folder='templates')
    
    @bp.route('/')
    def index():
        return 'Hello'
    
    return bp
```

## Заключение

Эта архитектура позволяет:
- ✅ Быстро добавлять новые проекты
- ✅ Изолировать зависимости и конфигурации
- ✅ Масштабироваться без изменения основного кода
- ✅ Тестировать проекты независимо
- ✅ Использовать разные технологии в разных проектах

Для добавления нового проекта достаточно:
1. Создать папку в `projects/`
2. Добавить `app.py` с `create_blueprint()`
3. Перезапустить приложение
