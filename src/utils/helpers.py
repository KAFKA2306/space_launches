"""Utility helper functions."""

import logging
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


def setup_logging(level=logging.INFO):
    """Set up logging configuration."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


def clean_numeric(value):
    """Clean and convert value to numeric."""
    if pd.isna(value) or value == "-" or value == "":
        return np.nan

    if isinstance(value, (int, float)):
        return float(value)

    # Remove commas, currency symbols, and parentheses
    value = str(value).replace(",", "").replace("円", "").replace("(", "").replace(")", "")

    # Extract numeric value
    match = re.search(r"-?\d+(\.\d+)?", value)
    if match:
        return float(match.group())

    return np.nan


def standardize_date(date_str):
    """Standardize date format to datetime."""
    if pd.isna(date_str) or date_str == "":
        return pd.NaT

    date_formats = ["%Y/%m/%d", "%Y-%m-%d", "%Y年%m月%d日", "%y/%m/%d", "%y-%m-%d"]

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
    for enc in ["shift_jis", "utf-8", "cp932", "iso-8859-1"]:
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
