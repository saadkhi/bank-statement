# Working
# import pdfplumber
# import re
# import time
# from pathlib import Path
# from datetime import datetime
# from collections import defaultdict
# import statistics

# class BankStatementExtractor:
#     ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

#     # Enhanced patterns for better matching
#     FIELD_PATTERNS = {
#         "en": {
#             "customer_name": r"Customer Name\s+([^\n]+)",
#             "city": r"City\s+([^\n]+)",
#             "account_number": r"Account Number\s+(\d+)",
#             "iban_number": r"IBAN Number\s+([A-Z0-9]+)",
#             "opening_balance": r"Opening Balance\s+([\d,]+\.?\d*)\s*SAR",
#             "closing_balance": r"Closing Balance\s+([\d,]+\.?\d*)\s*SAR",
#             "financial_period": r"On The Period\s+([\d/]+\s*-\s*[\d/]+)"
#         },
#         "ar": {
#             "customer_name": r"(?:اسم العميل|Customer Name)\s+([^\n]+)",
#             "city": r"(?:المدينة|City)\s+([^\n]+)",
#             "account_number": r"(?:رقم الحساب|Account Number)\s+(\d+)",
#             "iban_number": r"(?:رقم الآيبان|IBAN Number)\s+([A-Z0-9]+)",
#             "opening_balance": r"(?:الرصيد.*?الإفتتاحي|Opening Balance)\s+([\d,]+\.?\d*)\s*(?:SAR|ر\.س)",
#             "closing_balance": r"(?:الرصيد.*?الإقفال|Closing Balance)\s+([\d,]+\.?\d*)\s*(?:SAR|ر\.س)",
#             "financial_period": r"(?:خلال الفترة|On The Period)\s+([\d/]+\s*-\s*[\d/]+)"
#         }
#     }

#     def normalize_arabic_text(self, txt):
#         return re.sub(r"\s+", " ", txt.translate(self.ARABIC_DIGITS).strip())

#     def detect_language(self, text: str) -> str:
#         ARABIC_CHARS_PATTERN = r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
#         ENGLISH_CHARS_PATTERN = r"[A-Za-z]"

#         arabic_count = len(re.findall(ARABIC_CHARS_PATTERN, text))
#         english_count = len(re.findall(ENGLISH_CHARS_PATTERN, text))
        
#         return "ar" if arabic_count > english_count else "en"

#     def parse_account_summary(self, full_text: str) -> dict:
#         lang = self.detect_language(full_text)
#         patterns = self.FIELD_PATTERNS[lang]
#         summary = {}
        
#         for key, pattern in patterns.items():
#             m = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
#             if m:
#                 val = m.group(1).strip()
#                 if key == "customer_name" and lang == "ar":
#                     if "اسم العميل" in val:
#                         parts = val.split("اسم العميل")
#                         summary[key] = " ".join(parts[::-1]).strip()
#                     else:
#                         summary[key] = val
#                 elif key in {"opening_balance", "closing_balance"}:
#                     # Handle both formats: 25,661.50 and 25661.50
#                     val = val.replace(",", "")
#                     try:
#                         summary[key] = float(val)
#                     except ValueError:
#                         summary[key] = 0.0
#                 else:
#                     summary[key] = val
#         return summary

#     def extract_transactions_enhanced(self, full_text: str) -> list:
#         """Enhanced transaction extraction with multiple patterns"""
#         transactions = []
#         lang = self.detect_language(full_text)
        
#         print(f"Detected language: {lang}")
        
#         # Multiple transaction patterns to try
#         patterns = []
        
#         if lang == "en":
#             patterns = [
#                 # Pattern 1: Date Description Debit Credit Balance
#                 r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)",
#                 # Pattern 2: More flexible spacing
#                 r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+([\d,]+\.?\d*)\s*(?:SAR)?\s+([\d,]+\.?\d*)\s*(?:SAR)?\s+([\d,]+\.?\d*)\s*(?:SAR)?",
#                 # Pattern 3: Different date format
#                 r"(\d{2,4}[/-]\d{1,2}[/-]\d{1,2})\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)",
#             ]
#         else:
#             patterns = [
#                 # Arabic patterns
#                 r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+([\d,]+\.?\d*)\s*(?:ر\.س)?\s+([\d,]+\.?\d*)\s*(?:ر\.س)?\s+([\d,]+\.?\d*)\s*(?:ر\.س)?",
#                 r"(\d{2,4}[/-]\d{1,2}[/-]\d{1,2})\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)",
#             ]

#         lines = full_text.split('\n')
        
#         for pattern in patterns:
#             print(f"Trying pattern: {pattern}")
#             temp_transactions = []
            
#             for line_num, line in enumerate(lines):
#                 line = line.strip()
#                 if not line:
#                     continue
                    
#                 # Normalize Arabic digits
#                 if lang == "ar":
#                     line = self.normalize_arabic_text(line)
                
#                 match = re.search(pattern, line, re.IGNORECASE)
#                 if match:
#                     try:
#                         date, desc, debit, credit, balance = match.groups()
                        
#                         # Clean and convert amounts
#                         debit = float(debit.replace(",", "")) if debit.replace(",", "").replace(".", "").isdigit() else 0.0
#                         credit = float(credit.replace(",", "")) if credit.replace(",", "").replace(".", "").isdigit() else 0.0
#                         balance = float(balance.replace(",", "")) if balance.replace(",", "").replace(".", "").isdigit() else 0.0
                        
#                         temp_transactions.append({
#                             "date": date.strip(),
#                             "description": desc.strip(),
#                             "debit": debit,
#                             "credit": credit,
#                             "balance": balance,
#                             "line_number": line_num
#                         })
#                     except (ValueError, AttributeError) as e:
#                         print(f"Error parsing line {line_num}: {line} - {e}")
#                         continue
            
#             print(f"Pattern extracted {len(temp_transactions)} transactions")
            
#             if temp_transactions and len(temp_transactions) > len(transactions):
#                 transactions = temp_transactions
        
#         # If still no transactions, try a more relaxed approach
#         if not transactions:
#             print("Trying relaxed pattern matching...")
#             transactions = self.extract_transactions_relaxed(full_text, lang)
        
#         print(f"Final transaction count: {len(transactions)}")
#         return transactions

#     def extract_transactions_relaxed(self, full_text: str, lang: str) -> list:
#         """More relaxed transaction extraction"""
#         transactions = []
#         lines = full_text.split('\n')
        
#         # Look for lines with multiple numbers that could be transactions
#         for line_num, line in enumerate(lines):
#             line = line.strip()
#             if not line:
#                 continue
                
#             if lang == "ar":
#                 line = self.normalize_arabic_text(line)
            
#             # Find all numbers in the line
#             numbers = re.findall(r'[\d,]+\.?\d*', line)
#             dates = re.findall(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', line)
            
#             # If we have a date and at least 3 numbers, it might be a transaction
#             if dates and len(numbers) >= 3:
#                 try:
#                     date = dates[0]
#                     # Take the last 3 numbers as debit, credit, balance
#                     if len(numbers) >= 3:
#                         amounts = [float(num.replace(",", "")) for num in numbers[-3:]]
#                         debit, credit, balance = amounts
                        
#                         # Extract description (text between date and numbers)
#                         desc_match = re.search(rf'{re.escape(date)}\s+(.+?)\s+[\d,]+\.?\d*', line)
#                         description = desc_match.group(1).strip() if desc_match else "Transaction"
                        
#                         transactions.append({
#                             "date": date,
#                             "description": description,
#                             "debit": debit,
#                             "credit": credit,
#                             "balance": balance,
#                             "line_number": line_num
#                         })
#                 except (ValueError, IndexError) as e:
#                     continue
        
#         return transactions

#     def aggregate_monthly_analysis(self, transactions: list) -> dict:
#         """Create monthly analysis from transactions"""
#         monthly_data = defaultdict(lambda: {
#             "opening_balance": 0,
#             "closing_balance": 0,
#             "total_credit": 0,
#             "total_debit": 0,
#             "net_change": 0,
#             "fluctuation": 0,
#             "minimum_balance": float('inf'),
#             "maximum_balance": 0,
#             "international_inward_count": 0,
#             "international_outward_count": 0,
#             "international_inward_total": 0,
#             "international_outward_total": 0,
#             "transaction_count": 0,
#             "balances": []
#         })
        
#         if not transactions:
#             return {}
        
#         # Sort transactions by date
#         sorted_transactions = sorted(transactions, key=lambda x: self.parse_date(x["date"]))
        
#         for tx in sorted_transactions:
#             try:
#                 date = self.parse_date(tx["date"])
#                 month_key = date.strftime("%b")  # e.g., "Jan", "Feb"
                
#                 data = monthly_data[month_key]
#                 data["transaction_count"] += 1
#                 data["total_credit"] += tx.get("credit", 0)
#                 data["total_debit"] += tx.get("debit", 0)
#                 data["closing_balance"] = tx.get("balance", 0)
#                 data["minimum_balance"] = min(data["minimum_balance"], tx.get("balance", 0))
#                 data["maximum_balance"] = max(data["maximum_balance"], tx.get("balance", 0))
#                 data["balances"].append(tx.get("balance", 0))
                
#                 # Check for international transactions (basic heuristic)
#                 desc = tx.get("description", "").lower()
#                 if any(keyword in desc for keyword in ["international", "swift", "wire", "transfer"]):
#                     if tx.get("credit", 0) > 0:
#                         data["international_inward_count"] += 1
#                         data["international_inward_total"] += tx.get("credit", 0)
#                     if tx.get("debit", 0) > 0:
#                         data["international_outward_count"] += 1
#                         data["international_outward_total"] += tx.get("debit", 0)
                        
#             except Exception as e:
#                 print(f"Error processing transaction: {e}")
#                 continue
        
#         # Calculate derived metrics
#         prev_balance = 0
#         for month in sorted(monthly_data.keys(), key=lambda x: datetime.strptime(x, "%b").month):
#             data = monthly_data[month]
#             data["opening_balance"] = prev_balance if prev_balance > 0 else data["closing_balance"]
#             data["net_change"] = data["total_credit"] - data["total_debit"]
            
#             # Calculate fluctuation as standard deviation of balances
#             if len(data["balances"]) > 1:
#                 data["fluctuation"] = statistics.stdev(data["balances"]) / statistics.mean(data["balances"]) * 100
#             else:
#                 data["fluctuation"] = 0
                
#             # Clean up temporary data
#             del data["balances"]
            
#             if data["minimum_balance"] == float('inf'):
#                 data["minimum_balance"] = 0
                
#             prev_balance = data["closing_balance"]
        
#         return dict(monthly_data)

#     def calculate_analytics(self, transactions: list, monthly_data: dict) -> dict:
#         """Calculate overall analytics"""
#         if not transactions or not monthly_data:
#             return {
#                 "average_fluctuation": 0,
#                 "net_cash_flow_stability": 0,
#                 "total_foreign_transactions": 0,
#                 "total_foreign_amount": 0,
#                 "overdraft_frequency": 0,
#                 "overdraft_total_days": 0,
#                 "sum_total_inflow": 0,
#                 "sum_total_outflow": 0,
#                 "avg_total_inflow": 0,
#                 "avg_total_outflow": 0
#             }
        
#         # Calculate aggregated metrics
#         total_inflow = sum(data["total_credit"] for data in monthly_data.values())
#         total_outflow = sum(data["total_debit"] for data in monthly_data.values())
#         avg_inflow = total_inflow / len(monthly_data) if monthly_data else 0
#         avg_outflow = total_outflow / len(monthly_data) if monthly_data else 0
        
#         fluctuations = [data["fluctuation"] for data in monthly_data.values()]
#         avg_fluctuation = statistics.mean(fluctuations) if fluctuations else 0
        
#         # Calculate stability (inverse of fluctuation)
#         stability = max(0, 100 - avg_fluctuation)
        
#         # Count foreign transactions
#         foreign_count = sum(
#             data["international_inward_count"] + data["international_outward_count"]
#             for data in monthly_data.values()
#         )
#         foreign_amount = sum(
#             data["international_inward_total"] + data["international_outward_total"]
#             for data in monthly_data.values()
#         )
        
#         # Count overdraft instances (balance < 0)
#         overdraft_count = sum(1 for tx in transactions if tx.get("balance", 0) < 0)
        
#         return {
#             "average_fluctuation": round(avg_fluctuation, 2),
#             "net_cash_flow_stability": round(stability, 4),
#             "total_foreign_transactions": foreign_count,
#             "total_foreign_amount": round(foreign_amount, 2),
#             "overdraft_frequency": overdraft_count,
#             "overdraft_total_days": overdraft_count,  # Simplified
#             "sum_total_inflow": round(total_inflow, 2),
#             "sum_total_outflow": round(total_outflow, 2),
#             "avg_total_inflow": round(avg_inflow, 2),
#             "avg_total_outflow": round(avg_outflow, 2)
#         }

#     def parse_date(self, date_str: str) -> datetime:
#         """Parse date string with multiple format support"""
#         formats = [
#             "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d",
#             "%d-%m-%Y", "%m-%d-%Y", "%Y-%m-%d",
#             "%d/%m/%y", "%m/%d/%y", "%y/%m/%d"
#         ]
        
#         for fmt in formats:
#             try:
#                 return datetime.strptime(date_str, fmt)
#             except ValueError:
#                 continue
        
#         # If all else fails, return current date
#         print(f"Could not parse date: {date_str}")
#         return datetime.now()

#     def process_bank_statement(self, pdf_path):
#         start = time.time()
#         results = {
#             "pdf_file": str(Path(pdf_path).resolve()),
#             "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
#             "pages_processed": 0,
#             "account_info": {},
#             "transactions": [],
#             "total_transactions": 0,
#             "monthly_analysis": {},
#             "analytics": {},
#         }

#         try:
#             with pdfplumber.open(pdf_path) as pdf:
#                 full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
#                 results["pages_processed"] = len(pdf.pages)
                
#                 print(f"Processing {len(pdf.pages)} pages...")
                
#                 # Parse account info
#                 results["account_info"] = self.parse_account_summary(full_text)
#                 print(f"Account info extracted: {results['account_info']}")
                
#                 # Extract transactions with enhanced method
#                 results["transactions"] = self.extract_transactions_enhanced(full_text)
#                 results["total_transactions"] = len(results["transactions"])
                
#                 print(f"Extracted {results['total_transactions']} transactions")
                
#                 # Generate monthly analysis and analytics only if we have transactions
#                 if results["transactions"]:
#                     results["monthly_analysis"] = self.aggregate_monthly_analysis(results["transactions"])
#                     results["analytics"] = self.calculate_analytics(results["transactions"], results["monthly_analysis"])
#                     print(f"Generated analysis for {len(results['monthly_analysis'])} months")
#                 else:
#                     print("No transactions found - skipping analysis")
                    
#         except Exception as e:
#             print(f"Error processing PDF: {e}")
#             return {"error": str(e)}

#         results["processing_time"] = f"{time.time() - start:.2f}s"
#         return results

# Second

# import pdfplumber
# import re
# import time
# from pathlib import Path
# from datetime import datetime
# from collections import defaultdict
# from dataclasses import dataclass, field
# from functools import lru_cache
# from typing import Dict, List, Optional, Tuple, Generator
# import statistics

# @dataclass
# class Transaction:
#     """Optimized transaction data structure"""
#     date: str
#     description: str
#     debit: float = 0.0
#     credit: float = 0.0
#     balance: float = 0.0
#     line_number: int = 0

# @dataclass
# class MonthlyData:
#     """Optimized monthly analysis data structure"""
#     opening_balance: float = 0.0
#     closing_balance: float = 0.0
#     total_credit: float = 0.0
#     total_debit: float = 0.0
#     net_change: float = 0.0
#     fluctuation: float = 0.0
#     minimum_balance: float = float('inf')
#     maximum_balance: float = 0.0
#     international_inward_count: int = 0
#     international_outward_count: int = 0
#     international_inward_total: float = 0.0
#     international_outward_total: float = 0.0
#     transaction_count: int = 0
#     balances: List[float] = field(default_factory=list)

# class BankStatementExtractor:
#     """Optimized bank statement extractor with improved performance"""
    
#     # Pre-compiled constants
#     ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
#     ARABIC_CHARS_PATTERN = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
#     ENGLISH_CHARS_PATTERN = re.compile(r"[A-Za-z]")
#     WHITESPACE_PATTERN = re.compile(r"\s+")
    
#     # International transaction keywords (compiled once)
#     INTL_KEYWORDS = frozenset(["international", "swift", "wire", "transfer"])
    
#     def __init__(self):
#         # Pre-compile all regex patterns
#         self.field_patterns = self._compile_field_patterns()
#         self.transaction_patterns = self._compile_transaction_patterns()
#         self.date_formats = [
#             "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d",
#             "%d-%m-%Y", "%m-%d-%Y", "%Y-%m-%d",
#             "%d/%m/%y", "%m/%d/%y", "%y/%m/%d"
#         ]
        
#         # Number extraction pattern
#         self.number_pattern = re.compile(r'[\d,]+\.?\d*')
#         self.date_pattern = re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}')

#     def _compile_field_patterns(self) -> Dict[str, Dict[str, re.Pattern]]:
#         """Pre-compile field extraction patterns"""
#         raw_patterns = {
#             "en": {
#                 "customer_name": r"Customer Name\s+([^\n]+)",
#                 "city": r"City\s+([^\n]+)",
#                 "account_number": r"Account Number\s+(\d+)",
#                 "iban_number": r"IBAN Number\s+([A-Z0-9]+)",
#                 "opening_balance": r"Opening Balance\s+([\d,]+\.?\d*)\s*SAR",
#                 "closing_balance": r"Closing Balance\s+([\d,]+\.?\d*)\s*SAR",
#                 "financial_period": r"On The Period\s+([\d/]+\s*-\s*[\d/]+)"
#             },
#             "ar": {
#                 "customer_name": r"(?:اسم العميل|Customer Name)\s+([^\n]+)",
#                 "city": r"(?:المدينة|City)\s+([^\n]+)",
#                 "account_number": r"(?:رقم الحساب|Account Number)\s+(\d+)",
#                 "iban_number": r"(?:رقم الآيبان|IBAN Number)\s+([A-Z0-9]+)",
#                 "opening_balance": r"(?:الرصيد.*?الإفتتاحي|Opening Balance)\s+([\d,]+\.?\d*)\s*(?:SAR|ر\.س)",
#                 "closing_balance": r"(?:الرصيد.*?الإقفال|Closing Balance)\s+([\d,]+\.?\d*)\s*(?:SAR|ر\.س)",
#                 "financial_period": r"(?:خلال الفترة|On The Period)\s+([\d/]+\s*-\s*[\d/]+)"
#             }
#         }
        
#         return {
#             lang: {
#                 key: re.compile(pattern, re.IGNORECASE | re.MULTILINE | re.DOTALL)
#                 for key, pattern in patterns.items()
#             }
#             for lang, patterns in raw_patterns.items()
#         }

#     def _compile_transaction_patterns(self) -> Dict[str, List[re.Pattern]]:
#         """Pre-compile transaction extraction patterns"""
#         en_patterns = [
#             r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)",
#             r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+([\d,]+\.?\d*)\s*(?:SAR)?\s+([\d,]+\.?\d*)\s*(?:SAR)?\s+([\d,]+\.?\d*)\s*(?:SAR)?",
#             r"(\d{2,4}[/-]\d{1,2}[/-]\d{1,2})\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)"
#         ]
        
#         ar_patterns = [
#             r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+([\d,]+\.?\d*)\s*(?:ر\.س)?\s+([\d,]+\.?\d*)\s*(?:ر\.س)?\s+([\d,]+\.?\d*)\s*(?:ر\.س)?",
#             r"(\d{2,4}[/-]\d{1,2}[/-]\d{1,2})\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)"
#         ]
        
#         return {
#             "en": [re.compile(p, re.IGNORECASE) for p in en_patterns],
#             "ar": [re.compile(p, re.IGNORECASE) for p in ar_patterns]
#         }

#     @lru_cache(maxsize=128)
#     def normalize_arabic_text(self, txt: str) -> str:
#         """Cached Arabic text normalization"""
#         return self.WHITESPACE_PATTERN.sub(" ", txt.translate(self.ARABIC_DIGITS)).strip()

#     @lru_cache(maxsize=32)
#     def detect_language(self, text_sample: str) -> str:
#         """Optimized language detection using sample"""
#         # Use first 1000 chars for faster detection
#         sample = text_sample[:1000]
        
#         arabic_count = len(self.ARABIC_CHARS_PATTERN.findall(sample))
#         english_count = len(self.ENGLISH_CHARS_PATTERN.findall(sample))
        
#         return "ar" if arabic_count > english_count else "en"

#     def parse_account_summary(self, text: str) -> Dict[str, any]:
#         """Optimized account summary parsing"""
#         lang = self.detect_language(text)
#         patterns = self.field_patterns[lang]
#         summary = {}
        
#         for key, pattern in patterns.items():
#             match = pattern.search(text)
#             if match:
#                 val = match.group(1).strip()
                
#                 if key == "customer_name" and lang == "ar" and "اسم العميل" in val:
#                     parts = val.split("اسم العميل")
#                     summary[key] = " ".join(reversed(parts)).strip()
#                 elif key in {"opening_balance", "closing_balance"}:
#                     try:
#                         summary[key] = float(val.replace(",", ""))
#                     except ValueError:
#                         summary[key] = 0.0
#                 else:
#                     summary[key] = val
        
#         return summary

#     def _process_lines_generator(self, text: str, lang: str) -> Generator[str, None, None]:
#         """Memory-efficient line processing generator"""
#         for line in text.split('\n'):
#             line = line.strip()
#             if not line:
#                 continue
            
#             if lang == "ar":
#                 line = self.normalize_arabic_text(line)
            
#             yield line

#     def extract_transactions_enhanced(self, text: str) -> List[Transaction]:
#         """Enhanced transaction extraction with optimizations"""
#         lang = self.detect_language(text)
#         patterns = self.transaction_patterns[lang]
        
#         print(f"Detected language: {lang}")
        
#         best_transactions = []
#         max_found = 0
        
#         # Try each compiled pattern
#         for pattern_idx, pattern in enumerate(patterns):
#             print(f"Trying pattern {pattern_idx + 1}...")
#             transactions = []
            
#             for line_num, line in enumerate(self._process_lines_generator(text, lang)):
#                 match = pattern.search(line)
#                 if match:
#                     try:
#                         date, desc, debit_str, credit_str, balance_str = match.groups()
                        
#                         # Optimized number conversion
#                         debit = self._safe_float_convert(debit_str)
#                         credit = self._safe_float_convert(credit_str)
#                         balance = self._safe_float_convert(balance_str)
                        
#                         transactions.append(Transaction(
#                             date=date.strip(),
#                             description=desc.strip(),
#                             debit=debit,
#                             credit=credit,
#                             balance=balance,
#                             line_number=line_num
#                         ))
#                     except (ValueError, AttributeError) as e:
#                         print(f"Error parsing line {line_num}: {e}")
#                         continue
            
#             print(f"Pattern {pattern_idx + 1} extracted {len(transactions)} transactions")
            
#             if len(transactions) > max_found:
#                 best_transactions = transactions
#                 max_found = len(transactions)
        
#         # Fallback to relaxed extraction if needed
#         if not best_transactions:
#             print("Trying relaxed pattern matching...")
#             best_transactions = self._extract_transactions_relaxed(text, lang)
        
#         print(f"Final transaction count: {len(best_transactions)}")
#         return best_transactions

#     def _safe_float_convert(self, value_str: str) -> float:
#         """Safe and fast float conversion"""
#         try:
#             return float(value_str.replace(",", ""))
#         except (ValueError, AttributeError):
#             return 0.0

#     def _extract_transactions_relaxed(self, text: str, lang: str) -> List[Transaction]:
#         """Relaxed transaction extraction fallback"""
#         transactions = []
        
#         for line_num, line in enumerate(self._process_lines_generator(text, lang)):
#             numbers = self.number_pattern.findall(line)
#             dates = self.date_pattern.findall(line)
            
#             if dates and len(numbers) >= 3:
#                 try:
#                     date = dates[0]
#                     amounts = [self._safe_float_convert(num) for num in numbers[-3:]]
#                     debit, credit, balance = amounts
                    
#                     # Extract description more efficiently
#                     desc_parts = line.split(date, 1)
#                     if len(desc_parts) > 1:
#                         desc_part = desc_parts[1]
#                         # Remove numbers from description
#                         for num in numbers:
#                             desc_part = desc_part.replace(num, "", 1)
#                         description = desc_part.strip() or "Transaction"
#                     else:
#                         description = "Transaction"
                    
#                     transactions.append(Transaction(
#                         date=date,
#                         description=description,
#                         debit=debit,
#                         credit=credit,
#                         balance=balance,
#                         line_number=line_num
#                     ))
#                 except (ValueError, IndexError):
#                     continue
        
#         return transactions

#     @lru_cache(maxsize=1000)
#     def parse_date_cached(self, date_str: str) -> datetime:
#         """Cached date parsing for better performance"""
#         for fmt in self.date_formats:
#             try:
#                 return datetime.strptime(date_str, fmt)
#             except ValueError:
#                 continue
        
#         print(f"Could not parse date: {date_str}")
#         return datetime.now()

#     def aggregate_monthly_analysis(self, transactions: List[Transaction]) -> Dict[str, MonthlyData]:
#         """Optimized monthly analysis with dataclasses"""
#         if not transactions:
#             return {}
        
#         # Sort once using built-in sort
#         transactions.sort(key=lambda x: self.parse_date_cached(x.date))
        
#         monthly_data = defaultdict(MonthlyData)
        
#         for tx in transactions:
#             try:
#                 date = self.parse_date_cached(tx.date)
#                 month_key = date.strftime("%b")
                
#                 data = monthly_data[month_key]
#                 data.transaction_count += 1
#                 data.total_credit += tx.credit
#                 data.total_debit += tx.debit
#                 data.closing_balance = tx.balance
#                 data.minimum_balance = min(data.minimum_balance, tx.balance)
#                 data.maximum_balance = max(data.maximum_balance, tx.balance)
#                 data.balances.append(tx.balance)
                
#                 # Optimized international transaction detection
#                 desc_lower = tx.description.lower()
#                 if any(keyword in desc_lower for keyword in self.INTL_KEYWORDS):
#                     if tx.credit > 0:
#                         data.international_inward_count += 1
#                         data.international_inward_total += tx.credit
#                     if tx.debit > 0:
#                         data.international_outward_count += 1
#                         data.international_outward_total += tx.debit
                        
#             except Exception as e:
#                 print(f"Error processing transaction: {e}")
#                 continue
        
#         # Calculate derived metrics in batch
#         self._calculate_monthly_metrics(monthly_data)
        
#         return dict(monthly_data)

#     def _calculate_monthly_metrics(self, monthly_data: Dict[str, MonthlyData]) -> None:
#         """Calculate monthly metrics in batch"""
#         prev_balance = 0
        
#         # Sort months by chronological order
#         sorted_months = sorted(monthly_data.keys(), 
#                              key=lambda x: datetime.strptime(x, "%b").month)
        
#         for month in sorted_months:
#             data = monthly_data[month]
#             data.opening_balance = prev_balance if prev_balance > 0 else data.closing_balance
#             data.net_change = data.total_credit - data.total_debit
            
#             # Optimized fluctuation calculation
#             if len(data.balances) > 1:
#                 mean_balance = statistics.mean(data.balances)
#                 if mean_balance != 0:
#                     data.fluctuation = statistics.stdev(data.balances) / mean_balance * 100
#                 else:
#                     data.fluctuation = 0
#             else:
#                 data.fluctuation = 0
                
#             # Clean up temporary data
#             data.balances.clear()
            
#             if data.minimum_balance == float('inf'):
#                 data.minimum_balance = 0
                
#             prev_balance = data.closing_balance

#     def calculate_analytics(self, transactions: List[Transaction], 
#                           monthly_data: Dict[str, MonthlyData]) -> Dict[str, float]:
#         """Optimized analytics calculation"""
#         if not transactions or not monthly_data:
#             return self._empty_analytics()
        
#         # Vectorized calculations where possible
#         monthly_values = list(monthly_data.values())
        
#         total_inflow = sum(data.total_credit for data in monthly_values)
#         total_outflow = sum(data.total_debit for data in monthly_values)
        
#         num_months = len(monthly_data)
#         avg_inflow = total_inflow / num_months
#         avg_outflow = total_outflow / num_months
        
#         fluctuations = [data.fluctuation for data in monthly_values]
#         avg_fluctuation = statistics.mean(fluctuations) if fluctuations else 0
        
#         stability = max(0, 100 - avg_fluctuation)
        
#         # Optimized foreign transaction counting
#         foreign_count = sum(
#             data.international_inward_count + data.international_outward_count
#             for data in monthly_values
#         )
#         foreign_amount = sum(
#             data.international_inward_total + data.international_outward_total
#             for data in monthly_values
#         )
        
#         # Count overdrafts efficiently
#         overdraft_count = sum(1 for tx in transactions if tx.balance < 0)
        
#         return {
#             "average_fluctuation": round(avg_fluctuation, 2),
#             "net_cash_flow_stability": round(stability, 4),
#             "total_foreign_transactions": foreign_count,
#             "total_foreign_amount": round(foreign_amount, 2),
#             "overdraft_frequency": overdraft_count,
#             "overdraft_total_days": overdraft_count,
#             "sum_total_inflow": round(total_inflow, 2),
#             "sum_total_outflow": round(total_outflow, 2),
#             "avg_total_inflow": round(avg_inflow, 2),
#             "avg_total_outflow": round(avg_outflow, 2)
#         }

#     def _empty_analytics(self) -> Dict[str, float]:
#         """Return empty analytics structure"""
#         return {
#             "average_fluctuation": 0.0,
#             "net_cash_flow_stability": 0.0,
#             "total_foreign_transactions": 0,
#             "total_foreign_amount": 0.0,
#             "overdraft_frequency": 0,
#             "overdraft_total_days": 0,
#             "sum_total_inflow": 0.0,
#             "sum_total_outflow": 0.0,
#             "avg_total_inflow": 0.0,
#             "avg_total_outflow": 0.0
#         }

#     def process_bank_statement(self, pdf_path: str) -> Dict[str, any]:
#         """Main processing method with optimizations"""
#         start = time.time()
#         pdf_path_obj = Path(pdf_path).resolve()
        
#         results = {
#             "pdf_file": str(pdf_path_obj),
#             "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
#             "pages_processed": 0,
#             "account_info": {},
#             "transactions": [],
#             "total_transactions": 0,
#             "monthly_analysis": {},
#             "analytics": {},
#         }

#         try:
#             with pdfplumber.open(pdf_path) as pdf:
#                 # Process pages efficiently
#                 pages_text = []
#                 for page in pdf.pages:
#                     page_text = page.extract_text()
#                     if page_text:
#                         pages_text.append(page_text)
                
#                 full_text = "\n".join(pages_text)
#                 results["pages_processed"] = len(pdf.pages)
                
#                 print(f"Processing {len(pdf.pages)} pages...")
                
#                 # Parse account info
#                 results["account_info"] = self.parse_account_summary(full_text)
#                 print(f"Account info extracted: {results['account_info']}")
                
#                 # Extract transactions
#                 transactions = self.extract_transactions_enhanced(full_text)
#                 results["total_transactions"] = len(transactions)
                
#                 # Convert dataclass objects to dictionaries for JSON serialization
#                 results["transactions"] = [
#                     {
#                         "date": tx.date,
#                         "description": tx.description,
#                         "debit": tx.debit,
#                         "credit": tx.credit,
#                         "balance": tx.balance,
#                         "line_number": tx.line_number
#                     }
#                     for tx in transactions
#                 ]
                
#                 print(f"Extracted {results['total_transactions']} transactions")
                
#                 # Generate analysis
#                 if transactions:
#                     monthly_data = self.aggregate_monthly_analysis(transactions)
                    
#                     # Convert MonthlyData objects to dictionaries
#                     results["monthly_analysis"] = {
#                         month: {
#                             "opening_balance": data.opening_balance,
#                             "closing_balance": data.closing_balance,
#                             "total_credit": data.total_credit,
#                             "total_debit": data.total_debit,
#                             "net_change": data.net_change,
#                             "fluctuation": data.fluctuation,
#                             "minimum_balance": data.minimum_balance,
#                             "maximum_balance": data.maximum_balance,
#                             "international_inward_count": data.international_inward_count,
#                             "international_outward_count": data.international_outward_count,
#                             "international_inward_total": data.international_inward_total,
#                             "international_outward_total": data.international_outward_total,
#                             "transaction_count": data.transaction_count
#                         }
#                         for month, data in monthly_data.items()
#                     }
                    
#                     results["analytics"] = self.calculate_analytics(transactions, monthly_data)
#                     print(f"Generated analysis for {len(monthly_data)} months")
#                 else:
#                     print("No transactions found - skipping analysis")
                    
#         except Exception as e:
#             print(f"Error processing PDF: {e}")
#             return {"error": str(e)}

#         results["processing_time"] = f"{time.time() - start:.2f}s"
#         return results