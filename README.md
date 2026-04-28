# Contact Sender — Xodim Ma'lumot Yig'ish Tizimi

Xodimlar emailiga forma linki yuboriladi. Ular ism va familiyasini kiritganda, admin emailiga to'liq bildirishnoma keladi.

## Imkoniyatlar

- Email yuborib forma linki ulashish
- Email ochilgani kuzatish (pixel tracking — public server kerak)
- Link bosilgani kuzatish
- Forma ochilgani kuzatish
- Forma to'ldirilganda **ism, familiya, IP, vaqt, brauzer** ma'lumotlari adminning emailiga keladi
- Real-time dashboard (har 4 soniyada yangilanadi)
- Har bir xodim uchun to'liq tarix
- O'chirish funksiyasi

## Texnologiyalar

- **Python 3.12** + **FastAPI**
- **SQLAlchemy** + **SQLite**
- **Jinja2** templates
- **SMTP** (Gmail App Password)

## O'rnatish

### 1. Sozlamalar

```bash
cp .env.example .env
```

`.env` faylini tahrirlang:

```env
SIM_ADMIN_KEY=your-secret-key        # admin panel paroli
SIM_SMTP_USERNAME=youremail@gmail.com
SIM_SMTP_PASSWORD=your-app-password  # Gmail App Password (bo'sh joylarsiz)
SIM_SMTP_FROM=youremail@gmail.com
```

**Gmail App Password olish:**
Google Account → Security → 2-Step Verification → App passwords → Yarating

### 2. Ishga tushirish

```bash
./run.sh
```

Brauzerda oching: `http://127.0.0.1:7777`

Admin key so'ralganda `.env` dagi `SIM_ADMIN_KEY` ni kiriting.

## Ishlatish tartibi

1. Dashboard oching
2. Xodim emailini kiriting va "Yuborish" tugmasini bosing
3. Xodim emailiga chiroyli forma linki keladi
4. Xodim linkni bosib ism/familiyasini kiritadi
5. Siz emailingizga bildirishnoma olasiz:
   - **Forma ochildi** — kim, qachon, qaysi IP dan
   - **Forma to'ldirildi** — ism, familiya, IP, vaqt, brauzer

## Internet orqali ishlatish (ngrok)

```bash
# Yangi terminal
ngrok http 7777
```

Ngrok bergan URL ni xodimlarga yuborishingiz mumkin.

## Fayllar

```
app/
  main.py      — API endpointlar
  models.py    — DB modellari
  services.py  — biznes logika
  mailer.py    — SMTP va bildirishnomalar
  config.py    — sozlamalar
  database.py  — DB ulanish
templates/
  dashboard.html   — admin panel
  landing.html     — xodim formasi
  login.html       — kirish sahifasi
  recipient_detail.html
static/
  styles.css   — premium dark dizayn
run.sh         — server ishga tushirish
reset_db.sh    — DB ni tozalash
.env.example   — sozlamalar namunasi
```
