#!/bin/bash
set -e

echo "Switching traffic to GREEN"

# Update upstream config
sed -i 's/server api-go-blue:8080/# server api-go-blue:8080/' /root/deploy/api/docker/nginx-blue-green.conf
sed -i 's/# server api-go-green:8080/server api-go-green:8080/' /root/deploy/api/docker/nginx-blue-green.conf

# Reload nginx
docker exec screenshot-nginx nginx -t && docker exec screenshot-nginx nginx -s reload

echo "✅ Traffic switched to GREEN"
