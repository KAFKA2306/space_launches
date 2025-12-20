"""Utility helper functions."""

import logging
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import Config


def setup_logging(level=logging.INFO):
    """Set up logging configuration."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


def clean_numeric(value):
    """Clean and convert value to numeric.

    Handles Japanese financial formats like:
    - '100,000' -> 100000
    - '100,000(499)' -> 100000 (ignores points in parentheses)
    - '100,000円' -> 100000
    """
    if pd.isna(value) or value == "-" or value == "":
        return np.nan

    if isinstance(value, (int, float)):
        return float(value)

    import unicodedata

    value_str = str(value)
    
    # Normalize unicode characters (handles full-width numbers/punctuation)
    value_str = unicodedata.normalize("NFKC", value_str)

    # Handle 'amount(points)' format: extract value BEFORE parentheses
    # This is common in Japanese broker CSVs: 100,000(499) = 100k yen + 499 points
    if "(" in value_str:
        value_str = value_str.split("(")[0]

    # Remove commas and currency symbols
    value_str = value_str.replace(",", "").replace("円", "").strip()

    # Extract numeric value
    match = re.search(r"-?\d+(\.\d+)?", value_str)
    if match:
        return float(match.group())

    return np.nan


def standardize_date(date_str):
    """Standardize date format to datetime."""
    if pd.isna(date_str) or date_str == "":
        return pd.NaT

    date_formats = Config.get("date_formats")

    for fmt in date_formats:
        try:
            return pd.to_datetime(date_str, format=fmt)
        except ValueError:
            continue

    try:
        return pd.to_datetime(date_str, errors="coerce")
    except Exception:
        return pd.NaT


def standardize_transaction_type(transaction_type, mappings):
    """Standardize transaction type using mappings."""
    if pd.isna(transaction_type):
        return "unknown"

    original_type = str(transaction_type).lower().strip()

    for standard_type, variations in mappings.items():
        if any(variation in original_type for variation in variations):
            return standard_type

    return original_type


def standardize_currency(currency, mappings):
    """Standardize currency using mappings."""
    if pd.isna(currency):
        return "Unknown"

    original_currency = str(currency).strip()

    for standard_currency, variations in mappings.items():
        if original_currency in variations:
            return standard_currency

    return original_currency


def detect_file_encoding(file_path):
    """Detect file encoding using chardet."""
    try:
        import chardet

        with open(file_path, "rb") as f:
            result = chardet.detect(f.read())
            return result.get("encoding", "utf-8")
    except ImportError:
        return "utf-8"


def read_csv_safe(file_path, encoding=None, skiprows=0, **kwargs):
    """Safely read CSV file with encoding detection."""
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Try specified encoding or detected one
    encodings_to_try = []
    if encoding:
        encodings_to_try.append(encoding)
    else:
        detected = detect_file_encoding(file_path)
        encodings_to_try.append(detected)

    # Add common fallbacks
    for enc in Config.get("fallback_encodings"):
        if enc not in encodings_to_try:
            encodings_to_try.append(enc)

    for enc in encodings_to_try:
        try:
            return pd.read_csv(file_path, encoding=enc, skiprows=skiprows, **kwargs)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue

    # If all fail, raise the last exception or a generic one
    raise ValueError(f"Could not read CSV file {file_path} with any of the attempted encodings.")


def ensure_columns(df, required_columns):
    """Ensure DataFrame has all required columns."""
    for col in required_columns:
        if col not in df.columns:
            df[col] = None
    return df[required_columns]


def get_timestamp():
    """Get current timestamp string."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")
