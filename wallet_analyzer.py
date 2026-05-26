"""
Wallet scoring and analysis module
Scores wallets based on age, transaction count, and token launch history
"""

import os
import logging
import time
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

HELIUS_API_KEY = os.environ.get('HELIUS_API_KEY')
BASE_URL = 'https://api.helius.xyz/v0'


def score_wallet(wallet_address: str) -> dict:
    """
    Score a wallet based on:
    - Transaction count (fresh wallets score higher)
    - Wallet age (newer wallets score higher)
    - Token launch history (wallets that haven't launched tokens score higher)
    
    Returns:
        dict: {
            'score': int (0-100),
            'age_days': float,
            'nb_transactions': int,
            'has_launched_token': bool,
            'decision': str ('WATCH' or 'IGNORE')
        }
    """
    try:
        score = 0
        
        # Fetch transactions
        tx_data = _fetch_wallet_transactions(wallet_address)
        nb_transactions = len(tx_data.get('transactions', []))
        
        # Calculate wallet age
        age_days = _calculate_wallet_age(tx_data)
        
        # Check if wallet ever launched a token
        has_launched_token = _check_token_launch(wallet_address, tx_data)
        
        # Scoring logic
        # Fresh wallets (low transaction count)
        if nb_transactions <= 2:
            score += 40
        elif nb_transactions <= 5:
            score += 20
        
        # Very new wallets
        if age_days == 0:
            score += 30  # Created today
        elif age_days <= 1:
            score += 15  # Created yesterday
        
        # Never launched a token
        if not has_launched_token:
            score += 30
        
        # Cap score at 100
        score = min(score, 100)
        
        logger.debug(
            f"Wallet {wallet_address}: score={score}, "
            f"age={age_days}d, txs={nb_transactions}, launched_token={has_launched_token}"
        )
        
        return {
            'score': score,
            'age_days': age_days,
            'nb_transactions': nb_transactions,
            'has_launched_token': has_launched_token,
            'decision': 'WATCH' if score >= 60 else 'IGNORE'
        }
    
    except Exception as e:
        logger.error(f"Error scoring wallet {wallet_address}: {e}", exc_info=True)
        return {
            'score': 0,
            'age_days': -1,
            'nb_transactions': 0,
            'has_launched_token': False,
            'decision': 'IGNORE',
            'error': str(e)
        }


def _fetch_wallet_transactions(wallet_address: str, limit: int = 50) -> dict:
    """
    Fetch transaction history from Helius API with retries
    """
    url = f"{BASE_URL}/addresses/{wallet_address}/transactions"
    params = {
        'api_key': HELIUS_API_KEY,
        'limit': limit,
    }
    
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt < 2:
                wait_time = (2 ** attempt) * 0.5  # Exponential backoff
                logger.warning(f"Helius API attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                logger.error(f"Helius API failed after 3 attempts: {e}")
                raise
    
    return {'transactions': []}


def _calculate_wallet_age(tx_data: dict) -> float:
    """
    Calculate wallet age in days from first transaction
    """
    transactions = tx_data.get('transactions', [])
    
    if not transactions:
        return 0
    
    # Get oldest transaction (last in list if ordered by time)
    oldest_tx = transactions[-1]
    
    # Extract timestamp
    timestamp = oldest_tx.get('timestamp')
    if not timestamp:
        return 0
    
    # Calculate age in days
    tx_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    now = datetime.now(tz=timezone.utc)
    age_seconds = (now - tx_time).total_seconds()
    age_days = age_seconds / 86400
    
    return round(age_days, 2)


def _check_token_launch(wallet_address: str, tx_data: dict) -> bool:
    """
    Check if wallet ever called CREATE_MINT or similar token creation instruction
    """
    transactions = tx_data.get('transactions', [])
    
    # Common token creation program signatures
    token_creation_keywords = [
        'initializeMint',
        'CREATE_MINT',
        'createMint',
        'MintTo',
        'initialize',
    ]
    
    for tx in transactions:
        # Check transaction type
        tx_type = tx.get('type', '')
        if 'MINT' in tx_type or 'TOKEN' in tx_type:
            return True
        
        # Check description
        description = tx.get('description', '')
        for keyword in token_creation_keywords:
            if keyword.lower() in description.lower():
                return True
    
    return False
