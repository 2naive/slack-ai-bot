import os
import json
import subprocess
import re
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
def run_command(command, target):
    if command.strip().startswith("tracert"):
        command = f"tracert -d -h 10 -w 1000 {target}"

    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            shell=True,
            #encoding='cp866',
            errors='replace'
        )
        try:
            stdout, stderr = proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            return "Команда заняла слишком много времени и была прервана."

        return stdout if proc.returncode == 0 else stderr

    except FileNotFoundError:
        return f"Команда не найдена: {command.split()[0]}"

# Функция общения с OpenAI API для получения гипотез и команд
def ai_diagnose_issue(target):
    prompt = f"""
    Сайт или ресурс '{target}' упал.

    Предложи краткие гипотезы причин и предоставь сетевые команды ДЛЯ WINDOWS для проверки этих гипотез.
    Используй только следующие инструменты: curl, tracert, nslookup, ping, telnet.

    Формат ответа:
    Гипотеза: <описание гипотезы>
    Команда: <команда для проверки>
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.2
    )

    return response.choices[0].message.content.strip()

# Функция для формирования итогового резюме после выполнения команд
def summarize_results(diagnostic, results):
    summary_prompt = f"""
    Пиши кратко но емко.
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
        max_tokens=1500,
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

    say(f"# Анализирую проблему с ресурсом: {target}", thread_ts=thread_ts)
    ai_response = ai_diagnose_issue(target)
    response_text = (
        f"# AI Диагностика:\n{ai_response}\n\n"
    )
    say(response_text, thread_ts=thread_ts, mrkdwn=True)

    # Выполняем предложенные команды
    responses = []
    for match in re.findall(r"Команда: (.+)", ai_response):
        clean_command = match.strip("` ")
        output = run_command(clean_command, target)
        responses.append(f"Результат команды '{clean_command}':\n{output}")

    results_text = "\n".join(responses)
    response_text = (
        f"# Результаты проверок:\n{results_text}\n\n"
    )
    say(response_text, thread_ts=thread_ts, mrkdwn=True)

    summary = summarize_results(ai_response, results_text)
    response_text = (
        f"# Итоговое резюме:\n{summary}"
    )
    say(response_text, thread_ts=thread_ts, mrkdwn=True)
    print(response_text)

if __name__ == "__main__":
    print("Бот запущен и слушает сообщения...")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()