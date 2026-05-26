"""
Financeur wallet tracker
Tracks relationships between financeur and funded wallets
"""

import logging
from datetime import datetime, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)


class FinanceurTracker:
    """Track financeur → wallet relationships and success metrics"""
    
    def __init__(self):
        # wallet_address -> list of (timestamp, amount_sol)
        self.funded_wallets = defaultdict(list)
        # wallet_address -> {'mints': [], 'successful_buys': 0}
        self.wallet_stats = defaultdict(lambda: {'mints': [], 'successful_buys': 0})
        self.total_sol_sent = 0.0
        self.start_time = datetime.now(tz=timezone.utc)
    
    def record(self, financeur: str, funded_wallet: str, amount_sol: float):
        """
        Record a transfer from financeur to a new wallet
        
        Args:
            financeur: Sender wallet address
            funded_wallet: Recipient wallet address
            amount_sol: Amount transferred in SOL
        """
        timestamp = datetime.now(tz=timezone.utc)
        self.funded_wallets[funded_wallet].append({
            'timestamp': timestamp,
            'amount': amount_sol,
            'financeur': financeur
        })
        self.total_sol_sent += amount_sol
        
        logger.info(
            f"[TRACKER] Recorded: {financeur[:8]}... → {funded_wallet[:8]}... ({amount_sol} SOL) "
            f"at {timestamp.isoformat()}"
        )
    
    def record_token_detected(self, wallet: str, mint_address: str):
        """
        Record that a wallet created a token
        """
        if mint_address not in self.wallet_stats[wallet]['mints']:
            self.wallet_stats[wallet]['mints'].append(mint_address)
            logger.info(f"[TRACKER] Token detected for {wallet[:8]}...: {mint_address}")
    
    def record_buy_success(self, wallet: str):
        """
        Record a successful buy order for a wallet
        """
        self.wallet_stats[wallet]['successful_buys'] += 1
        logger.info(f"[TRACKER] Buy success for {wallet[:8]}... (total: {self.wallet_stats[wallet]['successful_buys']})")
    
    def count_funded_wallets(self, financeur: str = None) -> int:
        """
        Count how many wallets have been funded
        
        Args:
            financeur: If provided, count only wallets funded by this financeur
        
        Returns:
            Count of funded wallets
        """
        if financeur is None:
            return len(self.funded_wallets)
        
        count = 0
        for wallet, transfers in self.funded_wallets.items():
            for transfer in transfers:
                if transfer.get('financeur') == financeur:
                    count += 1
                    break
        return count
    
    def success_rate(self, financeur: str = None) -> float:
        """
        Calculate success rate (buys / wallets funded)
        
        Args:
            financeur: If provided, calculate for this financeur only
        
        Returns:
            Success rate as percentage (0-100)
        """
        funded = self.count_funded_wallets(financeur)
        if funded == 0:
            return 0.0
        
        successful = sum(
            1 for wallet, stats in self.wallet_stats.items()
            if stats['successful_buys'] > 0
        )
        
        return (successful / funded) * 100
    
    def get_stats(self) -> dict:
        """
        Get comprehensive statistics
        """
        uptime_seconds = (datetime.now(tz=timezone.utc) - self.start_time).total_seconds()
        uptime_minutes = uptime_seconds / 60
        
        return {
            'uptime_seconds': round(uptime_seconds),
            'uptime_minutes': round(uptime_minutes, 2),
            'total_wallets_funded': len(self.funded_wallets),
            'total_sol_sent': round(self.total_sol_sent, 4),
            'total_tokens_detected': sum(len(stats['mints']) for stats in self.wallet_stats.values()),
            'total_successful_buys': sum(stats['successful_buys'] for stats in self.wallet_stats.values()),
            'overall_success_rate': round(self.success_rate(), 2),
            'start_time': self.start_time.isoformat(),
        }
