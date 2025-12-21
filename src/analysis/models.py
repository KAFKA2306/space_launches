"""Shared data models for portfolio analysis."""

from dataclasses import dataclass
from typing import Dict


@dataclass
class PerformanceMetrics:
    """Performance metrics container."""

    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float


@dataclass
class AssetAllocation:
    """Asset allocation container."""

    by_asset_class: Dict[str, float]
    by_currency: Dict[str, float]
    by_region: Dict[str, float]
    by_account_type: Dict[str, float]
