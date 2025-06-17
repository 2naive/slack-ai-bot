# Slack AI Bot для диагностики сайтов

Интеллектуальный Slack-бот для автоматической диагностики неработающих сайтов с использованием AI и глобальных сетевых проверок.

## ✨ Возможности

- 🤖 **AI-диагностика** с GPT-4o для анализа проблем
- 🌍 **Globalping REST API** для проверки из разных регионов
- 🔧 **Автоматические сетевые тесты** (ping, traceroute, nslookup, curl)
- ⚡ **Система восстановления** после ошибок с автоматическими повторами
- 💬 **Удобный Slack интерфейс** с результатами в threads
- 📊 **Итоговые отчеты** с рекомендациями по устранению

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

**Скопируйте файл-пример:**
```bash
cp .env.example .env
```

**Отредактируйте `.env` файл с вашими токенами:**

```env
SLACK_APP_TOKEN=xapp-your-real-app-token
SLACK_BOT_TOKEN=xoxb-your-real-bot-token  
OPENAI_API_KEY=sk-your-real-openai-key
GLOBALPING_API_TOKEN=your-real-globalping-token  # ОПЦИОНАЛЬНО
```

### 🔑 Получение токенов:

**Slack:**
1. Создайте приложение: https://api.slack.com/apps
2. Включите Socket Mode 
3. Добавьте Bot Token Scopes: `app_mentions:read`, `channels:read`, `chat:write`, `im:read`, `im:write`
4. Установите в workspace
5. Скопируйте App-Level Token и Bot User OAuth Token

**OpenAI:**
1. Аккаунт: https://platform.openai.com/
2. API Keys: https://platform.openai.com/api-keys
3. Создайте Secret Key

**Globalping (рекомендуется):**
1. Бесплатный аккаунт: https://www.globalping.io/
2. Dashboard → API Tokens
3. Создайте токен

### 🔑 Globalping API Token (Рекомендуется)

Для наиболее надежной работы рекомендуется получить **бесплатный** API токен из панели Globalping:

1. Зайдите на https://www.globalping.io/
2. Создайте бесплатный аккаунт
3. Перейдите в Dashboard → API Tokens  
4. Создайте новый токен и добавьте его в `.env` как `GLOBALPING_API_TOKEN`

**Преимущества использования токена:**
- ✅ Более высокий лимит запросов
- ✅ Более стабильная работа
- ✅ Доступ ко всем типам тестов (ping, http, traceroute, dns, mtr)
- ✅ Приоритетная обработка запросов

**Без токена:** бот все равно будет работать через публичный REST API.

### 3. Запуск бота

```bash
python slack_ai_bot.py
```

## 🔧 Безопасность и Git

**⚠️ ВАЖНО:** Файл `.env` содержит секретные токены и **НЕ ДОЛЖЕН** попадать в Git!

- ✅ `.env.example` — **коммитится** (примеры без секретов)
- ❌ `.env` — **в .gitignore** (реальные токены)
- ✅ `.gitignore` — **настроен** для безопасности

### 4. Тестирование интеграции

```bash
# Основной тест
python slack_ai_bot.py

# Тест токена (если настроен)
python -c "from globalping_with_token import comprehensive_token_test; print(comprehensive_token_test('YOUR_TOKEN', 'google.com'))"
```

## 📝 Использование

Просто отправьте в Slack сообщение с URL или IP-адресом:

```
example.com не работает
https://mysite.com/api падает
Проверьте 192.168.1.1
```

Бот автоматически:
1. 🔍 Извлечет цель из сообщения
2. 🌐 Проведет глобальные тесты через Globalping API
3. 💻 Выполнит локальные сетевые команды
4. 🧠 Сгенерирует анализ с помощью AI
5. 📋 Предоставит итоговый отчет с рекомендациями

## 🏗️ Архитектура с системой восстановления

```mermaid
graph TD
    A["👤 Slack User<br/>google.com не работает"] --> B["📱 Slack Bot"]
    B --> C["🧠 OpenAI GPT-4o<br/>AI Анализ"]
    C --> D["💻 Local Commands<br/>ping, nslookup, curl"]
    C --> E["🌐 Globalping Client"]
    
    E --> F{"🔑 API Token?"}
    F -->|"✅ Есть токен"| G["🚀 Direct REST API<br/>(Приоритет #1)"]
    F -->|"❌ Нет токена"| H["🌍 Public REST API<br/>(Приоритет #2)"]
    
    G --> I["📡 Global Probes<br/>RU, EU, US, AS"]
    H --> I
    
    I --> J["⚡ Error Recovery System"]
    J --> K{"❌ Ошибка?"}
    K -->|"🔄 Retry"| L["🔁 Автоповтор<br/>(до 3 попыток)"]
    K -->|"✅ Success"| M["📊 Test Results<br/>✅ PING: 15ms<br/>✅ HTTP: 200 OK"]
    
    L --> I
    
    D --> N["💻 Windows/Linux Results<br/>ping, nslookup, curl"]
    
    M --> O["🤖 AI Summary<br/>+ Recommendations"]
    N --> O
    
    O --> P["💬 Slack Response<br/>with diagnostics"]
    P --> A
    
    style E fill:#e1f5fe
    style G fill:#4caf50
    style H fill:#ff9800
    style J fill:#f44336
    style L fill:#ff5722
    style M fill:#4caf50
    style O fill:#fff3e0
```

**Компоненты:**
- **AI Engine**: OpenAI GPT-4o для анализа и рекомендаций
- **REST API Client**: Прямое подключение к Globalping API
- **Error Recovery**: Система восстановления с автоматическими повторами
- **Global Testing**: ping, http, traceroute, dns, mtr из 4 регионов
- **Local Testing**: Windows/Linux network commands
- **Slack Integration**: Bolt framework с Socket Mode

## ⚡ Система восстановления после ошибок

### Конфигурация

```python
ERROR_RECOVERY_CONFIG = {
    "max_retries": 3,              # Максимум попыток
    "retry_delay": 2,              # Задержка между попытками (сек)
    "timeout_increase_factor": 1.5, # Увеличение таймаута
    "fallback_locations": ["EU", "NA", "AS"], # Резервные локации
    "emergency_fallback": True     # Экстренный fallback
}
```

### Механизмы восстановления

**🔄 Автоматические повторы:**
- До 3 попыток для каждого теста
- Увеличивающиеся таймауты
- Интеллектуальные задержки

**🌍 Fallback стратегии:**
- API Token → Public API
- Расширенные локации → Базовые локации
- Полные тесты → Упрощенные тесты

**💻 Локальные команды:**
- Автоматические повторы с увеличенными таймаутами
- Восстановление после таймаутов
- Обработка недоступных команд

**🧠 AI анализ:**
- Fallback при недоступности OpenAI
- Показ сырых результатов при ошибках AI
- Graceful degradation

## 🔧 Конфигурация

### Globalping REST API тесты
- **ping**: Проверка доступности и задержки из разных регионов
- **http**: HTTP статус и время ответа
- **traceroute**: Анализ маршрутизации и узких мест
- **dns**: DNS резолюция и проверка серверов
- **mtr**: Комбинированный ping/traceroute анализ

### Локации тестирования
- **RU**: Россия (при наличии токена)
- **EU**: Европа
- **US**: США
- **AS**: Азия

### Локальные команды
- `ping` - проверка связи
- `nslookup` - DNS резолюция
- `curl` - HTTP запросы

## 🐛 Устранение проблем

**Сетевые ошибки**: Автоматические повторы до 3 раз

**Таймауты команд**: Увеличивающиеся таймауты с каждой попыткой

**Ошибки Globalping**: Автоматический fallback к публичному API

**Проблемы AI**: Показ сырых результатов при недоступности OpenAI

**Проблемы Slack**: Уведомления об ошибках в чате

### 🎯 Преимущества новой архитектуры

**✅ УПРОЩЕННАЯ АРХИТЕКТУРА:**
- Убрана сложность MCP
- Только REST API интеграция
- Чистый и понятный код

**✅ НАДЕЖНОСТЬ:**
- Система восстановления после ошибок
- Автоматические fallback механизмы
- Intelligent retry с экспоненциальной задержкой

**✅ ПРОИЗВОДИТЕЛЬНОСТЬ:**
- Прямые REST API вызовы
- Оптимизированные таймауты
- Параллельные запросы

**Готов к продакшену!** 🚀

## 📁 Структура проекта

### Основные файлы:
- `slack_ai_bot.py` - Главный Slack бот с системой восстановления
- `globalping_with_token.py` - REST API клиент для Globalping
- `requirements.txt` - Зависимости Python
- `.env.example` - **Пример файла конфигурации** (коммитится в Git)
- `.gitignore` - **Правила исключения Git** (токены, cache, logs)
- `README.md` - Документация

## 📦 Зависимости

- `slack-bolt` - Slack интеграция
- `openai` - AI анализ
- `requests` - HTTP клиент
- `python-dotenv` - Переменные окружения

## 🔒 Безопасность

- Используйте переменные окружения для API ключей
- Ограничьте права Slack бота минимально необходимыми
- Регулярно обновляйте зависимости
- Мониторьте использование API лимитов 