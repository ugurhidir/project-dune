from DrissionPage import ChromiumPage, ChromiumOptions
import sqlite3
import time
import random

DB_NAME = "dubai_property.db"
BASE_URL = "https://www.propertyfinder.ae/en/buy/properties-for-sale.html"

# --- SQLite WAL Ayarı ---
def enable_wal_mode():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;") # Ekstra hız katar
    conn.close()

# --- Hafıza ---
def load_existing_data():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, price FROM listings")
    data = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return data

# --- Toplu Güncelleme ---
def update_seen_date(conn, ids_to_update):
    if not ids_to_update: return
    cursor = conn.cursor()
    cursor.executemany("UPDATE listings SET last_seen_date = CURRENT_TIMESTAMP WHERE id = ?", 
                       [(i,) for i in ids_to_update])

# --- Veri Kaydı (ARTIK BAĞLANTIYI DIŞARIDAN ALIYOR) ---
def save_listing_batch(conn, item, old_price=None):
    cursor = conn.cursor()
    
    if old_price is not None:
        print(f"   📉 FİYAT DEĞİŞİMİ! ID: {item['id']} | {old_price} -> {item['price']}")
        cursor.execute("INSERT INTO price_logs (listing_id, old_price, new_price) VALUES (?, ?, ?)", 
                       (item['id'], old_price, item['price']))
        cursor.execute("UPDATE listings SET price = ?, last_seen_date = CURRENT_TIMESTAMP WHERE id = ?", 
                       (item['price'], item['id']))
    else:
        print(f"   ➕ Yeni: {item['title'][:25]}... ({item['price']})")
        cursor.execute("""
            INSERT INTO listings (id, title, price, location, bedrooms, bathrooms, area_sqft, link)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (item['id'], item['title'], item['price'], item['location'], item['bedrooms'], item['bathrooms'], item['area'], item['link']))

def generate_price_ranges():
    ranges = []
    for i in range(0, 5000000, 250000): ranges.append((i, i + 250000))
    for i in range(5000000, 20000000, 1000000): ranges.append((i, i + 1000000))
    ranges.append((20000000, 500000000))
    return ranges

def main():
    enable_wal_mode()
    print("🧠 Veritabanı RAM'e yükleniyor...")
    db_cache = load_existing_data()
    print(f"🧠 {len(db_cache)} kayıt hafızaya alındı.")

    co = ChromiumOptions()
    co.set_argument('--blink-settings=imagesEnabled=false')
    # co.set_argument('--window-position=-10000,-10000') 
    
    page = ChromiumPage(co)
    price_ranges = generate_price_ranges()
    
    script_start_time = time.time()
    total_processed = 0

    # Veritabanı bağlantısını tek bir yerde yönetelim (Döngü içinde aç kapa yapmayalım)
    # Ancak SQLite uzun süre açık kalınca da şişebilir, SAYFA BAŞINA bir bağlantı en güvenlisidir.

    for start_price, end_price in price_ranges:
        print(f"\n💰 Segment: {start_price:,} - {end_price:,} AED")
        
        for page_num in range(1, 101):
            page_start_time = time.time()
            
            # --- BAĞLANTIYI AÇ (Sayfa Başına 1 Kere) ---
            conn = sqlite3.connect(DB_NAME)
            
            url = f"{BASE_URL}?pf={start_price}&pt={end_price}&page={page_num}"
            page.get(url)
            
            if page.wait.ele_displayed("@data-testid=property-card", timeout=10):
                cards = page.eles("@data-testid=property-card")
                card_count = len(cards)
                total_processed += card_count
                
                skipped_ids = []
                process_start = time.time()

                for card in cards:
                    try:
                        # ... (Veri çekme işlemleri aynı) ...
                        link_ele = card.ele("tag:a")
                        link = link_ele.attr("href")
                        ilan_id = link.split("-")[-1].replace(".html", "")
                        
                        price_text = card.ele("@data-testid=property-card-price").text
                        if "Ask for" in price_text or "Call" in price_text:
                            price = -1
                        else:
                            price = int(price_text.replace(",", "").replace("AED", "").strip())

                        old_price_val = None
                        if ilan_id in db_cache:
                            if db_cache[ilan_id] == price:
                                skipped_ids.append(ilan_id)
                                continue 
                            else:
                                old_price_val = db_cache[ilan_id]

                        # Detayları çek
                        title = link_ele.attr("title") or card.ele("tag:h2").text.strip()
                        
                        bed_ele = card.ele("@data-testid=property-card-spec-bedroom")
                        beds = bed_ele.text.strip() if bed_ele else "0"

                        bath_ele = card.ele("@data-testid=property-card-spec-bathroom")
                        baths = bath_ele.text.strip() if bath_ele else "0"

                        area_ele = card.ele("@data-testid=property-card-spec-area")
                        area = area_ele.text.replace("sqft", "").replace(",", "").strip() if area_ele else "0"

                        loc_ele = card.ele("@data-testid=property-card-location")
                        location = loc_ele.text.strip() if loc_ele else "Dubai"

                        item = {
                            "id": ilan_id, "title": title, "price": price,
                            "location": location, "bedrooms": beds, "bathrooms": baths,
                            "area": area, "link": link
                        }
                        
                        # KAYIT (Cursor'ı gönderiyoruz, commit yapmıyoruz)
                        save_listing_batch(conn, item, old_price=old_price_val)

                    except Exception as e:
                        continue
                
                # Skipped olanları güncelle
                if skipped_ids:
                    update_seen_date(conn, skipped_ids)
                
                # --- SAYFA SONU: TOPLU COMMIT ve KAPATMA ---
                conn.commit()
                conn.close() 
                # -------------------------------------------

                process_end = time.time()
                process_duration = process_end - process_start
                avg_per_card = process_duration / card_count if card_count > 0 else 0
                
                sleep_time = random.uniform(2, 3)
                time.sleep(sleep_time)
                
                total_page_duration = time.time() - page_start_time
                print(f"✅ Sayfa {page_num} | İlan: {card_count} | İşlem: {process_duration:.2f}s | Hız: {avg_per_card:.4f}s/ilan")

            else:
                conn.close() # Hata olursa kapatmayı unutma
                print(f"🚫 Segment bitti.")
                break

    page.quit()

if __name__ == "__main__":
    main()