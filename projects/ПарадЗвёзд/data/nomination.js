// Получение ID номинации из URL
const urlParams = new URLSearchParams(window.location.search);
const nominationId = urlParams.get('id') || 'default';

const nominationNames = {
    'zvezdnyy-lider': 'Звёздный лидер',
    'zvezdnyy-nastavnik': 'Звёздный наставник',
    'zvezdnyy-partner': 'Звёздный партнёр',
    'zvezdnyy-aktiv': 'Звёздный актив',
    'zvezdnaya-stsena': 'Звёздная сцена',
    'zvezdnaya-podderzhka': 'Звёздная поддержка',
    'zvezdnyy-start': 'Звёздный старт',
    'zvezdnoe-stremlenie': 'Звёздное стремление',
    'zvezdnoe-masterstvo': 'Звёздное мастерство',
    'zvezdnyy-intellekt': 'Звёздный интеллект',
    'zvezdnyy-vypusknik': 'Звёздный выпускник'
};

// Переменные состояния
let currentPhotoData = '';
let editingEntryId = null;

// Загрузка записей при старте
document.addEventListener('DOMContentLoaded', function() {
    // Проверка авторизации
    if (localStorage.getItem('isAdmin') !== 'true') {
        alert('Доступ запрещён! Требуется авторизация.');
        window.location.href = 'login.html';
        return;
    }

    const titleElement = document.getElementById('nominationTitle');
    if (titleElement) {
        titleElement.textContent = nominationNames[nominationId] || 'Номинация';
    }
    loadEntries();
});

// Показать форму добавления
function showAddForm() {
    document.getElementById('formCard').style.display = 'block';
    document.getElementById('formTitle').textContent = 'Добавить новую запись';
    document.getElementById('saveButtonText').textContent = 'Добавить';
    editingEntryId = null;
    clearForm();
}

// Открыть папку на сервере
function openServerFolder() {
    window.open('https://vm-ftp.anosov.ru/vm/Парад/', '_blank');
}

// Загрузка фото по URL
function loadPhotoFromUrl() {
    const url = document.getElementById('photoUrlInput').value.trim();
    
    if (!url) {
        alert('Пожалуйста, вставьте ссылку на изображение');
        return;
    }
    
    // Сохраняем URL и показываем предпросмотр
    currentPhotoData = url;
    document.getElementById('previewImg').src = url;
    document.getElementById('photoPreview').style.display = 'block';
}

// Сохранение записи
function saveEntry() {
    const description = document.getElementById('descriptionInput').value.trim();
    
    if (!currentPhotoData || !description) {
        alert('Пожалуйста, заполните все поля');
        return;
    }
    
    const entries = getEntries();
    
    if (editingEntryId) {
        const index = entries.findIndex(e => e.id === editingEntryId);
        if (index !== -1) {
            entries[index] = {
                id: editingEntryId,
                photo: currentPhotoData,
                description: description
            };
        }
    } else {
        entries.push({
            id: Date.now().toString(),
            photo: currentPhotoData,
            description: description
        });
    }
    
    saveEntries(entries);
    loadEntries();
    cancelForm();
}

// Отмена формы
function cancelForm() {
    document.getElementById('formCard').style.display = 'none';
    clearForm();
}

// Очистка формы
function clearForm() {
    document.getElementById('photoUrlInput').value = '';
    document.getElementById('descriptionInput').value = '';
    document.getElementById('photoPreview').style.display = 'none';
    currentPhotoData = '';
    editingEntryId = null;
}

// Редактирование записи
function editEntry(entryId) {
    const entries = getEntries();
    const entry = entries.find(e => e.id === entryId);
    
    if (!entry) return;
    
    editingEntryId = entryId;
    currentPhotoData = entry.photo;
    
    document.getElementById('photoUrlInput').value = entry.photo;
    document.getElementById('descriptionInput').value = entry.description;
    document.getElementById('previewImg').src = entry.photo;
    document.getElementById('photoPreview').style.display = 'block';
    
    document.getElementById('formTitle').textContent = 'Редактировать запись';
    document.getElementById('saveButtonText').textContent = 'Сохранить изменения';
    document.getElementById('formCard').style.display = 'block';
    
    document.getElementById('formCard').scrollIntoView({ behavior: 'smooth' });
}

// Удаление записи
function deleteEntry(entryId) {
    if (!confirm('Вы уверены, что хотите удалить эту запись?')) {
        return;
    }
    
    const entries = getEntries();
    const filteredEntries = entries.filter(e => e.id !== entryId);
    saveEntries(filteredEntries);
    loadEntries();
}

// Получение записей из localStorage
function getEntries() {
    const data = localStorage.getItem('nomination-' + nominationId);
    return data ? JSON.parse(data) : [];
}

// Сохранение записей в localStorage
function saveEntries(entries) {
    localStorage.setItem('nomination-' + nominationId, JSON.stringify(entries));
}

// Загрузка и отображение записей
function loadEntries() {
    const entries = getEntries();
    const entriesList = document.getElementById('entriesList');
    const emptyState = document.getElementById('emptyState');
    
    if (!entriesList || !emptyState) return;
    
    if (entries.length === 0) {
        emptyState.style.display = 'block';
        const cards = entriesList.querySelectorAll('.entry-card');
        cards.forEach(card => card.remove());
        return;
    }
    
    emptyState.style.display = 'none';
    
    const cards = entriesList.querySelectorAll('.entry-card');
    cards.forEach(card => card.remove());
    
    entries.forEach(entry => {
        const card = createEntryCard(entry);
        entriesList.appendChild(card);
    });
}

// Создание карточки записи
function createEntryCard(entry) {
    const card = document.createElement('div');
    card.className = 'entry-card';
    
    const photoUrl = entry.photo || '';
    const description = escapeHtml(entry.description || '');
    const entryId = entry.id || '';
    
    card.innerHTML = `
        <div class="entry-content">
            <div class="entry-photo">
                <img src="${photoUrl}" alt="Фото">
            </div>
            <div class="entry-details">
                <p class="entry-description">${description}</p>
                <div class="entry-actions">
                    <button class="btn btn-edit" onclick="editEntry('${entryId}')">
                        <span class="icon">✏️</span> Редактировать
                    </button>
                    <button class="btn btn-delete" onclick="deleteEntry('${entryId}')">
                        <span class="icon">🗑️</span> Удалить
                    </button>
                </div>
            </div>
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
