from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import re
import requests
import os

app = FastAPI(title="Master Catalog Product Scanner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to PostgreSQL (Render DATABASE_URL environment variable or local pgAdmin)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:Siddhartha@01@localhost:5432/catalog_db")
GOOGLE_SHEET_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyNyyly5-3rn7X9zz5BEKvPgF4GeJ8yzCZjSVAwvIGa0Ziiibi3nEuSe0ywy18vUGni/exec"

def query_master_catalog(raw_sku: str):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    clean = raw_sku.strip().upper()
    base_model = re.sub(r'-(CHR|CP|FG|RG|MB|BN|GM|WH|BLK|CH)-', '-', clean)
    digits_only = re.sub(r'[^0-9]', '', clean)

    # High-Performance JOIN query across Brands, Categories, and Series
    cursor.execute("""
        SELECT 
            b.brand_name,
            c.category_name,
            s.series_name,
            p.sku_cat_no,
            p.finish_code,
            p.finish_name,
            p.mrp_inr,
            p.description,
            p.page_no,
            p.source_file
        FROM products p
        JOIN brands b ON p.brand_id = b.brand_id
        JOIN categories c ON p.category_id = c.category_id
        LEFT JOIN series s ON p.series_id = s.series_id
        WHERE UPPER(p.sku_cat_no) = %s 
           OR UPPER(p.base_model_code) = %s 
           OR %s = ANY(p.search_variations)
        ORDER BY p.mrp_inr ASC
    """, (clean, base_model, clean))
    
    results = cursor.fetchall()

    # Digits-only fallback
    if not results and len(digits_only) >= 5:
        cursor.execute("""
            SELECT 
                b.brand_name,
                c.category_name,
                s.series_name,
                p.sku_cat_no,
                p.finish_code,
                p.finish_name,
                p.mrp_inr,
                p.description,
                p.page_no,
                p.source_file
            FROM products p
            JOIN brands b ON p.brand_id = b.brand_id
            JOIN categories c ON p.category_id = c.category_id
            LEFT JOIN series s ON p.series_id = s.series_id
            WHERE %s = ANY(p.search_variations)
            ORDER BY p.mrp_inr ASC
        """, (digits_only,))
        results = cursor.fetchall()

    conn.close()
    return results

def log_to_google_sheet(brand, category, series, sku, finish, mrp, desc, scan_type):
    if "YOUR_COPIED" not in GOOGLE_SHEET_WEBHOOK_URL and GOOGLE_SHEET_WEBHOOK_URL.startswith("http"):
        try:
            payload = {
                "brand": brand,
                "category": category,
                "series": series,
                "sku": sku,
                "finish": finish,
                "mrp": mrp,
                "description": desc,
                "scan_type": scan_type
            }
            requests.post(GOOGLE_SHEET_WEBHOOK_URL, json=payload, timeout=3)
        except Exception as e:
            print(f"Sheet Logging Error: {e}")

@app.get("/")
def home():
    return {
        "status": "online",
        "message": "Master Catalog Scanner API connected to PostgreSQL pgAdmin DB"
    }

@app.get("/scan")
def scan_product(sku: str = Query(..., description="Target Product Code or Barcode ID")):
    results = query_master_catalog(sku)

    if results:
        variants = []
        for r in results:
            variants.append({
                "brand": r[0],
                "category": r[1],
                "series": r[2] or "General",
                "sku_cat_no": r[3],
                "finish_code": r[4],
                "finish_name": r[5],
                "mrp_inr": f"₹{float(r[6]):,.2f}",
                "description": r[7] or "",
                "page_no": r[8],
                "source_catalog": r[9]
            })

        top_match = variants[0]
        log_to_google_sheet(
            brand=top_match["brand"],
            category=top_match["category"],
            series=top_match["series"],
            sku=top_match["sku_cat_no"],
            finish=top_match["finish_name"],
            mrp=top_match["mrp_inr"],
            desc=top_match["description"],
            scan_type="Camera Web Scan"
        )

        return {
            "status": "success",
            "searched_sku": sku,
            "total_variants_found": len(variants),
            "products": variants
        }
    else:
        raise HTTPException(status_code=404, detail=f"No item found matching SKU: '{sku}'")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)
