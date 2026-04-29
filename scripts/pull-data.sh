#!/usr/bin/env bash
# Downloads project data from S3. Run this after cloning or when data changes.
# Usage: ./scripts/pull-data.sh
set -euo pipefail

BUCKET="s3://warrenlanchonete-data"

echo "Pulling ChromaDB from S3..."
aws s3 sync "$BUCKET/rag_data/" warren-backend/rag_data/ --exclude ".gitkeep"

echo "Pulling processed CSVs from S3..."
aws s3 sync "$BUCKET/ingestion/processed/" warren-ingestion/data/processed/ --exclude "*.md"

echo "Pulling ingestion cache from S3..."
aws s3 sync "$BUCKET/ingestion/cache/" warren-ingestion/data/cache/ --exclude ".gitkeep"

echo "Done."
