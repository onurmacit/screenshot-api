package repository

import (
	"github.com/onurmacit/screenshot-api/api-go/internal/models"
	"gorm.io/gorm"
)

type RenderJobRepository struct {
	db *gorm.DB
}

func NewRenderJobRepository(db *gorm.DB) *RenderJobRepository {
	return &RenderJobRepository{db: db}
}

func (r *RenderJobRepository) Create(job *models.RenderJob) error {
	return r.db.Create(job).Error
}

func (r *RenderJobRepository) Update(job *models.RenderJob) error {
	return r.db.Save(job).Error
}

func (r *RenderJobRepository) Delete(id string) error {
	return r.db.Where("id = ?", id).Delete(&models.RenderJob{}).Error
}

func (r *RenderJobRepository) FindByID(id string) (*models.RenderJob, error) {
	var job models.RenderJob
	err := r.db.Where("id = ?", id).First(&job).Error
	return &job, err
}

func (r *RenderJobRepository) ListByUserID(userID string, limit, offset int) ([]models.RenderJob, int64, error) {
	var jobs []models.RenderJob
	var total int64

	err := r.db.Model(&models.RenderJob{}).Where("user_id = ?", userID).Count(&total).Error
	if err != nil {
		return nil, 0, err
	}

	err = r.db.Where("user_id = ?", userID).
		Order("created_at desc").
		Limit(limit).
		Offset(offset).
		Find(&jobs).Error

	return jobs, total, err
}
