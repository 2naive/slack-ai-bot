import os
import json
import subprocess
import re
import requests
import time
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from openai import OpenAI
from globalping_hybrid_client import GlobalpingHybridClient, hybrid_ping, hybrid_http
from globalping_with_token import GlobalpingTokenClient, token_ping, token_http, token_dns, token_traceroute, token_mtr, comprehensive_token_test

load_dotenv()

SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GLOBALPING_API_TOKEN = os.getenv("GLOBALPING_API_TOKEN")  # Токен из панели Globalping

app = App(token=SLACK_BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

# Функция для выполнения сетевых команд с гарантированным завершением по таймауту
def run_command(command):
    # Настройки таймаутов для разных команд
    if command.strip().startswith("tracert"):
        parts = command.strip().split()
        target = parts[-1]
        # Сокращенный tracert: максимум 8 прыжков, быстрый таймаут
        command = f"tracert -d -h 8 -w 500 {target}"
        timeout = 8  # 8 секунд максимум
    elif command.strip().startswith("pathping"):
        timeout = 15  # 15 секунд для pathping
    elif command.strip().startswith("telnet"):
        timeout = 3  # 3 секунды для telnet
    else:
        timeout = 5  # 5 секунд для остальных команд

    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            encoding='cp866',
            errors='replace'
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            if command.strip().startswith("tracert"):
                return "⏱️ Tracert прерван по таймауту (8 сек) - возможны проблемы с маршрутизацией"
            elif command.strip().startswith("telnet"):
                return "⏱️ Telnet таймаут - порт недоступен или заблокирован"
            else:
                return f"⏱️ Команда прервана по таймауту ({timeout} сек)"

        return stdout if proc.returncode == 0 else stderr

    except FileNotFoundError:
        return f"❌ Команда не найдена: {command.split()[0]}"

# Globalping Smart интеграция (Token → MCP → REST API fallback)
def globalping_hybrid_check(target: str, test_type: str) -> str:
    """Гибридная проверка с приоритетом токена"""
    # Приоритет 1: API Token → Direct REST API
    api_token = os.getenv("GLOBALPING_API_TOKEN")
    if api_token:
        print(f"🔑 Используем API токен для {test_type} теста {target}")
        try:
            if test_type == "ping":
                result = token_ping(api_token, target)
            elif test_type == "http":
                result = token_http(api_token, target)
            elif test_type == "dns":
                result = token_dns(api_token, target)
            elif test_type == "traceroute":
                result = token_traceroute(api_token, target)
            elif test_type == "mtr":
                result = token_mtr(api_token, target)
            else:
                result = f"❌ Неизвестный тип теста: {test_type}"
            
            # Если токен сработал, возвращаем результат
            if "✅" in result:
                return result
            else:
                print(f"⚠️ Токен не сработал: {result[:50]}, пробуем гибридный подход...")
        except Exception as e:
            print(f"⚠️ Ошибка токена: {e}, пробуем гибридный подход...")
    
    # Приоритет 2: MCP Server (если доступен)
    try:
        if test_type == "ping":
            return hybrid_ping(target)
        elif test_type == "http":
            return hybrid_http(target)
        else:
            print(f"⚠️ MCP не поддерживает {test_type}, переключаюсь на REST API...")
            # Fallback to public REST API for unsupported tests
            if test_type == "dns":
                return public_dns_check(target)
            elif test_type == "traceroute":
                return public_traceroute_check(target)
            elif test_type == "mtr":
                return public_mtr_check(target)
            else:
                return f"❌ Тип теста {test_type} не поддерживается"
    except Exception as e:
        print(f"⚠️ MCP не работает, переключаюсь на REST API...")
        
        # Приоритет 3: Public REST API fallback
        try:
            if test_type == "ping":
                return public_ping_check(target)
            elif test_type == "http":
                return public_http_check(target)
            elif test_type == "dns":
                return public_dns_check(target)
            elif test_type == "traceroute":
                return public_traceroute_check(target)
            elif test_type == "mtr":
                return public_mtr_check(target)
            else:
                return f"❌ Тип теста {test_type} не поддерживается"
        except Exception as public_e:
            return f"❌ Все источники недоступны: MCP({e}), Public({public_e})"

def public_dns_check(target: str) -> str:
    """Публичная DNS проверка через REST API"""
    try:
        # Очищаем URL от протокола
        clean_target = target
        if target.startswith(("http://", "https://")):
            clean_target = target.replace("https://", "").replace("http://", "").split("/")[0]
        
        payload = {
            "type": "dns",
            "target": clean_target,
            "locations": [{"magic": "EU"}],
            "limit": 2,
            "measurementOptions": {"query": {"type": "A"}}
        }
        
        response = requests.post("https://api.globalping.io/v1/measurements", json=payload, timeout=10)
        if response.status_code != 202:
            return f"❌ **Ошибка dns**: HTTP {response.status_code}"
        
        measurement_id = response.json().get("id")
        # Ждем результат
        for _ in range(15):
            time.sleep(1)
            result_response = requests.get(f"https://api.globalping.io/v1/measurements/{measurement_id}", timeout=10)
            if result_response.status_code == 200:
                data = result_response.json()
                if data.get("status") == "finished":
                    results = []
                    for result in data.get("results", []):
                        probe = result.get("probe", {})
                        location = f"{probe.get('city', 'Unknown')}, {probe.get('country', 'Unknown')}"
                        dns_result = result.get("result", {})
                        answers = dns_result.get("answers", [])
                        if answers:
                            ip = answers[0].get("value", "N/A")
                            results.append(f"📍 {location}: {ip}")
                    return f"🌍 **Globalping DNS** для `{clean_target}`:\n" + "\n".join(results)
        return "❌ **Ошибка dns**: Timeout"
    except Exception as e:
        return f"❌ **Ошибка dns**: {str(e)}"

def public_traceroute_check(target: str) -> str:
    """Публичная traceroute проверка через REST API"""
    try:
        # Очищаем URL от протокола
        clean_target = target
        if target.startswith(("http://", "https://")):
            clean_target = target.replace("https://", "").replace("http://", "").split("/")[0]
        
        payload = {
            "type": "traceroute",
            "target": clean_target,
            "locations": [{"magic": "EU"}],
            "limit": 2
        }
        
        response = requests.post("https://api.globalping.io/v1/measurements", json=payload, timeout=10)
        if response.status_code != 202:
            return f"❌ **Ошибка traceroute**: HTTP {response.status_code}"
        
        measurement_id = response.json().get("id")
        # Ждем результат
        for _ in range(15):
            time.sleep(1)
            result_response = requests.get(f"https://api.globalping.io/v1/measurements/{measurement_id}", timeout=10)
            if result_response.status_code == 200:
                data = result_response.json()
                if data.get("status") == "finished":
                    results = []
                    for result in data.get("results", []):
                        probe = result.get("probe", {})
                        location = f"{probe.get('city', 'Unknown')}, {probe.get('country', 'Unknown')}"
                        trace_result = result.get("result", {})
                        hops = trace_result.get("hops", [])
                        hop_count = len(hops)
                        last_hop = hops[-1] if hops else {}
                        last_time = last_hop.get("timings", [{}])[-1].get("rtt", "N/A") if last_hop else "N/A"
                        results.append(f"📍 {location}: {hop_count} прыжков, последний {last_time}ms")
                    return f"🌍 **Globalping TRACEROUTE** для `{clean_target}`:\n" + "\n".join(results)
        return "❌ **Ошибка traceroute**: Timeout"
    except Exception as e:
        return f"❌ **Ошибка traceroute**: {str(e)}"

def public_ping_check(target: str) -> str:
    """Публичная ping проверка через REST API"""
    try:
        # Очищаем URL от протокола
        clean_target = target
        if target.startswith(("http://", "https://")):
            clean_target = target.replace("https://", "").replace("http://", "").split("/")[0]
        
        payload = {
            "type": "ping",
            "target": clean_target,
            "locations": [{"magic": "EU"}],
            "limit": 2,
            "measurementOptions": {"packets": 3}
        }
        
        response = requests.post("https://api.globalping.io/v1/measurements", json=payload, timeout=10)
        if response.status_code != 202:
            return f"❌ **Ошибка ping**: HTTP {response.status_code}"
        
        measurement_id = response.json().get("id")
        # Ждем результат
        for _ in range(15):
            time.sleep(1)
            result_response = requests.get(f"https://api.globalping.io/v1/measurements/{measurement_id}", timeout=10)
            if result_response.status_code == 200:
                data = result_response.json()
                if data.get("status") == "finished":
                    results = []
                    for result in data.get("results", []):
                        probe = result.get("probe", {})
                        location = f"{probe.get('city', 'Unknown')}, {probe.get('country', 'Unknown')}"
                        stats = result.get("result", {}).get("stats", {})
                        avg_time = stats.get("avg", "N/A")
                        packet_loss = stats.get("loss", "N/A")
                        results.append(f"📍 {location}: {avg_time}ms (потерь: {packet_loss}%)")
                    return f"🌍 **Globalping PING** для `{clean_target}`:\n" + "\n".join(results)
        return "❌ **Ошибка ping**: Timeout"
    except Exception as e:
        return f"❌ **Ошибка ping**: {str(e)}"

def public_http_check(target: str) -> str:
    """Публичная HTTP проверка через REST API"""
    try:
        # Очищаем URL от протокола для HTTP тестов
        clean_target = target
        if target.startswith(("http://", "https://")):
            clean_target = target.replace("https://", "").replace("http://", "").split("/")[0]
        
        payload = {
            "type": "http",
            "target": clean_target,
            "locations": [{"magic": "EU"}],
            "limit": 2
        }
        
        response = requests.post("https://api.globalping.io/v1/measurements", json=payload, timeout=10)
        if response.status_code != 202:
            return f"❌ **Ошибка http**: HTTP {response.status_code}"
        
        measurement_id = response.json().get("id")
        # Ждем результат
        for _ in range(15):
            time.sleep(1)
            result_response = requests.get(f"https://api.globalping.io/v1/measurements/{measurement_id}", timeout=10)
            if result_response.status_code == 200:
                data = result_response.json()
                if data.get("status") == "finished":
                    results = []
                    for result in data.get("results", []):
                        probe = result.get("probe", {})
                        location = f"{probe.get('city', 'Unknown')}, {probe.get('country', 'Unknown')}"
                        http_result = result.get("result", {})
                        status = http_result.get("status", "N/A")
                        total_time = http_result.get("timings", {}).get("total", "N/A")
                        results.append(f"📍 {location}: HTTP {status} ({total_time}ms)")
                    return f"🌍 **Globalping HTTP** для `{clean_target}`:\n" + "\n".join(results)
        return "❌ **Ошибка http**: Timeout"
    except Exception as e:
        return f"❌ **Ошибка http**: {str(e)}"

def public_mtr_check(target: str) -> str:
    """Публичная mtr проверка через REST API"""
    try:
        # Очищаем URL от протокола
        clean_target = target
        if target.startswith(("http://", "https://")):
            clean_target = target.replace("https://", "").replace("http://", "").split("/")[0]
        
        payload = {
            "type": "mtr",
            "target": clean_target,
            "locations": [{"magic": "EU"}],
            "limit": 2
        }
        
        response = requests.post("https://api.globalping.io/v1/measurements", json=payload, timeout=10)
        if response.status_code != 202:
            return f"❌ **Ошибка mtr**: HTTP {response.status_code}"
        
        measurement_id = response.json().get("id")
        # Ждем результат
        for _ in range(15):
            time.sleep(1)
            result_response = requests.get(f"https://api.globalping.io/v1/measurements/{measurement_id}", timeout=10)
            if result_response.status_code == 200:
                data = result_response.json()
                if data.get("status") == "finished":
                    results = []
                    for result in data.get("results", []):
                        probe = result.get("probe", {})
                        location = f"{probe.get('city', 'Unknown')}, {probe.get('country', 'Unknown')}"
                        mtr_result = result.get("result", {})
                        results.append(f"📍 {location}: {mtr_result.get('status', 'N/A')}")
                    return f"🌍 **Globalping MTR** для `{clean_target}`:\n" + "\n".join(results)
        return "❌ **Ошибка mtr**: Timeout"
    except Exception as e:
        return f"❌ **Ошибка mtr**: {str(e)}"

def format_summary(summary):
    """Улучшает форматирование итогового резюме"""
    if not summary or len(summary.strip()) < 10:
        return "📝 _Резюме недоступно_"
    
    # Убираем лишние символы и разбиваем на абзацы
    formatted = summary.strip()
    
    # Заменяем markdown заголовки на эмодзи
    formatted = formatted.replace("### Итоговое резюме", "")
    formatted = formatted.replace("### ", "🔸 **")
    formatted = formatted.replace("**:", ":**")
    
    # Улучшаем списки
    formatted = formatted.replace("1. **", "1️⃣ **")
    formatted = formatted.replace("2. **", "2️⃣ **")
    formatted = formatted.replace("3. **", "3️⃣ **")
    formatted = formatted.replace("4. **", "4️⃣ **")
    formatted = formatted.replace("5. **", "5️⃣ **")
    
    # Ограничиваем длину до 1500 символов
    # if len(formatted) > 1500:
    #    formatted = formatted[:1500] + "...\n\n⚠️ _Резюме сокращено для удобства_"
    
    return formatted

# Функция общения с OpenAI API для получения гипотез и команд
def ai_diagnose_issue(target):
    prompt = f"""
    Сайт или ресурс '{target}' упал или работает медленно.

    Предложи КРАТКИЕ гипотезы причин и предоставь сетевые команды ДЛЯ WINDOWS для проверки этих гипотез.
    Используй только следующие инструменты: curl, nslookup, ping.

    Дополнительно, предложи Globalping тесты для проверки ресурса из разных регионов мира.
    Доступные Globalping инструменты: ping, http, traceroute, dns, mtr.

    ВАЖНО: Команды должны быть БЕЗ протокола http:// для ping, nslookup, tracert!

    Формат ответа:
    Гипотеза: <краткое описание>  
    Команда: <команда для проверки>  
    MCP: <тип_теста>
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,  # Сокращаем для более краткого ответа
        temperature=0.1
    )

    return response.choices[0].message.content.strip()

# Функция для формирования итогового резюме после выполнения команд
def summarize_results(diagnostic, results):
    summary_prompt = f"""
    Даны гипотезы и результаты их проверки:
    Гипотезы и команды:
    {diagnostic}

    Результаты выполнения команд:
    {results}

    Кратко резюмируй, укажи наиболее вероятные причины падения сайта и рекомендации по их устранению.
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": summary_prompt}],
        max_tokens=2000,
        temperature=0.1
    )

    return response.choices[0].message.content.strip()

# Извлечение целей из различных частей сообщения Slack
def extract_targets(event):
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

# Обработка входящих Slack-сообщений
@app.event("message")
def handle_message(event, say):
    bot_user_id = app.client.auth_test()["user_id"]
    if event.get('user') == bot_user_id:
        return

    targets = extract_targets(event)
    if not targets:
        return

    target = targets[0]
    thread_ts = event.get('ts')

    # Определяем статус Globalping интеграции
    token_status = "🔑 API Token" if GLOBALPING_API_TOKEN else "🌐 Public Access"
    say(f"🔍 *Диагностика ресурса:* `{target}`\n⚡ _Globalping: {token_status} | Запускаю комплексную проверку..._", thread_ts=thread_ts)
    
    # ЧАСТЬ 1: Globalping тесты (4 точки, включая 2 в РФ)
    globalping_results = []
    globalping_tests = ["ping", "http", "dns", "traceroute", "mtr"]
    
    say(f"🌍 **Запускаю {len(globalping_tests)} Globalping тестов** из 4 точек (включая РФ)...", thread_ts=thread_ts)
    
    for test_type in globalping_tests:
        result = globalping_hybrid_check_extended(target, test_type)
        globalping_results.append(f"**🌍 {test_type.upper()}:**\n{result}")
    
    # Отправляем результаты Globalping
    if globalping_results:
        globalping_text = "📊 **Результаты глобальных проверок:**\n" + "\n\n".join(globalping_results)
        say(globalping_text, thread_ts=thread_ts)

    # ЧАСТЬ 2: Локальные команды (фиксированный набор)
    local_commands = [
        f"ping -n 4 {extract_domain(target)}",
        f"nslookup {extract_domain(target)}",
        f"curl -I -m 10 {target}",
        f"tracert -d -h 10 {extract_domain(target)}",
        f"nslookup -type=MX {extract_domain(target)}"
    ]
    
    say("💻 **Выполняю локальные команды...**", thread_ts=thread_ts)
    
    local_results = []
    for command in local_commands:
        output = run_command(command)
        local_results.append(f"**💻** `{command}`:\n```{output}```")

    # Отправляем результаты локальных команд
    if local_results:
        local_text = "💻 **Результаты локальных команд:**\n" + "\n\n".join(local_results)
        say(local_text, thread_ts=thread_ts)

    # ЧАСТЬ 3: PathPing с полным выводом для LLM (Windows аналог MTR)
    pathping_command = f"pathping -n -q 5 -h 8 {extract_domain(target)}"
    say("🔬 **Запускаю PathPing анализ (Windows MTR)...**", thread_ts=thread_ts)
    
    pathping_output = run_command(pathping_command)
    pathping_result = f"**🔬 PathPing анализ** `{pathping_command}`:\n```{pathping_output}```"
    say(pathping_result, thread_ts=thread_ts)

    # ЧАСТЬ 4: LLM анализ всех результатов
    all_results = globalping_results + local_results + [pathping_result]
    analysis = analyze_all_results(target, "\n".join(all_results))
    
    formatted_analysis = format_summary(analysis)
    say(f"🤖 **Итоговый анализ:**\n{formatted_analysis}", thread_ts=thread_ts)

def extract_domain(target):
    """Извлекает чистый домен из URL"""
    return target.replace("https://", "").replace("http://", "").split("/")[0]

def globalping_hybrid_check_extended(target: str, test_type: str) -> str:
    """Гибридная проверка с 4 точками, включая 2 в РФ"""
    # Приоритет 1: API Token → Direct REST API
    api_token = os.getenv("GLOBALPING_API_TOKEN")
    if api_token:
        print(f"🔑 Используем API токен для {test_type} теста {target}")
        try:
            if test_type == "ping":
                result = token_ping_extended(api_token, target)
            elif test_type == "http":
                result = token_http_extended(api_token, target)
            elif test_type == "dns":
                result = token_dns_extended(api_token, target)
            elif test_type == "traceroute":
                result = token_traceroute_extended(api_token, target)
            elif test_type == "mtr":
                result = token_mtr_extended(api_token, target)
            else:
                result = f"❌ Неизвестный тип теста: {test_type}"
            
            # Если токен сработал, возвращаем результат
            if "✅" in result:
                return result
            else:
                print(f"⚠️ Токен не сработал: {result[:50]}, пробуем публичный API...")
        except Exception as e:
            print(f"⚠️ Ошибка токена: {e}, пробуем публичный API...")
    
    # Fallback: Public REST API с 4 точками
    try:
        if test_type == "ping":
            return public_ping_check_extended(target)
        elif test_type == "http":
            return public_http_check_extended(target)
        elif test_type == "dns":
            return public_dns_check_extended(target)
        elif test_type == "traceroute":
            return public_traceroute_check_extended(target)
        elif test_type == "mtr":
            return public_mtr_check_extended(target)
        else:
            return f"❌ Тип теста {test_type} не поддерживается"
    except Exception as e:
        return f"❌ Все источники недоступны: {e}"

def analyze_all_results(target: str, all_results: str) -> str:
    """Анализирует все результаты тестов с помощью LLM"""
    prompt = f"""
    Проведен комплексный анализ ресурса '{target}'. 
    
    Результаты тестов:
    {all_results}
    
    Проанализируй результаты и дай краткое заключение:
    1. Статус ресурса (работает/не работает/проблемы)
    2. Основные проблемы (если есть)
    3. Рекомендации по устранению
    
    Будь конкретен и лаконичен.
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0.1
    )

    return response.choices[0].message.content.strip()

# Функции для расширенных тестов с 4 точками (включая РФ)
def token_ping_extended(api_token: str, target: str) -> str:
    client = GlobalpingTokenClient(api_token)
    result = client.ping(extract_domain(target), "RU,EU,NA,AS", limit=4)
    if result["success"]:
        return f"✅ {result['result']}"
    else:
        return f"❌ **Ошибка ping**: {result['error']}"

def token_http_extended(api_token: str, target: str) -> str:
    client = GlobalpingTokenClient(api_token)
    result = client.http(extract_domain(target), "RU,EU,NA,AS", limit=4)
    if result["success"]:
        return f"✅ {result['result']}"
    else:
        return f"❌ **Ошибка http**: {result['error']}"

def token_dns_extended(api_token: str, target: str) -> str:
    client = GlobalpingTokenClient(api_token)
    result = client.dns(extract_domain(target), "RU,EU,NA,AS", limit=4)
    if result["success"]:
        return f"✅ {result['result']}"
    else:
        return f"❌ **Ошибка dns**: {result['error']}"

def token_traceroute_extended(api_token: str, target: str) -> str:
    client = GlobalpingTokenClient(api_token)
    result = client.traceroute(extract_domain(target), "RU,EU,NA,AS", limit=4)
    if result["success"]:
        return f"✅ {result['result']}"
    else:
        return f"❌ **Ошибка traceroute**: {result['error']}"

def token_mtr_extended(api_token: str, target: str) -> str:
    client = GlobalpingTokenClient(api_token)
    result = client.mtr(extract_domain(target), "RU,EU,NA,AS", limit=4)
    if result["success"]:
        return f"✅ {result['result']}"
    else:
        return f"❌ **Ошибка mtr**: {result['error']}"

# Публичные функции для расширенных тестов
def public_ping_check_extended(target: str) -> str:
    return execute_public_test_extended(extract_domain(target), "ping")

def public_http_check_extended(target: str) -> str:
    return execute_public_test_extended(extract_domain(target), "http")

def public_dns_check_extended(target: str) -> str:
    return execute_public_test_extended(extract_domain(target), "dns")

def public_traceroute_check_extended(target: str) -> str:
    return execute_public_test_extended(extract_domain(target), "traceroute")

def public_mtr_check_extended(target: str) -> str:
    return execute_public_test_extended(extract_domain(target), "mtr")

def execute_public_test_extended(target: str, test_type: str) -> str:
    """Выполняет тест через публичный API с 4 точками"""
    try:
        payload = {
            "type": test_type,
            "target": target,
            "locations": [{"magic": "RU"}, {"magic": "EU"}, {"magic": "NA"}, {"magic": "AS"}],
            "limit": 4
        }
        
        if test_type == "ping":
            payload["measurementOptions"] = {"packets": 4}
        elif test_type == "dns":
            payload["measurementOptions"] = {"query": {"type": "A"}}
        
        response = requests.post("https://api.globalping.io/v1/measurements", json=payload, timeout=15)
        if response.status_code != 202:
            return f"❌ **Ошибка {test_type}**: HTTP {response.status_code}"
        
        measurement_id = response.json().get("id")
        
        # Ждем результат (дольше для 4 точек)
        for _ in range(25):
            time.sleep(1)
            result_response = requests.get(f"https://api.globalping.io/v1/measurements/{measurement_id}", timeout=10)
            if result_response.status_code == 200:
                data = result_response.json()
                if data.get("status") == "finished":
                    return format_extended_results(data, test_type, target)
        
        return f"❌ **Ошибка {test_type}**: Timeout"
    except Exception as e:
        return f"❌ **Ошибка {test_type}**: {str(e)}"

def format_extended_results(result_data: dict, test_type: str, target: str) -> str:
    """Форматирует результаты тестов с 4 точек"""
    results = []
    
    for result in result_data.get("results", []):
        probe = result.get("probe", {})
        country = probe.get("country", "Unknown")
        city = probe.get("city", "Unknown")
        location = f"{city}, {country}"
        
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
        elif test_type in ["traceroute", "mtr"]:
            trace_result = result.get("result", {})
            hops = trace_result.get("hops", [])
            hop_count = len(hops)
            if hops:
                last_hop = hops[-1]
                if test_type == "mtr":
                    stats = last_hop.get("stats", {})
                    avg_time = stats.get("avg", "N/A")
                    results.append(f"📍 {location}: {hop_count} прыжков, {avg_time}ms")
                else:
                    timings = last_hop.get("timings", [{}])
                    last_time = timings[-1].get("rtt", "N/A") if timings else "N/A"
                    results.append(f"📍 {location}: {hop_count} прыжков, {last_time}ms")
            else:
                results.append(f"📍 {location}: Маршрут недоступен")
    
    return f"🌍 **{test_type.upper()}** для `{target}`:\n" + "\n".join(results)

if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
