# Deployment Checklist - screenshotbeam.com

## ✅ Pre-Deployment

### Domain & DNS
- [ ] Domain alındı: screenshotbeam.com (Güzelhosting)
- [ ] DNS panel erişimi var
- [ ] Domain transfer/activation tamamlandı

### DigitalOcean Setup
- [ ] DigitalOcean hesabı oluşturuldu
- [ ] Payment method eklendi
- [ ] GitHub repository bağlandı (onurmacit/screenshot-api)

### Services Setup
- [ ] **Spaces (S3 Storage)**
  - [ ] Space oluşturuldu: `screenshotbeam`
  - [ ] Access Keys oluşturuldu
  - [ ] Bucket oluşturuldu: `screenshot-api-renders`
  - [ ] CORS ayarları yapıldı
  - [ ] CDN enable edildi

- [ ] **Managed PostgreSQL**
  - [ ] Database cluster oluşturuldu
  - [ ] Connection string alındı
  - [ ] Trusted sources ayarlandı

- [ ] **Managed Redis**
  - [ ] Redis cluster oluşturuldu
  - [ ] Connection string alındı
  - [ ] Trusted sources ayarlandı

### Stripe Setup
- [ ] Stripe hesabı oluşturuldu
- [ ] API keys alındı (Secret, Publishable)
- [ ] Webhook endpoint hazırlandı
- [ ] Webhook secret alındı

---

## 🚀 Deployment

### App Platform Configuration
- [ ] App oluşturuldu (GitHub repo bağlandı)
- [ ] **API Service:**
  - [ ] Build command ayarlandı
  - [ ] Run command ayarlandı
  - [ ] Environment variables eklendi (tüm secret'lar)
  - [ ] Instance size seçildi
  - [ ] Health check path ayarlandı

- [ ] **Worker Service:**
  - [ ] Worker component eklendi
  - [ ] Build/Run commands ayarlandı
  - [ ] Environment variables eklendi
  - [ ] Queue configuration (default, high_priority)

- [ ] **Worker-High Service:**
  - [ ] High priority worker eklendi
  - [ ] Queue: high_priority

- [ ] **Database Connection:**
  - [ ] Managed PostgreSQL bağlandı
  - [ ] DATABASE_URL otomatik inject edildi

### Environment Variables (Encrypted)
- [ ] `SECRET_KEY` (güçlü random string)
- [ ] `DATABASE_URL` (Managed PostgreSQL)
- [ ] `REDIS_URL` (Managed Redis)
- [ ] `CELERY_BROKER_URL` (Redis)
- [ ] `CELERY_RESULT_BACKEND` (Redis)
- [ ] `AWS_ACCESS_KEY_ID` (Spaces)
- [ ] `AWS_SECRET_ACCESS_KEY` (Spaces)
- [ ] `AWS_S3_BUCKET` (screenshot-api-renders)
- [ ] `AWS_S3_ENDPOINT_URL` (Spaces endpoint)
- [ ] `AWS_S3_PUBLIC_URL` (Spaces public URL)
- [ ] `STRIPE_SECRET_KEY`
- [ ] `STRIPE_WEBHOOK_SECRET`
- [ ] `STRIPE_PUBLISHABLE_KEY`
- [ ] `APP_ENV=production`
- [ ] `DEBUG=false`
- [ ] `TRUSTED_PROXIES` (DO App Platform IP ranges)

### Domain Configuration
- [ ] App Platform'da domain eklendi: `screenshotbeam.com`
- [ ] App Platform'da domain eklendi: `api.screenshotbeam.com`
- [ ] Güzelhosting DNS ayarları yapıldı:
  - [ ] A Record: `@` → App Platform IP
  - [ ] CNAME: `api` → App Platform domain
  - [ ] CNAME: `www` → screenshotbeam.com

---

## 🔧 Post-Deployment

### Database Setup
- [ ] Alembic migrations çalıştırıldı: `alembic upgrade head`
- [ ] Seed data çalıştırıldı: `python scripts/seed_db.py`
- [ ] Plans oluşturuldu (Free, Starter, Pro, Business)

### Verification
- [ ] Health check: `curl https://api.screenshotbeam.com/api/v1/health`
- [ ] API docs: https://api.screenshotbeam.com/docs
- [ ] Test user registration
- [ ] Test login
- [ ] Test API key creation
- [ ] Test screenshot generation
- [ ] Test PDF generation
- [ ] Test async rendering
- [ ] Test webhook delivery

### SSL & Security
- [ ] SSL certificate aktif (Let's Encrypt - otomatik)
- [ ] HTTPS redirect çalışıyor
- [ ] CORS ayarları doğru
- [ ] Rate limiting aktif
- [ ] Environment variables encrypted

### Monitoring
- [ ] DigitalOcean metrics aktif
- [ ] Health checks çalışıyor
- [ ] Logs erişilebilir
- [ ] Error tracking (Sentry - opsiyonel)

---

## 📊 Testing Checklist

### API Endpoints
- [ ] `POST /api/v1/auth/register` - User registration
- [ ] `POST /api/v1/auth/login` - Login
- [ ] `POST /api/v1/auth/api-keys` - API key creation
- [ ] `POST /api/v1/render/screenshot` - Screenshot (sync)
- [ ] `POST /api/v1/render/screenshot` - Screenshot (async)
- [ ] `POST /api/v1/render/pdf` - PDF generation
- [ ] `GET /api/v1/render/{job_id}` - Job status
- [ ] `GET /api/v1/health` - Health check

### Features
- [ ] Rate limiting (per plan)
- [ ] Webhook delivery
- [ ] S3 upload (Spaces)
- [ ] Presigned URLs
- [ ] Celery workers (default, high priority)
- [ ] Database queries
- [ ] Redis caching

### Edge Cases
- [ ] Invalid URL handling
- [ ] Rate limit exceeded
- [ ] Large file uploads
- [ ] Timeout handling
- [ ] Error responses

---

## 🎯 Post-Launch

### Marketing
- [ ] Landing page güncellendi (API URL)
- [ ] Documentation link eklendi
- [ ] Demo section backend'e bağlandı
- [ ] Waitlist backend'e bağlandı

### Operations
- [ ] Backup strategy (database backups)
- [ ] Monitoring alerts setup
- [ ] Scaling plan (traffic artışı)
- [ ] Cost monitoring

### Documentation
- [ ] API documentation güncellendi
- [ ] Deployment guide tamamlandı
- [ ] Troubleshooting guide hazır

---

## 📝 Notes

### DNS Propagation
- DNS değişiklikleri 24-48 saat sürebilir
- `dig screenshotbeam.com` ile kontrol et

### SSL Certificate
- Let's Encrypt otomatik sağlanır
- Domain doğrulandıktan sonra aktif olur

### Cost Optimization
- İlk ay $200 credit kullanılabilir
- Basic plan'larla başla, scale up yap
- Spaces storage kullanımını izle

---

**Deployment Date:** _______________  
**Deployed By:** _______________  
**Status:** ⏳ Pending / ✅ Complete

