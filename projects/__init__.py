"""
Пакет проектов - централизованная система регистрации и управления проектами

Этот модуль предоставляет механизм автоматической регистрации проектов
как Flask Blueprint для масштабирования архитектуры приложения.

Использование:
    1. Каждый проект должен содержать файл app.py с функцией create_blueprint()
    2. Главный app.py импортирует register_all_blueprints(app)
    3. Все проекты автоматически регистрируются при запуске
"""

import os
import importlib.util
import sys
from pathlib import Path


def get_projects_directory():
    """Возвращает абсолютный путь к директории проектов"""
    return Path(__file__).parent


def discover_projects():
    """
    Обнаруживает все проекты в директории projects/
    
    Returns:
        dict: Словарь {имя_проекта: путь_к_директории}
    """
    projects_dir = get_projects_directory()
    projects = {}
    
    if not projects_dir.exists():
        return projects
    
    for item in projects_dir.iterdir():
        if item.is_dir() and not item.name.startswith('_') and not item.name.startswith('.'):
            # Проверяем, есть ли в проекте app.py
            app_file = item / 'app.py'
            if app_file.exists():
                projects[item.name] = item
    
    return projects


def load_project_blueprint(project_name, project_path):
    """
    Загружает Blueprint из проекта
    
    Args:
        project_name (str): Имя проекта
        project_path (Path): Путь к директории проекта
        
    Returns:
        tuple: (blueprint, config) или (None, error_message)
    """
    app_file = project_path / 'app.py'
    
    try:
        # Добавляем директорию проекта в sys.path для корректных импортов
        project_dir = str(project_path)
        if project_dir not in sys.path:
            sys.path.insert(0, project_dir)
        
        # Динамически загружаем модуль проекта
        spec = importlib.util.spec_from_file_location(
            f"projects.{project_name}",
            app_file
        )
        
        if not spec or not spec.loader:
            return None, f"Не удалось загрузить спецификацию для {project_name}"
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"projects.{project_name}"] = module
        spec.loader.exec_module(module)
        
        # Ищем функцию create_blueprint или Blueprint напрямую
        if hasattr(module, 'create_blueprint'):
            # Фабрика Blueprint (рекомендуемый подход)
            blueprint = module.create_blueprint()
        elif hasattr(module, 'create_app'):
            # Фабрика приложений (возвращает Blueprint или Flask app)
            result = module.create_app()
            from flask import Blueprint
            if isinstance(result, Blueprint):
                blueprint = result
            else:
                return None, f"create_app() должен возвращать Blueprint, а не {type(result)}"
        else:
            # Ищем Blueprint по распространённым именам
            possible_names = [
                f'{project_name.lower().replace(" ", "_").replace("!", "")}_bp',
                f'{project_name.lower().replace("-", "_")}_bp',
                'bp',
                'blueprint'
            ]
            
            blueprint = None
            for name in possible_names:
                if hasattr(module, name):
                    obj = getattr(module, name)
                    from flask import Blueprint
                    if isinstance(obj, Blueprint):
                        blueprint = obj
                        break
            
            if not blueprint:
                return None, f"Не найден Blueprint в проекте {project_name}. Ожидалась функция create_blueprint() или переменная Blueprint"
        
        return blueprint, None
        
    except Exception as e:
        import traceback
        error_msg = f"Ошибка загрузки проекта {project_name}: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return None, error_msg


def register_all_blueprints(flask_app, url_prefix='/projects'):
    """
    Регистрирует все обнаруженные проекты как Blueprint в главном приложении
    
    Args:
        flask_app (Flask): Основное Flask приложение
        url_prefix (str): Префикс URL для всех проектов
        
    Returns:
        dict: Информация о зарегистрированных проектах
    """
    projects = discover_projects()
    registered = {}
    
    print(f"Обнаружено проектов: {len(projects)}")
    
    for project_name, project_path in projects.items():
        # Создаём URL префикс для проекта
        # Для кириллических имён используем транслитерацию или оставляем как есть
        project_slug = project_name.lower().replace(' ', '-').replace('!', '')
        project_url_prefix = f"{url_prefix}/{project_slug}"
        
        blueprint, error = load_project_blueprint(project_name, project_path)
        
        if blueprint:
            # Проверяем, есть ли у Blueprint уже установленный url_prefix
            # Если нет - регистрируем с нашим префиксом
            if not blueprint.url_prefix:
                # Нужно перерегистрировать Blueprint с префиксом
                # К сожалению, Flask не позволяет изменить url_prefix после создания
                # Поэтому регистрируем как есть, а маршруты должны использовать относительные пути
                pass
            
            # Регистрируем Blueprint
            try:
                flask_app.register_blueprint(blueprint, url_prefix=project_url_prefix)
                registered[project_name] = {
                    'path': str(project_path),
                    'url_prefix': project_url_prefix,
                    'blueprint_name': blueprint.name,
                    'success': True
                }
                print(f"✓ Проект '{project_name}' зарегистрирован как '{project_url_prefix}'")
            except Exception as e:
                error = f"Ошибка регистрации Blueprint: {e}"
                registered[project_name] = {
                    'path': str(project_path),
                    'error': error,
                    'success': False
                }
                print(f"✗ Ошибка регистрации проекта '{project_name}': {error}")
        else:
            registered[project_name] = {
                'path': str(project_path),
                'error': error,
                'success': False
            }
            print(f"✗ Проект '{project_name}' не загружен: {error}")
    
    return registered


def get_project_info(flask_app):
    """
    Возвращает информацию о всех зарегистрированных проектах
    
    Args:
        flask_app (Flask): Основное Flask приложение
        
    Returns:
        list: Список словарей с информацией о проектах
    """
    projects = []
    
    for rule in flask_app.url_map.iter_rules():
        rule_str = str(rule)
        if rule_str.startswith('/projects/'):
            parts = rule_str.split('/')
            if len(parts) >= 3:
                project_name = parts[2]
                # Находим полную информацию о проекте
                project_path = get_projects_directory() / project_name
                
                projects.append({
                    'name': project_name,
                    'path': str(project_path) if project_path.exists() else 'unknown',
                    'routes': [str(r) for r in flask_app.url_map.iter_rules() 
                              if str(r).startswith(f'/projects/{project_name}/')]
                })
    
    # Удаляем дубликаты
    seen = set()
    unique_projects = []
    for p in projects:
        if p['name'] not in seen:
            seen.add(p['name'])
            unique_projects.append(p)
    
    return unique_projects


__all__ = [
    'get_projects_directory',
    'discover_projects',
    'load_project_blueprint',
    'register_all_blueprints',
    'get_project_info'
]
