"""
WebSocket listener for Pump.fun token creation detection
"""

import os
import logging
import asyncio
import json
import threading
from typing import Optional
from websocket import WebSocketApp, WebSocketException

from tradewiz import send_buy_order

logger = logging.getLogger(__name__)

# Pump.fun program ID
PUMP_FUN_PROGRAM_ID = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'


class TokenDetector:
    """Manages WebSocket connections for token detection"""
    
    def __init__(self, tracker=None):
        self.tracker = tracker
        self.watchers = {}  # wallet_address -> WalletWatcher
        self.helius_key = os.environ.get('HELIUS_API_KEY')
    
    def watch(self, wallet_address: str):
        """
        Start watching a wallet for token creation
        Runs in background thread
        """
        if wallet_address in self.watchers:
            logger.info(f"Already watching {wallet_address}")
            return
        
        logger.info(f"Starting token detector for wallet {wallet_address}")
        
        watcher = WalletWatcher(wallet_address, self.helius_key, self.tracker)
        self.watchers[wallet_address] = watcher
        
        # Run in background thread
        thread = threading.Thread(target=watcher.start, daemon=True)
        thread.start()
    
    def stop_watching(self, wallet_address: str):
        """Stop watching a wallet"""
        if wallet_address in self.watchers:
            watcher = self.watchers[wallet_address]
            watcher.stop()
            del self.watchers[wallet_address]
            logger.info(f"Stopped watching {wallet_address}")


class WalletWatcher:
    """Watches a single wallet via WebSocket"""
    
    def __init__(self, wallet_address: str, helius_key: str, tracker=None):
        self.wallet_address = wallet_address
        self.helius_key = helius_key
        self.tracker = tracker
        self.ws = None
        self.running = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
    
    def start(self):
        """Start WebSocket connection"""
        while self.running and self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                self._connect()
            except Exception as e:
                logger.error(f"WebSocket error for {self.wallet_address}: {e}")
                self.reconnect_attempts += 1
                
                if self.reconnect_attempts < self.max_reconnect_attempts:
                    wait_time = 5 * self.reconnect_attempts
                    logger.info(f"Reconnecting in {wait_time}s...")
                    asyncio.run(asyncio.sleep(wait_time))
    
    def _connect(self):
        """Establish WebSocket connection"""
        url = f"wss://mainnet.helius-rpc.com/?api-key={self.helius_key}"
        
        self.ws = WebSocketApp(
            url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        
        # Send subscription request
        self.ws.on_open = self._on_open
        
        # Run until closed
        self.ws.run_forever()
    
    def _on_open(self, ws):
        """Subscribe to wallet logs on connection"""
        subscription = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "logsSubscribe",
            "params": [
                {
                    "mentions": [self.wallet_address]
                },
                {"commitment": "processed"}
            ]
        }
        
        ws.send(json.dumps(subscription))
        logger.info(f"Subscribed to logs for {self.wallet_address}")
        self.reconnect_attempts = 0
    
    def _on_message(self, ws, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            
            # Check if this is a logs subscription response
            if 'result' in data and isinstance(data['result'], dict):
                logs = data['result'].get('logs', [])
                signature = data['result'].get('signature')
                
                # Check for Pump.fun program in logs
                if self._is_pump_fun_creation(logs):
                    logger.info(f"✓ Token creation detected in {signature}!")
                    mint_address = self._extract_mint_address(data['result'])
                    
                    if mint_address:
                        logger.info(f"Mint address: {mint_address}")
                        
                        # Send buy order
                        try:
                            send_buy_order(mint_address)
                        except Exception as e:
                            logger.error(f"Error sending buy order: {e}")
        
        except json.JSONDecodeError:
            logger.debug(f"Could not parse WebSocket message: {message[:100]}")
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
    
    def _on_error(self, ws, error):
        """Handle WebSocket error"""
        logger.error(f"WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        logger.warning(f"WebSocket closed for {self.wallet_address} (code: {close_status_code})")
    
    def _is_pump_fun_creation(self, logs: list) -> bool:
        """
        Check if logs contain Pump.fun program ID and token creation signal
        """
        for log in logs:
            if PUMP_FUN_PROGRAM_ID in log or 'Program' in log and 'success' in log:
                return True
        return False
    
    def _extract_mint_address(self, result: dict) -> Optional[str]:
        """
        Extract mint address from transaction result
        """
        # Look for mint in account keys or transaction data
        accounts = result.get('accounts', [])
        
        # Return first non-system account (likely the mint)
        for account in accounts:
            if account and len(account) > 20:  # Solana addresses are base58
                return account
        
        return None
    
    def stop(self):
        """Stop the watcher"""
        self.running = False
        if self.ws:
            self.ws.close()
