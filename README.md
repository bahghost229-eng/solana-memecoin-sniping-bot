# Solana Memecoin Sniping Bot

Automated bot that monitors a "financeur" wallet on Solana and automatically sniping new tokens created by funded wallets on Pump.fun.

## Architecture

```
Financeur Wallet
    ↓
    └─→ Sends SOL to New Wallet
           ↓
           └─→ Helius Webhook (POST /webhook)
                  ↓
                  └─→ Score Wallet (age, tx count, token history)
                         ↓
                         └─→ If Score ≥ 60: Watch for Token Creation
                                ↓
                                └─→ WebSocket Listener (Helius)
                                       ↓
                                       └─→ Detect Pump.fun CREATE_MINT
                                              ↓
                                              └─→ Auto-Send Buy Order (Tradewiz)
```

## Tech Stack

- **Python 3.11** - Core language
- **Flask 3.0** - HTTP webhook server
- **Helius API** - Solana blockchain monitoring (webhooks + WebSocket)
- **FluxRPC** - RPC endpoint
- **python-telegram-bot 20.7** - Telegram bot automation
- **websocket-client 1.7** - WebSocket connections
- **Railway** - Cloud hosting

## Project Structure

```
├── main.py                 # Entry point, env validation, Flask startup
├── webhook.py              # Flask server, receives Helius alerts
├── wallet_analyzer.py      # Scores wallets (0-100 scale)
├── token_detector.py       # WebSocket listener for token creation
├── tradewiz.py            # Sends buy commands via Telegram
├── financeur_tracker.py   # Tracks relationships & metrics
├── requirements.txt       # Python dependencies
├── Procfile               # Railway process definition
├── railway.toml           # Railway config
├── .env.example           # Environment variable template
└── README.md              # This file
```

## Setup

### 1. Prerequisites

- Python 3.11+
- Helius API key (from helius.xyz)
- Telegram bot token (from @BotFather)
- Railway account + CLI installed

### 2. Local Setup

```bash
# Clone repository
git clone https://github.com/bahghost229-eng/solana-memecoin-sniping-bot.git
cd solana-memecoin-sniping-bot

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your values

# Test locally
python main.py
```

### 3. Deploy to Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Deploy from repository root
railway up
```

### 4. Configure Environment Variables in Railway Dashboard

Go to https://railway.app → Select your project → Variables tab:

```
HELIUS_API_KEY = your_api_key
FLUX_RPC_URL = https://mainnet.solana.com
TELEGRAM_BOT_TOKEN = your_bot_token
TELEGRAM_CHAT_ID = your_chat_id
FINANCEUR_WALLET = your_wallet_address
BUY_AMOUNT_SOL = 0.1
MIN_SCORE_TO_TRACK = 60
WEBHOOK_URL = https://your-railway-url.railway.app/webhook
PORT = 8080
```

### 5. Register Helius Webhook

Once deployed, use the Railway public URL to register a webhook in Helius:

```bash
curl -X POST https://api.helius.xyz/v0/webhooks \
  -H "Content-Type: application/json" \
  -d '{
    "webhookUrl": "https://your-railway-url.railway.app/webhook",
    "transactionTypes": ["NATIVE_TRANSFER"],
    "accountAddresses": ["YOUR_FINANCEUR_WALLET"],
    "webhookType": "enhanced"
  }'
```

## Wallet Scoring Logic

Wallets are scored 0-100 based on:

| Metric | Points | Criteria |
|--------|--------|----------|
| Transaction Count | +40 | ≤ 2 transactions |
| Wallet Age | +30 | 0 days old |
| Wallet Age | +15 | 1 day old |
| Token History | +30 | Never launched token |

**Decision:** WATCH if score ≥ 60, IGNORE if < 60

## API Endpoints

### Health Check

```http
GET /health

Response: 200 OK
{
  "status": "ok",
  "service": "solana-sniping-bot"
}
```

### Webhook (Helius)

```http
POST /webhook

Request body: Helius enhanced transaction webhook
Response: 200 OK
{
  "status": "processed"
}
```

### Statistics

```http
GET /stats

Response: 200 OK
{
  "uptime_seconds": 3600,
  "uptime_minutes": 60,
  "total_wallets_funded": 5,
  "total_sol_sent": 0.5,
  "total_tokens_detected": 3,
  "total_successful_buys": 2,
  "overall_success_rate": 40.0,
  "start_time": "2026-05-26T14:00:00+00:00"
}
```

## Logging

All events are logged with timestamps:

```
[2026-05-26 14:32:15] [INFO] Detected transfer from financeur to 7Nq...: 0.1 SOL
[2026-05-26 14:32:16] [INFO] Wallet 7Nq... scored: 85/100 (age: 0.05d, txs: 1)
[2026-05-26 14:32:16] [INFO] ✓ Score 85 >= 60, watching wallet 7Nq...
[2026-05-26 14:32:45] [INFO] ✓ Token creation detected in 5aB...!
[2026-05-26 14:32:46] [INFO] ✓ Buy order sent successfully: /buy MINT 0.1
```

## Error Handling

- **Helius API down**: Retries 3x with exponential backoff
- **WebSocket disconnected**: Auto-reconnects after 5 seconds
- **Telegram send fails**: Retries 3x with 500ms delays
- **Invalid webhook**: Logged and skipped (never crashes)

## Testing

```bash
# Test webhook locally
curl -X POST http://localhost:8080/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "nativeTransfers": [{
      "from": "YOUR_FINANCEUR_WALLET",
      "to": "TEST_WALLET",
      "amount": 100000000
    }]
  }'

# Test health endpoint
curl http://localhost:8080/health

# View stats
curl http://localhost:8080/stats
```

## Troubleshooting

### Bot not detecting transfers

1. Verify Helius webhook is registered with correct financeur wallet
2. Check Railway logs: `railway logs`
3. Confirm environment variables are set in Railway dashboard

### WebSocket connection errors

1. Verify HELIUS_API_KEY is valid
2. Check internet connectivity
3. Bot automatically reconnects after 5 seconds

### Telegram buy orders not sending

1. Verify TELEGRAM_BOT_TOKEN is correct
2. Confirm TELEGRAM_CHAT_ID matches bot chat
3. Check bot has message permissions

## License

MIT
