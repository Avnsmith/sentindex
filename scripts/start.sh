#!/bin/bash

# Sentindex startup script
# This script starts all required services for Sentindex

set -e

echo "Starting Sentindex..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Warning: .env file not found. Copying from env.example..."
    cp env.example .env
    echo "Please edit .env file with your actual API keys before running again."
    exit 1
fi

# Create logs directory
mkdir -p logs

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose is not installed. Please install docker-compose and try again."
    exit 1
fi

# Start services
echo "Starting infrastructure services..."
docker-compose up -d timescaledb redis kafka

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 30

# Check if TimescaleDB is ready
echo "Checking TimescaleDB connection..."
until docker-compose exec timescaledb pg_isready -U sentindex -d sentindex; do
    echo "Waiting for TimescaleDB..."
    sleep 5
done

# Check if Redis is ready
echo "Checking Redis connection..."
until docker-compose exec redis redis-cli ping; do
    echo "Waiting for Redis..."
    sleep 5
done

# Check if Kafka is ready
echo "Checking Kafka connection..."
until docker-compose exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092; do
    echo "Waiting for Kafka..."
    sleep 5
done

# Start application services
echo "Starting application services..."
docker-compose up -d sentindex-api data-ingestion

# Start monitoring services
echo "Starting monitoring services..."
docker-compose up -d prometheus grafana

# Start nginx (optional)
echo "Starting nginx reverse proxy..."
docker-compose up -d nginx

# Wait for API to be ready
echo "Waiting for API to be ready..."
until curl -f http://localhost:8000/health > /dev/null 2>&1; do
    echo "Waiting for API..."
    sleep 5
done

echo "Sentindex is ready!"
echo ""
echo "Services:"
echo "  API: http://localhost:8000"
echo "  Grafana: http://localhost:3001 (admin/admin)"
echo "  Prometheus: http://localhost:9090"
echo "  Nginx: http://localhost:80"
echo ""
echo "API Endpoints:"
echo "  Health: http://localhost:8000/health"
echo "  Latest Index: http://localhost:8000/v1/index/gold_silver_oil_crypto/latest"
echo "  Metrics: http://localhost:8000/metrics"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f sentindex-api"
echo "  docker-compose logs -f data-ingestion"
echo ""
echo "To stop all services:"
echo "  docker-compose down"
