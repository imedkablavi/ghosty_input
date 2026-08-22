<div align="center">

<img src="assets/logo.jpg" alt="شعار Ghosty Input" width="130"/>

# Ghosty Input

**تحكم بالماوس ولوحة مفاتيح على سطح المكتب باستخدام إيماءات اليد — بالكامل محليًا**

[English](README.md) · [Türkçe](README.tr.md) · [المعمارية](docs/ARCHITECTURE.md) · [الخصوصية](PRIVACY.md)

</div>

Ghosty Input يحوّل كاميرا واحدة أو كاميرتين عاديتين إلى نظام إدخال بدون لمس. الكاميرا الأمامية تتبع اليد للتحكم بالماوس، والكاميرا العلوية الاختيارية تربط مساحة معايرة على الطاولة بلوحة مفاتيح QWERTY افتراضية.

## المزايا

- تحريك المؤشر بالسبابة اليمنى مع تنعيم للحركة
- ضم الإبهام والسبابة للنقر الأيسر
- ضم الإبهام والوسطى للنقر الأيمن
- ضم الإبهام والبنصر مع الاستمرار للسحب
- تمرير بإشارة إصبعين
- إيقاف/استئناف التحكم بعد إبقاء اليد قبضة لمدة 0.75 ثانية
- وضع كاميرا واحدة أو كاميرتين
- معايرة سطح المكتب بأربع نقاط
- لوحة مفاتيح QWERTY على سطح الطاولة مع Overlay
- اختصارات لليد اليسرى: Shift وBackspace وEnter وSpace
- حفظ الإعدادات والمعايرة محليًا
- واجهة Qt مع معاينة مباشرة للكاميرات
- اختبارات آلية وGitHub Actions
- دون Telemetry أو اتصال شبكي أثناء التشغيل

## المتطلبات

- Python 3.10 أو 3.11
- كاميرا واحدة على الأقل
- كاميرتان موصى بهما عند استخدام لوحة المفاتيح على الطاولة
- Windows أو Linux
- صلاحية الوصول إلى الكاميرا

## التشغيل من المصدر

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

## المعايرة

1. شغّل التطبيق واضغط **Start**.
2. فعّل الكاميرا العلوية المنفصلة إذا كنت تستخدم كاميرتين.
3. اضغط **Calibrate desk**.
4. اضغط على زوايا مساحة لوحة المفاتيح بالترتيب: أعلى يسار، أعلى يمين، أسفل يمين، أسفل يسار.
5. بعد الحفظ، حرّك سبابة اليد اليمنى فوق المفتاح واضمم الإبهام مع السبابة للكتابة.

## بيانات المستخدم

- Windows: `%APPDATA%\GhostyInput\config.json`
- Linux: `~/.local/share/GhostyInput/config.json`

لا يقوم التطبيق بحفظ صور الكاميرا أو النص المكتوب.

## التطوير والاختبارات

```bash
pip install -r requirements-ci.txt
ruff check .
pytest
```

## الحالة الحالية

هذه نسخة معاد بناؤها من الصفر بالاعتماد على مواصفات المشروع والصور التي بقيت في المستودع. تم تنفيذ البنية الأساسية، التتبع، الإيماءات، المعايرة، لوحة المفاتيح، الواجهة، الاختبارات وWorkflow لبناء نسخة Windows Portable. قد تحتاج قيم حساسية الإيماءات إلى ضبط حسب الكاميرا والإضاءة والمسافة.

## الدعم

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/imed_kablavi)
