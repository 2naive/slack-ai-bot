import os
import json
import subprocess
import re
import requests
import asyncio
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

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

# Globalping MCP интеграция
def globalping_mcp_request(target, test_type="ping", locations="EU,NA,AS"):
    """
    Использует Globalping MCP Server для AI-управляемых тестов
    
    Args:
        target: URL или IP для проверки
        test_type: тип теста (ping, traceroute, dns, http, mtr)
        locations: локации для тестирования
    """
    try:
        # Формируем запрос к OpenAI с инструкциями для использования Globalping MCP
        mcp_prompt = f"""
        Используй Globalping MCP инструменты для проверки {target}.
        
        Выполни {test_type} тест из регионов: {locations}
        
        Инструкции:
        1. Используй ping инструмент для проверки доступности
        2. Если нужно, используй http инструмент для веб-ресурсов  
        3. При необходимости используй traceroute для анализа маршрута
        4. Предоставь краткий анализ результатов
        
        Цель: {target}
        Тип теста: {test_type}
        Регионы: {locations}
        """
        
        # Используем OpenAI для генерации MCP команд
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system", 
                    "content": """Ты эксперт по сетевой диагностике. У тебя есть доступ к Globalping MCP инструментам:
                    - ping: проверка доступности и задержки
                    - http: HTTP запросы и проверка статуса
                    - traceroute: анализ маршрутизации
                    - dns: DNS резолюция
                    - locations: список доступных локаций
                    
                    Используй эти инструменты для диагностики проблем и предоставь структурированный отчет."""
                },
                {"role": "user", "content": mcp_prompt}
            ],
            max_tokens=800,
            temperature=0.1,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "globalping_ping",
                        "description": "Выполнить ping тест через Globalping",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "target": {"type": "string", "description": "Цель для ping"},
                                "locations": {"type": "string", "description": "Локации (EU, NA, AS и т.д.)"}
                            },
                            "required": ["target"]
                        }
                    }
                },
                {
                    "type": "function", 
                    "function": {
                        "name": "globalping_http",
                        "description": "Выполнить HTTP тест через Globalping",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "target": {"type": "string", "description": "URL для HTTP запроса"},
                                "locations": {"type": "string", "description": "Локации"}
                            },
                            "required": ["target"]
                        }
                    }
                }
            ],
            tool_choice="auto"
        )
        
        # Обрабатываем ответ с tool calls
        if response.choices[0].message.tool_calls:
            results = []
            for tool_call in response.choices[0].message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                # Выполняем соответствующий Globalping тест
                if tool_name == "globalping_ping":
                    result = execute_globalping_test(tool_args["target"], "ping", 
                                                   tool_args.get("locations", "EU,NA,AS"))
                elif tool_name == "globalping_http":
                    result = execute_globalping_test(tool_args["target"], "http",
                                                   tool_args.get("locations", "EU,NA,AS"))
                
                results.append(f"**{tool_name.replace('globalping_', '').upper()} результат:**\n{result}")
            
            return "\n\n".join(results)
        else:
            # Если нет tool calls, возвращаем обычный ответ
            return response.choices[0].message.content
            
    except Exception as e:
        return f"Ошибка MCP интеграции: {str(e)}"

def execute_globalping_test(target, test_type, locations):
    """Выполняет реальный тест через Globalping API"""
    try:
        clean_target = target.replace("https://", "").replace("http://", "").split("/")[0]
        
        if test_type == "http":
            test_target = target if target.startswith(("http://", "https://")) else f"http://{target}"
        else:
            test_target = clean_target
            
        # Создаем измерение
        create_url = "https://api.globalping.io/v1/measurements"
        payload = {
            "type": test_type,
            "target": test_target,
            "locations": [{"magic": locations}],
            "measurementOptions": {"packets": 3} if test_type == "ping" else {}
        }
        
        headers = {"Content-Type": "application/json"}
        response = requests.post(create_url, json=payload, headers=headers, timeout=10)
        
        if response.status_code != 202:
            return f"❌ Ошибка: {response.status_code}"
            
        measurement_data = response.json()
        measurement_id = measurement_data.get("id")
        
        # Получаем результаты
        import time
        for attempt in range(15):
            result_url = f"https://api.globalping.io/v1/measurements/{measurement_id}"
            result_response = requests.get(result_url, timeout=10)
            
            if result_response.status_code == 200:
                result_data = result_response.json()
                
                if result_data.get("status") == "finished":
                    return format_globalping_results(result_data, test_type, target)
                elif result_data.get("status") == "failed":
                    return f"❌ Тест неудачен: {result_data.get('error', 'Unknown')}"
                    
            time.sleep(1)
            
        return "⏱️ Таймаут ожидания результатов"
        
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def format_globalping_results(result_data, test_type, target):
    """Форматирует результаты Globalping в читаемый вид"""
    results = []
    
    for result in result_data.get("results", []):
        probe = result.get("probe", {})
        location = f"{probe.get('city', 'Unknown')}, {probe.get('country', 'Unknown')}"
        
        if test_type == "ping":
            stats = result.get("result", {}).get("stats", {})
            avg_time = stats.get("avg", "N/A")
            packet_loss = stats.get("loss", "N/A")
            results.append(f"📍 {location}: {avg_time}ms (loss: {packet_loss}%)")
            
        elif test_type == "http":
            http_result = result.get("result", {})
            status = http_result.get("status", "N/A")
            total_time = http_result.get("timings", {}).get("total", "N/A")
            results.append(f"📍 {location}: HTTP {status} ({total_time}ms)")
    
    return f"🌍 **Globalping {test_type.upper()}** для `{target}`:\n" + "\n".join(results)

# Функция общения с OpenAI API для получения гипотез и команд
def ai_diagnose_issue(target):
    prompt = f"""
    Сайт или ресурс '{target}' упал.

    Предложи краткие гипотезы причин и предоставь сетевые команды ДЛЯ WINDOWS для проверки этих гипотез.
    Используй только следующие инструменты: curl, tracert, nslookup, ping, telnet.

    Дополнительно, предложи Globalping MCP тесты для проверки ресурса из разных регионов мира.
    Доступные MCP инструменты: ping, http, traceroute, dns.

    Формат ответа:
    Гипотеза: <описание гипотезы>
    Команда: <команда для проверки>
    MCP: <тип_теста>
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

    say(f"🔍 *Анализирую проблему с ресурсом:* `{target}`\n⚡ _Используя Globalping MCP интеграцию..._", thread_ts=thread_ts)
    
    # AI диагностика
    ai_response = ai_diagnose_issue(target)

    responses = []
    
    # Обработка MCP тестов
    mcp_match = re.search(r"MCP: (.+)", ai_response)
    if mcp_match:
        test_type = mcp_match.group(1).strip().lower()
        if test_type in ["ping", "http", "traceroute", "dns"]:
            mcp_result = globalping_mcp_request(target, test_type=test_type)
            responses.append(f"🌍 *Globalping MCP {test_type.upper()}:*\n{mcp_result}")

    # Обработка локальных команд
    for match in re.findall(r"Команда: (.+)", ai_response):
        clean_command = match.strip("` ")
        output = run_command(clean_command)
        responses.append(f"💻 *Команда* `{clean_command}`:\n```{output}```")

    results_text = "\n\n".join(responses)
    summary = summarize_results(ai_response, results_text)

    response_text = f"""🤖 *AI Диагностика:*
```{ai_response}```

{results_text}

📋 *Итоговое резюме:*
```{summary}```"""
    
    say(response_text, thread_ts=thread_ts)

if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start() 