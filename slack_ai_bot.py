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
from globalping_with_token import GlobalpingTokenClient, token_ping, token_http, token_dns, token_traceroute, comprehensive_token_test

load_dotenv()

SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GLOBALPING_API_TOKEN = os.getenv("GLOBALPING_API_TOKEN")  # Токен из панели Globalping

app = App(token=SLACK_BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

# Функция для выполнения сетевых команд с гарантированным завершением по таймауту
def run_command(command):
    if command.strip().startswith("tracert"):
        parts = command.strip().split()
        target = parts[-1]
        command = f"tracert -d -h 5 -w 1000 {target}"

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
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            return "Команда заняла слишком много времени и была прервана."

        return stdout if proc.returncode == 0 else stderr

    except FileNotFoundError:
        return f"Команда не найдена: {command.split()[0]}"

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

# Функция общения с OpenAI API для получения гипотез и команд
def ai_diagnose_issue(target):
    # Извлекаем чистый домен без протокола для команд
    clean_domain = target.replace("https://", "").replace("http://", "").split("/")[0]
    
    prompt = f"""
    Ресурс '{target}' недоступен или работает с ошибками. Проведи диагностику.

    СТРОГО следуй формату:

    Гипотеза: Проблемы с DNS разрешением
    Команда: nslookup {clean_domain}
    MCP: dns

    Гипотеза: Проблемы с базовой связностью
    Команда: ping {clean_domain}
    MCP: ping

    Гипотеза: Проблемы с HTTP доступом
    Команда: curl -I {target}
    MCP: http

    Гипотеза: Проблемы с маршрутизацией
    Команда: tracert {clean_domain}
    MCP: traceroute

    Гипотеза: Проблемы с портами
    Команда: telnet {clean_domain} 80
    MCP: ping

    ВАЖНО: Используй ТОЧНО такой формат. Каждая строка "MCP:" должна содержать только одно слово: ping, http, traceroute или dns.
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
        temperature=0.2
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

    Сделай итоговое резюме, укажи наиболее вероятные причины падения сайта и рекомендации по их устранению.
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": summary_prompt}],
        max_tokens=500,
        temperature=0.2
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
    say(f"🔍 **Анализирую проблему с ресурсом:** `{target}`\n⚡ _Globalping: {token_status} | Smart Fallback Strategy активна_\n🌍 _Готовлю глобальную диагностику..._", thread_ts=thread_ts)
    ai_response = ai_diagnose_issue(target)

    responses = []
    
    # Сначала выполняем ВСЕ Globalping тесты
    mcp_matches = re.findall(r"MCP: (.+)", ai_response)
    globalping_tests_performed = set()  # Избегаем дублирования
    
    # Подсчитываем уникальные тесты
    unique_tests = set()
    for mcp_match in mcp_matches:
        test_type = mcp_match.strip().lower()
        if test_type in ["ping", "http", "traceroute", "dns"]:
            unique_tests.add(test_type)
    
    if unique_tests:
        test_list = ", ".join(unique_tests)
        say(f"🚀 **Запускаю {len(unique_tests)} Globalping тест(ов):** {test_list}\n⏳ _Проверяю доступность из разных регионов мира..._", thread_ts=thread_ts)
    
    for mcp_match in mcp_matches:
        test_type = mcp_match.strip().lower()
        if test_type in ["ping", "http", "traceroute", "dns"] and test_type not in globalping_tests_performed:
            globalping_tests_performed.add(test_type)
            hybrid_result = globalping_hybrid_check(target, test_type=test_type)
            responses.append(f"**🌍 Globalping {test_type.upper()} тест:**\n{hybrid_result}")

    # Затем выполняем локальные команды
    for match in re.findall(r"Команда: (.+)", ai_response):
        clean_command = match.strip("` ")
        output = run_command(clean_command)
        responses.append(f"**💻 Локальная команда** `{clean_command}`:\n```{output}```")

    results_text = "\n".join(responses)
    summary = summarize_results(ai_response, results_text)

    response_text = f"*AI Диагностика:*\n```{ai_response}```\n\n*Результаты проверок:*\n{results_text}\n\n*Итоговое резюме:*\n```{summary}```"
    say(response_text, thread_ts=thread_ts)

if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
