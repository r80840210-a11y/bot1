# OrdoGram Telegram bot (Render)

## What this starter does
- `/start`, `/number`, `/count`
- One stable, unique **synthetic test identifier** per Telegram user ID, stored in PostgreSQL.
- A small HTTP health endpoint for Render (`/`, `/health`).
- An authenticated event endpoint for status notifications from your own OrdoGram backend.

**Important:** Generated values are explicitly `TEST-...` identifiers, not working phone numbers. This project does not receive SMS or relay authentication codes. For your own app, send safe status notifications such as login approved/denied; keep authentication codes within your app's trusted verification flow.

## Deploy to GitHub + Render
1. Upload `bot.py`, `requirements.txt`, `render.yaml`, and this README to a GitHub repository.
2. In Render, create a Blueprint from that repository, or create a Web Service and a PostgreSQL database manually.
3. Set environment variables:
   - `BOT_TOKEN`: token from @BotFather
   - `DATABASE_URL`: Render PostgreSQL **Internal Database URL** when both services are on Render
   - `ORDOGRAM_API_KEY`: a long random secret shared only with your own backend
4. Deploy. Build command: `pip install -r requirements.txt`; start command: `python bot.py`.
5. Open your bot in Telegram and press Start before expecting it to message you.

## Notify a Telegram user from your own OrdoGram backend
Send an HTTP POST to `https://YOUR-RENDER-SERVICE/ordogram/event` with:
- Header: `X-OrdoGram-Key: YOUR_ORDOGRAM_API_KEY`
- JSON body:
```json
{
  "telegram_id": 123456789,
  "event": "login_approved",
  "message": "Вход в OrdoGram подтверждён."
}
```
Allowed `event` values: `login_approved`, `login_denied`, `security_notice`.

Do not put `BOT_TOKEN` or `ORDOGRAM_API_KEY` in GitHub. Use Render Environment Variables.
