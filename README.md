# Virtual Number Bot + API

Минимальный starter для собственного мессенджера. Номера `+7XXXXXXXXXX` здесь — внутренние идентификаторы, они не являются реальными телефонными номерами и не принимают SMS.

## Как работает
- Пользователь запускает бота и получает постоянный виртуальный ID через `/start` или `/mynumber`.
- Ваше приложение вызывает `POST /auth/request-code` с номером. API отправляет одноразовый 5-значный код в Telegram-чат, который ранее зарегистрировал этот ID.
- Приложение вызывает `POST /auth/verify-code` для проверки. Код действует 5 минут и имеет максимум 5 попыток.
- Запросы API требуют заголовок `X-API-Key: <API_SECRET>`.

## Render
`render.yaml` описывает Web Service API и Background Worker бота. Создайте сервисы из Blueprint и задайте один и тот же `BOT_TOKEN` обоим сервисам. `API_SECRET` нужен API; сохраните его в настройках сервера и не встраивайте секрет в публичное мобильное приложение. Для production мобильное приложение должно вызывать API через ваш собственный backend, а не содержать общий API key.

**Важно про базу данных:** два Render-сервиса с разными persistent disks не разделяют SQLite-файл, даже если у них одинаковый путь. Для реального деплоя используйте общую PostgreSQL базу (рекомендуется) или запускайте бот и API в одном сервисе с одним persistent disk. Этот starter оставляет SQLite для локального теста; не деплойте два сервиса как есть, пока не замените DB-слой на общую БД.

## Локальный запуск
```bash
pip install -r requirements.txt
export BOT_TOKEN="токен_от_BotFather"
export API_SECRET="длинный_случайный_секрет"
python bot.py
```
В другом терминале с теми же переменными:
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

## API
```http
POST /auth/request-code
X-API-Key: <API_SECRET>
Content-Type: application/json

{"phone":"+71234567890"}
```

```http
POST /auth/verify-code
X-API-Key: <API_SECRET>
Content-Type: application/json

{"phone":"+71234567890","code":"01234"}
```

Для production: используйте PostgreSQL, HTTPS, rate limiting, подписанные session tokens, ротацию секретов и мониторинг. Не используйте для входа в сторонние сервисы.


## Render Web Service (один сервис)
В этой версии `api.py` запускает HTTP API на `$PORT` и polling Telegram-бота в том же процессе. На Render используй команду запуска:
`uvicorn api:app --host 0.0.0.0 --port $PORT`

Не запускай одновременно `python bot.py` или старый Background Worker с тем же токеном — иначе Telegram выдаст `Conflict: terminated by other getUpdates request`. Удали/останови старый worker после успешного обновления. SQLite хранится на persistent disk, который подключён к этому единственному сервису.
\n\nПорт добавлен: приложение слушает `0.0.0.0` и читает номер порта из переменной окружения `PORT` (локальный запасной порт — `10000`). Для Render Start Command: `uvicorn api:app --host 0.0.0.0 --port $PORT`. Не указывай фиксированный порт вместо `$PORT` в настройках Render.\n\n\n### Render Web Service, если Start Command = `python bot.py`\n`bot.py` теперь запускает HTTP health endpoint на `0.0.0.0:$PORT` (fallback `10000`) и Telegram polling. Используй Start Command `python bot.py`. Не запускай второй polling-процесс с тем же токеном.\n