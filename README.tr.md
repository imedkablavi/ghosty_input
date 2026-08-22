# Ghosty Input

**Yerel bilgisayarlı görü ile hassas el hareketi fare kontrolü ve masa yüzeyi klavyesi.**

[English](README.md) · [العربية](README.ar.md) · [Quality](docs/QUALITY.md)

0.3 sürümü, sabit demo eşikleri yerine farklı kamera sistemlerine ayarlanabilen daha kararlı bir ürün temeli oluşturur.

## Hassasiyet geliştirmeleri

- Varsayılan 1080p/30 kamera isteği; 720p, 1080p ve 1440p profilleri
- Kameranın gerçekten sağladığı çözünürlük ve FPS değerlerini canlı gösterme
- Zamansal el landmark stabilizasyonu
- Düşük hızda jitter azaltan, hızlı harekette gecikmeyi düşüren adaptif işaretçi filtresi
- Elin kameraya uzaklığından daha az etkilenen, avuç boyutuna normalize edilmiş pinch ölçümü
- Tık, sürükleme ve yazma için hysteresis
- Tuş basmadan önce kısa stabil hover süresi
- Tek pinch hareketinin birden fazla karakter üretmesini engelleyen release guard
- Komşu tuş hatalarını azaltan güvenli tuş kenar boşluğu
- Dört noktalı perspektif kalibrasyonu ve 0–100 kalite skoru
- Klavye overlay'inin kalibre edilen gerçek dörtgen içine projekte edilmesi
- Kamera ve MediaPipe işlemlerinin Qt arayüzünden ayrı thread üzerinde çalıştırılması

## Control Center

Yeni kontrol panelinde canlı kamera görüntüleri, gerçek FPS/çözünürlük, el takip güveni, kalibrasyon kalitesi, Balanced/Precision/Performance profilleri ve hassasiyet ayarları bulunur.

## Masa klavyesi

En iyi sonuç için masaya yukarıdan bakan ayrı bir kamera kullanın. Dört köşeyi sol üst → sağ üst → sağ alt → sol alt sırasıyla seçin. Klavye çizgileri fiziksel alanla hizalandıktan sonra sağ işaret parmağıyla tuşu hedefleyip başparmak + işaret parmağı pinch hareketiyle yazın.

## Kurulum

Python 3.10 veya 3.11 kullanın.

```bash
git clone https://github.com/imedkablavi/ghosty_input.git
cd ghosty_input
python -m venv .venv
```

Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

## Kalite ve gizlilik

Gerçek kamera donanımıyla yapılması gereken yayın öncesi testler için [docs/QUALITY.md](docs/QUALITY.md) dosyasına bakın. Kamera kareleri yerel bellekte işlenir; telemetry, analytics veya cloud inference bulunmaz.
