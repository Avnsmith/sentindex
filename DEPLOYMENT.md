# Sentindex Deployment Guide

## GitHub Setup

1. **Create a new repository on GitHub**:
   - Go to https://github.com/new
   - Repository name: `sentindex`
   - Description: "Financial index platform with AI-powered insights using Sentient LLM"
   - Make it public or private as needed

2. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "Initial commit: Sentindex with Sentient LLM integration"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/sentindex.git
   git push -u origin main
   ```

## Vercel Deployment

### Option 1: Deploy from GitHub (Recommended)

1. **Connect to Vercel**:
   - Go to https://vercel.com
   - Sign in with GitHub
   - Click "New Project"
   - Import your `sentindex` repository

2. **Configure Environment Variables**:
   In Vercel dashboard, add these environment variables:
   ```
   ALPHAVANTAGE_API_KEY=your_alphavantage_key
   EIA_API_KEY=your_eia_key
   SENTIENT_API_KEY=key_4pVTEkqgJWn3ZMVz
   SECRET_KEY=your_secret_key
   ```

3. **Deploy**:
   - Click "Deploy"
   - Vercel will automatically build and deploy your API

### Option 2: Deploy with Vercel CLI

1. **Install Vercel CLI**:
   ```bash
   npm i -g vercel
   ```

2. **Login to Vercel**:
   ```bash
   vercel login
   ```

3. **Deploy**:
   ```bash
   vercel
   ```

4. **Set Environment Variables**:
   ```bash
   vercel env add ALPHAVANTAGE_API_KEY
   vercel env add EIA_API_KEY
   vercel env add SENTIENT_API_KEY
   vercel env add SECRET_KEY
   ```

## API Endpoints

Once deployed, your API will be available at:
- `https://your-project.vercel.app/`
- `https://your-project.vercel.app/health`
- `https://your-project.vercel.app/v1/index/gold_silver_oil_crypto/latest`
- `https://your-project.vercel.app/v1/index/gold_silver_oil_crypto/insights`

## Local Development

For local development with full services:

1. **Setup environment**:
   ```bash
   python setup_sentient.py
   ```

2. **Start services**:
   ```bash
   ./scripts/start.sh
   ```

3. **Test API**:
   ```bash
   python scripts/test_api.py
   ```

## Production Considerations

### Vercel Limitations
- **Serverless Functions**: 30-second timeout limit
- **No Persistent Storage**: Use external database (TimescaleDB, PostgreSQL)
- **No Background Tasks**: Kafka consumers won't work on Vercel

### Recommended Production Setup
1. **API on Vercel**: For REST endpoints
2. **Database**: External TimescaleDB (Railway, Supabase, or AWS RDS)
3. **Background Workers**: Separate deployment for data ingestion
4. **Monitoring**: Vercel Analytics + external monitoring

### Environment Variables for Production
```bash
# Database (external)
DATABASE_URL=postgresql://user:pass@host:port/db

# Redis (external)
REDIS_URL=redis://host:port

# Kafka (external)
KAFKA_BOOTSTRAP_SERVERS=host:port

# API Keys
ALPHAVANTAGE_API_KEY=your_key
EIA_API_KEY=your_key
SENTIENT_API_KEY=key_4pVTEkqgJWn3ZMVz
SECRET_KEY=your_secret
```

## Testing Deployment

1. **Health Check**:
   ```bash
   curl https://your-project.vercel.app/health
   ```

2. **API Test**:
   ```bash
   curl https://your-project.vercel.app/v1/index/gold_silver_oil_crypto/latest
   ```

3. **Compute Index** (if you have data):
   ```bash
   curl -X POST https://your-project.vercel.app/v1/index/gold_silver_oil_crypto/compute \
     -H "Content-Type: application/json" \
     -d '{
       "index_name": "gold_silver_oil_crypto",
       "prices": {
         "GOLD": 1900.12,
         "SILVER": 24.31,
         "OIL": 78.45,
         "BTC": 27450.0,
         "ETH": 1850.0
       },
       "method": "level_normalized"
     }'
   ```

## Troubleshooting

### Common Issues
1. **Import Errors**: Make sure all dependencies are in `requirements-vercel.txt`
2. **Environment Variables**: Check they're set correctly in Vercel dashboard
3. **Timeout Issues**: Optimize code for serverless execution
4. **Database Connection**: Use external database for production

### Logs
- Check Vercel function logs in the dashboard
- Use `vercel logs` command for CLI deployment
