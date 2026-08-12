from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import re
import requests

app = FastAPI(title="Catalog Product Scanner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paste your Google Apps Script URL below
GOOGLE_SHEET_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyNBzXCgogYweXJk6UH40hnvGe_cQ4GVjzLthLkYj0SZ4J3aUTo_W-fZ18K2JDx08s4/exec"


def query_db_sku(raw_sku: str):
    conn = sqlite3.connect("master_products.db")
    cursor = conn.cursor()

    clean = raw_sku.strip().upper()
    # Strip finish modifiers (e.g. KIO-CHR-1110118 -> KIO-1110118)
    clean_stripped = re.sub(r'-(CHR|CP|FG|RG|MB|BN|GM|WH|BLK)-', '-', clean)
    digits_only = re.sub(r'[^0-9]', '', clean)

    # 1. Exact SKU Match
    cursor.execute("""
        SELECT brand, category, sku_cat_no, mrp_inr, description, page_no, source_file 
        FROM products 
        WHERE UPPER(sku_cat_no) = ? OR UPPER(sku_cat_no) = ?
    """, (clean, clean_stripped))
    results = cursor.fetchall()

    # 2. Substring Fallback
    if not results:
        cursor.execute("""
            SELECT brand, category, sku_cat_no, mrp_inr, description, page_no, source_file 
            FROM products 
            WHERE UPPER(sku_cat_no) LIKE ? OR UPPER(sku_cat_no) LIKE ?
            LIMIT 1
        """, (f"%{clean}%", f"%{clean_stripped}%"))
        results = cursor.fetchall()

    # 3. Digits-Only Match (e.g., searching 1110118)
    if not results and len(digits_only) >= 5:
        cursor.execute("""
            SELECT brand, category, sku_cat_no, mrp_inr, description, page_no, source_file 
            FROM products 
            WHERE REPLACE(UPPER(sku_cat_no), '-', '') LIKE ?
            LIMIT 1
        """, (f"%{digits_only}%",))
        results = cursor.fetchall()

    conn.close()
    return results


def log_to_google_sheet(brand: str, category: str, sku: str, mrp: str, desc: str, scan_type: str):
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


@app.get("/")
def home():
    return {
        "status": "online",
        "message": "Catalog Product Scanner API is active",
        "docs": "/docs"
    }


@app.get("/scan")
def scan_text_sku(sku: str = Query(..., description="Target SKU or Cat. No.")):
    results = query_db_sku(sku)

    if results:
        r = results[0]
        brand_name = r[0]
        cat_name = r[1]
        sku_code = r[2]
        mrp_str = f"₹{r[3]:,.2f}"
        cleaned_desc = r[4] or ""
        page_num = r[5]
        source_cat = r[6]

        log_to_google_sheet(
            brand=brand_name,
            category=cat_name,
            sku=sku_code,
            mrp=mrp_str,
            desc=cleaned_desc,
            scan_type="Camera Web Scan"
        )

        return {
            "status": "success",
            "searched_sku": sku,
            "matched_sku": sku_code,
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
        raise HTTPException(status_code=404, detail=f"No product found matching SKU: '{sku}'")
