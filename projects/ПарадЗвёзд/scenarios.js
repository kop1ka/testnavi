// Переменные состояния
let currentScenarioData = null;
let currentScenarioFileName = '';

// Загрузка сценариев при старте
document.addEventListener('DOMContentLoaded', function() {
    // Проверка авторизации
    if (sessionStorage.getItem('isAdmin') !== 'true') {
        alert('Доступ запрещён! Требуется авторизация.');
        window.location.href = '/login.html';
        return;
    }
    loadScenarios();
});


// Показать форму добавления
function showAddScenarioForm() {
    document.getElementById('scenarioFormCard').style.display = 'block';
    clearScenarioForm();
}

// Открыть папку на сервере
function openServerFolder() {
    window.open('https://vm-fb.anosov.ru/files/Парад/', '_blank');
}

// Загрузка сценария по URL
function loadScenarioFromUrl() {
    const url = document.getElementById('scenarioUrlInput').value.trim();
    
    if (!url) {
        alert('Пожалуйста, вставьте ссылку на файл');
        return;
    }
    
    // Извлекаем имя файла из URL
    const urlParts = url.split('/');
    const fileName = decodeURIComponent(urlParts[urlParts.length - 1]);
    
    // Сохраняем URL файла
    currentScenarioFileName = fileName;
    currentScenarioData = url;
    
    document.getElementById('fileName').textContent = fileName;
    document.getElementById('filePreview').style.display = 'block';
}

// Сохранение сценария
async function saveScenario() {
    const name = document.getElementById('scenarioName').value.trim();
    
    if (!name || !currentScenarioData) {
        alert('Пожалуйста, заполните все поля');
        return;
    }
    
    try {
        const scenarioData = {
            name: name,
            fileName: currentScenarioFileName,
            fileData: currentScenarioData,
            createdAt: new Date().toLocaleDateString('ru-RU')
        };
        
        const response = await fetch('api/scenarios', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(scenarioData)
        });
        
        if (response.ok) {
            loadScenarios();
            cancelScenarioForm();
        } else {
            const error = await response.json();
            alert('Ошибка при сохранении: ' + (error.message || 'Неизвестная ошибка'));
        }
    } catch (error) {
        console.error('Ошибка сохранения:', error);
        alert('Ошибка подключения к серверу');
    }
}

// Отмена формы
function cancelScenarioForm() {
    document.getElementById('scenarioFormCard').style.display = 'none';
    clearScenarioForm();
}

// Очистка формы
function clearScenarioForm() {
    document.getElementById('scenarioName').value = '';
    document.getElementById('scenarioUrlInput').value = '';
    const filePreview = document.getElementById('filePreview');
    if (filePreview) {
        filePreview.style.display = 'none';
    }
    currentScenarioData = null;
    currentScenarioFileName = '';
}

// Удаление сценария
async function deleteScenario(scenarioId) {
    if (!confirm('Вы уверены, что хотите удалить этот сценарий?')) {
        return;
    }
    
    try {
        const response = await fetch(`api/scenarios/${scenarioId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            loadScenarios();
        } else {
            alert('Ошибка при удалении сценария');
        }
    } catch (error) {
        console.error('Ошибка удаления:', error);
        alert('Ошибка подключения к серверу');
    }
}

// Просмотр сценария
async function viewScenario(scenarioId) {
    const scenarios = await getScenarios();
    const scenario = scenarios.find(s => s.id === scenarioId);
    
    if (!scenario) return;
    
    document.getElementById('modalTitle').textContent = scenario.name;
    
    const modalBody = document.getElementById('modalBody');
    
    const fileExtension = scenario.fileName.split('.').pop().toLowerCase();
    
    if (fileExtension === 'pdf') {
        modalBody.innerHTML = `
            <embed src="${scenario.fileData}" type="application/pdf" width="100%" height="600px" />
            <p style="text-align: center; margin-top: 10px;">
                <a href="${scenario.fileData}" target="_blank" class="btn btn-primary">
                    Открыть в новой вкладке
                </a>
            </p>
        `;
    } else if (fileExtension === 'txt') {
        fetch(scenario.fileData)
            .then(response => response.text())
            .then(text => {
                modalBody.innerHTML = `
                    <pre style="white-space: pre-wrap; word-wrap: break-word; max-height: 600px; overflow-y: auto; padding: 20px; background: #f9fafb; border-radius: 8px;">${escapeHtml(text)}</pre>
                    <p style="text-align: center; margin-top: 10px;">
                        <a href="${scenario.fileData}" target="_blank" class="btn btn-primary">
                            Открыть в новой вкладке
                        </a>
                    </p>
                `;
            })
            .catch(error => {
                modalBody.innerHTML = `
                    <div style="text-align: center; padding: 40px;">
                        <div style="font-size: 4rem; margin-bottom: 20px;">⚠️</div>
                        <p style="color: #6b7280;">Не удалось загрузить файл с сервера</p>
                        <p style="text-align: center; margin-top: 10px;">
                            <a href="${scenario.fileData}" target="_blank" class="btn btn-primary">
                                Открыть в новой вкладке
                            </a>
                        </p>
                    </div>
                `;
            });
    } else {
        modalBody.innerHTML = `
            <div style="text-align: center; padding: 40px;">
                <div style="font-size: 4rem; margin-bottom: 20px;">📄</div>
                <h3>${escapeHtml(scenario.fileName)}</h3>
                <p style="color: #6b7280; margin: 20px 0;">Файл формата ${fileExtension.toUpperCase()}</p>
                <p style="color: #6b7280; margin-bottom: 30px;">Файл будет открыт с сервера</p>
                <a href="${scenario.fileData}" target="_blank" class="btn btn-primary">
                    Открыть в новой вкладке
                </a>
            </div>
        `;
    }
    
    document.getElementById('scenarioModal').style.display = 'flex';
}

// Закрыть модальное окно
function closeScenarioModal() {
    document.getElementById('scenarioModal').style.display = 'none';
}

// Закрытие по клику вне модального окна
window.onclick = function(event) {
    const modal = document.getElementById('scenarioModal');
    if (event.target === modal) {
        closeScenarioModal();
    }
}

// Получение сценариев из API
async function getScenarios() {
    try {
        const response = await fetch('api/scenarios');
        if (response.ok) {
            return await response.json();
        }
        return [];
    } catch (error) {
        console.error('Ошибка загрузки:', error);
        return [];
    }
}

// Сохранение сценариев в API (не используется напрямую, оставлено для совместимости)
async function saveScenarios(scenarios) {
    // Данные сохраняются через saveScenario
}

// Загрузка и отображение сценариев
async function loadScenarios() {
    const scenarios = await getScenarios();
    const scenariosList = document.getElementById('scenariosList');
    const emptyState = document.getElementById('emptyState');
    
    if (!scenariosList || !emptyState) return;
    
    if (scenarios.length === 0) {
        emptyState.style.display = 'block';
        const cards = scenariosList.querySelectorAll('.scenario-card');
        cards.forEach(card => card.remove());
        return;
    }
    
    emptyState.style.display = 'none';
    
    const cards = scenariosList.querySelectorAll('.scenario-card');
    cards.forEach(card => card.remove());
    
    scenarios.forEach(scenario => {
        const card = createScenarioCard(scenario);
        scenariosList.appendChild(card);
    });
}

// Создание карточки сценария
function createScenarioCard(scenario) {
    const card = document.createElement('div');
    card.className = 'scenario-card';
    
    const fileExtension = scenario.fileName.split('.').pop().toLowerCase();
    let fileIcon = '📄';
    
    if (fileExtension === 'pdf') {
        fileIcon = '📕';
    } else if (fileExtension === 'doc' || fileExtension === 'docx') {
        fileIcon = '📘';
    } else if (fileExtension === 'txt') {
        fileIcon = '📝';
    }
    
    card.innerHTML = `
        <div class="scenario-icon" onclick="viewScenario('${scenario.id}')">
            <div class="icon-circle">
                <span class="file-icon">${fileIcon}</span>
            </div>
            <p class="scenario-name">${escapeHtml(scenario.name)}</p>
            <p class="scenario-date">${scenario.createdAt}</p>
        </div>
        <div class="scenario-actions">
            <button class="btn-icon btn-view" onclick="viewScenario('${scenario.id}')" title="Просмотреть">
                👁️
            </button>
            <button class="btn-icon btn-delete" onclick="deleteScenario('${scenario.id}')" title="Удалить">
                🗑️
            </button>
        </div>
    `;
    
    return card;
}

// Экранирование HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
