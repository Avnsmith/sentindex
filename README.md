# Sentindex

A comprehensive financial index platform that aggregates and normalizes data from multiple sources (commodities, crypto, forex) to create weighted indices with AI-powered insights.

## Features

- **Normalized Index Calculation**: Level-based and return-based index methods
- **Multi-Source Data Ingestion**: Microservices for each data source
- **Real-time Processing**: Kafka streams and TimescaleDB for time-series data
- **AI Insights**: Sentient Dobby LLM integration with structured JSON output
- **Observability**: Full monitoring and alerting stack
- **Provenance Tracking**: Complete audit trail of data sources

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Sources  │    │  Microservices  │    │   Message Bus   │
│                 │    │                 │    │     (Kafka)     │
│ • AlphaVantage  │───▶│ • Gold Service  │───▶│                 │
│ • Yahoo Finance │    │ • Crypto Service│    │                 │
│ • CoinGecko     │    │ • Oil Service   │    │                 │
│ • EIA           │    │ • Silver Service│    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │  TimescaleDB    │    │  Index Engine   │
│   Endpoints     │◀───│  Time Series    │◀───│   Consumer      │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  Sentient LLM   │
                       │   Insights      │
                       │                 │
                       └─────────────────┘
```

## Quick Start

1. **Clone and setup**:
   ```bash
   git clone <repo>
   cd sentindex
   docker-compose up -d
   ```

2. **Access the API**:
   ```bash
   curl http://localhost:8000/v1/index/gold-silver-oil-crypto/latest
   ```

3. **View dashboard**: http://localhost:3000

## Index Calculation Methods

### Level-based Normalized (Recommended)
Normalizes each asset to its base value at index origin, preventing price magnitude dominance.

### Return-based
Computes period returns and applies weights to returns, commonly used for financial indices.

## Data Sources

- **Commodities**: AlphaVantage, Yahoo Finance, EIA
- **Crypto**: CoinGecko, Sentient Crypto Agent
- **Forex**: Multiple providers with fallback

## API Endpoints

- `GET /v1/index/{name}/latest` - Latest index value
- `GET /v1/index/{name}/history` - Historical data
- `POST /v1/index/{name}/compute` - Manual recompute (admin)

## Configuration

All configuration is managed through environment variables and `config.yaml`. See `config/` directory for details.

## Monitoring

- Prometheus metrics at `/metrics`
- Grafana dashboards at http://localhost:3001
- Health checks at `/health`

## License

See LICENSE file for details.
