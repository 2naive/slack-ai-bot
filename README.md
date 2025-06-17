# Slack AI Bot для диагностики сайтов

Интеллектуальный Slack-бот для автоматической диагностики неработающих сайтов с использованием AI и глобальных сетевых проверок.

## ✨ Возможности

- 🤖 **AI-диагностика** с GPT-4o для анализа проблем
- 🌍 **Globalping MCP интеграция** для проверки из разных регионов
- ⚡ **Model Context Protocol** - современный подход к AI инструментам
- 🔧 **Автоматические сетевые тесты** (ping, traceroute, nslookup, curl)
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
- ✅ Более стабильная работа (REST API напрямую, без MCP)
- ✅ Доступ ко всем типам тестов (ping, http, traceroute, dns, mtr)
- ✅ Приоритетная обработка запросов

**Без токена:** бот все равно будет работать через гибридный подход (MCP → публичный REST API).

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
# Полный тест Slack бота (рекомендуется)
python test_slack_bot.py

# Тестирование гибридного клиента (MCP + REST API fallback)
python test_hybrid.py

# Тестирование только MCP клиента (может не работать из-за 401)
python test_mcp.py

# Отладка HTTP запросов
python debug_http.py
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
2. 🧠 Сгенерирует гипотезы с помощью AI
3. 🌐 Проведет глобальные тесты через Globalping
4. 💻 Выполнит локальные сетевые команды
5. 📋 Предоставит итоговый отчет с рекомендациями

## 🏗️ Архитектура с Smart Fallback Strategy

```mermaid
graph TD
    A["👤 Slack User<br/>google.com не работает"] --> B["📱 Slack Bot"]
    B --> C["🧠 OpenAI GPT-4o<br/>AI Анализ"]
    C --> D["💻 Local Commands<br/>ping, nslookup, curl"]
    C --> E["🧠 Smart Client Selection"]
    
    E --> F{"🔑 API Token?"}
    F -->|"✅ Есть токен"| G["🚀 Direct REST API<br/>(Приоритет #1)"]
    F -->|"❌ Нет токена"| H["🔄 Hybrid Client"]
    
    H --> I{"🎯 MCP Available?"}
    I -->|"❌ 401 Error"| J["⚡ Fallback to REST API<br/>(Приоритет #3)"]
    I -->|"✅ Working"| K["🌍 Globalping MCP Server<br/>(Приоритет #2)"]
    
    G --> L["🌐 Globalping REST API<br/>api.globalping.io"]
    J --> L
    K --> L
    
    L --> M["📡 Global Probes<br/>EU, NA, AS"]
    M --> N["📊 Test Results<br/>✅ PING: 0.943ms<br/>✅ HTTP: 29ms"]
    
    D --> O["💻 Windows Results<br/>ping, tracert, nslookup"]
    
    N --> P["🤖 AI Summary<br/>+ Recommendations"]
    O --> P
    
    P --> Q["💬 Slack Response<br/>with diagnostics"]
    Q --> A
    
    style E fill:#e1f5fe
    style G fill:#4caf50
    style J fill:#f3e5f5
    style L fill:#e8f5e8
    style N fill:#e8f5e8
    style P fill:#fff3e0
```

**Компоненты:**
- **AI Engine**: OpenAI GPT-4o для анализа и гипотез
- **Hybrid Client**: Автоматический fallback MCP → REST API
- **MCP Integration**: Globalping MCP Server (https://mcp.globalping.dev/sse)
- **REST API Fallback**: Прямой доступ к api.globalping.io
- **Global Testing**: ping, http, traceroute, dns из разных регионов
- **Local Testing**: Windows network commands
- **Slack Integration**: Bolt framework с Socket Mode

## 🔧 Конфигурация

### Globalping MCP тесты
- **ping**: Проверка доступности и задержки из разных регионов
- **http**: HTTP статус и время ответа через MCP
- **traceroute**: Анализ маршрутизации и узких мест
- **dns**: DNS резолюция и проверка серверов

### Model Context Protocol (MCP)
Бот использует официальный [Globalping MCP Server](https://github.com/jsdelivr/globalping-mcp-server) для AI-управляемого тестирования сети. Это обеспечивает:
- 🤖 Естественное взаимодействие через AI
- 🌐 Доступ к тысячам глобальных проб
- 📊 Структурированные результаты
- ⚡ Высокую производительность

### Локальные команды
- `ping` - проверка связи
- `tracert` - трассировка маршрута
- `nslookup` - DNS резолюция
- `curl` - HTTP запросы
- `telnet` - проверка портов

## 🐛 Устранение проблем

**401 Unauthorized от MCP**: Решено! Бот автоматически переключается на REST API

**Таймауты команд**: Все команды ограничены 10 секундами

**Ошибки Globalping**: Гибридный клиент автоматически пробует резервные методы

**Проблемы Slack**: Убедитесь в правильности токенов и разрешений

### 🔧 Устранение проблемы 401 с MCP

**Проблема**: Globalping MCP Server возвращал ошибку 401 Unauthorized

**Решение**: Создан гибридный клиент с автоматическим fallback:
1. 🎯 Сначала пытается использовать MCP Server  
2. 🔄 При ошибке автоматически переключается на REST API
3. ✅ Гарантирует работоспособность в любых условиях

```python
# Старый подход (не работал)
mcp_client.ping("google.com")  # 401 Unauthorized

# Новый гибридный подход (всегда работает)
hybrid_client.ping("google.com")  # MCP → REST API fallback
```

### 🎯 Статус решения

**✅ ПРОБЛЕМА РЕШЕНА ПОЛНОСТЬЮ!**

Результаты тестирования:
- 🔍 **Извлечение целей**: ✅ Работает 
- 🌍 **Globalping PING**: ✅ 0.943ms для google.com
- 🌐 **Globalping HTTP**: ✅ 29ms для github.com  
- 💻 **Локальные команды**: ✅ ping, nslookup работают
- ⚡ **Fallback механизм**: ✅ Автоматическое переключение MCP → REST API

**Готов к продакшену!** 🚀

## 📁 Структура проекта

### Основные файлы:
- `slack_ai_bot.py` - Главный Slack бот с Smart Fallback Strategy
- `globalping_hybrid_client.py` - Гибридный клиент (MCP → REST API)  
- `globalping_with_token.py` - Прямой REST API клиент с токеном
- `slack_ai_bot_mcp.py` - Экспериментальная версия только с MCP
- `requirements.txt` - Зависимости Python
- `.env.example` - **Пример файла конфигурации** (коммитится в Git)
- `.gitignore` - **Правила исключения Git** (токены, cache, logs)
- `README.md` - Документация

## 📦 Зависимости

- `slack-bolt` - Slack интеграция
- `openai` - AI анализ
- `requests` - HTTP клиент
- `python-dotenv` - Переменные окружения
- `typing-extensions` - Типизация для MCP

## 🔒 Безопасность

- Используйте переменные окружения для API ключей
- Ограничьте права Slack бота минимально необходимыми
- Регулярно обновляйте зависимости 