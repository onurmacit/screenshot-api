# DigitalOcean App Platform Deployment Guide

Bu rehber, Screenshot API'yi DigitalOcean App Platform'a deploy etmek için adım adım talimatlar içerir.

**Domain:** screenshotbeam.com (Güzelhosting)

---

## 📋 Ön Hazırlık

### 1. Gereksinimler
- ✅ DigitalOcean hesabı
- ✅ GitHub repository (onurmacit/screenshot-api)
- ✅ Domain (screenshotbeam.com) - Güzelhosting'ten alındı
- ✅ Stripe hesabı (billing için)

### 2. DigitalOcean Servisleri
- **App Platform** - API ve Worker'lar için
- **Managed PostgreSQL** - Database
- **Managed Redis** (veya container) - Cache ve Celery broker
- **Spaces** - S3-compatible object storage

---

## 🚀 Adım 1: DigitalOcean Spaces (S3 Storage) Kurulumu

### 1.1 Spaces Oluştur
1. DigitalOcean Dashboard → **Spaces** → **Create a Space**
2. **Settings:**
   - **Name:** `screenshotbeam` (domain ile uyumlu)
   - **Region:** `NYC3` (veya tercih ettiğin)
   - **CDN:** Enable (önerilir)
   - **File Listing:** Disable (güvenlik)
3. **Create Space**

### 1.2 Access Keys Oluştur
1. **API** → **Spaces Keys** → **Generate New Key**
2. **Key Name:** `screenshot-api-production`
3. **Access:** Read & Write
4. **Generate Key**
5. **Access Key ID** ve **Secret Access Key**'i kaydet (sadece bir kez gösterilir!)

### 1.3 Bucket Oluştur
1. Space içinde **Settings** → **File Listing** → **Disable**
2. Bucket adı: `screenshot-api-renders` (veya istediğin)

### 1.4 CORS Ayarları
1. Space → **Settings** → **CORS Configurations**
2. **Add CORS Rule:**
   ```json
   {
     "AllowedOrigins": ["https://screenshotbeam.com", "https://api.screenshotbeam.com"],
     "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
     "AllowedHeaders": ["*"],
     "ExposeHeaders": ["ETag"],
     "MaxAgeSeconds": 3000
   }
   ```

---

## 🗄️ Adım 2: Managed PostgreSQL Kurulumu

### 2.1 Database Cluster Oluştur
1. DigitalOcean Dashboard → **Databases** → **Create Database Cluster**
2. **Settings:**
   - **Engine:** PostgreSQL 15
   - **Plan:** Basic ($15/month - başlangıç için yeterli)
   - **Region:** NYC3 (Spaces ile aynı)
   - **Database Name:** `screenshot_api`
   - **Cluster Name:** `screenshot-api-db-cluster`
3. **Create Database Cluster**

### 2.2 Connection String Al
1. Database → **Connection Details**
2. **Connection String** formatı:
   ```
   postgresql+asyncpg://doadmin:PASSWORD@HOST:25060/screenshot_api?sslmode=require
   ```
3. Bu string'i kaydet (App Platform'da kullanılacak)

### 2.3 Trusted Sources
1. Database → **Settings** → **Trusted Sources**
2. **Add Trusted Source:**
   - **Source:** `App Platform` (otomatik eklenir)
   - Veya manuel IP: `0.0.0.0/0` (sadece test için, production'da kısıtla)

---

## 🔴 Adım 3: Redis Kurulumu

### Seçenek 1: Managed Redis (Önerilen - Production)
1. DigitalOcean Dashboard → **Databases** → **Create Database Cluster**
2. **Settings:**
   - **Engine:** Redis 7
   - **Plan:** Basic ($15/month)
   - **Region:** NYC3
3. **Connection String** al ve kaydet

### Seçenek 2: Container (Daha ucuz - Development)
App Platform'da ayrı bir worker service olarak Redis container çalıştırılabilir (önerilmez, production için).

---

## 🌐 Adım 4: Domain (screenshotbeam.com) Kurulumu

### 4.1 Güzelhosting DNS Ayarları
1. Güzelhosting panel → **DNS Yönetimi**
2. **A Record** ekle:
   ```
   Type: A
   Name: @ (veya boş)
   Value: [DigitalOcean App Platform IP] (deploy sonrası alınacak)
   TTL: 3600
   ```

3. **CNAME Record** ekle (API için):
   ```
   Type: CNAME
   Name: api
   Value: [DigitalOcean App Platform Domain] (örn: screenshot-api-xxxxx.ondigitalocean.app)
   TTL: 3600
   ```

4. **CNAME Record** ekle (www için):
   ```
   Type: CNAME
   Name: www
   Value: screenshotbeam.com
   TTL: 3600
   ```

### 4.2 DigitalOcean'da Domain Ekle
1. App Platform → **Settings** → **Domains**
2. **Add Domain:**
   - `screenshotbeam.com`
   - `api.screenshotbeam.com`
   - `www.screenshotbeam.com`
3. DNS kayıtlarını doğrula (24-48 saat sürebilir)

---

## 🚀 Adım 5: App Platform Deployment

### 5.1 GitHub Repository Bağla
1. DigitalOcean Dashboard → **App Platform** → **Create App**
2. **GitHub** → Repository seç: `onurmacit/screenshot-api`
3. **Branch:** `main`
4. **Auto Deploy:** Enable (her push'ta otomatik deploy)

### 5.2 App Spec (app.yaml) Kullan
1. **Source:** `.do/app.yaml` dosyasını kullan
2. Veya **Web UI** ile manuel yapılandır (aşağıdaki adımlar)

### 5.3 API Service Yapılandırma

#### Build Settings
- **Build Command:**
  ```bash
  pip install --upgrade pip && pip install -r requirements.txt && playwright install chromium --with-deps
  ```
- **Run Command:**
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```

#### Environment Variables
Aşağıdaki environment variable'ları **encrypted** olarak ekle:

```bash
# Application
APP_ENV=production
APP_NAME=ScreenshotAPI
DEBUG=false
LOG_LEVEL=INFO

# Security (MUTLAKA DEĞİŞTİR!)
SECRET_KEY=[Güçlü random string - openssl rand -hex 32]
JWT_ALGORITHM=HS256

# Database (Managed PostgreSQL connection string)
DATABASE_URL=[Adım 2.2'den alınan connection string]

# Redis (Managed Redis connection string)
REDIS_URL=[Adım 3'ten alınan connection string]
CELERY_BROKER_URL=[Aynı Redis URL]
CELERY_RESULT_BACKEND=[Aynı Redis URL, farklı DB numarası ile]

# DigitalOcean Spaces (S3)
AWS_ACCESS_KEY_ID=[Adım 1.2'den alınan Access Key]
AWS_SECRET_ACCESS_KEY=[Adım 1.2'den alınan Secret Key]
AWS_REGION=nyc3
AWS_S3_BUCKET=screenshot-api-renders
AWS_S3_ENDPOINT_URL=https://nyc3.digitaloceanspaces.com
AWS_S3_PUBLIC_URL=https://screenshotbeam.nyc3.digitaloceanspaces.com

# Stripe
STRIPE_SECRET_KEY=[Stripe Dashboard'dan]
STRIPE_WEBHOOK_SECRET=[Stripe Dashboard'dan]
STRIPE_PUBLISHABLE_KEY=[Stripe Dashboard'dan]

# Trusted Proxies (DigitalOcean App Platform)
TRUSTED_PROXIES=["10.0.0.0/8","172.16.0.0/12","192.168.0.0/16"]
```

#### Resources
- **Instance Size:** Basic ($5/month - başlangıç)
- **Instance Count:** 1 (scale up later)
- **HTTP Port:** 8000

#### Health Check
- **Path:** `/api/v1/health`
- **Initial Delay:** 30s
- **Period:** 10s

### 5.4 Worker Service Yapılandırma

#### Worker (Default Queue)
- **Build Command:** (API ile aynı)
- **Run Command:**
  ```bash
  celery -A app.workers.celery_app worker --loglevel=info -Q default,low_priority -c 2
  ```
- **Environment Variables:** (API ile aynı, DATABASE_URL, REDIS_URL, AWS credentials)
- **Instance Size:** Basic ($5/month)
- **Instance Count:** 1

#### Worker-High (High Priority Queue)
- **Run Command:**
  ```bash
  celery -A app.workers.celery_app worker --loglevel=info -Q high_priority -c 2
  ```
- Diğer ayarlar Worker ile aynı

### 5.5 Database Connection
1. App Platform → **Components** → **Add Component** → **Database**
2. **Select Database:** `screenshot-api-db-cluster` (Adım 2'de oluşturulan)
3. **Environment Variable Name:** `DATABASE_URL` (otomatik inject edilir)

### 5.6 Deploy
1. **Review** → **Create Resources**
2. İlk deploy 5-10 dakika sürebilir
3. Logs'u takip et: **Runtime Logs**

---

## 🔧 Adım 6: Database Migrations

### 6.1 Alembic Migrations Çalıştır
1. App Platform → **Components** → **API Service** → **Console**
2. Veya local'den (DATABASE_URL ile):
   ```bash
   export DATABASE_URL="[Production DB URL]"
   alembic upgrade head
   ```

### 6.2 Seed Data (Plans)
```bash
python scripts/seed_db.py
```

---

## ✅ Adım 7: Doğrulama

### 7.1 Health Check
```bash
curl https://api.screenshotbeam.com/api/v1/health
```

### 7.2 API Docs
- https://api.screenshotbeam.com/docs
- https://api.screenshotbeam.com/redoc

### 7.3 Test Request
```bash
# Register user
curl -X POST https://api.screenshotbeam.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@screenshotbeam.com", "password": "Test123!"}'

# Login
curl -X POST https://api.screenshotbeam.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@screenshotbeam.com", "password": "Test123!"}'
```

---

## 🔒 Adım 8: Güvenlik

### 8.1 SSL Certificates
- DigitalOcean App Platform otomatik SSL sağlar (Let's Encrypt)
- Domain doğrulandıktan sonra aktif olur

### 8.2 Environment Variables
- Tüm secret'ları **encrypted** olarak sakla
- Production'da `DEBUG=false` olduğundan emin ol

### 8.3 Rate Limiting
- Production'da rate limiting aktif
- Plan bazlı limitler çalışıyor

---

## 📊 Adım 9: Monitoring

### 9.1 DigitalOcean Metrics
- App Platform → **Metrics** → CPU, Memory, Request rates

### 9.2 Application Logs
- **Runtime Logs** → Real-time log streaming
- **Build Logs** → Build süreci

### 9.3 Health Checks
- `/api/v1/health` endpoint'i otomatik monitor edilir
- Failure durumunda alert

---

## 💰 Maliyet Tahmini

| Servis | Plan | Aylık Maliyet |
|--------|------|---------------|
| App Platform (API) | Basic | $5 |
| App Platform (Worker) | Basic x2 | $10 |
| Managed PostgreSQL | Basic | $15 |
| Managed Redis | Basic | $15 |
| Spaces (Storage) | 250GB | $5 |
| **Toplam** | | **~$50/ay** |

**Not:** İlk ay $200 credit ile başlayabilirsin (referral link ile).

---

## 🚨 Troubleshooting

### Build Fails
- **Playwright install hatası:** `playwright install chromium --with-deps` komutunu kontrol et
- **Dependencies:** `requirements.txt` dosyasını kontrol et

### Database Connection Error
- **SSL Mode:** `?sslmode=require` ekle
- **Trusted Sources:** Database'de App Platform IP'sini ekle

### Redis Connection Error
- **Connection String:** Formatı kontrol et
- **Database Number:** Celery broker ve result backend farklı DB numaraları kullanmalı

### Spaces Upload Fails
- **CORS:** CORS ayarlarını kontrol et
- **Access Keys:** Doğru key'leri kullandığından emin ol
- **Bucket Name:** `AWS_S3_BUCKET` environment variable'ını kontrol et

---

## 📝 Sonraki Adımlar

1. ✅ Production deployment tamamlandı
2. ⏳ Domain DNS ayarları (24-48 saat)
3. ⏳ SSL certificate aktif olması
4. ⏳ Monitoring setup (Sentry, Datadog - opsiyonel)
5. ⏳ Backup strategy (database backups)
6. ⏳ Scaling plan (traffic artışına göre)

---

## 🔗 Önemli Linkler

- **DigitalOcean Dashboard:** https://cloud.digitalocean.com
- **App Platform Docs:** https://docs.digitalocean.com/products/app-platform/
- **Spaces Docs:** https://docs.digitalocean.com/products/spaces/
- **API URL:** https://api.screenshotbeam.com
- **Landing Page:** https://screenshotbeam.com

---

**Son Güncelleme:** 2024-12-07

