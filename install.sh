#!/bin/bash

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции вывода
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Проверяем права root
if [[ $EUID -ne 0 ]]; then
   log_error "Этот скрипт должен быть запущен с правами root (sudo)"
   exit 1
fi

log_info "🚀 Установка Slack AI Bot для systemd..."

# Константы
BOT_USER="slackbot"
BOT_GROUP="slackbot"
INSTALL_DIR="/opt/slack-ai-bot"
SERVICE_NAME="slack-ai-bot"
CURRENT_DIR="$(pwd)"

# 1. Создаем пользователя и группу
log_info "👤 Создание пользователя и группы..."
if ! id "$BOT_USER" &>/dev/null; then
    groupadd --system "$BOT_GROUP"
    useradd --system --gid "$BOT_GROUP" --home-dir "$INSTALL_DIR" --shell /bin/false "$BOT_USER"
    log_success "Пользователь $BOT_USER создан"
else
    log_info "Пользователь $BOT_USER уже существует"
fi

# 2. Создаем директорию установки
log_info "📁 Создание директории установки..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/logs"

# 3. Копируем файлы
log_info "📋 Копирование файлов проекта..."
cp "$CURRENT_DIR"/*.py "$INSTALL_DIR/"
cp "$CURRENT_DIR"/requirements.txt "$INSTALL_DIR/"
cp "$CURRENT_DIR"/README.md "$INSTALL_DIR/"

# Копируем .env файл если существует
if [[ -f "$CURRENT_DIR/.env" ]]; then
    cp "$CURRENT_DIR/.env" "$INSTALL_DIR/"
    log_success "Конфигурация .env скопирована"
else
    log_warning "Файл .env не найден! Создайте его вручную в $INSTALL_DIR/"
fi

# 4. Устанавливаем Python 3 и pip
log_info "🐍 Проверка Python и установка зависимостей..."
if ! command -v python3 &> /dev/null; then
    log_info "Установка Python 3..."
    apt-get update
    apt-get install -y python3 python3-pip python3-venv
fi

# 5. Создаем виртуальное окружение
log_info "🔧 Создание виртуального окружения..."
cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
log_success "Виртуальное окружение создано и зависимости установлены"

# 6. Устанавливаем права доступа
log_info "🔒 Настройка прав доступа..."
chown -R "$BOT_USER:$BOT_GROUP" "$INSTALL_DIR"
chmod 755 "$INSTALL_DIR"
chmod 644 "$INSTALL_DIR"/*.py
chmod 600 "$INSTALL_DIR/.env" 2>/dev/null || log_warning "Файл .env не найден"
chmod 755 "$INSTALL_DIR/logs"

# 7. Копируем и устанавливаем systemd service
log_info "⚙️ Установка systemd service..."
cp "$CURRENT_DIR/slack-ai-bot.service" "/etc/systemd/system/"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
log_success "Systemd service установлен и включен"

# 8. Проверяем конфигурацию .env
log_info "🔍 Проверка конфигурации..."
if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    log_error "❌ Файл .env не найден!"
    log_info "📝 Создайте файл $INSTALL_DIR/.env со следующими переменными:"
    cat << EOF

SLACK_APP_TOKEN=xapp-your-app-token
SLACK_BOT_TOKEN=xoxb-your-bot-token
OPENAI_API_KEY=sk-your-openai-key
GLOBALPING_API_TOKEN=your-globalping-token

EOF
else
    # Проверяем наличие обязательных переменных
    source "$INSTALL_DIR/.env"
    missing_vars=()
    
    [[ -z "$SLACK_APP_TOKEN" ]] && missing_vars+=("SLACK_APP_TOKEN")
    [[ -z "$SLACK_BOT_TOKEN" ]] && missing_vars+=("SLACK_BOT_TOKEN")
    [[ -z "$OPENAI_API_KEY" ]] && missing_vars+=("OPENAI_API_KEY")
    
    if [[ ${#missing_vars[@]} -eq 0 ]]; then
        log_success "✅ Все обязательные переменные настроены"
        [[ -z "$GLOBALPING_API_TOKEN" ]] && log_warning "⚠️ GLOBALPING_API_TOKEN не установлен (будет использован публичный API)"
    else
        log_error "❌ Отсутствуют переменные: ${missing_vars[*]}"
        log_info "Отредактируйте файл $INSTALL_DIR/.env"
    fi
fi

log_success "🎉 Установка завершена!"

# Показываем инструкции по использованию
cat << EOF

${GREEN}📚 КАК ПОЛЬЗОВАТЬСЯ:${NC}

${BLUE}🚀 Запуск бота:${NC}
sudo systemctl start $SERVICE_NAME

${BLUE}🛑 Остановка бота:${NC}
sudo systemctl stop $SERVICE_NAME

${BLUE}🔄 Перезапуск бота:${NC}
sudo systemctl restart $SERVICE_NAME

${BLUE}📊 Статус бота:${NC}
sudo systemctl status $SERVICE_NAME

${BLUE}📜 Просмотр логов:${NC}
sudo journalctl -u $SERVICE_NAME -f
sudo journalctl -u $SERVICE_NAME --since "1 hour ago"

${BLUE}🔧 Отключение автозапуска:${NC}
sudo systemctl disable $SERVICE_NAME

${BLUE}⚙️ Конфигурация:${NC}
Файл настроек: $INSTALL_DIR/.env
Логи приложения: $INSTALL_DIR/logs/
Systemd service: /etc/systemd/system/$SERVICE_NAME.service

${YELLOW}⚠️ ВАЖНО:${NC}
1. Настройте все токены в файле $INSTALL_DIR/.env
2. Проверьте статус после запуска: systemctl status $SERVICE_NAME
3. Мониторьте логи для выявления проблем

${GREEN}✅ Готово к запуску!${NC}

EOF 