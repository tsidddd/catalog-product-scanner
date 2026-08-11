from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import re
import requests

app = FastAPI(title="Catalog Product Scanner API")

# Enable CORS for phone and web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# Google Sheets Webhook Configuration
# -------------------------------------------------------------------
GOOGLE_SHEET_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyNBzXCgogYweXJk6UH40hnvGe_cQ4GVjzLthLkYj0SZ4J3aUTo_W-fZ18K2JDx08s4/exec"


# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------
def query_db_sku(clean_sku: str):
    """
    Queries SQLite for a product SKU.
    Prioritizes EXACT matches first.
    """
    conn = sqlite3.connect("master_products.db")
    cursor = conn.cursor()

    # 1. Exact SKU Match
    cursor.execute("""
        SELECT brand, category, sku_cat_no, mrp_inr, description, page_no, source_file 
        FROM products 
        WHERE UPPER(sku_cat_no) = ?
    """, (clean_sku,))
    results = cursor.fetchall()

    # 2. Wildcard Search Fallback
    if not results:
        cursor.execute("""
            SELECT brand, category, sku_cat_no, mrp_inr, description, page_no, source_file 
            FROM products 
            WHERE UPPER(sku_cat_no) LIKE ?
            LIMIT 1
        """, (f"%{clean_sku}%",))
        results = cursor.fetchall()

    conn.close()
    return results


def log_to_google_sheet(brand: str, category: str, sku: str, mrp: str, desc: str, scan_type: str):
    """
    Posts scanned metadata to Google Sheets via Webhook.
    """
    if "YOUR_COPIED" not in GOOGLE_SHEET_WEBHOOK_URL and GOOGLE_SHEET_WEBHOOK_URL.startswith("http"):
        try:
            payload = {
                "brand": brand,
                "category": category,
                "sku": sku,
                "mrp": mrp,
                "description": desc,
                "scan_type": scan_type
            }
            requests.post(GOOGLE_SHEET_WEBHOOK_URL, json=payload, timeout=4)
        except Exception as e:
            print(f"Google Sheet Logging Exception: {e}")


def clean_description(desc_raw: str) -> str:
    """
    Cleans footer noise from catalog descriptions.
    """
    if not desc_raw:
        return ""
    cleaned = re.sub(r'esscobathware\.com\s*\|\s*\d+', '', desc_raw, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------
@app.get("/")
def home():
    return {
        "status": "online",
        "message": "Catalog Product Scanner API is operational",
        "docs": "/docs"
    }


@app.get("/scan")
def scan_text_sku(sku: str = Query(..., description="Target SKU or Cat. No.")):
    clean_sku = sku.strip().upper()
    results = query_db_sku(clean_sku)

    if results:
        r = results[0]
        brand_name = r[0]
        cat_name = r[1]
        sku_code = r[2]
        mrp_str = f"₹{r[3]:,.2f}"
        cleaned_desc = clean_description(r[4])
        page_num = r[5]
        source_cat = r[6]

        # Log single match to Google Sheet
        log_to_google_sheet(
            brand=brand_name,
            category=cat_name,
            sku=sku_code,
            mrp=mrp_str,
            desc=cleaned_desc,
            scan_type="Camera Scanner"
        )

        return {
            "status": "success",
            "products": [{
                "brand": brand_name,
                "category": cat_name,
                "sku_cat_no": sku_code,
                "mrp_inr": mrp_str,
                "description": cleaned_desc,
                "page_no": page_num,
                "source_catalog": source_cat
            }]
        }
    else:
        raise HTTPException(status_code=404, detail=f"No item found matching SKU: '{sku}'")
