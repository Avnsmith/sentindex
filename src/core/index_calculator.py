"""
Index calculation methods for Sentindex.

Implements both level-based normalized and return-based index calculations
to prevent price magnitude dominance and provide accurate weighted indices.
"""

from typing import Dict, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class IndexCalculator:
    """Handles index calculations with multiple methods."""
    
    def __init__(self, weights: Dict[str, float], base_prices: Dict[str, float], 
                 index_base: float = 1000.0):
        """
        Initialize calculator with weights and base prices.
        
        Args:
            weights: Asset weights (must sum to 1.0)
            base_prices: Base prices at index origin
            index_base: Starting index level (default 1000.0)
        """
        self.weights = weights
        self.base_prices = base_prices
        self.index_base = index_base
        
        # Validate weights sum to 1.0
        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {weight_sum}")
    
    def compute_level_normalized(self, prices: Dict[str, float]) -> float:
        """
        Compute level-based normalized index.
        
        Normalizes each asset to its base value at index origin so different 
        price magnitudes don't dominate the index.
        
        Formula: index = sum((price / base_price) * weight) * index_base
        
        Args:
            prices: Current asset prices
            
        Returns:
            Calculated index value
        """
        try:
            score = 0.0
            for symbol, weight in self.weights.items():
                if symbol not in prices:
                    logger.warning(f"Missing price for {symbol}, skipping")
                    continue
                    
                if symbol not in self.base_prices:
                    logger.error(f"Missing base price for {symbol}")
                    continue
                
                if self.base_prices[symbol] <= 0:
                    logger.error(f"Invalid base price for {symbol}: {self.base_prices[symbol]}")
                    continue
                
                normalized_price = prices[symbol] / self.base_prices[symbol]
                score += normalized_price * weight
            
            index_value = round(score * self.index_base, 2)
            logger.debug(f"Level normalized index: {index_value}")
            return index_value
            
        except Exception as e:
            logger.error(f"Error computing level normalized index: {e}")
            raise
    
    def compute_return_index(self, prev_prices: Dict[str, float], 
                           cur_prices: Dict[str, float], 
                           prev_index_level: float) -> float:
        """
        Compute return-based index.
        
        Computes period returns, applies weights to returns, and accumulates.
        Good for risk/return focused indexes.
        
        Formula: new_index = prev_index * (1 + weighted_return)
        
        Args:
            prev_prices: Previous period prices
            cur_prices: Current period prices
            prev_index_level: Previous index level
            
        Returns:
            New index level
        """
        try:
            weighted_return = 0.0
            
            for symbol, weight in self.weights.items():
                if symbol not in prev_prices or symbol not in cur_prices:
                    logger.warning(f"Missing price data for {symbol}, skipping")
                    continue
                
                if prev_prices[symbol] <= 0:
                    logger.error(f"Invalid previous price for {symbol}: {prev_prices[symbol]}")
                    continue
                
                period_return = (cur_prices[symbol] - prev_prices[symbol]) / prev_prices[symbol]
                weighted_return += period_return * weight
            
            new_index = round(prev_index_level * (1 + weighted_return), 4)
            logger.debug(f"Return-based index: {new_index} (weighted return: {weighted_return:.4f})")
            return new_index
            
        except Exception as e:
            logger.error(f"Error computing return index: {e}")
            raise
    
    def compute_index_delta_24h(self, current_index: float, 
                              prev_24h_index: float) -> float:
        """
        Compute 24-hour percentage change.
        
        Args:
            current_index: Current index value
            prev_24h_index: Index value 24 hours ago
            
        Returns:
            Percentage change (e.g., 1.5 for 1.5% increase)
        """
        if prev_24h_index <= 0:
            logger.warning("Invalid previous index value for delta calculation")
            return 0.0
        
        delta_pct = ((current_index - prev_24h_index) / prev_24h_index) * 100
        return round(delta_pct, 2)
    
    def validate_prices(self, prices: Dict[str, float]) -> Tuple[bool, str]:
        """
        Validate price data quality.
        
        Args:
            prices: Price data to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not prices:
            return False, "No price data provided"
        
        for symbol in self.weights.keys():
            if symbol not in prices:
                return False, f"Missing price for {symbol}"
            
            if prices[symbol] <= 0:
                return False, f"Invalid price for {symbol}: {prices[symbol]}"
        
        return True, ""


class IndexConfig:
    """Configuration for index calculations."""
    
    @staticmethod
    def get_gold_silver_oil_crypto_config() -> Dict:
        """Get configuration for Gold-Silver-Oil-Crypto index."""
        return {
            "name": "Gold-Silver-Oil-Crypto Index",
            "base_level": 1000.0,
            "base_date": "2025-01-01",
            "weights": {
                "GOLD": 0.25,
                "SILVER": 0.25,
                "OIL": 0.20,
                "BTC": 0.15,
                "ETH": 0.15
            },
            "base_prices": {
                "GOLD": 1800.0,    # USD/oz
                "SILVER": 23.0,    # USD/oz
                "OIL": 75.0,       # USD/bbl
                "BTC": 20000.0,    # USD
                "ETH": 1000.0      # USD
            }
        }
    
    @staticmethod
    def create_calculator(config: Dict) -> IndexCalculator:
        """Create IndexCalculator from configuration."""
        return IndexCalculator(
            weights=config["weights"],
            base_prices=config["base_prices"],
            index_base=config["base_level"]
        )


# Example usage and testing
if __name__ == "__main__":
    # Test the index calculator
    config = IndexConfig.get_gold_silver_oil_crypto_config()
    calculator = IndexConfig.create_calculator(config)
    
    # Example prices
    test_prices = {
        "GOLD": 1900.12,
        "SILVER": 24.31,
        "OIL": 78.45,
        "BTC": 27450.0,
        "ETH": 1850.0
    }
    
    # Test level-based calculation
    index_value = calculator.compute_level_normalized(test_prices)
    print(f"Level-based index: {index_value}")
    
    # Test return-based calculation
    prev_prices = {
        "GOLD": 1800.0,
        "SILVER": 23.0,
        "OIL": 75.0,
        "BTC": 20000.0,
        "ETH": 1000.0
    }
    
    return_index = calculator.compute_return_index(prev_prices, test_prices, 1000.0)
    print(f"Return-based index: {return_index}")
    
    # Test validation
    is_valid, error = calculator.validate_prices(test_prices)
    print(f"Price validation: {is_valid}, {error}")
