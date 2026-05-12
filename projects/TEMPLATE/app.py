"""
Пример проекта с Flask Blueprint

Этот файл демонстрирует правильную структуру проекта для автоматической
регистрации в главной системе.
"""

from flask import Blueprint, render_template, jsonify


def create_blueprint():
    """
    Фабрика Blueprint для примера проекта
    
    Returns:
        Blueprint: Настроенный Blueprint проекта
    """
    bp = Blueprint(
        'template_project',  # Уникальное имя Blueprint
        __name__,
        template_folder='templates',
        static_folder='static'
    )
    
    # ------------------- Маршруты -------------------
    
    @bp.route('/')
    def index():
        """Главная страница проекта"""
        return render_template('index.html')
    
    @bp.route('/api/info')
    def api_info():
        """API endpoint с информацией о проекте"""
        return jsonify({
            'name': 'Template Project',
            'version': '1.0.0',
            'description': 'Пример проекта для демонстрации структуры'
        })
    
    @bp.route('/about')
    def about():
        """Страница о проекте"""
        return render_template('about.html')
    
    return bp


# Для совместимости со старым кодом
blueprint = create_blueprint()

if __name__ == '__main__':
    # Запуск проекта отдельно для тестирования
    from flask import Flask
    
    app = Flask(__name__)
    app.secret_key = 'dev-secret-key'
    
    # Регистрируем Blueprint для тестирования
    bp = create_blueprint()
    app.register_blueprint(bp)
    
    print("Запуск тестового сервера...")
    print("Доступ по адресу: http://localhost:5000/")
    app.run(host='0.0.0.0', port=5000, debug=True)
