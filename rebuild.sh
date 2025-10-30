#!/bin/bash
echo "Rebuilding with no cache to ensure fresh dependencies..."
gcloud builds submit --tag gcr.io/bens-projects-475115/rag-chatbot --no-cache
