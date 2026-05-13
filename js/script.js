document.addEventListener('DOMContentLoaded', () => {
    // ----- Элементы DOM -----
    const sidebar = document.getElementById('sidebarLeft');
    const overlay = document.querySelector('.overlay');
    const openBtn = document.getElementById('openCatalog');
    const closeBtn = document.getElementById('closeSidebar');
    const backBtn = document.getElementById('backBtn');
    const catalogTitle = document.getElementById('catalogTitle');
    const catalogGrid = document.getElementById('catalogGrid');
    const searchInput = document.getElementById('searchInput');
    const searchClearBtn = document.getElementById('searchClearBtn');

    // ----- Состояние навигации (история) -----
    let historyStack = [];
    let catalogData = null; // будет загружен с сервера
    let currentSearchQuery = ''; // текущий поисковый запрос

    // ----- Функции для сохранения/восстановления состояния -----
    function saveState() {
        const state = {
            historyStack: historyStack,
            sidebarActive: sidebar.classList.contains('active')
        };
        sessionStorage.setItem('catalogState', JSON.stringify(state));
    }

    function restoreState() {
        const saved = sessionStorage.getItem('catalogState');
        if (!saved) return;

        try {
            const state = JSON.parse(saved);
            if (state.historyStack && Array.isArray(state.historyStack) && state.historyStack.length > 0) {
                historyStack = state.historyStack;
                renderCurrentLevel();

                if (state.sidebarActive) {
                    sidebar.removeAttribute('hidden');
                    overlay.removeAttribute('hidden');
                    sidebar.classList.add('active');
                    overlay.classList.add('active');
                    openBtn.setAttribute('aria-expanded', 'true');
                }
            }
        } catch (e) {
            console.warn('Не удалось восстановить состояние каталога', e);
        }
    }

    // ----- Вспомогательные функции -----
    function getIconPath(iconName) {
        // URLs-заглушки, которые следует заменять на logo.png
        const placeholderUrls = [
            'https://vm-ftp.anosov.ru/icons/folder.gif',
            'http://vm-ftp.anosov.ru/icons/folder.gif',
            'vm-ftp.anosov.ru/icons/folder.gif'
        ];
        
        // Если iconName пустой - возвращаем логотип по умолчанию
        if (!iconName || iconName.trim() === '') {
            return 'page/logo.png';
        }
        
        // Проверяем, является ли iconName URL-заглушкой
        for (const placeholderUrl of placeholderUrls) {
            if (iconName.includes(placeholderUrl)) {
                return 'page/logo.png';
            }
        }
        
        // Если iconName начинается с http:// или https:// – используем как есть
        if (iconName.startsWith('http://') || iconName.startsWith('https://')) {
            // Для внешних URL с vm-ftp.anosov.ru используем прокси для обхода rate limiting
            if (iconName.includes('vm-ftp.anosov.ru')) {
                return '/api/proxy-image?url=' + encodeURIComponent(iconName);
            }
            return iconName;
        }
        
        // Иначе используем локальный путь из папки page/
        return `page/${iconName}`;
    }

    // Функция поиска по всем элементам каталога (рекурсивно)
    function searchInCatalog(query, items = catalogData?.children || []) {
        if (!query || query.trim() === '') {
            return [];
        }
        
        const results = [];
        const lowerQuery = query.toLowerCase();
        
        function searchRecursive(itemsList, path = []) {
            for (const item of itemsList) {
                const currentPath = [...path, item.name];
                
                // Проверяем имя элемента
                if (item.name.toLowerCase().includes(lowerQuery)) {
                    results.push({
                        ...item,
                        searchPath: currentPath.join(' / ')
                    });
                }
                
                // Рекурсивно ищем в дочерних элементах
                if (item.children && item.children.length > 0) {
                    searchRecursive(item.children, currentPath);
                }
            }
        }
        
        searchRecursive(items);
        return results;
    }

    function renderCurrentLevel() {
        if (historyStack.length === 0) return;

        const currentLevel = historyStack[historyStack.length - 1];
        
        // Если есть активный поисковый запрос, показываем результаты поиска
        if (currentSearchQuery && currentSearchQuery.trim() !== '') {
            catalogTitle.textContent = `Поиск: "${currentSearchQuery}"`;
            const searchResults = searchInCatalog(currentSearchQuery);
            renderItems(searchResults, true);
        } else {
            catalogTitle.textContent = currentLevel.title;
            renderItems(currentLevel.items, false);
        }
        
        updateBackButton();
        saveState();
    }

    function renderItems(items, isSearchResults) {
        catalogGrid.innerHTML = '';

        if (items.length === 0) {
            const noResults = document.createElement('div');
            noResults.className = 'item';
            noResults.style.justifyContent = 'center';
            noResults.style.alignItems = 'center';
            noResults.style.color = '#999';
            noResults.style.fontSize = '16px';
            noResults.textContent = isSearchResults ? 'Ничего не найдено' : 'Пусто';
            catalogGrid.appendChild(noResults);
            return;
        }

        items.forEach(item => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'item';
            itemDiv.setAttribute('role', 'button');
            itemDiv.setAttribute('tabindex', '0');
            itemDiv.dataset.name = item.name;

            const img = document.createElement('img');
            img.className = 'item-icon';
            img.src = getIconPath(item.icon);
            img.alt = item.name;
            img.loading = 'lazy';
            img.onerror = () => { img.src = 'page/logo.png'; };

            const span = document.createElement('span');
            span.className = 'item-name';
            span.textContent = item.name;

            // Если это результаты поиска, добавляем путь к элементу
            if (isSearchResults && item.searchPath) {
                const pathSpan = document.createElement('span');
                pathSpan.className = 'item-search-path';
                pathSpan.textContent = item.searchPath;
                span.appendChild(document.createElement('br'));
                span.appendChild(pathSpan);
            }

            itemDiv.appendChild(img);
            itemDiv.appendChild(span);
            itemDiv._itemData = item;

            catalogGrid.appendChild(itemDiv);
        });
    }

    function updateBackButton() {
        backBtn.hidden = historyStack.length <= 1;
    }

    // ----- Функция: проверка, является ли файл видео -----
    function isVideoFile(url) {
        if (!url) return false;
        try {
            // Очищаем URL от пробелов по краям
            const trimmedUrl = url.trim();
            // Пытаемся декодировать URL, но если он уже содержит некорректные проценты - используем как есть
            let cleanUrl;
            try {
                cleanUrl = decodeURIComponent(trimmedUrl);
            } catch (e) {
                cleanUrl = trimmedUrl;
            }
            // Регулярное выражение для проверки расширения видео (с учётом возможных пробелов в конце)
            const videoExtensions = /\.(mp4|webm|ogg|mov|avi|mkv|flv|wmv|m4v)\s*$/i;
            const isVideo = videoExtensions.test(cleanUrl);
            console.log('isVideoFile check:', { original: url, trimmed: trimmedUrl, decoded: cleanUrl, isVideo: isVideo });
            return isVideo;
        } catch (e) {
            console.warn('Ошибка при проверке видео:', e);
            return false;
        }
    }

    // Функция для получения прокси-URL для видео
    function getVideoProxyUrl(url) {
        // Очищаем URL от пробелов и декодируем
        const cleanUrl = decodeURIComponent(url.trim());
        // Проверяем, является ли URL внешним (с vm-ftp.anosov.ru)
        if (cleanUrl.includes('vm-ftp.anosov.ru')) {
            return '/api/video-proxy?url=' + encodeURIComponent(cleanUrl);
        }
        // Для локальных или других URL возвращаем как есть
        return cleanUrl;
    }

    function handleItemClick(event) {
        const itemDiv = event.target.closest('.item');
        if (!itemDiv) return;

        const itemData = itemDiv._itemData;
        if (!itemData) return;

        if (itemData.children && itemData.children.length > 0) {
            // Папка – углубляемся
            historyStack.push({
                title: itemData.name,
                items: itemData.children
            });
            renderCurrentLevel();
        } else {
            // Конечный элемент (файл)
            if (itemData.url) {
                saveState();

                // Очищаем URL от лишних пробелов перед проверкой и использованием
                const cleanUrl = itemData.url.trim();
                
                console.log('handleItemClick:', { name: itemData.name, url: itemData.url, cleanUrl: cleanUrl });
                
                // Проверяем, является ли файл видео по расширению в URL
                if (isVideoFile(cleanUrl)) {
                    console.log('Это видео, открываем через video-player');
                    // Видео – открываем в новой вкладке через видеоплеер
                    const videoPlayerUrl = `/video-player?url=${encodeURIComponent(cleanUrl)}&name=${encodeURIComponent(itemData.name)}`;
                    console.log('Video player URL:', videoPlayerUrl);
                    window.open(videoPlayerUrl, '_blank');
                } else {
                    console.log('Это не видео, открываем напрямую');
                    // Остальные файлы – переход в текущей вкладке
                    window.location.href = cleanUrl;
                }
            } else {
                alert(`Вы выбрали: ${itemData.name}\n(URL не указан)`);
            }
        }
    }

    function goBack() {
        if (historyStack.length > 1) {
            historyStack.pop();
            renderCurrentLevel();
        } else if (currentSearchQuery) {
            // Если активен поиск, очищаем его и возвращаемся к корневому уровню
            clearSearch();
        }
    }

    function clearSearch() {
        currentSearchQuery = '';
        searchInput.value = '';
        searchClearBtn.hidden = true;
        resetToRoot();
    }

    function resetToRoot() {
        if (!catalogData) {
            setTimeout(resetToRoot, 100);
            return;
        }
        historyStack = [{
            title: catalogData.name,
            items: catalogData.children
        }];
        renderCurrentLevel();
    }

    // ----- Открытие/закрытие сайдбара -----
    function openSidebar() {
        if (!catalogData) {
            loadCatalog().then(() => openSidebar());
            return;
        }
        if (sidebar.classList.contains('active')) return;

        resetToRoot();

        sidebar.removeAttribute('hidden');
        overlay.removeAttribute('hidden');

        void sidebar.offsetHeight; // reflow

        sidebar.classList.add('active');
        overlay.classList.add('active');
        openBtn.setAttribute('aria-expanded', 'true');

        saveState();
    }

    function closeSidebar() {
        if (!sidebar.classList.contains('active')) return;

        sidebar.classList.remove('active');
        overlay.classList.remove('active');
        openBtn.setAttribute('aria-expanded', 'false');

        let transitionEnded = false;
        const onTransitionEnd = () => {
            if (transitionEnded) return;
            transitionEnded = true;

            sidebar.setAttribute('hidden', '');
            overlay.setAttribute('hidden', '');
            sidebar.removeEventListener('transitionend', onTransitionEnd);
            overlay.removeEventListener('transitionend', onTransitionEnd);
            clearTimeout(fallbackTimer);

            saveState();
        };

        const fallbackTimer = setTimeout(() => {
            if (!transitionEnded) {
                sidebar.removeEventListener('transitionend', onTransitionEnd);
                overlay.removeEventListener('transitionend', onTransitionEnd);
                sidebar.setAttribute('hidden', '');
                overlay.setAttribute('hidden', '');
                transitionEnded = true;
                saveState();
            }
        }, 1500);

        sidebar.addEventListener('transitionend', onTransitionEnd);
        overlay.addEventListener('transitionend', onTransitionEnd);
    }

    // ----- Загрузка каталога с сервера -----
    async function loadCatalog() {
        try {
            const response = await fetch('/api/catalog');
            if (!response.ok) throw new Error('Ошибка загрузки');
            catalogData = await response.json();
            if (sidebar.classList.contains('active')) {
                resetToRoot();
            }
            return catalogData;
        } catch (e) {
            console.error('Не удалось загрузить каталог:', e);
            catalogData = { name: 'Ошибка загрузки', children: [] };
        }
    }

    // Функция для обновления каталога при изменениях
    function refreshCatalog() {
        loadCatalog().then(() => {
            if (historyStack.length > 0) {
                renderCurrentLevel();
            }
        });
    }

    // ----- Обработчики событий -----
    openBtn.addEventListener('click', openSidebar);
    closeBtn.addEventListener('click', closeSidebar);
    overlay.addEventListener('click', closeSidebar);
    backBtn.addEventListener('click', goBack);

    catalogGrid.addEventListener('click', handleItemClick);

    catalogGrid.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            const item = e.target.closest('.item');
            if (item) {
                e.preventDefault();
                handleItemClick({ target: item });
            }
        }
    });

    // Обработчики для поиска
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        currentSearchQuery = query;
        
        // Показываем/скрываем кнопку очистки
        searchClearBtn.hidden = query === '';
        
        // Обновляем отображение
        renderCurrentLevel();
    });

    searchClearBtn.addEventListener('click', clearSearch);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sidebar.classList.contains('active')) {
            if (currentSearchQuery) {
                clearSearch();
            } else {
                closeSidebar();
            }
        }
    });

    // ----- Запуск: загружаем данные и восстанавливаем состояние -----
    (async () => {
        await loadCatalog();
        restoreState();
        
        // Слушаем события обновления из других вкладок (админ-панели)
        window.addEventListener('storage', (e) => {
            if (e.key === 'catalogUpdated') {
                refreshCatalog();
            }
        });
    })();
});