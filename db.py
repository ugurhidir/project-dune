import sqlite3

DB_NAME = "dubai_property.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. GÜNCEL İLANLAR TABLOSU (Listings)
    # Bir ilanın en son durumu burada durur.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS listings (
        id TEXT PRIMARY KEY,              -- İlan ID (Site ID'si)
        title TEXT,                       -- Başlık
        price REAL,                       -- Fiyat (AED)
        location TEXT,                    -- Konum (Dubai Marina, vs.)
        bedrooms TEXT,                    -- Oda Sayısı
        bathrooms TEXT,                   -- Banyo Sayısı
        area_sqft REAL,                   -- Alan (SqFt)
        link TEXT,                        -- İlan Linki
        agent_name TEXT,                  -- Emlakçı Adı
        listing_type TEXT,                -- Buy / Rent
        
        -- Meta Veriler
        first_seen_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- İlk ne zaman gördük?
        last_seen_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- En son ne zaman gördük?
        is_active BOOLEAN DEFAULT 1       -- İlan yayında mı?
    )
    """)

    # 2. FİYAT GEÇMİŞİ TABLOSU (Price History)
    # Para eden tablo budur. Fiyat değiştiği an buraya satır atacağız.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS price_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id TEXT,
        old_price REAL,
        new_price REAL,
        change_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(listing_id) REFERENCES listings(id)
    )
    """)

    conn.commit()
    conn.close()
    print(f"✅ Veritabanı ({DB_NAME}) ve Tablolar hazır!")

if __name__ == "__main__":
    init_db()