from DrissionPage import ChromiumPage, ChromiumOptions
import sqlite3
import time
import random

# --- AYARLAR ---
DB_NAME = "dubai_property.db"
# Dubai - Satılık (Örnek URL, kiralık için /rent/ yapabilirsin)
BASE_URL = "https://www.propertyfinder.ae/en/buy/properties-for-sale.html"

def save_listing(data):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT price FROM listings WHERE id = ?", (data['id'],))
    existing = cursor.fetchone()

    if existing:
        old_price = existing[0]
        if old_price != data['price']:
            print(f"📉 FİYAT DEĞİŞİMİ! ID: {data['id']} | {old_price} -> {data['price']}")
            cursor.execute("INSERT INTO price_logs (listing_id, old_price, new_price) VALUES (?, ?, ?)", 
                           (data['id'], old_price, data['price']))
            cursor.execute("UPDATE listings SET price = ?, last_seen_date = CURRENT_TIMESTAMP WHERE id = ?", 
                           (data['price'], data['id']))
        else:
            cursor.execute("UPDATE listings SET last_seen_date = CURRENT_TIMESTAMP WHERE id = ?", (data['id'],))
            
    else:
        print(f"➕ Yeni İlan: {data['title'][:30]}... ({data['price']} AED)")
        cursor.execute("""
            INSERT INTO listings (id, title, price, location, bedrooms, bathrooms, area_sqft, link)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (data['id'], data['title'], data['price'], data['location'], data['bedrooms'], data['bathrooms'], data['area'], data['link']))

    conn.commit()
    conn.close()

def main():
    co = ChromiumOptions()
    # Resimleri kapat (Hız için)
    co.set_argument('--blink-settings=imagesEnabled=false')
    
    # Ninja Modu (Ekran dışı) - Test ederken kapalı tutabilirsin
    # co.set_argument('--window-position=-10000,-10000') 
    
    page = ChromiumPage(co)
    print("🌍 Property Finder Dubai'ye bağlanılıyor...")

    # İlk 3 sayfayı test edelim
    for page_num in range(1, 51):
        url = f"{BASE_URL}?page={page_num}"
        print(f"\n🔄 Sayfa {page_num} taranıyor...")
        
        page.get(url)
        
        # Kartların yüklenmesini bekle (data-testid='property-card' olan article'lar)
        if page.wait.ele_displayed("@data-testid=property-card", timeout=15):
            
            # Tüm kartları bul
            cards = page.eles("@data-testid=property-card")
            print(f"   📊 {len(cards)} ilan bulundu. Veriler işleniyor...")

            for card in cards:
                try:
                    # --- 1. Link Elementini Al ---
                    # Bu satır zaten çalışıyor, başlığı da buradan alacağız
                    link_ele = card.ele("tag:a")
                    link = link_ele.attr("href")
                    
                    # ID Çıkarma
                    ilan_id = link.split("-")[-1].replace(".html", "")

                    # --- 2. Başlık (DÜZELTME) ---
                    # h2 aramak yerine, link elementinin "title" özelliğini veya "aria-label"ını alıyoruz.
                    # Bu %100 garantidir.
                    title = link_ele.attr("title")
                    
                    # Eğer title boşsa (bazen olur), h2'yi veya linkin metnini deneyelim
                    if not title:
                        h2_ele = card.ele("tag:h2")
                        if h2_ele:
                            title = h2_ele.text.strip()
                        else:
                            title = link_ele.text.strip() # En son çare linkin içindeki yazı

                    # --- 3. Fiyat Temizleme ---
                    price_text = card.ele("@data-testid=property-card-price").text
                    
                    # Eğer "Ask for price" içeriyorsa
                    if "Ask for price" in price_text or "Call" in price_text:
                        price = -1 # Gizli Fiyat Kodu
                    else:
                        # Sadece rakamları al
                        price = int(price_text.replace(",", "").replace("AED", "").strip())

                    # --- 4. Diğer Özellikler ---
                    bed_ele = card.ele("@data-testid=property-card-spec-bedroom")
                    beds = bed_ele.text.strip() if bed_ele else "0"

                    bath_ele = card.ele("@data-testid=property-card-spec-bathroom")
                    baths = bath_ele.text.strip() if bath_ele else "0"

                    area_ele = card.ele("@data-testid=property-card-spec-area")
                    area = area_ele.text.replace("sqft", "").replace(",", "").strip() if area_ele else "0"

                    # Location
                    loc_ele = card.ele("@data-testid=property-card-location")
                    location = loc_ele.text.strip() if loc_ele else "Dubai"

                    # Veri Paketi
                    item = {
                        "id": ilan_id,
                        "title": title,
                        "price": price,
                        "location": location,
                        "bedrooms": beds,
                        "bathrooms": baths,
                        "area": area,
                        "link": link
                    }
                    
                    save_listing(item)
                    
                except Exception as e:
                    print(f"   ⚠️ Kart işlenirken hata: {e}")
                    continue
            
            # İnsan gibi bekle
            time.sleep(random.uniform(2, 4))
            
        else:
            print("❌ İlanlar bulunamadı. Cloudflare engeli olabilir.")
            break

    print("\n🏁 Operasyon Tamamlandı.")
    page.quit()

if __name__ == "__main__":
    main()