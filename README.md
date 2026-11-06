# مهنة — منصة التوظيف العراقية (v2)

نسخة مُعاد بناؤها بالكامل من مشروع «مهنة»، بنفس الهوية البصرية والشعار، مع بنية كود
أوضح وأكثر أمانًا وقابلية للتوسّع. تعمل بدون JavaScript إلزامي، بواجهة عربية RTL
خفيفة على شبكات 4G.

- **الخلفية:** Flask 3 + SQLAlchemy 2 + Alembic
- **الواجهة:** Jinja2 (SSR) + HTMX + CSS Design System
- **قاعدة البيانات:** SQLite للتطوير، PostgreSQL للإنتاج
- **الاختبارات:** 40 اختبارًا (pytest) — كلها ناجحة

---

## التشغيل السريع (Windows)

```powershell
cd C:\Users\pc\Desktop\mehna-v2
.\.venv\Scripts\Activate.ps1        # أو استخدم .\.venv\Scripts\python.exe مباشرة
pip install -r requirements-dev.txt

copy .env.example .env              # ثم عدّل SECRET_KEY
flask --app run.py db upgrade       # إنشاء/تحديث الجداول
flask --app run.py seed             # بيانات تجريبية (اختياري)

python run.py                       # http://127.0.0.1:5000
```

> ملف `.env` الحالي جاهز للتطوير ومزوّد بـ `SECRET_KEY` عشوائي.

### الحسابات التجريبية

| الدور | البريد | كلمة المرور |
|---|---|---|
| باحث عن عمل | `seeker@mehna.iq` | `Seeker@1234` |
| صاحب عمل | `hr@rafidain-tech.iq` | `Employer@1234` |
| مسؤول النظام | `admin@mehna.iq` | `Admin@1234` |

صفحة الدخول فيها **دخول سريع بضغطة** لهذه الحسابات (زر واحد لكل دور) — مناسب للتجربة
والعرض. هذا الخيار يُعطَّل تلقائيًا في الإنتاج (`ProductionConfig.DEMO_ACCOUNTS = []`).

---

## الدخول عبر Google

الزر موجود في صفحتي الدخول والتسجيل، ويعمل بمجرد إضافة المفاتيح:

```env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
# اختياري — يُشتق تلقائيًا من الطلب إن تُرك فارغًا
GOOGLE_REDIRECT_URI=
```

خطوات الحصول على المفاتيح (٥ دقائق) مشروحة في [`docs/GOOGLE_LOGIN.md`](docs/GOOGLE_LOGIN.md).

عند أول دخول عبر Google يُنشأ الحساب تلقائيًا (باحث عن عمل افتراضيًا، أو صاحب عمل إذا
جاء من صفحة تسجيل أصحاب العمل)، ويُربط لاحقًا بأي حساب موجود بنفس البريد.

---

## البنية

```
app/
  __init__.py          مصنع التطبيق، الأخطاء، الفلاتر، الهيدرز الأمنية
  config.py            إعدادات البيئة + قواعد العمل + حسابات التجربة
  extensions.py        db / migrate / login_manager / csrf / limiter
  cli.py               seed / create-admin / expire-jobs
  models/              User, Profile, Company, Job, Application, SavedJob, ...
  services/            منطق العمل والتحقق من الملكية (auth, jobs, applications, google_auth)
  routes/              public, auth, seeker, employer, admin, api (واجهات رقيقة)
  templates/           base + admin_base + components + pages
  static/css/          tokens.css (الهوية) + app.css + admin.css
  static/js/app.js     القوائم، CSRF لـ HTMX، حماية الإرسال المزدوج
  utils/               تطبيع العربية، الأمان، التنسيق، الديكوريتورز
migrations/            Alembic (لا يوجد db.create_all في الإنتاج)
tests/                 40 اختبارًا
```

تفاصيل أعمق: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — الهوية البصرية:
[`docs/DESIGN.md`](docs/DESIGN.md) — الخطة القادمة: [`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## الأوامر

```bash
flask --app run.py seed              # بيانات تجريبية كاملة
flask --app run.py create-admin      # إنشاء مسؤول من متغيرات البيئة
flask --app run.py expire-jobs       # إغلاق الوظائف المنتهية (Cron يوميًا)
flask --app run.py db upgrade        # تطبيق المخططات
python -m pytest -q                  # الاختبارات
ruff check . && ruff format --check . # الجودة والتنسيق
```

## النشر

```bash
docker compose up --build
```

أو يدويًا على أي خادم Linux:

```bash
pip install -r requirements.txt
flask --app wsgi.py db upgrade
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

لا تنسَ في الإنتاج:

- `SECRET_KEY` طويل وعشوائي
- `DATABASE_URL` لـ PostgreSQL + `psycopg2-binary`
- `SESSION_COOKIE_SECURE=true`
- `GOOGLE_REDIRECT_URI` للنطاق العام
- `DEMO_ACCOUNTS` فارغة (مضبوطة افتراضيًا)

## الأمان

- كل إجراء يغيّر الحالة = POST + CSRF، والملكية تُفحص في الخدمة لا في المسار فقط.
- `is_active` يُفحص عند الدخول (عادي وGoogle) — الحسابات المعطّلة لا تدخل.
- جلسة جديدة عند الدخول/الخروج، وحماية جلسة Flask-Login بوضع `strong`.
- حدود معدّل على الدخول وإعادة التعيين والدخول عبر Google.
- لا كلمات مرور في السجلات، ولا تعداد للحسابات في «نسيت كلمة المرور».
- ملفات CV مستقبلًا: تحقق نوع/حجم + تخزين خارج الويب روت.

## الترخيص

خاص — جميع الحقوق محفوظة.
