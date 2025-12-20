<div align="center">

<img src="assets/logo.jpg" alt="Ghosty Input Logo" width="140"/>

# Ghosty Input

**التحكم بالماوس ولوحة مفاتيح على الطاولة باستخدام إيماءات اليد**

نظام تتبع يد محلي يعمل دون إنترنت للتحكم بالماوس والكتابة على سطح المكتب باستخدام الرؤية الحاسوبية.

[الموقع](https://imedkablavi.info) ·
[الإصدارات](https://github.com/imedkablavi/ghosty_input/releases) ·
[المشاكل](https://github.com/imedkablavi/ghosty_input/issues) ·
[التوثيق](docs/)

<br/>

<img src="https://img.shields.io/github/v/release/imedkablavi/ghosty_input?label=release"/>
<img src="https://img.shields.io/github/license/imedkablavi/ghosty_input"/>
<img src="https://img.shields.io/github/issues/imedkablavi/ghosty_input"/>
<img src="https://img.shields.io/github/stars/imedkablavi/ghosty_input"/>
<img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey"/>
<img src="https://img.shields.io/badge/python-3.10%20%7C%203.11-blue"/>

<br/><br/>

**اللغة**  
[English](README.md) · [العربية](README.ar.md) · [Türkçe](README.tr.md)

</div>

---

## نظرة عامة

**Ghosty Input** هو تطبيق سطح مكتب يتيح التحكم بالماوس والكتابة على لوحة مفاتيح افتراضية موضوعة على الطاولة باستخدام إيماءات اليد.

- الكاميرا الأمامية للتحكم بالماوس  
- الكاميرا العلوية لمعايرة لوحة المفاتيح  
- دعم وضع كاميرا واحدة أو كاميرتين  
- كل المعالجة محلية دون اتصال بالإنترنت  

---

## المزايا

- بنية بكاميرتين  
  - كاميرا أمامية → ماوس  
  - كاميرا علوية → لوحة مفاتيح
- وضع كاميرا واحدة تلقائي عند الحاجة
- معايرة سطح الطاولة باستخدام 4 نقاط
- التحكم بالماوس عبر الإيماءات (تحريك، نقر، سحب، تمرير، إيقاف)
- لوحة مفاتيح افتراضية اختيارية
- مفاتيح مساعدة باليد اليسرى (مسافة، حذف، شِفت، إدخال)
- إعدادات وملفات مستخدم محفوظة محليًا

---

## دليل الإيماءات

<div align="center">
  <img src="assets/screenshots/gesture-guide.png" width="100%"/>
</div>

**ملاحظات**
- الكاميرا الأمامية مسؤولة عن الماوس
- الكاميرا العلوية مسؤولة عن لوحة المفاتيح
- الكتابة تتطلب إجراء المعايرة أولًا

---

## صور من التطبيق

### الواجهة الرئيسية
<div align="center">
  <img src="assets/screenshots/dashboard.png" width="100%"/>
</div>


### لوحة المفاتيح الافتراضية
<div align="center">
  <img src="assets/screenshots/keyboard-overlay.png" width="100%"/>
</div>

---

## التثبيت

### للمستخدمين (موصى به)

#### مثبت ويندوز
1. انتقل إلى صفحة **Releases**
2. حمّل **GhostyInputSetup.exe**
3. ثبّت وشغّل التطبيق

لا حاجة لبايثون أو أدوات تطوير.

#### نسخة محمولة
- حمّل ملف ZIP
- فك الضغط وشغّل `GhostyInput.exe`

---

### للمطورين

```bash
git clone https://github.com/imedkablavi/ghosty_input.git
cd ghosty_input
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
يتطلب Python 3.10 أو 3.11.

أوضاع الكاميرا
كاميرا واحدة: بث مشترك للماوس ولوحة المفاتيح

كاميرتان: أمامية للماوس، علوية للوحة المفاتيح

اختفاء المعاينة الثانية أمر طبيعي في وضع الكاميرا الواحدة.

الملفات والسجلات
Windows: %APPDATA%\GhostyInput

Linux: ~/.local/share/GhostyInput

استكشاف الأخطاء
شاشة سوداء: تحقق من رقم الكاميرا أو أذونات الخصوصية

لوحة المفاتيح لا تعمل: تأكد من إجراء المعايرة

أخطاء MediaPipe: استخدم Python 3.10 أو 3.11 فقط

الخصوصية
يعمل Ghosty Input دون اتصال بالإنترنت.
لا يتم إرسال أو تخزين أي بيانات.

```


  ## 💰 You can help me by Donating
  [![BuyMeACoffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/imed_kablavi) 
