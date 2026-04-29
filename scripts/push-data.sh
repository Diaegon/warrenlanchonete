#!/usr/bin/env bash
# Uploads project data to S3. Run this after ingestion or when local data changes.
# Usage: ./scripts/push-data.sh
set -euo pipefail

BUCKET="s3://warrenlanchonete-data"

echo "Pushing ChromaDB to S3..."
aws s3 sync warren-backend/rag_data/ "$BUCKET/rag_data/" --exclude ".gitkeep"

echo "Pushing processed CSVs to S3..."
aws s3 sync warren-ingestion/data/processed/ "$BUCKET/ingestion/processed/" --exclude "*.md"

echo "Pushing ingestion cache to S3..."
aws s3 sync warren-ingestion/data/cache/ "$BUCKET/ingestion/cache/" --exclude ".gitkeep"

echo "Done."
