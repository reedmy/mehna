# تفعيل الدخول عبر Google

الدخول عبر Google مبني على OAuth 2.0 + OpenID Connect مباشرة (بدون SDK)، ويحتاج فقط
`Client ID` و`Client Secret` من Google Cloud Console.

## 1) إنشاء المشروع

1. افتح <https://console.cloud.google.com/>
2. من أعلى الصفحة: **Select a project → New project**
3. الاسم: `Mehna` (أو أي اسم) → **Create**

## 2) شاشة الموافقة (OAuth consent screen)

1. **APIs & Services → OAuth consent screen**
2. اختر **External** (للتجربة) → **Create**
3. املأ:
   - App name: `مهنة`
   - User support email: بريدك
   - Developer contact: بريدك
4. **Save and continue** حتى النهاية.
5. أثناء التطوير: أضف بريدك في **Test users** (وإلا سترى `Access blocked`).
6. عندما يصبح الموقع عامًا: **Publish app** (قد تحتاج مراجعة Google للصلاحيات الحساسة؛
   نحن نطلب فقط `email` و`profile` وهما غير حساسة عادة).

## 3) إنشاء بيانات الاعتماد

1. **APIs & Services → Credentials → Create credentials → OAuth client ID**
2. Application type: **Web application**
3. الاسم: `Mehna Web`
4. **Authorized JavaScript origins** (اختياري، غير مطلوب لتدفق الخادم):
   - `http://localhost:5000`
   - `https://your-domain.com`
5. **Authorized redirect URIs** — مهم جدًا، يجب أن يطابق حرفيًا:
   - `http://localhost:5000/auth/google/callback`
   - `https://your-domain.com/auth/google/callback`
6. **Create** ثم انسخ `Client ID` و`Client Secret`.

## 4) ضع المفاتيح في `.env`

```env
GOOGLE_CLIENT_ID=1234567890-xxxxxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxx
# اختياري: ضعه فقط إذا كان النطاق العام يختلف عن نطاق الطلب
# GOOGLE_REDIRECT_URI=https://your-domain.com/auth/google/callback
```

أعد تشغيل الخادم. سيصبح زر «المتابعة عبر Google» فعّالًا، وتختفي رسالة «غير مفعّل بعد».

## 5) اختبر

1. افتح `http://localhost:5000/login`
2. اضغط **المتابعة عبر Google**
3. اختر حسابك → ستعود إلى `/dashboard/` (أو لوحة صاحب العمل إن سجّلت من صفحة أصحاب العمل)
4. أول دخول يُنشئ الحساب + الملف الشخصي تلقائيًا، ويضع `email_verified_at`.

## كيف يعمل داخليًا

```
/auth/google            → state عشوائي في الجلسة + nonce + PKCE → redirect إلى Google
/auth/google/callback   → التحقق من state (compare_digest) + nonce
                        → exchange code → access_token
                        → verify_id_token (signature, iss, audience, expiry, nonce)
                        → userinfo (sub, email, email_verified, name, picture)
                        → ربط/إنشاء المستخدم → login_user
```

- `state` يمنع CSRF على الـ callback.
- `nonce` يمنع إعادةplay للهوية (يجب match مع `session["google_nonce"]`).
- `code_challenge S256` (PKCE) يضيف طبقة أمان إضافية للمCod client.
- `verify_id_token` يتحقق من التوقيع، الصادرة، الجمهور،期限, and nonce معًا.
- الحساب المعطّل (`is_active=False`) يُرفض حتى لو جاء من Google.
- الحساب الموجود بنفس البريد يُربط تلقائيًا (`google_id`) بدل إنشاء تكرار.
- الحسابات المنشأة عبر Google تحصل على كلمة مرور عشوائية غير معروفة؛ يمكنها استخدام
  «نسيت كلمة المرور» لاحقًا لتعيين كلمة مرور.

## حل المشاكل

| الرسالة | السبب | الحل |
|---|---|---|
| `redirect_uri_mismatch` | الـ URI في Google لا يطابق الطلب | أضف `http://localhost:5000/auth/google/callback` حرفيًا |
| `Access blocked` | التطبيق في وضع Testing وبريدك ليس Test user | أضف بريدك في Test users أو انشر التطبيق |
| `انتهت صلاحية جلسة الدخول` | انتهت الجلسة أو تغيّر `state` | أعد المحاولة من الصفحة |
| الزر يقول «غير مفعّل بعد» | المفاتيح فارغة | أضف `GOOGLE_CLIENT_ID` و`GOOGLE_CLIENT_SECRET` |
| يعمل محليًا ولا يعمل على النطاق | `GOOGLE_REDIRECT_URI` غير مضبوط | اضبطه على نطاق HTTPS العام |

## ملاحظات أمنية

- لا تضع `GOOGLE_CLIENT_SECRET` في المستودع أو في JavaScript.
- استخدم HTTPS في الإنتاج (شرط Google للنطاقات العامة).
- لا تطلب صلاحيات إضافية (Gmail/Drive) — `openid email profile` تكفي.
