from fastapi import FastAPI, Query, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import pytesseract
from PIL import Image
import io
import re
import requests

app = FastAPI(title="Cloud Product Scanner API with Category Logger")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Replace with your deployed Google Apps Script Web App URL
GOOGLE_SHEET_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyNBzXCgogYweXJk6UH40hnvGe_cQ4GVjzLthLkYj0SZ4J3aUTo_W-fZ18K2JDx08s4/exec"

def query_db_sku(clean_sku):
    conn = sqlite3.connect("master_products.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT brand, category, sku_cat_no, mrp_inr, description, page_no, source_file 
        FROM products 
        WHERE UPPER(sku_cat_no) = ? OR UPPER(sku_cat_no) LIKE ?
    """, (clean_sku, f"%{clean_sku}%"))
    results = cursor.fetchall()
    conn.close()
    return results

def log_to_google_sheet(brand, category, sku, mrp, desc, scan_type="Phone Photo"):
    if "YOUR_COPIED" not in GOOGLE_SHEET_WEBHOOK_URL:
        try:
            requests.post(GOOGLE_SHEET_WEBHOOK_URL, json={
                "brand": brand,
                "category": category,
                "sku": sku,
                "mrp": mrp,
                "description": desc,
                "scan_type": scan_type
            }, timeout=3)
        except Exception as e:
            print("Google Sheet Logging Error:", e)

@app.get("/scan")
def scan_text_sku(sku: str = Query(...)):
    clean_sku = sku.strip().upper()
    results = query_db_sku(clean_sku)
    
    if results:
        items = []
        for r in results:
            brand_name = r[0]
            cat_name = r[1]
            sku_code = r[2]
            mrp_formatted = f"₹{r[3]:,.2f}"
            description_text = r[4]
            page_number = r[5]
            catalog_file = r[6]
            
            items.append({
                "brand": brand_name,
                "category": cat_name,
                "sku_cat_no": sku_code,
                "mrp_inr": mrp_formatted,
                "description": description_text,
                "page_no": page_number,
                "source_catalog": catalog_file
            })
            
            # Log to Google Sheet with Category
            log_to_google_sheet(brand_name, cat_name, sku_code, mrp_formatted, description_text, "Manual Text Scan")
            
        return {"status": "success", "products": items}
    else:
        raise HTTPException(status_code=404, detail=f"No item found for '{sku}'")

@app.post("/scan-image")
async def scan_uploaded_image(file: UploadFile = File(...)):
    contents = await file.read()
    image = Image.open(io.BytesIO(contents))
    
    # Run OCR on the image
    ocr_text = pytesseract.image_to_string(image)
    
    # Extract candidate SKU patterns (e.g. AEC-1111N, S1013265VS, F1021451FG)
    sku_pattern = re.compile(r'\b([A-Z0-9]{2,5}-[A-Z0-9-]{3,18}|[SFEABSP][0-9]{7,8}[A-Z0-9]*)\b', re.IGNORECASE)
    matches = sku_pattern.findall(ocr_text)
    
    for candidate in matches:
        clean_candidate = candidate.strip().upper()
        results = query_db_sku(clean_candidate)
        if results:
            r = results[0]
            brand_name = r[0]
            cat_name = r[1]
            sku_code = r[2]
            mrp_formatted = f"₹{r[3]:,.2f}"
            description_text = r[4]
            page_number = r[5]
            catalog_file = r[6]
            
            # Log to Google Sheet with Category
            log_to_google_sheet(brand_name, cat_name, sku_code, mrp_formatted, description_text, "Camera Photo OCR")
            
            return {
                "status": "success",
                "detected_sku": clean_candidate,
                "products": [{
                    "brand": brand_name,
                    "category": cat_name,
                    "sku_cat_no": sku_code,
                    "mrp_inr": mrp_formatted,
                    "description": description_text,
                    "page_no": page_number,
                    "source_catalog": catalog_file
                }]
            }
            
    raise HTTPException(status_code=404, detail="No matching SKU detected in photo.")