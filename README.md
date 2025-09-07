# URL Shortener Service

A modern, async URL shortener service built with FastAPI, featuring comprehensive analytics, caching, and both REST and gRPC APIs.

## 🚀 Features

- **URL Shortening**: Custom and auto-generated short codes
- **Analytics**: Comprehensive click tracking and statistics
- **Performance**: Redis caching and async operations
- **Security**: Rate limiting, URL validation, domain blacklisting
- **APIs**: Both REST and gRPC support
- **Monitoring**: Health checks and system metrics
- **Production Ready**: Docker support, migrations, logging

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │     gRPC        │
│   REST API      │    │   Service       │
└─────────────────┘    └─────────────────┘
         │                       │
         └───────────┬───────────┘
                     │
         ┌─────────────────┐
         │   Services      │
         │  - URL Service  │
         │  - Analytics    │
         │  - Cache        │
         │  - Validation   │
         └─────────────────┘
                     │
         ┌─────────────────┐
         │   Data Layer    │
         │  - PostgreSQL   │
         │  - Redis Cache  │
         └─────────────────┘
```

## 🛠️ Tech Stack

- **Framework**: FastAPI (Python 3.11+)
- **Database**: SQLAlchemy (Async) + SQLite/PostgreSQL
- **Cache**: Redis (aioredis)
- **Validation**: Pydantic v2
- **Migration**: Alembic
- **Containerization**: Docker & Docker Compose
- **Testing**: pytest + pytest-asyncio

## 📦 Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Make (optional, for convenience commands)

### 1. Clone Repository

```bash
git clone <repository-url>
cd url-shortener
```

### 2. Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

### 3. Docker Deployment (Recommended)

```bash
# Build and start all services
make docker-up

# Or manually
docker-compose up -d
```

The service will be available at:
- **API Documentation**: http://localhost:8000/api/v1/docs
- **ReDoc**: http://localhost:8000/api/v1/redoc
- **Health Check**: http://localhost:8000/health

### 4. Local Development

```bash
# Install dependencies
make install

# Run migrations
make migrate

# Start development server
make dev
```

## 🔧 Configuration

### Environment Variables

```bash
# Application
APP_NAME="URL Shortener Service"
DEBUG=false
LOG_LEVEL=INFO

# Database
DATABASE_URL="sqlite+aiosqlite:///./data/url_shortener.db"

# Redis
REDIS_URL="redis://localhost:6379"
CACHE_TTL=3600

# URL Shortening
BASE_URL="http://localhost:8000"
SHORT_CODE_LENGTH=6
MAX_URL_LENGTH=2048
DEFAULT_EXPIRY_DAYS=365

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_BURST=10
```

### Docker Compose Services

- **app**: Main FastAPI application
- **redis**: Redis cache server
- **test-db**: PostgreSQL for testing (optional)

## 📖 API Documentation

### REST Endpoints

#### URL Management
```bash
# Shorten URL
POST /api/v1/urls/shorten
{
  "original_url": "https://example.com/very/long/url",
  "custom_code": "my-link",
  "expires_in_days": 30
}

# Access short URL (redirects)
GET /{short_code}

# Get URL info
GET /api/v1/urls/{short_code}/info

# List URLs
GET /api/v1/urls/?limit=20&offset=0

# Update URL
PUT /api/v1/urls/{short_code}

# Delete URL
DELETE /api/v1/urls/{short_code}
```

#### Analytics
```bash
# URL analytics
GET /api/v1/analytics/{short_code}

# Global statistics
GET /api/v1/analytics/global/overview

# Daily trends
GET /api/v1/analytics/trends/daily?days=30

# Geographic distribution
GET /api/v1/analytics/geographic/distribution

# Export data
GET /api/v1/analytics/export/{short_code}
```

#### Admin
```bash
# Health check
GET /api/v1/admin/health

# System stats
GET /api/v1/admin/stats/system

# Cache management
POST /api/v1/admin/cache/flush
GET /api/v1/admin/cache/keys
```

## 🗄️ Database

### Migrations

```bash
# Run migrations
make migrate
# or
python scripts/migrate.py migrate

# Create new migration
make create-migration
# or
python scripts/migrate.py create "Add new feature"

# Check current revision
python scripts/migrate.py current

# Show migration history
python scripts/migrate.py history
```

### Schema

**shortened_urls**
- `short_code` (PK): Unique short identifier
- `original_url`: Target URL
- `click_count`: Total clicks
- `expires_at`: Expiration timestamp
- `is_active`: Active status
- Analytics metadata

**url_clicks**
- `id` (PK): Auto-increment ID
- `short_code` (FK): Reference to shortened URL
- `ip_address`: Visitor IP (masked for privacy)
- `user_agent`: Browser information
- Geographic data

## 🧪 Testing

```bash
# Run all tests
make test

# Run with coverage
pytest --cov=app tests/

# Run specific test
pytest tests/test_url_service.py -v
```

## 📊 Monitoring

### Health Checks

```bash
# Quick health check
curl http://localhost:8000/health

# Detailed system status
curl http://localhost:8000/api/v1/admin/health
```

### Logs

```bash
# View application logs
make logs

# Follow logs
docker-compose logs -f app
```

### Metrics

The service provides comprehensive metrics:
- URL creation/access rates
- Cache hit/miss ratios
- Response times
- Error rates
- Geographic distribution

## 🚀 Production Deployment

### 1. Production Configuration

```bash
# Create production environment
cp .env.example .env.production

# Configure for production
DATABASE_URL="postgresql+asyncpg://user:pass@localhost/url_shortener"
REDIS_URL="redis://redis-cluster:6379"
DEBUG=false
```

### 2. Database Setup

```bash
# For PostgreSQL
docker-compose up -d test-db
python scripts/migrate.py migrate
```

### 3. Security Considerations

- Configure proper CORS origins
- Set up SSL/TLS certificates
- Use environment-specific secrets
- Enable rate limiting
- Configure trusted hosts
- Set up monitoring and alerting

### 4. Scaling

- Use Redis cluster for cache
- Implement database read replicas
- Load balance application instances
- Monitor performance metrics

## 🛡️ Security Features

- **Rate Limiting**: IP-based request limiting
- **Input Validation**: Comprehensive data validation
- **URL Validation**: Malicious URL detection
- **Domain Blacklisting**: Configurable domain blocking
- **IP Masking**: Privacy-compliant analytics
- **CORS Protection**: Configurable origin policies

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Run tests and linting (`make test && make lint`)
6. Commit changes (`git commit -m 'Add amazing feature'`)
7. Push to branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## 📝 Development Workflow

### Code Style

```bash
# Format code
make format

# Check code style
make lint

# Fix imports
isort app/ tests/
```

### Database Changes

```bash
# Create migration for model changes
make create-migration

# Apply migrations
make migrate

# Check current database state
python scripts/migrate.py current
```

### Adding New Features

1. **Models**: Add/modify in `app/models/`
2. **Schemas**: Add Pydantic models in `app/schemas/`
3. **Services**: Implement business logic in `app/services/`
4. **APIs**: Add endpoints in `app/api/rest/`
5. **Tests**: Add tests in `tests/`
6. **Migration**: Create database migration if needed

## 📊 Performance Optimization

### Caching Strategy

- **URL Resolution**: Cached for fast redirects
- **Analytics**: Cached for 30 minutes
- **Metadata**: Cached for 24 hours
- **Rate Limits**: Cached for window duration

### Database Optimization

- **Indexes**: Optimized for common queries
- **Connection Pooling**: Async connection management
- **Query Optimization**: Efficient SQLAlchemy queries
- **Batch Operations**: Bulk inserts/updates

### Monitoring Queries

```sql
-- Most popular URLs
SELECT short_code, original_url, click_count 
FROM shortened_urls 
ORDER BY click_count DESC 
LIMIT 10;

-- Recent activity
SELECT DATE(created_at) as date, COUNT(*) as clicks
FROM url_clicks 
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date;

-- Geographic distribution
SELECT country, COUNT(*) as clicks
FROM url_clicks 
WHERE country IS NOT NULL
GROUP BY country
ORDER BY clicks DESC;
```

## 🔧 Troubleshooting

### Common Issues

**1. Database Connection Error**
```bash
# Check database status
docker-compose ps

# Check database logs
docker-compose logs db

# Reset database
docker-compose down -v
docker-compose up -d
make migrate
```

**2. Redis Connection Error**
```bash
# Check Redis status
docker-compose exec redis redis-cli ping

# Clear Redis cache
docker-compose exec redis redis-cli flushall

# Restart Redis
docker-compose restart redis
```

**3. Migration Issues**
```bash
# Check migration status
python scripts/migrate.py current

# Show migration history
python scripts/migrate.py history

# Reset to specific revision
python scripts/migrate.py downgrade <revision>
```

**4. Performance Issues**
```bash
# Check system stats
curl http://localhost:8000/api/v1/admin/stats/system

# Monitor cache performance
curl http://localhost:8000/api/v1/admin/cache/keys

# Clean expired cache
curl -X POST http://localhost:8000/api/v1/admin/maintenance/cleanup
```

### Debug Mode

```bash
# Enable debug logging
export DEBUG=true
export LOG_LEVEL=DEBUG

# Run with verbose logging
uvicorn app.main:app --log-level debug
```

## 📚 API Examples

### Python Client Example

```python
import httpx
import asyncio

async def shorten_url_example():
    async with httpx.AsyncClient() as client:
        # Shorten URL
        response = await client.post(
            "http://localhost:8000/api/v1/urls/shorten",
            json={
                "original_url": "https://example.com/very/long/url",
                "custom_code": "my-short-url",
                "expires_in_days": 30
            }
        )
        
        result = response.json()
        print(f"Short URL: {result['short_url']}")
        
        # Get analytics
        short_code = result['short_code']
        analytics = await client.get(
            f"http://localhost:8000/api/v1/analytics/{short_code}"
        )
        
        print(f"Analytics: {analytics.json()}")

# Run example
asyncio.run(shorten_url_example())
```

### cURL Examples

```bash
# Shorten URL
curl -X POST "http://localhost:8000/api/v1/urls/shorten" \
  -H "Content-Type: application/json" \
  -d '{
    "original_url": "https://example.com/page",
    "custom_code": "example"
  }'

# Access short URL (will redirect)
curl -L "http://localhost:8000/example"

# Get URL info
curl "http://localhost:8000/api/v1/urls/example/info"

# Get analytics
curl "http://localhost:8000/api/v1/analytics/example"

# Bulk shorten
curl -X POST "http://localhost:8000/api/v1/urls/bulk/shorten" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      {"original_url": "https://example1.com"},
      {"original_url": "https://example2.com"}
    ]
  }'
```

## 🔒 Security Best Practices

### Production Security Checklist

- [ ] Use HTTPS in production
- [ ] Configure proper CORS origins
- [ ] Set up rate limiting
- [ ] Enable request logging
- [ ] Use strong Redis passwords
- [ ] Implement proper secret management
- [ ] Set up monitoring and alerting
- [ ] Regular security updates
- [ ] Database connection encryption
- [ ] Input sanitization and validation

### Rate Limiting Configuration

```python
# Custom rate limits for different endpoints
RATE_LIMITS = {
    "shorten": "10/minute",
    "redirect": "100/minute", 
    "analytics": "30/minute",
    "admin": "5/minute"
}
```

## 📈 Scaling Considerations

### Horizontal Scaling

1. **Load Balancer**: Distribute requests across multiple app instances
2. **Database**: Read replicas for analytics queries
3. **Cache**: Redis cluster for high availability
4. **CDN**: Cache static assets and redirect responses

### Performance Metrics

- **Latency**: P95 < 100ms for redirects
- **Throughput**: 1000+ requests/second
- **Cache Hit Rate**: > 90% for URL resolution
- **Availability**: 99.9% uptime

## 🧰 Useful Commands

```bash
# Development
make dev                    # Start development server
make test                   # Run tests
make format                 # Format code
make lint                   # Check code style

# Database
make migrate               # Run migrations
make create-migration      # Create new migration

# Docker
make docker-build         # Build containers
make docker-up            # Start services
make docker-down          # Stop services
make logs                 # View logs

# Production
make deploy-prod          # Deploy to production
make backup-db           # Backup database
make restore-db          # Restore database
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- FastAPI for the excellent async framework
- SQLAlchemy for powerful ORM capabilities
- Redis for high-performance caching
- Pydantic for data validation
- Docker for containerization

## 📞 Support

- **Documentation**: `/api/v1/docs`
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

---

Built with ❤️ using FastAPI and modern Python async technologies.