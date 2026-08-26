# Ghosty Input

**El hareketleriyle fare kontrolü ve masa yüzeyinde sanal klavye - yerel ve çevrimdışı.**

[English](README.md) · [العربية](README.ar.md)

Ghosty Input, ön kamerayı fare kontrolü için; isteğe bağlı üst kamerayı ise kalibre edilmiş masa klavyesi için kullanır.

## Özellikler

- Sağ işaret parmağıyla imleç hareketi
- Başparmak + işaret parmağı: sol tık
- Başparmak + orta parmak: sağ tık
- Başparmak + yüzük parmağı: sürükle
- İki parmak hareketiyle kaydırma
- 0,75 saniye yumruk: duraklat/devam et
- Tek veya çift kamera modu
- Dört noktalı masa kalibrasyonu
- QWERTY masa klavyesi overlay'i
- Yerel ayar saklama
- Qt masaüstü arayüzü
- Windows/Linux kaynak desteği
- Otomatik test ve Windows portable build workflow'u

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

## Masa kalibrasyonu

Uygulamayı başlatın, **Calibrate desk** düğmesine basın ve masa alanının köşelerini sırasıyla sol üst → sağ üst → sağ alt → sol alt olarak seçin. Bir tuşun üzerine sağ işaret parmağını getirip başparmak + işaret parmağı pinch hareketiyle tuşa basın.

## Gizlilik

Kamera kareleri bellekte yerel olarak işlenir. Uygulamada telemetry, analytics veya cloud API bulunmaz. Ayrıntılar için [PRIVACY.md](PRIVACY.md).
