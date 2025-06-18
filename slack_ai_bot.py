import os
import json
import subprocess
import re
import requests
import time
import platform
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from openai import OpenAI
from globalping_with_token import GlobalpingTokenClient

load_dotenv()

SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GLOBALPING_API_TOKEN = os.getenv("GLOBALPING_API_TOKEN")

app = App(token=SLACK_BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

# Конфигурация для восстановления после ошибок
ERROR_RECOVERY_CONFIG = {
    "max_retries": 3,
    "retry_delay": 2,
    "timeout_increase_factor": 1.5,
    "fallback_locations": ["RU", "EU", "US", "GB"],
    "emergency_fallback": True
}

def run_command_with_recovery(command, attempt=1):
    """Выполнение команд с восстановлением после ошибок"""
    # Настройки таймаутов для разных команд
    base_timeouts = {
        "tracert": 20, "traceroute": 20,
        "pathping": 25, "mtr": 25,
        "telnet": 8,
        "ping": 12,
        "dig": 8, "nslookup": 8,
        "default": 10
    }
    
    cmd_name = command.split()[0].lower()
    base_timeout = base_timeouts.get(cmd_name, base_timeouts["default"])
    
    # Увеличиваем таймаут с каждой попыткой
    timeout = int(base_timeout * (ERROR_RECOVERY_CONFIG["timeout_increase_factor"] ** (attempt - 1)))
    
    try:
        # Определяем кодировку в зависимости от ОС
        encoding = 'cp866' if platform.system().lower() == 'windows' else 'utf-8'
            
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            encoding=encoding,
            errors='replace'
        )
        
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            
            # Проверяем успешность выполнения
            if proc.returncode == 0 and stdout.strip():
                return stdout
            elif stderr.strip():
                # Если есть ошибка, пробуем повторить
                if attempt < ERROR_RECOVERY_CONFIG["max_retries"]:
                    time.sleep(ERROR_RECOVERY_CONFIG["retry_delay"])
                    return run_command_with_recovery(command, attempt + 1)
                return f"❌ Ошибка после {attempt} попыток: {stderr.strip()}"
            else:
                return stdout if stdout else "⚠️ Команда выполнена, но результат пуст"
                
        except subprocess.TimeoutExpired:
            proc.kill()
            
            # Пробуем повторить с увеличенным таймаутом
            if attempt < ERROR_RECOVERY_CONFIG["max_retries"]:
                time.sleep(ERROR_RECOVERY_CONFIG["retry_delay"])
                return run_command_with_recovery(command, attempt + 1)
                
            return f"⏱️ {cmd_name.title()} прерван по таймауту ({timeout}с) после {attempt} попыток"

    except FileNotFoundError:
        return f"❌ Команда не найдена: {cmd_name} (возможно, не установлена в системе)"
    except Exception as e:
        if attempt < ERROR_RECOVERY_CONFIG["max_retries"]:
            time.sleep(ERROR_RECOVERY_CONFIG["retry_delay"])
            return run_command_with_recovery(command, attempt + 1)
        return f"❌ Критическая ошибка {cmd_name}: {str(e)}"

def globalping_test_with_recovery(target: str, test_type: str, attempt=1) -> str:
    """Выполнение Globalping тестов с восстановлением после ошибок"""
    
    # Очищаем цель от протокола
    clean_target = target
    if target.startswith(("http://", "https://")):
        clean_target = target.replace("https://", "").replace("http://", "").split("/")[0]
    
    # Приоритет 1: API Token (если есть)
    if GLOBALPING_API_TOKEN:
        try:
            token_client = GlobalpingTokenClient(GLOBALPING_API_TOKEN)
            
            # Выбираем метод в зависимости от типа теста
            test_methods = {
                "ping": token_client.ping,
                "http": token_client.http,
                "dns": token_client.dns,
                "traceroute": token_client.traceroute,
                "mtr": token_client.mtr
            }
            
            if test_type in test_methods:
                # Используем расширенные локации для лучшего покрытия
                locations = "RU,EU,US,GB" if attempt == 1 else ",".join(ERROR_RECOVERY_CONFIG["fallback_locations"])
                limit = 4 if attempt == 1 else 2
                
                result = test_methods[test_type](clean_target, locations, limit)
                
                if result["success"]:
                    return f"✅ {result['result']}"
                else:
                    # Если токен не сработал, пробуем fallback
                    if attempt < ERROR_RECOVERY_CONFIG["max_retries"] and ERROR_RECOVERY_CONFIG["emergency_fallback"]:
                        time.sleep(ERROR_RECOVERY_CONFIG["retry_delay"])
                        return public_api_fallback(clean_target, test_type, attempt + 1)
                    return f"❌ **Ошибка {test_type}** (токен): {result['error']}"
                    
        except Exception as e:
            # Если токен полностью не работает, переходим к публичному API
            if attempt == 1 and ERROR_RECOVERY_CONFIG["emergency_fallback"]:
                return public_api_fallback(clean_target, test_type, attempt)
            return f"❌ **Критическая ошибка {test_type}**: {str(e)}"
    
    # Приоритет 2: Публичный API (если нет токена или токен не работает)
    return public_api_fallback(clean_target, test_type, attempt)

def public_api_fallback(target: str, test_type: str, attempt=1) -> str:
    """Fallback к публичному API с восстановлением после ошибок"""
    try:
        # Настройка локаций в зависимости от попытки
        if attempt == 1:
            locations = [{"magic": "RU"}, {"magic": "EU"}, {"magic": "US"}, {"magic": "GB"}]
            limit = 4
        else:
            # Упрощенная конфигурация для повторных попыток
            locations = [{"magic": loc} for loc in ERROR_RECOVERY_CONFIG["fallback_locations"]]
            limit = len(locations)
        
        payload = {
            "type": test_type,
            "target": target,
            "locations": locations,
            "limit": limit
        }
        
        # Специальные параметры для разных типов тестов
        if test_type == "ping":
            payload["measurementOptions"] = {"packets": 3}
        elif test_type == "dns":
            payload["measurementOptions"] = {"query": {"type": "A"}}
        
        # Увеличиваем таймаут для повторных попыток
        timeout = 10 * (ERROR_RECOVERY_CONFIG["timeout_increase_factor"] ** (attempt - 1))
        
        response = requests.post(
            "https://api.globalping.io/v1/measurements", 
            json=payload, 
            timeout=timeout
        )
        
        if response.status_code != 202:
            if attempt < ERROR_RECOVERY_CONFIG["max_retries"]:
                time.sleep(ERROR_RECOVERY_CONFIG["retry_delay"])
                return public_api_fallback(target, test_type, attempt + 1)
            return f"❌ **Ошибка {test_type}**: HTTP {response.status_code} после {attempt} попыток"
        
        measurement_id = response.json().get("id")
        if not measurement_id:
            return f"❌ **Ошибка {test_type}**: Нет ID измерения"
        
        # Ждем результаты с увеличенным таймаутом для повторных попыток
        max_wait_cycles = 20 + (5 * attempt)
        
        for cycle in range(max_wait_cycles):
            time.sleep(1)
            try:
                result_response = requests.get(
                    f"https://api.globalping.io/v1/measurements/{measurement_id}", 
                    timeout=timeout
                )
                
                if result_response.status_code == 200:
                    data = result_response.json()
                    status = data.get("status", "unknown")
                    
                    if status == "finished":
                        return format_public_results(data, test_type, target)
                    elif status == "failed":
                        error_msg = data.get("error", "Неизвестная ошибка")
                        if attempt < ERROR_RECOVERY_CONFIG["max_retries"]:
                            time.sleep(ERROR_RECOVERY_CONFIG["retry_delay"])
                            return public_api_fallback(target, test_type, attempt + 1)
                        return f"❌ **Ошибка {test_type}**: Тест завершился с ошибкой: {error_msg}"
                        
            except requests.RequestException as e:
                # Игнорируем временные сетевые ошибки и продолжаем ждать
                if cycle > max_wait_cycles - 5:  # Только в конце показываем ошибки
                    print(f"⚠️ Сетевая ошибка при получении результатов: {e}")
                continue
        
        # Таймаут ожидания результатов
        if attempt < ERROR_RECOVERY_CONFIG["max_retries"]:
            time.sleep(ERROR_RECOVERY_CONFIG["retry_delay"])
            return public_api_fallback(target, test_type, attempt + 1)
        return f"❌ **Ошибка {test_type}**: Таймаут ожидания после {attempt} попыток"
        
    except Exception as e:
        if attempt < ERROR_RECOVERY_CONFIG["max_retries"]:
            time.sleep(ERROR_RECOVERY_CONFIG["retry_delay"])
            return public_api_fallback(target, test_type, attempt + 1)
        return f"❌ **Критическая ошибка {test_type}**: {str(e)} (попытка {attempt})"

def format_public_results(result_data: dict, test_type: str, target: str) -> str:
    """Форматирование результатов публичного API"""
    results = []
    
    for result in result_data.get("results", []):
        probe = result.get("probe", {})
        country = probe.get("country", "Unknown")
        city = probe.get("city", "Unknown")
        location = f"{city}, {country}"
        
        try:
            if test_type == "ping":
                stats = result.get("result", {}).get("stats", {})
                avg_time = stats.get("avg", "N/A")
                packet_loss = stats.get("loss", "N/A")
                results.append(f"📍 {location}: {avg_time}ms (потерь: {packet_loss}%)")
                
            elif test_type == "http":
                http_result = result.get("result", {})
                status = http_result.get("status", "N/A")
                total_time = http_result.get("timings", {}).get("total", "N/A")
                results.append(f"📍 {location}: HTTP {status} ({total_time}ms)")
                
            elif test_type == "dns":
                dns_result = result.get("result", {})
                answers = dns_result.get("answers", [])
                if answers:
                    ip = answers[0].get("value", "N/A")
                    results.append(f"📍 {location}: {ip}")
                else:
                    results.append(f"📍 {location}: DNS timeout")
                    
            elif test_type == "traceroute":
                trace_result = result.get("result", {})
                hops = trace_result.get("hops", [])
                
                if hops:
                    hop_details = []
                    for hop_index, hop in enumerate(hops, 1):
                        hop_num = hop_index  # Используем индекс как номер хопа
                        timings = hop.get("timings", [])
                        
                        if timings:
                            # Берем первый успешный timing
                            timing = timings[0]
                            rtt = timing.get("rtt", "N/A")
                            
                            # Получаем IP или hostname из правильных полей
                            ip_or_host = hop.get("resolvedHostname") or hop.get("resolvedAddress") or "* * *"
                            
                            hop_details.append(f"  {hop_num:2}. {ip_or_host} - {rtt}ms")
                        else:
                            hop_details.append(f"  {hop_num:2}. * * * (timeout)")
                    
                    results.append(f"📍 {location} TRACEROUTE:\n" + "\n".join(hop_details))
                else:
                    results.append(f"📍 {location}: Traceroute данные недоступны")
                    
            elif test_type == "mtr":
                mtr_result = result.get("result", {})
                hops = mtr_result.get("hops", [])
                
                if hops:
                    hop_details = []
                    for hop_index, hop in enumerate(hops, 1):
                        hop_num = hop_index  # Используем индекс как номер хопа
                        stats = hop.get("stats", {})
                        avg_time = stats.get("avg", "N/A")
                        packet_loss = stats.get("loss", 0)
                        
                        # Получаем IP или hostname из правильных полей
                        ip_or_host = hop.get("resolvedHostname") or hop.get("resolvedAddress") or "* * *"
                        
                        # Форматируем строку хопа
                        loss_str = f" ({packet_loss}% loss)" if packet_loss > 0 else ""
                        hop_details.append(f"  {hop_num:2}. {ip_or_host} - {avg_time}ms{loss_str}")
                    
                    results.append(f"📍 {location} MTR:\n" + "\n".join(hop_details))
                else:
                    results.append(f"📍 {location}: MTR данные недоступны")
                    
        except Exception as e:
            results.append(f"📍 {location}: Ошибка обработки данных")
    
    if not results:
        return f"❌ **{test_type.upper()}** для `{target}`: Нет результатов"
    
    return f"🌍 **{test_type.upper()}** для `{target}`:\n" + "\n".join(results)

def get_website_screenshot(target: str) -> str:
    """Создает миниатюрный скриншот веб-страницы без кеширования для актуальной диагностики"""
    try:
        import random
        import time
        
        # Очищаем URL
        url = target
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        
        # Генерируем уникальные параметры против кеширования
        timestamp = int(time.time())
        random_id = random.randint(10000, 99999)
        cache_bust = f"{timestamp}{random_id}"
        
        # Используем бесплатные API с anti-cache параметрами
        screenshot_services = [
            # thum.io с force refresh
            f"https://image.thum.io/get/width/480/crop/360/noanimate/{url}?cache={cache_bust}",
            # s-shot.ru с timestamp
            f"https://mini.s-shot.ru/480x360/JPEG/480/Z100/?{url}&_={cache_bust}",
            # screenshotapi.net с fresh параметром
            f"https://shot.screenshotapi.net/screenshot?url={url}&output=image&file_type=png&wait_for_event=load&width=480&height=360&fresh=true&cache_bust={cache_bust}"
        ]
        
        for service_url in screenshot_services:
            try:
                # Добавляем заголовки против кеширования
                headers = {
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0',
                    'User-Agent': f'SlackBot-Screenshot-{cache_bust}'
                }
                
                response = requests.get(
                    service_url, 
                    timeout=7,  # Увеличиваем таймаут для свежих скриншотов
                    allow_redirects=True,
                    headers=headers
                )
                
                if response.status_code == 200 and len(response.content) > 1000:  # Минимальный размер изображения
                    return service_url
            except requests.RequestException:
                continue
        return ""
        
    except Exception as e:
        return f"📷 Скриншот недоступен: {str(e)}"

def get_os_commands(target):
    """Возвращает команды в зависимости от ОС"""
    domain = extract_domain(target)
    
    if platform.system().lower() == 'windows':
        return [
            f"ping -n 10 -l 1000 {domain}",
            f"nslookup -type=SOA {domain}",
            f"nslookup {domain}",
            f"curl -I -v -m 10 {target}"
        ]
    else:
        return [
            f"ping -n 10 -i 0.2 -s 1000 {domain}",
            f"dig {domain} SOA +short",
            f"dig {domain} +short",
            f"curl -I -v -m 10 {target}",
            f"mtr -4 -w -c 10 -b -y 2 -z -m 20 {domain}"
        ]

def extract_domain(target):
    """Извлекает чистый домен из URL"""
    return target.replace("https://", "").replace("http://", "").split("/")[0]

def extract_targets(event):
    """Извлечение целей из различных частей сообщения Slack"""
    targets = []
    text = event.get('text', '')
    targets += re.findall(r"(\b(?:\d{1,3}\.){3}\d{1,3}\b|https?://[\w.-]+|\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b)", text)

    for file in event.get('files', []):
        plain_text = file.get('plain_text', '')
        targets += re.findall(r"(\b(?:\d{1,3}\.){3}\d{1,3}\b|https?://[\w.-]+|\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b)", plain_text)

    for attachment in event.get('attachments', []):
        for field in attachment.get('fields', []):
            field_value = field.get('value', '')
            targets += re.findall(r"(\b(?:\d{1,3}\.){3}\d{1,3}\b|https?://[\w.-]+|\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b)", field_value)

    return targets

def analyze_all_results(target: str, all_results: str) -> str:
    """Анализирует все результаты тестов с помощью AI"""
    #Фокус на конечной доступности и стабильности финального узла.
    try:
        prompt = f"""
        Вы - специалист по диагностике сетевых проблем.
        Будьте конкретны, точны.
        "Пиши, сокращай". 
        Используй форматирование markdown для Slack.
        Используй только русский язык.

        Учитывай для MTR и Traceroute: Потеря пакетов на промежуточных узлах может быть нормальной из-за:
        - Низкого приоритета ICMP трафика на маршрутизаторах
        - Блокировки ICMP на промежуточных узлах
        - Rate limiting на сетевом оборудовании
        НЕ УКАЗЫВАЙ это в заключении ЕСЛИ НЕТ потерь на финальном узле.
    
        Не давай рекомендаций, по устранению причин и проблем. Только точная диагностика.

        Проведен комплексный анализ ресурса '{target}'. 
        
        Результаты тестов:
        {all_results}
        
        Проанализируйте результаты и дайте краткое заключение:
        1. Статус ресурса (работает/не работает/проблемы)
        2. Выявленные проблемы (если есть)
        3. Причины проблем (если есть проблемы)
        
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.1
        )

        return response.choices[0].message.content.strip()
        
    except Exception as e:
        return f"❌ Ошибка AI анализа: {str(e)}\n\n📊 *Результаты доступны выше для ручного анализа*"

def format_summary(summary):
    """Улучшает форматирование итогового резюме"""
    if not summary or len(summary.strip()) < 10:
        return "📝 _Резюме недоступно_"
    
    formatted = summary.strip()
    
    # Улучшаем форматирование
    formatted = formatted.replace("#### ", "")
    formatted = formatted.replace("### ", "")
    formatted = formatted.replace("**", "*")

    
    return formatted

@app.event("message")
def handle_message(event, say):
    # Пропускаем дочерние сообщения в тредах
    if event.get('thread_ts') and event.get('thread_ts') != event.get('ts'):
        return
    # print(f"🔍 DEBUG EVENT: {json.dumps(event, indent=2, ensure_ascii=False)}")
    """Обработка входящих Slack-сообщений с восстановлением после ошибок"""
    try:
        bot_user_id = app.client.auth_test()["user_id"]
        if event.get('user') == bot_user_id:
            return

        targets = extract_targets(event)
        if not targets:
            return

        target = targets[0]
        if "backup03.itsoft.ru" in target.lower() and len(targets) > 1:
            target = targets[1]

        if "slack.com" in target.lower():
            return
        
        import datetime
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        thread_ts = event.get('ts')
        
        # Получаем ссылку на сообщение
        try:
            channel_id = event.get('channel')
            message_ts = event.get('ts')
            permalink = app.client.chat_getPermalink(
                channel=channel_id,
                message_ts=message_ts
            )['permalink']
        except Exception as e:
            permalink = f"Ошибка получения ссылки: {str(e)}"
        
        print(f"🔍 {current_time} {target} {permalink}")
       
        # Определяем статус интеграции
        token_status = "🔑" if GLOBALPING_API_TOKEN else "🌐"
        say(f"🔍 *Диагностика ресурса:* `{target}`", thread_ts=thread_ts)
        
        # ЧАСТЬ 0: Скриншот страницы
        screenshot_url = get_website_screenshot(target)
        say(f"📸 <{screenshot_url}|Скриншот>", thread_ts=thread_ts)
 
        # ЧАСТЬ 1: Globalping тесты
        globalping_results = []
        globalping_tests = ["ping", "http", "dns", "traceroute", "mtr"]
        
        for test_type in globalping_tests:
            try:
                result = globalping_test_with_recovery(target, test_type)
                globalping_results.append(result)
            except Exception as e:
                globalping_results.append(f"❌ **Критическая ошибка {test_type}**: {str(e)}")
        
        # Отправляем результаты Globalping
        if globalping_results:
            globalping_text = f"`{token_status}` *Результаты глобальных проверок:*\n" + "\n\n".join(globalping_results)
            say(globalping_text, thread_ts=thread_ts)

        # ЧАСТЬ 2: Локальные команды
        local_commands = get_os_commands(target)
        os_name = "Windows" if platform.system().lower() == 'windows' else "Linux"
        
        local_results = []
        for command in local_commands:
            try:
                output = run_command_with_recovery(command)
                local_results.append(f"💻 `{command}`:\n```{output}```")
            except Exception as e:
                local_results.append(f"💻 `{command}`: ❌ Критическая ошибка: {str(e)}")

        # Отправляем результаты локальных команд
        if local_results:
            local_text = "💻 *Результаты локальных команд:*\n" + "\n\n".join(local_results)
            say(local_text, thread_ts=thread_ts)

        # ЧАСТЬ 3: AI анализ
        try:
            all_results = globalping_results + local_results
            analysis = analyze_all_results(target, "\n".join(all_results))
            formatted_analysis = format_summary(analysis)
            say(f"🤖 *Итоговый анализ:*\n{formatted_analysis}", thread_ts=thread_ts)
        except Exception as e:
            say(f"⚠️ *AI анализ недоступен*: {str(e)}\n📊 Результаты тестов доступны выше", thread_ts=thread_ts)
            
    except Exception as e:
        # Критическая ошибка - отправляем уведомление
        try:
            say(f"❌ *Критическая ошибка бота*: {str(e)}\nПовторите запрос через несколько минут", thread_ts=event.get('ts'))
        except:
            print(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    try:
        print("🚀 Запуск Slack AI бота...")
        print(f"🔑 Globalping токен: {'✅ Настроен' if GLOBALPING_API_TOKEN else '❌ Отсутствует (будет использован публичный API)'}")
        print(f"🤖 OpenAI API: {'✅ Настроен' if OPENAI_API_KEY else '❌ Отсутствует'}")
        print(f"⚙️ Система восстановления: ✅ Активна (макс. {ERROR_RECOVERY_CONFIG['max_retries']} попыток)")
        
        handler = SocketModeHandler(app, SLACK_APP_TOKEN)
        handler.start()
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
        print("Проверьте переменные окружения в .env файле")
