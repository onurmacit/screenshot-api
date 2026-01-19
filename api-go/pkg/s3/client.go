package s3

import (
	"bytes"
	"context"
	"fmt"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

type Client struct {
	s3Client *s3.Client
	bucket   string
}

func Connect(ctx context.Context, region, endpoint, accessKey, secretKey, bucket string) (*Client, error) {
	cfg, err := config.LoadDefaultConfig(ctx,
		config.WithRegion(region),
		config.WithCredentialsProvider(credentials.NewStaticCredentialsProvider(accessKey, secretKey, "")),
	)
	if err != nil {
		return nil, err
	}

	// Custom endpoint for DigitalOcean Spaces (S3-compatible)
	s3Client := s3.NewFromConfig(cfg, func(o *s3.Options) {
		if endpoint != "" {
			o.BaseEndpoint = aws.String(endpoint)
			o.UsePathStyle = true // Essential for most S3-compatible storage
		}
	})

	return &Client{
		s3Client: s3Client,
		bucket:   bucket,
	}, nil
}

func (c *Client) Upload(ctx context.Context, key string, data []byte, contentType string, metadata map[string]string) (string, error) {
	_, err := c.s3Client.PutObject(ctx, &s3.PutObjectInput{
		Bucket:      aws.String(c.bucket),
		Key:         aws.String(key),
		Body:        bytes.NewReader(data),
		ContentType: aws.String(contentType),
		Metadata:    metadata,
		ACL:         "public-read", // Make public for now
	})
	if err != nil {
		return "", err
	}

	// Construct URL (assuming DO Spaces or standard S3)
	// Note: This is simplified. You might want to use CDN URL if available.
	endpoint := c.s3Client.Options().BaseEndpoint
	if endpoint != nil {
		return fmt.Sprintf("%s/%s/%s", *endpoint, c.bucket, key), nil
	}

	return fmt.Sprintf("https://%s.s3.amazonaws.com/%s", c.bucket, key), nil
}

func (c *Client) GeneratePresignedURL(ctx context.Context, key string, expiry time.Duration) (string, error) {
	presignClient := s3.NewPresignClient(c.s3Client)
	req, err := presignClient.PresignGetObject(ctx, &s3.GetObjectInput{
		Bucket: aws.String(c.bucket),
		Key:    aws.String(key),
	}, s3.WithPresignExpires(expiry))

	if err != nil {
		return "", err
	}

	return req.URL, nil
}

func (c *Client) Delete(ctx context.Context, key string) error {
	_, err := c.s3Client.DeleteObject(ctx, &s3.DeleteObjectInput{
		Bucket: aws.String(c.bucket),
		Key:    aws.String(key),
	})
	return err
}
