"""Build comprehensive investment fund name dictionary from historical data."""

import pandas as pd
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class FundDictionaryBuilder:
    """Build comprehensive fund name dictionary with aliases from historical data."""
    
    def __init__(self, config=None):
        self.config = config
        self.base_dir = Path(__file__).parent.parent.parent
        self.dic_mapping = self._load_dic_mapping()
        
    def _load_dic_mapping(self) -> Dict[str, str]:
        """Load existing DIC/securitycode2.csv mapping."""
        mapping = {}
        try:
            mapping_file = self.base_dir / "DIC" / "securitycode2.csv"
            if mapping_file.exists():
                df = pd.read_csv(mapping_file)
                for _, row in df.iterrows():
                    security_name = str(row['security_name']).strip()
                    security_code = str(row['security_code']).strip()
                    
                    # Clean up security_code
                    if security_code and security_code != 'nan':
                        security_code = security_code.lstrip('，,').strip()
                        if security_code and security_code != 'nan' and len(security_code) > 0:
                            mapping[security_name] = security_code
                
                logger.info(f"Loaded {len(mapping)} DIC mappings")
            return mapping
        except Exception as e:
            logger.error(f"Error loading DIC mapping: {e}")
            return {}
    
    def extract_all_fund_names_from_history(self) -> Set[str]:
        """Extract all investment fund names from historical trade data."""
        fund_names = set()
        
        try:
            # Search for all processed trade files
            processed_dir = self.base_dir / "data" / "processed"
            if not processed_dir.exists():
                logger.warning(f"Processed data directory not found: {processed_dir}")
                return fund_names
            
            trade_files = list(processed_dir.glob("trades_*.csv"))
            logger.info(f"Found {len(trade_files)} trade files to analyze")
            
            for trade_file in trade_files:
                try:
                    df = pd.read_csv(trade_file)
                    logger.info(f"Processing {trade_file.name}: {len(df)} trades")
                    
                    for _, row in df.iterrows():
                        security_name = str(row.get('security_name', '')).strip()
                        security_code = str(row.get('security_code', '')).strip()
                        
                        # Identify investment funds (no security code or fund-like names)
                        if security_name and self._is_likely_fund(security_name, security_code):
                            fund_names.add(security_name)
                            
                except Exception as e:
                    logger.warning(f"Error processing {trade_file}: {e}")
                    continue
            
            logger.info(f"Extracted {len(fund_names)} unique fund names from history")
            return fund_names
            
        except Exception as e:
            logger.error(f"Error extracting fund names: {e}")
            return fund_names
    
    def _is_likely_fund(self, security_name: str, security_code: str) -> bool:
        """Determine if a security is likely an investment fund."""
        # Empty or very short security codes often indicate funds
        if not security_code or len(security_code.strip()) == 0:
            return True
            
        # Fund indicators in name
        fund_indicators = [
            'ファンド', 'Fund', 'インデックス', 'Index', '投信', '投資信託',
            'eMAXIS', 'iFree', 'SBI', 'ＳＢＩ', '楽天', 'Rakuten',
            'ニッセイ', 'Nissay', 'Tracers', 'トレーサーズ',
            '雪だるま', '購入・換金手数料なし', 'Slim'
        ]
        
        return any(indicator in security_name for indicator in fund_indicators)
    
    def generate_comprehensive_aliases(self, fund_name: str) -> List[str]:
        """Generate comprehensive aliases for a fund name using regex patterns."""
        aliases = [fund_name]  # Original name
        
        # Normalize the name for pattern matching
        normalized = self._normalize_fund_name(fund_name)
        aliases.append(normalized)
        
        # Company/Brand aliases
        company_aliases = self._generate_company_aliases(fund_name)
        aliases.extend(company_aliases)
        
        # Index/Asset class aliases
        index_aliases = self._generate_index_aliases(fund_name)
        aliases.extend(index_aliases)
        
        # Regional aliases
        regional_aliases = self._generate_regional_aliases(fund_name)
        aliases.extend(regional_aliases)
        
        # Punctuation variations
        punctuation_aliases = self._generate_punctuation_variations(fund_name)
        aliases.extend(punctuation_aliases)
        
        # Remove duplicates while preserving order
        unique_aliases = []
        seen = set()
        for alias in aliases:
            if alias and alias not in seen:
                unique_aliases.append(alias)
                seen.add(alias)
        
        return unique_aliases
    
    def _normalize_fund_name(self, name: str) -> str:
        """Normalize fund name by removing/standardizing common elements."""
        normalized = name
        
        # Remove common brackets and parentheses content variations
        patterns = [
            r'[（(][^）)]*[）)]',  # Remove content in parentheses
            r'[＜<][^＞>]*[＞>]',   # Remove content in angle brackets
            r'[【][^】]*[】]',       # Remove content in Japanese brackets
            r'\s*・\s*',           # Replace middle dots with space
            r'\s*･\s*',            # Replace alternate middle dots
            r'\s+',                # Multiple spaces to single space
        ]
        
        for pattern in patterns:
            normalized = re.sub(pattern, ' ', normalized)
        
        return normalized.strip()
    
    def _generate_company_aliases(self, name: str) -> List[str]:
        """Generate company/brand name aliases."""
        aliases = []
        
        company_patterns = {
            r'ＳＢＩ[・･\s]*': ['SBI ', 'エスビーアイ'],
            r'楽天[・･\s]*': ['Rakuten ', 'らくてん'],
            r'ニッセイ[・･\s]*': ['Nissay ', '日本生命'],
            r'eMAXIS[・･\s]*': ['イーマクシス', 'emaxis '],
            r'iFree[・･\s]*': ['アイフリー', 'ifree '],
            r'Tracers[・･\s]*': ['トレーサーズ', 'tracers '],
            r'ダイワ[・･\s]*': ['Daiwa ', '大和'],
            r'野村[・･\s]*': ['Nomura ', 'ノムラ'],
        }
        
        for pattern, replacements in company_patterns.items():
            if re.search(pattern, name, re.IGNORECASE):
                for replacement in replacements:
                    alias = re.sub(pattern, replacement, name, flags=re.IGNORECASE)
                    aliases.append(alias.strip())
        
        return aliases
    
    def _generate_index_aliases(self, name: str) -> List[str]:
        """Generate index/asset class aliases."""
        aliases = []
        
        index_patterns = {
            r'S&P\s*500': ['SP500', 'ＳＰ５００', 'エス・アンド・ピー500'],
            r'TOPIX': ['トピックス', 'ＴＯＰＩＸ'],
            r'NASDAQ': ['ナスダック', 'ＮＡＳＤＡＱ'],
            r'MSCI': ['エムエスシーアイ', 'ＭＳＣＩ'],
            r'全世界株式': ['world equity', 'global stock', 'オール・カントリー'],
            r'先進国株式': ['developed market', 'developed equity'],
            r'新興国株式': ['emerging market', 'emerging equity'],
            r'米国株式': ['US equity', 'american stock'],
        }
        
        for pattern, replacements in index_patterns.items():
            if re.search(pattern, name, re.IGNORECASE):
                for replacement in replacements:
                    alias = re.sub(pattern, replacement, name, flags=re.IGNORECASE)
                    aliases.append(alias.strip())
        
        return aliases
    
    def _generate_regional_aliases(self, name: str) -> List[str]:
        """Generate regional aliases."""
        aliases = []
        
        regional_patterns = {
            r'全世界': ['world', 'global', 'オール・カントリー', 'all country'],
            r'先進国': ['developed', 'developed market'],
            r'新興国': ['emerging', 'emerging market'], 
            r'米国': ['US', 'USA', 'america', 'アメリカ'],
            r'欧州': ['europe', 'european', 'ヨーロッパ'],
            r'日本': ['japan', 'japanese', 'にほん'],
        }
        
        for pattern, replacements in regional_patterns.items():
            if re.search(pattern, name):
                for replacement in replacements:
                    alias = re.sub(pattern, replacement, name)
                    aliases.append(alias.strip())
        
        return aliases
    
    def _generate_punctuation_variations(self, name: str) -> List[str]:
        """Generate punctuation and spacing variations."""
        aliases = []
        
        # Variations with different punctuation
        variations = [
            re.sub(r'[（(]([^）)]*)[）)]', r'(\1)', name),  # Full-width to half-width parentheses
            re.sub(r'[（(][^）)]*[）)]', '', name),         # Remove parentheses content
            re.sub(r'[・･]', '・', name),                   # Standardize middle dots
            re.sub(r'[・･]', ' ', name),                   # Replace middle dots with spaces
            re.sub(r'\s+', ' ', name),                     # Normalize spaces
            re.sub(r'[　\s]+', '', name),                   # Remove all spaces
        ]
        
        for variation in variations:
            if variation and variation != name:
                aliases.append(variation.strip())
        
        return aliases
    
    def build_comprehensive_dictionary(self) -> Dict:
        """Build comprehensive fund dictionary from historical data."""
        logger.info("Building comprehensive fund dictionary...")
        
        # Extract all fund names from history
        historical_fund_names = self.extract_all_fund_names_from_history()
        
        # Build comprehensive dictionary
        fund_dictionary = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "total_funds": 0,
                "sources": ["historical_trades", "DIC/securitycode2.csv"],
                "description": "Comprehensive investment fund name to ticker mapping with aliases"
            },
            "funds": {}
        }
        
        # Process each fund name
        processed_count = 0
        for fund_name in historical_fund_names:
            # Try to find ticker from DIC mapping
            ticker = self._find_ticker_from_dic(fund_name)
            
            if ticker:
                aliases = self.generate_comprehensive_aliases(fund_name)
                
                fund_dictionary["funds"][fund_name] = {
                    "ticker": ticker,
                    "aliases": aliases,
                    "source": "DIC_mapping",
                    "confidence": "high"
                }
                processed_count += 1
                logger.debug(f"Mapped: {fund_name} -> {ticker} ({len(aliases)} aliases)")
            else:
                # Add as unmapped for manual review
                aliases = self.generate_comprehensive_aliases(fund_name)
                fund_dictionary["funds"][fund_name] = {
                    "ticker": None,
                    "aliases": aliases,
                    "source": "historical_only",
                    "confidence": "unmapped",
                    "note": "Requires manual ticker assignment"
                }
                logger.warning(f"Unmapped fund: {fund_name}")
        
        fund_dictionary["metadata"]["total_funds"] = len(fund_dictionary["funds"])
        fund_dictionary["metadata"]["mapped_funds"] = processed_count
        fund_dictionary["metadata"]["unmapped_funds"] = len(fund_dictionary["funds"]) - processed_count
        
        logger.info(f"Dictionary built: {len(fund_dictionary['funds'])} funds, {processed_count} mapped")
        return fund_dictionary
    
    def _find_ticker_from_dic(self, fund_name: str) -> Optional[str]:
        """Find ticker for fund from DIC mapping using fuzzy matching."""
        # Direct match first
        if fund_name in self.dic_mapping:
            return self.dic_mapping[fund_name]
        
        # Fuzzy matching with aliases
        normalized_target = self._normalize_fund_name(fund_name)
        
        for dic_name, ticker in self.dic_mapping.items():
            if self._names_match_regex(fund_name, dic_name):
                return ticker
            
            # Try with normalized names
            if normalized_target and self._names_match_regex(normalized_target, dic_name):
                return ticker
        
        return None
    
    def _names_match_regex(self, name1: str, name2: str) -> bool:
        """Advanced regex-based name matching."""
        if not name1 or not name2:
            return False
        
        # Normalize both names
        norm1 = self._normalize_fund_name(name1).lower()
        norm2 = self._normalize_fund_name(name2).lower()
        
        # Exact match after normalization
        if norm1 == norm2:
            return True
        
        # Extract key terms using regex
        key_terms1 = self._extract_key_terms(norm1)
        key_terms2 = self._extract_key_terms(norm2)
        
        # Check for significant overlap in key terms
        if key_terms1 and key_terms2:
            overlap = len(key_terms1 & key_terms2)
            min_terms = min(len(key_terms1), len(key_terms2))
            if min_terms > 0 and overlap / min_terms >= 0.7:
                return True
        
        # Partial string matching for longer names
        if len(norm1) > 10 and len(norm2) > 10:
            if norm1 in norm2 or norm2 in norm1:
                return True
        
        return False
    
    def _extract_key_terms(self, normalized_name: str) -> Set[str]:
        """Extract key terms from normalized fund name."""
        # Remove common stop words
        stop_words = {
            'の', 'と', 'を', 'に', 'は', 'が', 'で', 'から', 'まで',
            'and', 'or', 'of', 'the', 'in', 'on', 'at', 'by', 'for',
            'ファンド', 'fund', 'インデックス', 'index', 'etf', '投信',
            '株式', 'equity', 'stock', '債券', 'bond'
        }
        
        # Extract meaningful terms (3+ characters, not stop words)
        terms = set()
        words = re.findall(r'\w{3,}', normalized_name.lower())
        
        for word in words:
            if word not in stop_words:
                terms.add(word)
        
        return terms
    
    def save_dictionary(self, dictionary: Dict, output_path: Path = None) -> Path:
        """Save the comprehensive dictionary to JSON file."""
        if output_path is None:
            output_path = self.base_dir / "DIC" / "comprehensive_fund_dictionary.json"
        
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(dictionary, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Comprehensive fund dictionary saved to: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error saving dictionary: {e}")
            raise
    
    def build_and_save_dictionary(self) -> Path:
        """Build and save comprehensive fund dictionary."""
        dictionary = self.build_comprehensive_dictionary()
        return self.save_dictionary(dictionary)