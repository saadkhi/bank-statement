import io, os, json, re, base64
from PIL import Image
import fitz                     
from huggingface_hub import InferenceClient
from concurrent.futures import ThreadPoolExecutor
from functools import partial

# ---------- Config ----------
PDF_PATH      = "4608277 alinma.pdf"          # <-- your PDF
MODEL_ID      = "meta-llama/Llama-4-Scout-17B-16E-Instruct"
HF_TOKEN      = "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"

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

# ---------- Hugging Face client ----------
client = InferenceClient(provider="fireworks-ai", api_key=HF_TOKEN)

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

# ---------- Run pipeline ----------
if __name__ == "__main__":
    images = pdf_to_images(PDF_PATH)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(
            partial(process_single_page, total=len(images)),
            images, range(1, len(images)+1)
        ))

    # Merge results
    master = dict(account_holder_name="", account_number="", id_or_iqama_number="", transactions=[])
    for parsed in results:
        if not parsed:
            continue
        for key in ["account_holder_name", "account_number", "id_or_iqama_number"]:
            val = parsed.get(key, "")
            if val and not master[key]:
                master[key] = val
        txs = [normalize_transaction(x) for x in parsed.get("transactions", []) if isinstance(x, dict)]
        master["transactions"].extend(txs)

    # Save final JSON
    with open("bank_statement.json", "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False, indent=2)

    print("✅ Done → bank_statement.json")
