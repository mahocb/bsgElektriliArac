# EV Charge Station — WebSocket Anomaly Demo

**İki parça:**

- `server.py` → Şarj Yönetim Sistemi (CSMS). WebSocket sunucu.
- `station.py` → Şarj İstasyonu simülatörü (istemci).
- `rules.py` → Basit kural tabanlı anomali tespiti.
- `requirements.txt` → Gerekli paketler.

## Çalıştırma

```bash
# 1) Sanal ortam (isteğe bağlı)
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2) Gerekli paketler
pip install -r requirements.txt

# 3) Sunucuyu başlat
python server.py

# 4) Başka bir terminalde istasyonu çalıştır (normal)
python station.py --scenario normal

# Farklı senaryolar:
python station.py --scenario power_spike
python station.py --scenario non_monotonic_energy
python station.py --scenario timestamp_drift
python station.py --scenario weak_encryption
python station.py --scenario unauthorized
python station.py --scenario firmware_mismatch
```

## Ne oluyor?
- İstasyon, her 2–3 saniyede **voltaj / akım / güç / kWh / sıcaklık** gönderir.
- Sunucu `rules.py` içindeki kurallarla veriyi kontrol eder.
- Anomali yakalanırsa **STOP_CHARGE** komutu gönderir ve oturumu sonlandırır.

## Notlar

  - Zayıf şifreleme (weak_encryption)
  - Yetkisiz erişim (unauthorized)
  - MitM benzeri zaman/sıra tutarsızlığı (timestamp_drift)
  - Sahte veri/enerji hırsızlığı (power_spike, non_monotonic_energy)
  - Firmware/versiyon uyumsuzluğu (firmware_mismatch)

