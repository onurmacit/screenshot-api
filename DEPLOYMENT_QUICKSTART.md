# 🚀 Quick Start - DigitalOcean Deployment

**Domain:** screenshotbeam.com  
**Platform:** DigitalOcean App Platform

---

## ⚡ 5 Dakikada Başlangıç

### 1. DigitalOcean Spaces (S3 Storage)
```bash
1. Dashboard → Spaces → Create Space
   - Name: screenshotbeam
   - Region: NYC3
   - CDN: Enable
2. API → Spaces Keys → Generate New Key
3. Settings → CORS → Add Rule (see DEPLOYMENT_DIGITALOCEAN.md)
```

### 2. Managed PostgreSQL
```bash
1. Dashboard → Databases → Create Database
   - Engine: PostgreSQL 15
   - Plan: Basic ($15/month)
   - Region: NYC3
2. Copy connection string
```

### 3. Managed Redis
```bash
1. Dashboard → Databases → Create Database
   - Engine: Redis 7
   - Plan: Basic ($15/month)
   - Region: NYC3
2. Copy connection string
```

### 4. App Platform Deployment
```bash
1. Dashboard → App Platform → Create App
2. Connect GitHub: onurmacit/screenshot-api
3. Use app.yaml: .do/app.yaml
4. Add Environment Variables (see .env.production.example)
5. Deploy!
```

### 5. Domain Setup (Güzelhosting)
```bash
1. Güzelhosting DNS Panel:
   - A Record: @ → [App Platform IP]
   - CNAME: api → [App Platform Domain]
2. App Platform → Settings → Domains:
   - Add: screenshotbeam.com
   - Add: api.screenshotbeam.com
```

---

## 📋 Environment Variables (Kritik!)

**Tüm secret'ları "Encrypted" olarak ekle!**

### Zorunlu Variables:
- `SECRET_KEY` (openssl rand -hex 32)
- `DATABASE_URL` (Managed PostgreSQL)
- `REDIS_URL` (Managed Redis)
- `CELERY_BROKER_URL` (Redis)
- `CELERY_RESULT_BACKEND` (Redis)
- `AWS_ACCESS_KEY_ID` (Spaces)
- `AWS_SECRET_ACCESS_KEY` (Spaces)
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`

### Detaylı liste: `.env.production.example`

---

## 🔧 Post-Deployment

### Database Migrations
```bash
# App Platform Console veya local:
export DATABASE_URL="[Production DB URL]"
alembic upgrade head
python scripts/seed_db.py
```

### Test
```bash
curl https://api.screenshotbeam.com/api/v1/health
```

---

## 📚 Detaylı Rehber

Tam adım adım rehber için: `DEPLOYMENT_DIGITALOCEAN.md`  
Checklist için: `DEPLOYMENT_CHECKLIST.md`

---

## 💰 Tahmini Maliyet

- App Platform: $15/month (API + 2 Workers)
- PostgreSQL: $15/month
- Redis: $15/month
- Spaces: $5/month
- **Toplam: ~$50/month**

---

## 🆘 Sorun mu var?

1. **Build fails:** Playwright install komutunu kontrol et
2. **DB connection error:** SSL mode ve trusted sources kontrol et
3. **Spaces upload fails:** CORS ve access keys kontrol et
4. **DNS not working:** 24-48 saat bekle, propagation sürebilir

---

**Hızlı başlangıç tamamlandı! 🎉**

