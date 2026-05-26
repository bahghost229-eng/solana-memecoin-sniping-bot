#!/usr/bin/env python3
"""
Main entry point for Solana Memecoin Sniping Bot
Starts Flask webhook server and Telegram bot
"""

import os
import sys
import logging
import signal
import threading
import asyncio
from dotenv import load_dotenv

from webhook import create_app
from financeur_tracker import FinanceurTracker
from telegram_handler import create_telegram_bot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Required environment variables
REQUIRED_ENV_VARS = [
    'HELIUS_API_KEY',
    'FLUX_RPC_URL',
    'TELEGRAM_BOT_TOKEN',
    'TELEGRAM_CHAT_ID',
    'FINANCEUR_WALLET',
    'WEBHOOK_URL',
]

OPTIONAL_ENV_VARS = {
    'BUY_AMOUNT_SOL': '0.1',
    'MIN_SCORE_TO_TRACK': '60',
    'PORT': '8080',
}

# Global bot instance
telegram_bot = None


def validate_env_vars():
    """Validate all required environment variables are set"""
    missing = []
    for var in REQUIRED_ENV_VARS:
        if not os.environ.get(var):
            missing.append(var)
    
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)
    
    # Set optional vars with defaults
    for var, default in OPTIONAL_ENV_VARS.items():
        if not os.environ.get(var):
            os.environ[var] = default
            logger.info(f"Using default for {var}: {default}")
    
    logger.info("✓ All environment variables validated")


def signal_handler(signum, frame):
    """Handle graceful shutdown"""
    logger.info("Received SIGTERM, shutting down gracefully...")
    
    # Stop telegram bot if running
    if telegram_bot:
        try:
            asyncio.run(telegram_bot.stop())
        except:
            pass
    
    sys.exit(0)


def run_telegram_bot(bot, loop):
    """Run Telegram bot in separate event loop"""
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot.start())
    except Exception as e:
        logger.error(f"Telegram bot error: {e}", exc_info=True)


def main():
    """Main entry point"""
    global telegram_bot
    
    logger.info("=" * 60)
    logger.info("Solana Memecoin Sniping Bot Starting")
    logger.info("=" * 60)
    
    # Validate environment variables
    validate_env_vars()
    
    # Initialize tracker
    tracker = FinanceurTracker()
    
    # Create Flask app with tracker dependency
    app = create_app(tracker)
    
    # Create Telegram bot
    telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    telegram_bot = create_telegram_bot(telegram_token, tracker)
    
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start Telegram bot in separate thread with its own event loop
    telegram_loop = asyncio.new_event_loop()
    telegram_thread = threading.Thread(
        target=run_telegram_bot,
        args=(telegram_bot, telegram_loop),
        daemon=True
    )
    telegram_thread.start()
    logger.info("✓ Telegram bot started in background thread")
    
    # Get port from environment
    port = int(os.environ.get('PORT', 8080))
    
    try:
        logger.info(f"Starting Flask server on port {port}...")
        logger.info(f"Webhook URL: {os.environ.get('WEBHOOK_URL')}")
        logger.info(f"Financeur wallet: {os.environ.get('FINANCEUR_WALLET')}")
        logger.info(f"Min score to track: {os.environ.get('MIN_SCORE_TO_TRACK')}")
        logger.info(f"Telegram bot active for wallet management")
        
        # Run Flask app (blocks)
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True
        )
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
