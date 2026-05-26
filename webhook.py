"""
Flask webhook server for receiving Helius enhanced transaction alerts
"""

import os
import logging
from flask import Flask, request, jsonify

from wallet_analyzer import score_wallet
from token_detector import TokenDetector
from financeur_tracker import FinanceurTracker

logger = logging.getLogger(__name__)

# Global token detector instance
token_detector = None


def create_app(tracker: FinanceurTracker) -> Flask:
    """Create and configure Flask app"""
    app = Flask(__name__)
    app.config['JSON_SORT_KEYS'] = False
    
    global token_detector
    token_detector = TokenDetector(tracker)
    
    financeur_wallet = os.environ.get('FINANCEUR_WALLET')
    min_score = int(os.environ.get('MIN_SCORE_TO_TRACK', 60))
    
    @app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint for Railway"""
        return jsonify({'status': 'ok', 'service': 'solana-sniping-bot'}), 200
    
    @app.route('/webhook', methods=['POST'])
    def webhook():
        """
        Receive Helius enhanced transaction webhook
        Parse for SOL transfers from FINANCEUR_WALLET
        """
        try:
            payload = request.get_json()
            
            if not payload:
                logger.warning("Received empty webhook payload")
                return jsonify({'error': 'empty payload'}), 400
            
            # Handle batch of transactions
            transactions = payload if isinstance(payload, list) else [payload]
            
            for tx in transactions:
                try:
                    _process_transaction(tx, financeur_wallet, min_score, tracker)
                except Exception as e:
                    logger.error(f"Error processing transaction: {e}", exc_info=True)
                    continue
            
            return jsonify({'status': 'processed'}), 200
        
        except Exception as e:
            logger.error(f"Webhook error: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    @app.route('/stats', methods=['GET'])
    def stats():
        """Return tracker statistics"""
        return jsonify(tracker.get_stats()), 200
    
    return app


def _process_transaction(tx: dict, financeur_wallet: str, min_score: int, tracker: FinanceurTracker):
    """Process single transaction looking for transfers from financeur"""
    
    # Check if transaction has nativeTransfers
    if 'nativeTransfers' not in tx:
        return
    
    transfers = tx['nativeTransfers']
    
    for transfer in transfers:
        # Check if this is a transfer FROM the financeur wallet
        if transfer.get('from') != financeur_wallet:
            continue
        
        recipient = transfer.get('to')
        amount_lamports = transfer.get('amount', 0)
        amount_sol = amount_lamports / 1e9
        
        logger.info(f"Detected transfer from financeur to {recipient}: {amount_sol} SOL")
        
        # Score the recipient wallet
        score_result = score_wallet(recipient)
        
        logger.info(
            f"Wallet {recipient} scored: {score_result['score']}/100 "
            f"(age: {score_result['age_days']}d, txs: {score_result['nb_transactions']}, "
            f"launched_token: {score_result['has_launched_token']})"
        )
        
        # Record in tracker
        tracker.record(financeur_wallet, recipient, amount_sol)
        
        # If score is high enough, start monitoring
        if score_result['score'] >= min_score:
            logger.info(f"✓ Score {score_result['score']} >= {min_score}, watching wallet {recipient}")
            score_result['decision'] = 'WATCH'
            
            # Start token detector for this wallet
            if token_detector:
                token_detector.watch(recipient)
        else:
            logger.info(f"✗ Score {score_result['score']} < {min_score}, ignoring wallet {recipient}")
            score_result['decision'] = 'IGNORE'
