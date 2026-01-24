#!/bin/bash
set -e

STEPS=${1:-1}

echo "====================================="
echo "Database Migration Rollback"
echo "====================================="
echo ""

echo "Current migration version:"
docker exec screenshot-api-go /migrate version
echo ""

read -p "Are you sure you want to rollback $STEPS migration(s)? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 1
fi

echo ""
echo "Rolling back $STEPS migration(s)..."

for i in $(seq 1 $STEPS); do
  echo "Rollback step $i/$STEPS"
  docker exec screenshot-api-go /migrate down
done

echo ""
echo "Final migration version:"
docker exec screenshot-api-go /migrate version

echo ""
echo "====================================="
echo "✅ Migration rollback complete"
echo "====================================="
echo ""
echo "Note: You may need to restart the API containers:"
echo "  docker restart api-go-blue api-go-green"
