import pdfplumber
import re
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional, Tuple, Generator
import statistics

# Import the combine extraction logic (adjust paths as needed)
from accounts.new_scrappers.combine_scrapper import run_scraper1, run_scraper2, run_scraper3, run_scraper4, run_scraper5, run_scraper6, run_scraper7

@dataclass
class Transaction:
    """Optimized transaction data structure"""
    date: str
    description: str
    debit: float = 0.0
    credit: float = 0.0
    balance: float = 0.0
    line_number: int = 0

@dataclass
class MonthlyData:
    """Optimized monthly analysis data structure"""
    opening_balance: float = 0.0
    closing_balance: float = 0.0
    total_credit: float = 0.0
    total_debit: float = 0.0
    net_change: float = 0.0
    fluctuation: float = 0.0
    minimum_balance: float = float('inf')
    maximum_balance: float = 0.0
    international_inward_count: int = 0
    international_outward_count: int = 0
    international_inward_total: float = 0.0
    international_outward_total: float = 0.0
    transaction_count: int = 0
    balances: List[float] = field(default_factory=list)

class BankStatementExtractor:
    """Enhanced bank statement extractor integrating combine_scrapper.py scrapers with complete analytics"""
    
    # Pre-compiled constants
    ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    ARABIC_CHARS_PATTERN = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
    ENGLISH_CHARS_PATTERN = re.compile(r"[A-Za-z]")
    WHITESPACE_PATTERN = re.compile(r"\s+")
    
    # International transaction keywords (compiled once)
    INTL_KEYWORDS = frozenset(["international", "swift", "wire", "transfer", "intl"])
    
    def __init__(self):
        # List of scraper functions from combine_scrapper.py
        self.scrapers = [
            run_scraper1,
            run_scraper2,
            run_scraper3,
            run_scraper4,
            run_scraper5,
            run_scraper6,
            run_scraper7
        ]
        
        # Pre-compile all regex patterns for fallback
        self.field_patterns = self._compile_field_patterns()
        self.transaction_patterns = self._compile_transaction_patterns()
        self.date_formats = [
            "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d",
            "%d-%m-%Y", "%m-%d-%Y", "%Y-%m-%d",
            "%d/%m/%y", "%m/%d/%y", "%y/%m/%d"
        ]
        
        # Number extraction pattern
        self.number_pattern = re.compile(r'[\d,]+\.?\d*')
        self.date_pattern = re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}')

    def _compile_field_patterns(self) -> Dict[str, Dict[str, re.Pattern]]:
        """Pre-compile field extraction patterns"""
        raw_patterns = {
            "en": {
                "customer_name": r"Customer Name\s+([^\n]+)",
                "city": r"City\s+([^\n]+)",
                "account_number": r"Account Number\s+(\d+)",
                "iban_number": r"IBAN Number\s+([A-Z0-9]+)",
                "opening_balance": r"Opening Balance\s+([\d,]+\.?\d*)\s*SAR",
                "closing_balance": r"Closing Balance\s+([\d,]+\.?\d*)\s*SAR",
                "financial_period": r"On The Period\s+([\d/]+\s*-\s*[\d/]+)"
            },
            "ar": {
                "customer_name": r"(?:اسم العميل|Customer Name)\s+([^\n]+)",
                "city": r"(?:المدينة|City)\s+([^\n]+)",
                "account_number": r"(?:رقم الحساب|Account Number)\s+(\d+)",
                "iban_number": r"(?:رقم الآيبان|IBAN Number)\s+([A-Z0-9]+)",
                "opening_balance": r"(?:الرصيد.*?الإفتتاحي|Opening Balance)\s+([\d,]+\.?\d*)\s*(?:SAR|ر\.س)",
                "closing_balance": r"(?:الرصيد.*?الإقفال|Closing Balance)\s+([\d,]+\.?\d*)\s*(?:SAR|ر\.س)",
                "financial_period": r"(?:خلال الفترة|On The Period)\s+([\d/]+\s*-\s*[\d/]+)"
            }
        }
        
        return {
            lang: {
                key: re.compile(pattern, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                for key, pattern in patterns.items()
            }
            for lang, patterns in raw_patterns.items()
        }

    def _compile_transaction_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Pre-compile transaction extraction patterns"""
        en_patterns = [
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)",
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+([\d,]+\.?\d*)\s*(?:SAR)?\s+([\d,]+\.?\d*)\s*(?:SAR)?\s+([\d,]+\.?\d*)\s*(?:SAR)?",
            r"(\d{2,4}[/-]\d{1,2}[/-]\d{1,2})\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)"
        ]
        
        ar_patterns = [
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+([\d,]+\.?\d*)\s*(?:ر\.س)?\s+([\d,]+\.?\d*)\s*(?:ر\.س)?\s+([\d,]+\.?\d*)\s*(?:ر\.س)?",
            r"(\d{2,4}[/-]\d{1,2}[/-]\d{1,2})\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)"
        ]
        
        return {
            "en": [re.compile(p, re.IGNORECASE) for p in en_patterns],
            "ar": [re.compile(p, re.IGNORECASE) for p in ar_patterns]
        }

    @lru_cache(maxsize=128)
    def normalize_arabic_text(self, txt: str) -> str:
        """Cached Arabic text normalization"""
        return self.WHITESPACE_PATTERN.sub(" ", txt.translate(self.ARABIC_DIGITS)).strip()

    @lru_cache(maxsize=32)
    def detect_language(self, text_sample: str) -> str:
        """Optimized language detection using sample"""
        sample = text_sample[:1000]
        
        arabic_count = len(self.ARABIC_CHARS_PATTERN.findall(sample))
        english_count = len(self.ENGLISH_CHARS_PATTERN.findall(sample))
        
        return "ar" if arabic_count > english_count else "en"

    def parse_account_summary(self, text: str) -> Dict[str, any]:
        """Optimized account summary parsing"""
        lang = self.detect_language(text)
        patterns = self.field_patterns[lang]
        summary = {}
        
        for key, pattern in patterns.items():
            match = pattern.search(text)
            if match:
                val = match.group(1).strip()
                
                if key == "customer_name" and lang == "ar" and "اسم العميل" in val:
                    parts = val.split("اسم العميل")
                    summary[key] = " ".join(reversed(parts)).strip()
                elif key in {"opening_balance", "closing_balance"}:
                    try:
                        summary[key] = float(val.replace(",", ""))
                    except ValueError:
                        summary[key] = 0.0
                else:
                    summary[key] = val
        
        return summary

    def _combine_extract(self, pdf_path: str) -> Dict[str, any]:
        """Run all scrapers sequentially and return the first successful result"""
        for scraper in self.scrapers:
            try:
                result = scraper(pdf_path)
                if result and result.get("total_transactions", 0) > 0:
                    print(f"✅ Success with {result['total_transactions']} transactions using {scraper.__name__}")
                    return result
            except Exception as e:
                print(f"❌ {scraper.__name__} failed: {e}")
        print("❌ All scrapers failed or found no transactions.")
        return {}

    @lru_cache(maxsize=1000)
    def parse_date_cached(self, date_str: str) -> datetime:
        """Cached date parsing for better performance"""
        for fmt in self.date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        print(f"Could not parse date: {date_str}")
        return datetime.now()

    def aggregate_monthly_analysis(self, transactions: List[Transaction]) -> Dict[str, MonthlyData]:
        """Optimized monthly analysis with dataclasses - FROM OLD CODE"""
        if not transactions:
            return {}
        
        # Sort once using built-in sort
        transactions.sort(key=lambda x: self.parse_date_cached(x.date))
        
        monthly_data = defaultdict(MonthlyData)
        
        for tx in transactions:
            try:
                date = self.parse_date_cached(tx.date)
                month_key = date.strftime("%b")
                
                data = monthly_data[month_key]
                data.transaction_count += 1
                data.total_credit += tx.credit
                data.total_debit += tx.debit
                data.closing_balance = tx.balance
                data.minimum_balance = min(data.minimum_balance, tx.balance)
                data.maximum_balance = max(data.maximum_balance, tx.balance)
                data.balances.append(tx.balance)
                
                # Optimized international transaction detection
                desc_lower = tx.description.lower()
                if any(keyword in desc_lower for keyword in self.INTL_KEYWORDS):
                    if tx.credit > 0:
                        data.international_inward_count += 1
                        data.international_inward_total += tx.credit
                    if tx.debit > 0:
                        data.international_outward_count += 1
                        data.international_outward_total += tx.debit
                        
            except Exception as e:
                print(f"Error processing transaction: {e}")
                continue
        
        # Calculate derived metrics in batch
        self._calculate_monthly_metrics(monthly_data)
        
        return dict(monthly_data)

    def _calculate_monthly_metrics(self, monthly_data: Dict[str, MonthlyData]) -> None:
        """Calculate monthly metrics in batch - FROM OLD CODE"""
        prev_balance = 0
        
        # Sort months by chronological order
        sorted_months = sorted(monthly_data.keys(), 
                             key=lambda x: datetime.strptime(x, "%b").month)
        
        for month in sorted_months:
            data = monthly_data[month]
            data.opening_balance = prev_balance if prev_balance > 0 else data.closing_balance
            data.net_change = data.total_credit - data.total_debit
            
            # Optimized fluctuation calculation
            if len(data.balances) > 1:
                mean_balance = statistics.mean(data.balances)
                if mean_balance != 0:
                    data.fluctuation = statistics.stdev(data.balances) / mean_balance * 100
                else:
                    data.fluctuation = 0
            else:
                data.fluctuation = 0
                
            # Clean up temporary data
            data.balances.clear()
            
            if data.minimum_balance == float('inf'):
                data.minimum_balance = 0
                
            prev_balance = data.closing_balance

    def calculate_analytics(self, transactions: List[Transaction], 
                          monthly_data: Dict[str, MonthlyData]) -> Dict[str, float]:
        """Optimized analytics calculation - FROM OLD CODE"""
        if not transactions or not monthly_data:
            return self._empty_analytics()
        
        # Vectorized calculations where possible
        monthly_values = list(monthly_data.values())
        
        total_inflow = sum(data.total_credit for data in monthly_values)
        total_outflow = sum(data.total_debit for data in monthly_values)
        
        num_months = len(monthly_data)
        avg_inflow = total_inflow / num_months
        avg_outflow = total_outflow / num_months
        
        fluctuations = [data.fluctuation for data in monthly_values]
        avg_fluctuation = statistics.mean(fluctuations) if fluctuations else 0
        
        stability = max(0, 100 - avg_fluctuation)
        
        # Optimized foreign transaction counting
        foreign_count = sum(
            data.international_inward_count + data.international_outward_count
            for data in monthly_values
        )
        foreign_amount = sum(
            data.international_inward_total + data.international_outward_total
            for data in monthly_values
        )
        
        # Count overdrafts efficiently
        overdraft_count = sum(1 for tx in transactions if tx.balance < 0)
        
        return {
            "average_fluctuation": round(avg_fluctuation, 2),
            "net_cash_flow_stability": round(stability, 4),
            "total_foreign_transactions": foreign_count,
            "total_foreign_amount": round(foreign_amount, 2),
            "overdraft_frequency": overdraft_count,
            "overdraft_total_days": overdraft_count,
            "sum_total_inflow": round(total_inflow, 2),
            "sum_total_outflow": round(total_outflow, 2),
            "avg_total_inflow": round(avg_inflow, 2),
            "avg_total_outflow": round(avg_outflow, 2)
        }

    def _empty_analytics(self) -> Dict[str, float]:
        """Return empty analytics structure - FROM OLD CODE"""
        return {
            "average_fluctuation": 0.0,
            "net_cash_flow_stability": 0.0,
            "total_foreign_transactions": 0,
            "total_foreign_amount": 0.0,
            "overdraft_frequency": 0,
            "overdraft_total_days": 0,
            "sum_total_inflow": 0.0,
            "sum_total_outflow": 0.0,
            "avg_total_inflow": 0.0,
            "avg_total_outflow": 0.0
        }

    def extract_transactions_enhanced(self, text: str) -> List[Transaction]:
        """Enhanced transaction extraction with optimizations - FALLBACK METHOD"""
        lang = self.detect_language(text)
        patterns = self.transaction_patterns[lang]
        
        print(f"Detected language: {lang}")
        
        best_transactions = []
        max_found = 0
        
        # Try each compiled pattern
        for pattern_idx, pattern in enumerate(patterns):
            print(f"Trying pattern {pattern_idx + 1}...")
            transactions = []
            
            for line_num, line in enumerate(text.split('\n')):
                line = line.strip()
                if not line:
                    continue
                
                if lang == "ar":
                    line = self.normalize_arabic_text(line)
                
                match = pattern.search(line)
                if match:
                    try:
                        date, desc, debit_str, credit_str, balance_str = match.groups()
                        
                        # Optimized number conversion
                        debit = self._safe_float_convert(debit_str)
                        credit = self._safe_float_convert(credit_str)
                        balance = self._safe_float_convert(balance_str)
                        
                        transactions.append(Transaction(
                            date=date.strip(),
                            description=desc.strip(),
                            debit=debit,
                            credit=credit,
                            balance=balance,
                            line_number=line_num
                        ))
                    except (ValueError, AttributeError) as e:
                        print(f"Error parsing line {line_num}: {e}")
                        continue
            
            print(f"Pattern {pattern_idx + 1} extracted {len(transactions)} transactions")
            
            if len(transactions) > max_found:
                best_transactions = transactions
                max_found = len(transactions)
        
        print(f"Final transaction count: {len(best_transactions)}")
        return best_transactions

    def _safe_float_convert(self, value_str: str) -> float:
        """Safe and fast float conversion"""
        try:
            return float(value_str.replace(",", ""))
        except (ValueError, AttributeError):
            return 0.0

    def process_bank_statement(self, pdf_path: str) -> Dict[str, any]:
        """Main processing method using combined scrapers with fallback and complete analytics"""
        start = time.time()
        pdf_path_obj = Path(pdf_path).resolve()
        
        results = {
            "pdf_file": str(pdf_path_obj),
            "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pages_processed": 0,
            "account_info": {},
            "transactions": [],
            "total_transactions": 0,
            "monthly_analysis": {},
            "analytics": {},
        }

        try:
            # Step 1: Try the combined scrapers
            scraper_result = self._combine_extract(pdf_path)
            
            transactions = []  # Will hold Transaction objects for analysis
            
            if scraper_result and scraper_result.get("total_transactions", 0) > 0:
                results["account_info"] = scraper_result.get("account_summary", {})
                results["transactions"] = scraper_result["transactions"]  # List of dicts for output
                results["total_transactions"] = scraper_result["total_transactions"]
                results["pages_processed"] = scraper_result.get("total_pages", 0)
                
                # Convert to Transaction objects for internal analysis
                transactions = [
                    Transaction(
                        date=tx.get("date", ""),
                        description=tx.get("description", ""),
                        debit=float(tx.get("debit", 0.0)),
                        credit=float(tx.get("credit", 0.0)),
                        balance=float(tx.get("balance", 0.0)),
                        line_number=tx.get("line_number", 0)
                    )
                    for tx in results["transactions"]
                    if all(key in tx for key in ["date", "description", "debit", "credit", "balance"])
                ]
                
                print(f"Extracted {results['total_transactions']} transactions using combined scrapers")
            else:
                # Step 2: Fallback to original regex-based extraction
                with pdfplumber.open(pdf_path) as pdf:
                    pages_text = []
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            pages_text.append(page_text)
                    
                    full_text = "\n".join(pages_text)
                    results["pages_processed"] = len(pdf.pages)
                    
                    print(f"Processing {len(pdf.pages)} pages with fallback...")
                    
                    results["account_info"] = self.parse_account_summary(full_text)
                    print(f"Account info extracted: {results['account_info']}")
                    
                    transactions = self.extract_transactions_enhanced(full_text)
                    results["total_transactions"] = len(transactions)
                    
                    # Convert to dicts for output
                    results["transactions"] = [
                        {
                            "date": tx.date,
                            "description": tx.description,
                            "debit": tx.debit,
                            "credit": tx.credit,
                            "balance": tx.balance,
                            "line_number": tx.line_number
                        }
                        for tx in transactions
                    ]
                    
                    print(f"Extracted {results['total_transactions']} transactions with fallback")

            # Step 3: Generate analysis if transactions found (USING OLD CODE METHODS)
            if results["total_transactions"] > 0:
                monthly_data = self.aggregate_monthly_analysis(transactions)
                
                # Convert MonthlyData objects to dictionaries
                results["monthly_analysis"] = {
                    month: {
                        "opening_balance": data.opening_balance,
                        "closing_balance": data.closing_balance,
                        "total_credit": data.total_credit,
                        "total_debit": data.total_debit,
                        "net_change": data.net_change,
                        "fluctuation": data.fluctuation,
                        "minimum_balance": data.minimum_balance,
                        "maximum_balance": data.maximum_balance,
                        "international_inward_count": data.international_inward_count,
                        "international_outward_count": data.international_outward_count,
                        "international_inward_total": data.international_inward_total,
                        "international_outward_total": data.international_outward_total,
                        "transaction_count": data.transaction_count
                    }
                    for month, data in monthly_data.items()
                }
                
                results["analytics"] = self.calculate_analytics(transactions, monthly_data)
                print(f"Generated analysis for {len(monthly_data)} months")
            else:
                print("No transactions found - skipping analysis")
                    
        except Exception as e:
            print(f"Error processing PDF: {e}")
            return {"error": str(e)}

        results["processing_time"] = f"{time.time() - start:.2f}s"
        return results