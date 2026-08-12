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

GOOGLE_SHEET_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyNBzXCgogYweXJk6UH40hnvGe_cQ4GVjzLthLkYj0SZ4J3aUTo_W-fZ18K2JDx08s4/exec"


def sanitize_sku(raw_sku: str) -> list:
    """
    Generates a list of target SKU variations by stripping common finish/color codes 
    (e.g., CHR, CP, FG, RG, MB, BN, GM, WH, BLK) so KIO-CHR-1110118 matches KIO-1110118.
    """
    clean = raw_sku.strip().upper()
    variations = [clean]
    
    # List of common brand finish identifiers in bathware & hardware
    finish_pattern = re.compile(r'-(CHR|CP|FG|RG|MB|BN|GM|WH|BLK|CH|S8|FG32|58)-', re.IGNORECASE)
    
    # Strip finish identifier from middle of SKU
    stripped_mid = finish_pattern.sub('-', clean)
    if stripped_mid not in variations:
        variations.append(stripped_mid)
        
    # Strip finish identifier if appended at end (e.g., AEC-1111N-CHR -> AEC-1111N)
    stripped_end = re.sub(r'-(CHR|CP|FG|RG|MB|BN|GM|WH|BLK|CH)$', '', clean, flags=re.IGNORECASE)
    if stripped_end not in variations:
        variations.append(stripped_end)

    return variations


def query_db_sku(clean_sku: str):
    conn = sqlite3.connect("master_products.db")
    cursor = conn.cursor()

    clean = clean_sku.strip().upper()
    
    # Query SQLite using the JSON Search Variations Index
    cursor.execute("""
        SELECT brand, category, sku_cat_no, finish_code, finish_name, mrp_inr, description, page_no, source_file 
        FROM products 
        WHERE search_variations LIKE ? OR UPPER(sku_cat_no) = ? OR UPPER(base_model_code) = ?
        LIMIT 1
    """, (f'%"{clean}"%', clean, clean))
    
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


def clean_description(desc_raw: str) -> str:
    if not desc_raw:
        return ""
    cleaned = re.sub(r'esscobathware\.com\s*\|\s*\d+', '', desc_raw, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


@app.get("/")
def home():
    return {
        "status": "online",
        "message": "Catalog Product Scanner API is operational",
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
        cleaned_desc = clean_description(r[4])
        page_num = r[5]
        source_cat = r[6]

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
        raise HTTPException(status_code=404, detail=f"No item found matching SKU: '{sku}'")
