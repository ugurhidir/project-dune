from DrissionPage import ChromiumPage, ChromiumOptions
from bs4 import BeautifulSoup # HIZIN KAYNAĞI
import sqlite3
import time
import random

DB_NAME = "dubai_property.db"
BASE_URL = "https://www.propertyfinder.ae/en/buy/properties-for-sale.html"

# --- SQLite WAL Ayarı ---
def enable_wal_mode():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.close()

# --- Hafıza ---
def load_existing_data():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, price FROM listings")
    data = {str(row[0]): row[1] for row in cursor.fetchall()} # ID'leri string yapalım garanti olsun
    conn.close()
    return data

# --- Toplu Güncelleme ---
def update_seen_date(conn, ids_to_update):
    if not ids_to_update: return
    cursor = conn.cursor()
    cursor.executemany("UPDATE listings SET last_seen_date = CURRENT_TIMESTAMP WHERE id = ?", 
                       [(i,) for i in ids_to_update])

# --- Veri Kaydı ---
def save_listing_batch(conn, item, old_price=None):
    cursor = conn.cursor()
    
    if old_price is not None:
        print(f"   📉 FİYAT DEĞİŞİMİ! ID: {item['id']} | {old_price} -> {item['price']}")
        cursor.execute("INSERT INTO price_logs (listing_id, old_price, new_price) VALUES (?, ?, ?)", 
                       (item['id'], old_price, item['price']))
        cursor.execute("UPDATE listings SET price = ?, last_seen_date = CURRENT_TIMESTAMP WHERE id = ?", 
                       (item['price'], item['id']))
    else:
        # Terminali çok kirletmemek için sadece ID yazalım
        # print(f"   ➕ Yeni: {item['id']}") 
        cursor.execute("""
            INSERT INTO listings (id, title, price, location, bedrooms, bathrooms, area_sqft, link)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (item['id'], item['title'], item['price'], item['location'], item['bedrooms'], item['bathrooms'], item['area'], item['link']))

def generate_price_ranges():
    ranges = []
    # 0-5M arası 250k (Yoğun)
    for i in range(0, 5000000, 250000): ranges.append((i, i + 250000))
    # 5M-20M arası 1M
    for i in range(5000000, 20000000, 1000000): ranges.append((i, i + 1000000))
    # 20M+ (Geniş)
    ranges.append((20000000, 500000000))
    return ranges

def main():
    enable_wal_mode()
    print("🧠 Veritabanı RAM'e yükleniyor...")
    db_cache = load_existing_data()
    print(f"🧠 {len(db_cache)} kayıt hafızaya alındı.")

    co = ChromiumOptions()
    co.set_argument('--blink-settings=imagesEnabled=false')
    # co.set_argument('--window-position=-10000,-10000') # Ninja Modu (İstersen aç)
    
    page = ChromiumPage(co)
    price_ranges = generate_price_ranges()
    
    script_start_time = time.time()
    total_processed = 0

    for start_price, end_price in price_ranges:
        print(f"\n💰 Segment: {start_price:,} - {end_price:,} AED")
        
        for page_num in range(1, 999):
            page_start_time = time.time()
            conn = sqlite3.connect(DB_NAME)
            
            url = f"{BASE_URL}?pf={start_price}&pt={end_price}&page={page_num}"
            page.get(url)
            
            # Sayfanın yüklenmesini bekle (DrissionPage ile)
            if page.wait.ele_displayed("@data-testid=property-card", timeout=10):
                
                # --- HIZ DEVRİMİ BURADA ---
                # Sayfa kaynağını (HTML) alıp BeautifulSoup'a veriyoruz.
                # Artık tarayıcıyla işimiz bitti.
                soup = BeautifulSoup(page.html, "html.parser")
                
                # Kartları bul (BS4 Syntax)
                cards = soup.find_all("article", attrs={"data-testid": "property-card"})
                card_count = len(cards)
                total_processed += card_count
                
                skipped_ids = []
                process_start = time.time()

                for card in cards:
                    try:
                        # BS4 ile veri çekme (Çok daha hızlı)
                        
                        # Link ve ID
                        link_tag = card.find("a", href=True)
                        link = link_tag["href"]
                        ilan_id = link.split("-")[-1].replace(".html", "")
                        
                        # Fiyat
                        price_tag = card.find(attrs={"data-testid": "property-card-price"})
                        price_text = price_tag.text if price_tag else "0"
                        
                        if "Ask for" in price_text or "Call" in price_text:
                            price = -1
                        else:
                            price = int(price_text.replace(",", "").replace("AED", "").strip())

                        # Cache Kontrolü
                        old_price_val = None
                        if ilan_id in db_cache:
                            if db_cache[ilan_id] == price:
                                skipped_ids.append(ilan_id)
                                continue 
                            else:
                                old_price_val = db_cache[ilan_id]

                        # Diğer Detaylar (Sadece yeni/değişenler için çalışır)
                        title = link_tag.get("title")
                        if not title: 
                            h2_tag = card.find("h2")
                            title = h2_tag.text.strip() if h2_tag else "Başlık Yok"

                        bed_tag = card.find(attrs={"data-testid": "property-card-spec-bedroom"})
                        beds = bed_tag.text.strip() if bed_tag else "0"

                        bath_tag = card.find(attrs={"data-testid": "property-card-spec-bathroom"})
                        baths = bath_tag.text.strip() if bath_tag else "0"

                        area_tag = card.find(attrs={"data-testid": "property-card-spec-area"})
                        area = area_tag.text.replace("sqft", "").replace(",", "").strip() if area_tag else "0"

                        loc_tag = card.find(attrs={"data-testid": "property-card-location"})
                        location = loc_tag.text.strip() if loc_tag else "Dubai"

                        item = {
                            "id": ilan_id, "title": title, "price": price,
                            "location": location, "bedrooms": beds, "bathrooms": baths,
                            "area": area, "link": link
                        }
                        
                        save_listing_batch(conn, item, old_price=old_price_val)
                        
                        # Yeni eklenenleri de cache'e ekleyelim ki sonraki sayfalarda (varsa) tekrar uğraşmayalım
                        db_cache[ilan_id] = price

                    except Exception as e:
                        # print(f"Hata: {e}")
                        continue
                
                if skipped_ids:
                    update_seen_date(conn, skipped_ids)
                
                conn.commit()
                conn.close() 

                process_end = time.time()
                process_duration = process_end - process_start
                avg_per_card = process_duration / card_count if card_count > 0 else 0
                
                sleep_time = random.uniform(1.5, 2.5) # Beklemeyi biraz azalttık
                time.sleep(sleep_time)
                
                total_page_duration = time.time() - page_start_time
                
                # Yeni/Değişen varsa belirtelim
                new_count = card_count - len(skipped_ids)
                status_msg = f"(+{new_count} Yeni)" if new_count > 0 else "(Hepsi Eski)"
                
                print(f"✅ Sayfa {page_num} | İlan: {card_count} {status_msg} | İşlem: {process_duration:.2f}s | Toplam: {total_page_duration:.2f}s")

            else:
                conn.close()
                print(f"🚫 Segment bitti (Sayfa {page_num} boş).")
                break

    page.quit()

if __name__ == "__main__":
    main()