# Database Migrations

Bu dizin `golang-migrate` ile yönetilen SQL migration dosyalarını içerir.

## Migration Dosya Yapısı

```
migrations/
├── 000001_initial_schema.up.sql
├── 000001_initial_schema.down.sql
├── 000002_add_render_job_fields.up.sql
├── 000002_add_render_job_fields.down.sql
└── README.md
```

## Kullanım

### Local Development

```bash
# DATABASE_URL ayarla
export DATABASE_URL="postgresql://user:pass@localhost:5432/dbname?sslmode=disable"

# Tüm migration'ları uygula
go run cmd/migrate/main.go up

# Son migration'ı geri al
go run cmd/migrate/main.go down

# Mevcut versiyonu göster
go run cmd/migrate/main.go version
```

### Production (Docker)

```bash
# Migration uygula
docker exec screenshot-api-go /migrate up

# Version kontrol
docker exec screenshot-api-go /migrate version
```

### Sunucuda Manuel

```bash
cd /root/deploy/api
source .env.production
go run api-go/cmd/migrate/main.go up
```

## Yeni Migration Oluşturma

```bash
# golang-migrate CLI ile
migrate create -ext sql -dir api-go/migrations -seq add_new_feature

# Bu şu dosyaları oluşturur:
# - 000003_add_new_feature.up.sql
# - 000003_add_new_feature.down.sql
```

## Best Practices

1. ✅ Her zaman `IF NOT EXISTS` / `IF EXISTS` kullan (idempotent migration)
2. ✅ Her migration'ı local'de test et
3. ✅ Hem `up` hem `down` migration yaz
4. ✅ Migration'ları küçük ve odaklı tut
5. ✅ Mevcut migration'ları değiştirme, yeni oluştur
6. ❌ Production'da GORM AutoMigrate kullanma

## Acil Durum

Migration başarısız olup "dirty" state kalırsa:

```bash
# Versiyonu zorla ayarla
docker exec screenshot-api-go /migrate force <version>

# Sonra migration'ı düzelt ve tekrar dene
```
