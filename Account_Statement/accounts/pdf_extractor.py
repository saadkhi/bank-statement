import io, os, json, re, base64, time
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Generator
import statistics

# Conditional imports for OCR functionality
try:
    from PIL import Image
    import fitz
    from huggingface_hub import InferenceClient
    from concurrent.futures import ThreadPoolExecutor
    from functools import partial
    OCR_AVAILABLE = True

    # ---------- Config ----------
    MODEL_ID      = "no model"
    HF_TOKEN      = "no code"

    # ---------- Hugging Face client ----------
    client = InferenceClient(provider="fireworks-ai", api_key=HF_TOKEN)

    # ---------- Helper: PDF → JPEG ----------
    def pdf_to_images(pdf_path, dpi=150):
        doc = fitz.open(pdf_path)
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            images.append(img)
        doc.close()
        return images

except ImportError:
    OCR_AVAILABLE = False
    print("Warning: OCR dependencies not available. Using fallback text extraction.")

    # Define dummy functions when OCR is not available
    def pdf_to_images(pdf_path, dpi=150):
        return []

    client = None
    MODEL_ID = ""
    HF_TOKEN = ""

@dataclass
class Transaction:
    """Transaction data structure"""
    date: str
    description: str
    debit: float = 0.0
    credit: float = 0.0
    balance: float = 0.0
    line_number: int = 0

@dataclass
class MonthlyData:
    """Monthly analysis data structure"""
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

# ---------- Prompt ----------
SYSTEM_RULES = (
    "You are a precise bank statement parser.\n"
    "The table columns are in this order:\n"
    "Balance | Credit | Debit | Transaction Description | Date.\n\n"
    "OUTPUT FORMAT:\n"
    "{\n"
    "  \"account_holder_name\": \"...\",\n"
    "  \"account_number\": \"...\",\n"
    "  \"id_or_iqama_number\": \"...\",\n"
    "  \"transactions\": [\n"
    "    {\n"
    "      \"date\": \"YYYY-MM-DD\",\n"
    "      \"credit\": \"123.45\" or \"\",\n"
    "      \"debit\": \"123.45\" or \"\",\n"
    "      \"transaction_description\": \"...\"\n"
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Rules:\n"
    "- Extract account_holder_name, account_number, id_or_iqama_number if present at top of statement.\n"
    "- For each transaction row:\n"
    "   • Use the Date from the rightmost column.\n"
    "   • Take Credit from Credit column, Debit from Debit column.\n"
    "   • Exactly one of credit or debit must be non-empty.\n"
    "   • Normalize amounts with 2 decimals.\n"
    "   • Never include Balance.\n"
    "Return ONLY valid JSON following the above schema."
)

# ---------- Helper: encode image ----------
def encode_image(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return "data:image/jpeg;base64," + base64.b64encode(buf.read()).decode()

# ---------- Robust JSON extraction ----------
def extract_json_object(text: str):
    text = text.strip()

    # Remove code fences
    text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text, flags=re.IGNORECASE).strip()

    # Try direct load
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try JSON block inside text
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass

    # Fallback if all fails
    return {"transactions": []}

# ---------- Normalization ----------
def norm_amount(value):
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return f"{float(value):.2f}"
    s = str(value)
    m = re.search(r"-?\d+(?:\.\d+)?", s.replace(",", ""))
    return f"{float(m.group(0)):.2f}" if m else ""

def normalize_transaction(row):
    r = {k.strip().lower(): v for k, v in row.items()}
    out = {
        "date": str(r.get("date", "")).strip(),
        "credit": norm_amount(r.get("credit", "")),
        "debit": norm_amount(r.get("debit", "")),
        "transaction_description": str(
            r.get("transaction description", r.get("transaction_description", r.get("description", "")))
        ).strip(),
    }
    # Ensure only one side populated
    if out["credit"] and out["debit"]:
        c, d = float(out["credit"]), float(out["debit"])
        if c >= d:
            out["debit"] = ""
        else:
            out["credit"] = ""
    # Date cleanup
    dm = re.search(r"\d{4}-\d{2}-\d{2}", out["date"])
    if dm:
        out["date"] = dm.group(0)
    return out

# ---------- Main page processor ----------
def process_single_page(img, page_no, total):
    print(f"Processing page {page_no}/{total} …")
    data_url = encode_image(img)
    try:
        resp = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": SYSTEM_RULES},
                {"role": "user", "content": [
                    {"type": "text", "text": "Extract all details and transactions from this statement."},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]}
            ],
            temperature=0,
            max_tokens=3072,
            response_format={"type": "json_object"}   # ✅ force JSON output
        )
        raw_text = resp.choices[0].message["content"]

        return extract_json_object(raw_text)

    except Exception as e:
        print(f"[WARN] Failed parsing page {page_no}: {e}")
        return {"transactions": []}

def aggregate_monthly_analysis(transactions: List[Transaction]) -> Dict[str, MonthlyData]:
    """Monthly analysis aggregation"""
    if not transactions:
        return {}

    # Sort once using built-in sort
    transactions.sort(key=lambda x: parse_date_for_sorting(x.date))

    monthly_data = defaultdict(MonthlyData)

    for tx in transactions:
        try:
            date = parse_date_for_sorting(tx.date)
            month_key = date.strftime("%b")

            data = monthly_data[month_key]
            data.transaction_count += 1
            data.total_credit += tx.credit
            data.total_debit += tx.debit
            data.closing_balance = tx.balance
            data.minimum_balance = min(data.minimum_balance, tx.balance)
            data.maximum_balance = max(data.maximum_balance, tx.balance)
            data.balances.append(tx.balance)

            # International transaction detection
            desc_lower = tx.description.lower()
            if any(keyword in desc_lower for keyword in ["international", "swift", "wire", "transfer", "intl"]):
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
    _calculate_monthly_metrics(monthly_data)

    return dict(monthly_data)

def _calculate_monthly_metrics(monthly_data: Dict[str, MonthlyData]) -> None:
    """Calculate monthly metrics in batch"""
    prev_balance = 0

    # Sort months by chronological order
    sorted_months = sorted(monthly_data.keys(),
                          key=lambda x: datetime.strptime(x, "%b").month)

    for month in sorted_months:
        data = monthly_data[month]
        data.opening_balance = prev_balance if prev_balance > 0 else data.closing_balance
        data.net_change = data.total_credit - data.total_debit

        # Fluctuation calculation
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

def calculate_analytics(transactions: List[Transaction],
                       monthly_data: Dict[str, MonthlyData]) -> Dict[str, float]:
    """Analytics calculation"""
    if not transactions or not monthly_data:
        return _empty_analytics()

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

    # Foreign transaction counting
    foreign_count = sum(
        data.international_inward_count + data.international_outward_count
        for data in monthly_values
    )
    foreign_amount = sum(
        data.international_inward_total + data.international_outward_total
        for data in monthly_values
    )

    # Count overdrafts
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

def _empty_analytics() -> Dict[str, float]:
    """Return empty analytics structure"""
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

def parse_date_for_sorting(date_str: str) -> datetime:
    """Parse date for sorting transactions"""
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y"]:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return datetime.now()

class BankStatementExtractor:
    """Enhanced bank statement extractor using OCR with Hugging Face"""

    def __init__(self):
        self.ocr_available = OCR_AVAILABLE
        if not self.ocr_available:
            print("OCR not available, will use fallback text extraction")

    def _fallback_text_extraction(self, pdf_path: str) -> Dict[str, any]:
        """Fallback method using pdfplumber for text extraction"""
        results = {
            "pdf_file": str(Path(pdf_path).resolve()),
            "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pages_processed": 0,
            "account_info": {},
            "transactions": [],
            "total_transactions": 0,
            "monthly_analysis": {},
            "analytics": {},
        }

        try:
            import pdfplumber
        except ImportError:
            # If pdfplumber is not available, return a basic structure with error info
            print("Warning: pdfplumber not available. PDF processing will be limited.")
            results["error"] = "PDF processing libraries not available. Please install pdfplumber and OCR dependencies for full functionality."
            results["analytics"] = _empty_analytics()
            results["processing_time"] = "0.00s"
            return results

        try:
            with pdfplumber.open(pdf_path) as pdf:
                pages_text = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        pages_text.append(page_text)

                full_text = "\n".join(pages_text)
                results["pages_processed"] = len(pdf.pages)

                # Simple transaction extraction (basic implementation)
                transactions = []
                lines = full_text.split('\n')

                for line_num, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        continue

                    # Basic pattern matching for transactions
                    # This is a simplified version - you may need to adjust patterns
                    date_match = re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', line)
                    amount_match = re.search(r'[\d,]+\.?\d*', line)

                    if date_match and amount_match:
                        transactions.append(Transaction(
                            date=date_match.group(0),
                            description=line,
                            debit=0.0,
                            credit=float(amount_match.group(0).replace(",", "")),
                            balance=0.0,
                            line_number=line_num
                        ))

                results["total_transactions"] = len(transactions)
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

                # Basic account info extraction
                results["account_info"] = {
                    "customer_name": "Unknown",
                    "account_number": "Unknown",
                    "iban_number": "",
                    "opening_balance": 0.0,
                    "closing_balance": 0.0,
                    "financial_period": "",
                }

                # Generate basic analysis if transactions found
                if results["total_transactions"] > 0:
                    monthly_data = aggregate_monthly_analysis(transactions)
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
                    results["analytics"] = calculate_analytics(transactions, monthly_data)
                else:
                    results["analytics"] = _empty_analytics()

        except Exception as e:
            print(f"Error in fallback text extraction: {e}")
            results["error"] = str(e)
            results["analytics"] = _empty_analytics()

        results["processing_time"] = f"{time.time() - time.time():.2f}s"
        return results

    def process_bank_statement(self, pdf_path: str) -> Dict[str, any]:
        """Main processing method - uses OCR if available, otherwise fallback"""
        if self.ocr_available:
            return self._process_bank_statement_ocr(pdf_path)
        else:
            print("Using fallback text extraction method")
            return self._fallback_text_extraction(pdf_path)

    def _process_bank_statement_ocr(self, pdf_path: str) -> Dict[str, any]:
        """OCR-based processing method"""
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
            images = pdf_to_images(pdf_path)
            results["pages_processed"] = len(images)

            with ThreadPoolExecutor(max_workers=8) as pool:
                page_results = list(pool.map(
                    partial(process_single_page, total=len(images)),
                    images, range(1, len(images)+1)
                ))

            # Merge results
            master = dict(account_holder_name="", account_number="", id_or_iqama_number="", transactions=[])
            for parsed in page_results:
                if not parsed:
                    continue
                for key in ["account_holder_name", "account_number", "id_or_iqama_number"]:
                    val = parsed.get(key, "")
                    if val and not master[key]:
                        master[key] = val
                txs = [normalize_transaction(x) for x in parsed.get("transactions", []) if isinstance(x, dict)]
                master["transactions"].extend(txs)

            # Convert OCR transactions to Transaction objects for analysis
            transactions = []
            for idx, tx in enumerate(master["transactions"]):
                try:
                    debit = float(tx.get("debit", 0) or 0)
                    credit = float(tx.get("credit", 0) or 0)
                    transactions.append(Transaction(
                        date=tx.get("date", ""),
                        description=tx.get("transaction_description", ""),
                        debit=debit,
                        credit=credit,
                        balance=0.0,  # Will be calculated later
                        line_number=idx
                    ))
                except (ValueError, TypeError):
                    continue

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

            # Map account info
            results["account_info"] = {
                "customer_name": master.get("account_holder_name", ""),
                "account_number": master.get("account_number", ""),
                "iban_number": "",  # Not available in OCR output
                "opening_balance": 0.0,  # Will be calculated
                "closing_balance": 0.0,  # Will be calculated
                "financial_period": "",  # Not available in OCR output
            }

            # Calculate balances if we have transactions
            if transactions:
                # Sort transactions by date
                transactions.sort(key=lambda x: parse_date_for_sorting(x.date))

                # Calculate running balance
                current_balance = 0.0
                for tx in transactions:
                    current_balance += tx.credit - tx.debit
                    tx.balance = current_balance

                # Update results with calculated balances
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

                # Set opening and closing balances
                if transactions:
                    results["account_info"]["opening_balance"] = transactions[0].balance - (transactions[0].credit - transactions[0].debit)
                    results["account_info"]["closing_balance"] = transactions[-1].balance

            # Generate analysis if transactions found
            if results["total_transactions"] > 0:
                monthly_data = aggregate_monthly_analysis(transactions)
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

                results["analytics"] = calculate_analytics(transactions, monthly_data)
            else:
                results["analytics"] = _empty_analytics()

        except Exception as e:
            print(f"Error processing PDF with OCR: {e}")
            return {"error": str(e)}

        results["processing_time"] = f"{time.time() - start:.2f}s"
        return results