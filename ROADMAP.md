# 🗺️ Screenshot API - Yol Haritası

**Mevcut Durum:** MVP ve Infrastructure hazır, API ve Landing Page canlıda.
**Domain:** screenshotbeam.com (Vercel) / api.screenshotbeam.com (DigitalOcean)
**Platform:** DigitalOcean Droplet (Docker Compose)

---

## 📍 Mevcut Durum (Aralık 2024)

### ✅ Tamamlananlar
- [x] Backend API (FastAPI + Playwright)
- [x] Database models & migrations
- [x] Authentication & Authorization (JWT + API Keys)
- [x] Rendering service (Screenshot + PDF + WebP Desteği)
- [x] Celery background jobs & Worker yapısı
- [x] S3 storage integration (DigitalOcean Spaces)
- [x] Rate limiting (multi-tier)
- [x] Billing & usage tracking (Backend logic)
- [x] Docker setup & Docker Compose configuration
- [x] Domain Migration (Root domain -> Vercel, api subdomain -> DO)
- [x] SSL Certificates (Let's Encrypt & Vercel)
- [x] Landing page integration (Next.js)

### ⏳ Sırada Bekleyenler (Kısa Vadeli)
- [ ] User Dashboard (Kullanıcı giriş yapıp API Key yönetebilmeli)
- [ ] Usage Statistics (Kullanıcı günlük/aylık kullanımını görebilmeli)
- [ ] Stripe UI Integration (Abonelik paketlerinin frontend ile bağlanması)
- [ ] Error Tracking (Sentry entegrasyonu)
- [ ] Automated CI/CD (GitHub Actions ile Droplet'e otomatik deploy)

---

## 🎯 Sonraki Adımlar (Öncelik Sırası)

### Faz 1: Domain & Infrastructure Setup (1-2 gün)

#### 1.1 Domain Alımı
- [ ] **Güzelhosting'ten domain al:**
  - Domain: `screenshotbeam.com`
  - Süre: 1 yıl (veya daha uzun)
  - Fiyat: ~$10-15/yıl
  - DNS panel erişimi kontrol et

#### 1.2 DigitalOcean Hesabı
- [ ] **DigitalOcean hesabı oluştur:**
  - https://cloud.digitalocean.com
  - Payment method ekle
  - İlk ay $200 credit (referral link ile)
  - GitHub hesabını bağla

#### 1.3 DigitalOcean Servisleri
- [ ] **Spaces (S3 Storage) oluştur:**
  - Name: `screenshotbeam`
  - Region: NYC3 (veya tercih ettiğin)
  - CDN: Enable
  - Access Keys oluştur
  - CORS ayarları yap
  - **Süre:** 15 dakika
  - **Maliyet:** ~$5/ay (250GB)

- [ ] **Managed PostgreSQL oluştur:**
  - Engine: PostgreSQL 15
  - Plan: Basic ($15/ay)
  - Region: NYC3
  - Database name: `screenshot_api`
  - Connection string al
  - **Süre:** 10 dakika
  - **Maliyet:** $15/ay

- [ ] **Managed Redis oluştur:**
  - Engine: Redis 7
  - Plan: Basic ($15/ay)
  - Region: NYC3
  - Connection string al
  - **Süre:** 10 dakika
  - **Maliyet:** $15/ay

**Toplam Süre:** ~1 saat  
**Toplam Maliyet:** ~$35/ay (ilk ay $200 credit ile başla)

---

### Faz 2: App Platform Deployment (2-3 saat)

#### 2.1 App Platform Setup
- [ ] **App oluştur:**
  - GitHub repo: `onurmacit/screenshot-api`
  - Branch: `main`
  - App spec: `.do/app.yaml` kullan
  - Auto-deploy: Enable

#### 2.2 Environment Variables
- [ ] **Secret'ları ekle (Encrypted):**
  - `SECRET_KEY` (openssl rand -hex 32)
  - `DATABASE_URL` (Managed PostgreSQL)
  - `REDIS_URL` (Managed Redis)
  - `CELERY_BROKER_URL` (Redis)
  - `CELERY_RESULT_BACKEND` (Redis)
  - `AWS_ACCESS_KEY_ID` (Spaces)
  - `AWS_SECRET_ACCESS_KEY` (Spaces)
  - `STRIPE_SECRET_KEY`
  - `STRIPE_WEBHOOK_SECRET`
  - Diğer variables (`.env.production.example` dosyasından)

#### 2.3 Services Configuration
- [ ] **API Service:**
  - Build command kontrol et
  - Run command kontrol et
  - Instance size: Basic ($5/ay)
  - Health check path: `/api/v1/health`

- [ ] **Worker Service (Default Queue):**
  - Run command: `celery -A app.workers.celery_app worker --loglevel=info -Q default,low_priority -c 2`
  - Instance size: Basic ($5/ay)

- [ ] **Worker-High Service (High Priority):**
  - Run command: `celery -A app.workers.celery_app worker --loglevel=info -Q high_priority -c 2`
  - Instance size: Basic ($5/ay)

#### 2.4 Database Connection
- [ ] Managed PostgreSQL'i App Platform'a bağla
- [ ] `DATABASE_URL` otomatik inject edildiğini kontrol et

#### 2.5 İlk Deploy
- [ ] Deploy başlat
- [ ] Build logs'u takip et
- [ ] Runtime logs'u kontrol et
- [ ] Health check çalışıyor mu kontrol et

**Toplam Süre:** 2-3 saat  
**Maliyet:** $15/ay (3 service: API + 2 Workers)

---

### Faz 3: Domain & DNS Configuration (1-2 saat)

#### 3.1 App Platform Domain
- [ ] App Platform → Settings → Domains
- [ ] Domain ekle: `screenshotbeam.com`
- [ ] Domain ekle: `api.screenshotbeam.com`
- [ ] DNS kayıtlarını al (CNAME/A records)

#### 3.2 Güzelhosting DNS Ayarları
- [ ] Güzelhosting DNS panel'e gir
- [ ] **A Record ekle:**
  ```
  Type: A
  Name: @ (veya boş)
  Value: [App Platform IP] (App Platform'dan alınacak)
  TTL: 3600
  ```

- [ ] **CNAME Record ekle (API için):**
  ```
  Type: CNAME
  Name: api
  Value: [App Platform Domain] (örn: screenshot-api-xxxxx.ondigitalocean.app)
  TTL: 3600
  ```

- [ ] **CNAME Record ekle (www için):**
  ```
  Type: CNAME
  Name: www
  Value: screenshotbeam.com
  TTL: 3600
  ```

#### 3.3 DNS Propagation
- [ ] DNS değişikliklerini kontrol et: `dig screenshotbeam.com`
- [ ] 24-48 saat bekle (genellikle 1-2 saat içinde çalışır)
- [ ] SSL certificate otomatik oluşturulacak (Let's Encrypt)

**Toplam Süre:** 1-2 saat (DNS propagation hariç)

---

### Faz 4: Database Setup & Testing (1 saat)

#### 4.1 Migrations
- [ ] App Platform Console'a gir
- [ ] Alembic migrations çalıştır:
  ```bash
  alembic upgrade head
  ```

#### 4.2 Seed Data
- [ ] Plans oluştur:
  ```bash
  python scripts/seed_db.py
  ```

#### 4.3 Testing
- [ ] Health check: `curl https://api.screenshotbeam.com/api/v1/health`
- [ ] API docs: https://api.screenshotbeam.com/docs
- [ ] Test user registration
- [ ] Test login
- [ ] Test screenshot generation
- [ ] Test PDF generation
- [ ] Test async rendering
- [ ] Test webhook delivery

**Toplam Süre:** 1 saat

---

### Faz 5: Landing Page Integration (1 saat)

#### 5.1 Backend API Bağlantısı
- [ ] Landing page'de API URL'yi güncelle:
  - `NEXT_PUBLIC_API_URL=https://api.screenshotbeam.com`
- [ ] Waitlist endpoint'i backend'e bağla
- [ ] Demo section'ı gerçek API'ye bağla

#### 5.2 Domain Configuration
- [ ] Vercel'de custom domain ekle: `screenshotbeam.com`
- [ ] DNS ayarları (Vercel'den gelecek)
- [ ] SSL certificate (otomatik)

**Toplam Süre:** 1 saat

---

## 📊 Toplam Süre & Maliyet

### Süre
- **Faz 1 (Infrastructure):** 1-2 gün (domain alımı + DO setup)
- **Faz 2 (Deployment):** 2-3 saat
- **Faz 3 (DNS):** 1-2 saat (propagation hariç)
- **Faz 4 (Testing):** 1 saat
- **Faz 5 (Integration):** 1 saat
- **Toplam:** ~2-3 gün (DNS propagation dahil)

### Maliyet (Aylık)
| Servis | Plan | Maliyet |
|--------|------|---------|
| App Platform (API) | Basic | $5 |
| App Platform (Worker) | Basic x2 | $10 |
| Managed PostgreSQL | Basic | $15 |
| Managed Redis | Basic | $15 |
| Spaces (Storage) | 250GB | $5 |
| Domain | screenshotbeam.com | ~$1 (yıllık) |
| **Toplam** | | **~$50/ay** |

**İlk Ay:** $200 credit ile başla (referral link ile)

---

## 🎯 Hemen Yapılacaklar (Bugün)

### Öncelik 1: Domain Alımı
1. Güzelhosting'e git
2. `screenshotbeam.com` domain'ini ara
3. Sepete ekle ve öde
4. DNS panel erişimini kontrol et

### Öncelik 2: DigitalOcean Hesabı
1. DigitalOcean'a kayıt ol
2. Payment method ekle
3. GitHub hesabını bağla
4. İlk $200 credit'i al (referral link)

### Öncelik 3: Servisleri Oluştur
1. Spaces oluştur (15 dk)
2. PostgreSQL oluştur (10 dk)
3. Redis oluştur (10 dk)
4. Access keys ve connection string'leri kaydet

---

## 📝 Notlar

### Domain (screenshotbeam.com)
- Güzelhosting'ten alınacak
- DNS panel erişimi gerekli
- Transfer süresi: Anında aktif

### DigitalOcean
- İlk ay $200 credit (referral link ile)
- Auto-scaling mevcut
- Monitoring dahil
- SSL otomatik (Let's Encrypt)

### Deployment
- `.do/app.yaml` dosyası hazır
- Environment variables template hazır (`.env.production.example`)
- Deployment checklist hazır (`DEPLOYMENT_CHECKLIST.md`)
- Detaylı rehber hazır (`DEPLOYMENT_DIGITALOCEAN.md`)

---

## 🚀 Sonraki Fazlar (Deployment Sonrası)

### Faz 6: Monitoring & Optimization (1 hafta)
- [ ] Sentry error tracking
- [ ] Performance monitoring
- [ ] Cost optimization
- [ ] Scaling plan

### Faz 7: Marketing & Launch (2 hafta)
- [ ] Product Hunt launch
- [ ] SEO optimization
- [ ] Content marketing
- [ ] Beta testers

### Faz 8: Feature Development (Sürekli)
- [ ] Block Ads & Cookie Banners
- [ ] Scrolling screenshots
- [ ] HTML rendering
- [ ] Stealth mode

---

## ✅ Checklist

### Domain & Infrastructure
- [ ] Domain alındı (screenshotbeam.com)
- [ ] DigitalOcean hesabı oluşturuldu
- [ ] Spaces oluşturuldu
- [ ] PostgreSQL oluşturuldu
- [ ] Redis oluşturuldu

### Deployment
- [ ] App Platform app oluşturuldu
- [ ] Environment variables eklendi
- [ ] İlk deploy başarılı
- [ ] Health check çalışıyor

### Domain & DNS
- [ ] DNS ayarları yapıldı
- [ ] Domain propagation tamamlandı
- [ ] SSL certificate aktif

### Testing
- [ ] Database migrations çalıştı
- [ ] Seed data eklendi
- [ ] API testleri geçti
- [ ] Production ready ✅

---

**Son Güncelleme:** 2024-12-07  
**Durum:** Deployment hazır, domain ve infrastructure bekliyor

