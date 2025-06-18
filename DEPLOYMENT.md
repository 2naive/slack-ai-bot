# 🚀 Развертывание Slack AI Bot через systemd

## 📋 Быстрая установка

### 1. Подготовка

```bash
# Клонируйте репозиторий
git clone <your-repo-url>
cd slack-ai-bot

# Создайте конфигурацию
cp env.example .env
nano .env  # Заполните токены
```

### 2. Автоматическая установка

```bash
# Сделайте скрипт исполняемым
chmod +x install.sh

# Запустите установку (требуется sudo)
sudo ./install.sh
```

### 3. Запуск бота

```bash
# Запустить бота
sudo systemctl start slack-ai-bot

# Проверить статус
sudo systemctl status slack-ai-bot

# Посмотреть логи
sudo journalctl -u slack-ai-bot -f
```

---

## 🔧 Ручная установка

### 1. Создание пользователя

```bash
sudo groupadd --system slackbot
sudo useradd --system --gid slackbot --home-dir /opt/slack-ai-bot --shell /bin/false slackbot
```

### 2. Копирование файлов

```bash
sudo mkdir -p /opt/slack-ai-bot/logs
sudo cp *.py requirements.txt README.md /opt/slack-ai-bot/
sudo cp .env /opt/slack-ai-bot/  # Ваш настроенный .env файл
```

### 3. Установка зависимостей

```bash
cd /opt/slack-ai-bot
sudo python3 -m venv venv
sudo /opt/slack-ai-bot/venv/bin/pip install -r requirements.txt
```

### 4. Настройка прав

```bash
sudo chown -R slackbot:slackbot /opt/slack-ai-bot
sudo chmod 600 /opt/slack-ai-bot/.env
```

### 5. Установка systemd service

```bash
sudo cp slack-ai-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable slack-ai-bot
```

---

## 🎛️ Управление сервисом

### Основные команды

```bash
# Запуск
sudo systemctl start slack-ai-bot

# Остановка
sudo systemctl stop slack-ai-bot

# Перезапуск
sudo systemctl restart slack-ai-bot

# Статус
sudo systemctl status slack-ai-bot

# Включить автозапуск
sudo systemctl enable slack-ai-bot

# Отключить автозапуск
sudo systemctl disable slack-ai-bot
```

### Просмотр логов

```bash
# Последние логи (в реальном времени)
sudo journalctl -u slack-ai-bot -f

# Логи за последний час
sudo journalctl -u slack-ai-bot --since "1 hour ago"

# Логи за сегодня
sudo journalctl -u slack-ai-bot --since today

# Все логи
sudo journalctl -u slack-ai-bot --no-pager
```

---

## 📁 Структура после установки

```
/opt/slack-ai-bot/
├── slack_ai_bot.py              # Основной файл бота
├── globalping_with_token.py     # Globalping клиент
├── requirements.txt             # Зависимости
├── .env                         # Конфигурация (токены)
├── logs/                        # Директория логов
└── venv/                        # Виртуальное окружение
    └── bin/python               # Python интерпретер

/etc/systemd/system/
└── slack-ai-bot.service         # Systemd unit файл
```

---

## 🔍 Диагностика проблем

### Проверка конфигурации

```bash
# Проверить переменные окружения
sudo -u slackbot cat /opt/slack-ai-bot/.env

# Проверить права доступа
ls -la /opt/slack-ai-bot/

# Проверить Python зависимости
sudo -u slackbot /opt/slack-ai-bot/venv/bin/pip list
```

### Тестирование бота

```bash
# Запуск в режиме отладки (не через systemd)
sudo -u slackbot /opt/slack-ai-bot/venv/bin/python /opt/slack-ai-bot/slack_ai_bot.py

# Проверка сетевых соединений
sudo netstat -tulpn | grep python
```

### Частые проблемы

**❌ Бот не запускается:**
1. Проверьте токены в `.env` файле
2. Проверьте права доступа: `ls -la /opt/slack-ai-bot/`
3. Посмотрите логи: `journalctl -u slack-ai-bot`

**❌ "Permission denied":**
```bash
sudo chown -R slackbot:slackbot /opt/slack-ai-bot
sudo chmod 600 /opt/slack-ai-bot/.env
```

**❌ "Module not found":**
```bash
cd /opt/slack-ai-bot
sudo /opt/slack-ai-bot/venv/bin/pip install -r requirements.txt
```

---

## 🔄 Обновление бота

```bash
# Остановить бота
sudo systemctl stop slack-ai-bot

# Сделать резервную копию
sudo cp -r /opt/slack-ai-bot /opt/slack-ai-bot.backup

# Обновить файлы
sudo cp *.py /opt/slack-ai-bot/
sudo cp requirements.txt /opt/slack-ai-bot/

# Обновить зависимости
cd /opt/slack-ai-bot
sudo /opt/slack-ai-bot/venv/bin/pip install -r requirements.txt

# Восстановить права
sudo chown -R slackbot:slackbot /opt/slack-ai-bot

# Запустить бота
sudo systemctl start slack-ai-bot
```

---

## 🔒 Безопасность

### Настройки systemd service

- **User/Group**: Запуск от отдельного пользователя `slackbot`
- **ProtectSystem**: Защита системных директорий
- **PrivateTmp**: Изолированная временная папка  
- **NoNewPrivileges**: Запрет повышения привилегий
- **MemoryMax**: Ограничение памяти (512MB)

### Файловые права

```bash
# Конфигурация доступна только владельцу
chmod 600 /opt/slack-ai-bot/.env

# Исполняемые файлы недоступны для записи
chmod 644 /opt/slack-ai-bot/*.py
```

---

## 📊 Мониторинг

### Проверка ресурсов

```bash
# Использование CPU и памяти
sudo systemctl status slack-ai-bot

# Детальная информация о процессе
sudo ps aux | grep slack_ai_bot

# Использование памяти
sudo cat /proc/$(pgrep -f slack_ai_bot)/status | grep VmRSS
```

### Логирование

- **Системные логи**: `journalctl -u slack-ai-bot`
- **Ротация логов**: Автоматическая через systemd-journald
- **Уровень детализации**: INFO, WARNING, ERROR

---

## ✅ Готово!

После установки ваш Slack AI Bot будет:

- 🚀 **Автоматически запускаться** при загрузке системы
- 🔄 **Перезапускаться** при ошибках  
- 📊 **Логировать** все события через journald
- 🔒 **Работать безопасно** с минимальными привилегиями
- ⚡ **Мониториться** через systemctl 