# API Reference

This document provides a comprehensive reference for all API endpoints in the BargainB system.

## Base URLs

- **Development**: `http://localhost:8000`
- **Production**: `https://api.bargainb.nl`

## Authentication

All API endpoints require authentication using Bearer tokens.

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" https://api.bargainb.nl/api/endpoint
```

## Agent Management

### Start Scraping Operation

Start a scraping job for a specific store.

**Endpoint**: `POST /api/agents/start-scraping`

**Request Body**:
```json
{
  "store": "albert_heijn",
  "scrape_type": "price_update"
}
```

**Parameters**:
- `store` (string): Store identifier (`dirk`, `albert_heijn`, `hoogvliet`, `jumbo`)
- `scrape_type` (string): Type of scrape (`full_scrape`, `price_update`, `validation`)

**Response**:
```json
{
  "success": true,
  "job_id": "job_123456789",
  "estimated_duration": 300,
  "message": "Scraping job started successfully"
}
```

### Get Agent Status

Retrieve the current status of all agents.

**Endpoint**: `GET /api/agents/status`

**Response**:
```json
{
  "orchestrator": {
    "status": "running",
    "active_jobs": 2,
    "last_health_check": "2024-01-15T10:30:00Z"
  },
  "scrapers": {
    "dirk": {
      "status": "idle",
      "last_run": "2024-01-15T09:00:00Z",
      "success_rate": 0.98
    },
    "albert_heijn": {
      "status": "running",
      "current_job": "job_123456789",
      "progress": 0.45
    }
  }
}
```

### Stop Agent

Stop a specific agent or job.

**Endpoint**: `POST /api/agents/stop`

**Request Body**:
```json
{
  "agent_id": "dirk_scraper"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Agent stopped successfully"
}
```

## Product Management

### Search Products

Search for products across all stores.

**Endpoint**: `GET /api/products/search`

**Query Parameters**:
- `q` (string): Search query
- `store` (string, optional): Filter by store
- `category` (string, optional): Filter by category
- `min_price` (number, optional): Minimum price filter
- `max_price` (number, optional): Maximum price filter
- `page` (number, optional): Page number (default: 1)
- `limit` (number, optional): Results per page (default: 20, max: 100)

**Response**:
```json
{
  "products": [
    {
      "id": "prod_123",
      "name": "Nutrilon Baby Formula",
      "normalized_name": "nutrilon baby formula",
      "brand": "Nutrilon",
      "category": "Baby Food",
      "prices": [
        {
          "store": "albert_heijn",
          "price": 15.99,
          "last_updated": "2024-01-15T10:00:00Z"
        }
      ]
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 150,
    "pages": 8
  }
}
```

### Get Product Details

Get detailed information about a specific product.

**Endpoint**: `GET /api/products/{product_id}`

**Response**:
```json
{
  "id": "prod_123",
  "name": "Nutrilon Baby Formula",
  "description": "Premium baby formula for infants",
  "brand": "Nutrilon",
  "category": "Baby Food",
  "barcode": "8710398541234",
  "unit_type": "piece",
  "unit_size": 800,
  "image_url": "https://example.com/image.jpg",
  "stores": [
    {
      "store_id": "albert_heijn",
      "store_name": "Albert Heijn",
      "current_price": 15.99,
      "original_price": 17.99,
      "discount_percentage": 11.1,
      "is_promotion": true,
      "promotion_text": "2e product halve prijs",
      "last_updated": "2024-01-15T10:00:00Z",
      "in_stock": true
    }
  ],
  "price_history": [
    {
      "store": "albert_heijn",
      "price": 15.99,
      "date": "2024-01-15"
    }
  ]
}
```

## Price Management

### Get Price History

Retrieve price history for a product across all stores.

**Endpoint**: `GET /api/prices/history/{product_id}`

**Query Parameters**:
- `store` (string, optional): Filter by store
- `days` (number, optional): Number of days to retrieve (default: 30)

**Response**:
```json
{
  "product_id": "prod_123",
  "price_history": [
    {
      "store": "albert_heijn",
      "price": 15.99,
      "original_price": 17.99,
      "is_promotion": true,
      "date": "2024-01-15T10:00:00Z"
    }
  ],
  "statistics": {
    "current_lowest": 15.99,
    "current_highest": 18.50,
    "average_price": 16.75,
    "price_volatility": 0.12
  }
}
```

### Get Price Alerts

Retrieve price change alerts.

**Endpoint**: `GET /api/prices/alerts`

**Query Parameters**:
- `severity` (string, optional): Filter by severity (`low`, `medium`, `high`)
- `store` (string, optional): Filter by store
- `limit` (number, optional): Number of alerts to retrieve

**Response**:
```json
{
  "alerts": [
    {
      "id": "alert_123",
      "product_id": "prod_123",
      "store": "albert_heijn",
      "alert_type": "price_increase",
      "severity": "high",
      "old_price": 15.99,
      "new_price": 18.99,
      "percentage_change": 18.8,
      "created_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

## Store Management

### Get Stores

List all supported stores.

**Endpoint**: `GET /api/stores`

**Response**:
```json
{
  "stores": [
    {
      "id": "albert_heijn",
      "name": "Albert Heijn",
      "logo_url": "https://example.com/ah_logo.png",
      "base_url": "https://www.ah.nl",
      "is_active": true,
      "last_scrape": "2024-01-15T09:00:00Z",
      "product_count": 25000
    }
  ]
}
```

### Update Store Configuration

Update scraping configuration for a store.

**Endpoint**: `PUT /api/stores/{store_id}/config`

**Request Body**:
```json
{
  "rate_limit": 2.0,
  "retry_attempts": 3,
  "schedule": "0 9 * * *",
  "is_active": true
}
```

**Response**:
```json
{
  "success": true,
  "message": "Store configuration updated successfully"
}
```

## System Monitoring

### Get System Health

Retrieve overall system health status.

**Endpoint**: `GET /api/system/health`

**Response**:
```json
{
  "status": "healthy",
  "uptime": 86400,
  "agents": {
    "total": 8,
    "running": 6,
    "idle": 2,
    "error": 0
  },
  "database": {
    "status": "connected",
    "response_time": 45
  },
  "metrics": {
    "products_updated_today": 15000,
    "successful_scrapes": 98.5,
    "error_rate": 0.02
  }
}
```

### Get System Metrics

Retrieve detailed system metrics.

**Endpoint**: `GET /api/system/metrics`

**Query Parameters**:
- `period` (string): Time period (`1h`, `24h`, `7d`, `30d`)

**Response**:
```json
{
  "period": "24h",
  "metrics": {
    "scraping_performance": {
      "total_jobs": 48,
      "successful_jobs": 47,
      "failed_jobs": 1,
      "average_duration": 180
    },
    "data_quality": {
      "products_processed": 45000,
      "validation_errors": 23,
      "duplicate_rate": 0.001
    },
    "system_resources": {
      "cpu_usage": 65.2,
      "memory_usage": 78.5,
      "disk_usage": 45.1
    }
  }
}
```

### Get System Logs

Retrieve system logs with filtering.

**Endpoint**: `GET /api/system/logs`

**Query Parameters**:
- `level` (string, optional): Log level (`info`, `warning`, `error`, `critical`)
- `component` (string, optional): System component
- `limit` (number, optional): Number of logs to retrieve (default: 100)
- `from` (string, optional): Start date (ISO 8601)
- `to` (string, optional): End date (ISO 8601)

**Response**:
```json
{
  "logs": [
    {
      "id": "log_123",
      "level": "info",
      "message": "Scraping job completed successfully",
      "component": "albert_heijn_scraper",
      "timestamp": "2024-01-15T10:00:00Z",
      "metadata": {
        "job_id": "job_123456789",
        "products_processed": 1500
      }
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 100,
    "total": 5000
  }
}
```

## Data Management

### Export Data

Export product or pricing data.

**Endpoint**: `POST /api/data/export`

**Request Body**:
```json
{
  "type": "products",
  "format": "csv",
  "filters": {
    "store": "albert_heijn",
    "category": "baby_food"
  }
}
```

**Response**:
```json
{
  "export_id": "export_123",
  "status": "processing",
  "estimated_completion": "2024-01-15T10:05:00Z",
  "download_url": null
}
```

### Get Export Status

Check the status of a data export.

**Endpoint**: `GET /api/data/export/{export_id}`

**Response**:
```json
{
  "export_id": "export_123",
  "status": "completed",
  "file_size": 1048576,
  "download_url": "https://api.bargainb.nl/downloads/export_123.csv",
  "expires_at": "2024-01-16T10:00:00Z"
}
```

## Error Codes

| Code | Message | Description |
|------|---------|-------------|
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | System maintenance or overload |

## Rate Limiting

API requests are limited to prevent abuse:

- **Authenticated users**: 1000 requests per hour
- **Admin users**: 5000 requests per hour
- **System integrations**: 10000 requests per hour

Rate limit headers are included in all responses:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642248000
```

## Webhooks

The system supports webhooks for real-time notifications:

### Price Change Webhook

Triggered when significant price changes are detected.

**Payload**:
```json
{
  "event": "price_change",
  "product_id": "prod_123",
  "store": "albert_heijn",
  "old_price": 15.99,
  "new_price": 18.99,
  "percentage_change": 18.8,
  "timestamp": "2024-01-15T10:00:00Z"
}
```

### System Alert Webhook

Triggered for system-level alerts and errors.

**Payload**:
```json
{
  "event": "system_alert",
  "severity": "high",
  "component": "albert_heijn_scraper",
  "message": "Scraper failed after 3 retry attempts",
  "timestamp": "2024-01-15T10:00:00Z"
}
```

## SDKs and Libraries

Official SDKs are available for popular programming languages:

- **JavaScript/TypeScript**: `@bargainb/js-sdk`
- **Python**: `bargainb-python`
- **PHP**: `bargainb/php-sdk`

Example usage with JavaScript SDK:

```javascript
import { BargainB } from '@bargainb/js-sdk';

const client = new BargainB({
  apiKey: 'your-api-key',
  baseUrl: 'https://api.bargainb.nl'
});

const products = await client.products.search('baby formula');
``` 