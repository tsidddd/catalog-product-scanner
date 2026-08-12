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

GOOGLE_SHEET_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyNyyly5-3rn7X9zz5BEKvPgF4GeJ8yzCZjSVAwvIGa0Ziiibi3nEuSe0ywy18vUGni/exec"


def query_db_sku_variants(raw_sku: str):
    conn = sqlite3.connect("master_products.db")
    cursor = conn.cursor()

    clean = raw_sku.strip().upper()
    # Strip middle finish code to get base model (e.g. KIO-CHR-1110118 -> KIO-1110118)
    base_model = re.sub(r'-(CHR|CP|FG|RG|MB|BN|GM|WH|BLK|CH)-', '-', clean)
    digits_only = re.sub(r'[^0-9]', '', clean)

    # 1. Search all variants sharing the same base model
    cursor.execute("""
        SELECT brand, category, sku_cat_no, finish_code, finish_name, mrp_inr, description, page_no, source_file 
        FROM products 
        WHERE UPPER(base_model_code) = ? OR UPPER(sku_cat_no) = ? OR UPPER(sku_cat_no) = ?
        ORDER BY mrp_inr ASC
    """, (base_model, clean, base_model))
    results = cursor.fetchall()

    # 2. Substring fallback if exact base model is not found
    if not results:
        cursor.execute("""
            SELECT brand, category, sku_cat_no, finish_code, finish_name, mrp_inr, description, page_no, source_file 
            FROM products 
            WHERE UPPER(sku_cat_no) LIKE ? OR UPPER(base_model_code) LIKE ?
            ORDER BY mrp_inr ASC
        """, (f"%{base_model}%", f"%{base_model}%"))
        results = cursor.fetchall()

    # 3. Digits fallback (e.g., matching 1110118)
    if not results and len(digits_only) >= 5:
        cursor.execute("""
            SELECT brand, category, sku_cat_no, finish_code, finish_name, mrp_inr, description, page_no, source_file 
            FROM products 
            WHERE REPLACE(UPPER(sku_cat_no), '-', '') LIKE ?
            ORDER BY mrp_inr ASC
        """, (f"%{digits_only}%",))
        results = cursor.fetchall()

    conn.close()
    return results


def log_to_google_sheet(brand: str, category: str, sku: str, finish: str, mrp: str, desc: str, scan_type: str):
    if "YOUR_COPIED" not in GOOGLE_SHEET_WEBHOOK_URL and GOOGLE_SHEET_WEBHOOK_URL.startswith("http"):
        try:
            payload = {
                "brand": brand,
                "category": category,
                "sku": sku,
                "finish": finish,
                "mrp": mrp,
                "description": desc,
                "scan_type": scan_type
            }
            requests.post(GOOGLE_SHEET_WEBHOOK_URL, json=payload, timeout=3)
        except Exception as e:
            print(f"Google Sheet Logging Exception: {e}")


@app.get("/")
def home():
    return {"status": "online", "message": "Catalog Scanner API active"}


@app.get("/scan")
def scan_text_sku(sku: str = Query(..., description="Target SKU or Cat. No.")):
    results = query_db_sku_variants(sku)

    if results:
        variants = []
        for r in results:
            variants.append({
                "brand": r[0],
                "category": r[1],
                "sku_cat_no": r[2],
                "finish_code": r[3],
                "finish_name": r[4],
                "mrp_inr": f"₹{r[5]:,.2f}",
                "description": r[6] or "",
                "page_no": r[7],
                "source_catalog": r[8]
            })

        # Log primary matching item to Google Sheets
        top_match = variants[0]
        log_to_google_sheet(
            brand=top_match["brand"],
            category=top_match["category"],
            sku=top_match["sku_cat_no"],
            finish=top_match["finish_name"],
            mrp=top_match["mrp_inr"],
            desc=top_match["description"],
            scan_type="Camera Scan"
        )

        return {
            "status": "success",
            "searched_sku": sku,
            "total_variants_found": len(variants),
            "products": variants
        }
    else:
        raise HTTPException(status_code=404, detail=f"No item found matching SKU: '{sku}'")
