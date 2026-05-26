"""
Tradewiz Telegram bot integration
Sends buy commands to Tradewiz bot
"""

import os
import logging
import time
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
BUY_AMOUNT_SOL = float(os.environ.get('BUY_AMOUNT_SOL', 0.1))


async def send_buy_order(mint_address: str, retries: int = 3) -> bool:
    """
    Send buy command to Tradewiz bot via Telegram
    
    Args:
        mint_address: The token mint address to buy
        retries: Number of retry attempts
    
    Returns:
        bool: True if sent successfully, False otherwise
    """
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    message = f"/buy {mint_address} {BUY_AMOUNT_SOL}"
    
    for attempt in range(retries):
        try:
            response = await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message
            )
            
            logger.info(f"✓ Buy order sent successfully: {message}")
            logger.info(f"Telegram response: {response}")
            return True
        
        except TelegramError as e:
            if attempt < retries - 1:
                wait_time = 0.5 * (attempt + 1)  # 500ms, 1s, 1.5s
                logger.warning(f"Telegram send attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to send buy order after {retries} attempts: {e}")
                return False
        
        except Exception as e:
            logger.error(f"Unexpected error sending buy order: {e}", exc_info=True)
            return False
    
    return False
