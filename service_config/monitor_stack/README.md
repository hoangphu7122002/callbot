
# Grafana & Prometheus Monitoring Stack

This is a complete monitoring stack based on Prometheus and Grafana, configured with Docker Compose.

## Components Overview

The monitoring stack consists of these key components:

1. **Prometheus**: Time-series database and monitoring system that collects and stores metrics
2. **Grafana**: Visualization and analytics platform to create dashboards from the metrics
3. **AlertManager**: Handles alerts sent by Prometheus and manages notifications
4. **Node Exporter**: Collects system-level metrics from the host machine
5. **cAdvisor**: Provides container resource usage and performance metrics

## Prerequisites

- Docker and Docker Compose installed
- Ports 3000, 9090, 9093, 9100, and 8080 available

## Quick Start

1. Clone this repository:
   ```
   git clone <your-repository>
   cd <directory>
   ```

2. Start the stack:
   ```
   docker-compose up -d
   ```

3. Access the interfaces:
   - Grafana: http://localhost:3000 (username: admin, password: admin)
   - Prometheus: http://localhost:9090
   - AlertManager: http://localhost:9093
   - Node Exporter: http://localhost:9100
   - cAdvisor: http://localhost:8080

## Docker Compose Configuration

The `docker-compose.yml` file includes:
- Proper networking between all services
- Persistent volumes for Prometheus, Grafana, and AlertManager data
- Exposed ports for web interfaces
- Mounted configuration files
- Container health dependencies
- Environment variables for customization

## Prometheus Configuration

The `prometheus.yml` configuration includes:
- Optimized scraping intervals (15s)
- Integration with AlertManager for alert handling
- Rule file loading for alert definitions
- Scrape configurations for all services:
  - Prometheus itself
  - Node Exporter for host metrics
  - cAdvisor for container metrics
  - Ability to add custom application targets

## Alert Rules

The alert rules defined in `alert_rules.yml` cover:

### System Monitoring
- High CPU load alerts (> 80% for 5 minutes)
- High memory usage alerts (> 85% for 5 minutes)
- High disk usage alerts (> 85% for 5 minutes)

### Container Monitoring
- Container CPU usage alerts (> 80% for 5 minutes)
- Container memory usage alerts (> 80% for 5 minutes)

## AlertManager Configuration

The AlertManager is configured with:
- Basic notification receivers
- Alert grouping by name and job
- Configurable notification intervals
- Templates for notification customization
- Ability to add various notification channels (email, Slack, webhooks)

## Grafana Configuration

Grafana is configured with:
- Automatic Prometheus data source provisioning
- Pre-configured dashboards for system metrics
- Dashboard provisioning system
- Default admin credentials (customizable via environment variables)

## Pre-configured Dashboard

The Node Exporter dashboard includes panels for:
- CPU usage
- Memory usage
- Disk usage
- System load (1m, 5m, 15m)

## Directory Structure

```
monitor_stack/
├── docker-compose.yml
├── prometheus/
│   ├── prometheus.yml
│   └── rules/
│       └── alert_rules.yml
├── alertmanager/
│   └── config.yml
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── datasource.yml
│   │   └── dashboards/
│   │       └── dashboards.yml
│   └── dashboards/
│       └── node-exporter-dashboard.json
└── README.md
```

## Customization

### Adding More Exporters
You can add additional monitoring targets by updating the Prometheus scrape configurations.

### Alert Configuration
You can customize alert rules in `prometheus/rules/alert_rules.yml` and configure notification channels in `alertmanager/config.yml`.

### Adding More Dashboards
You can import additional dashboards through the Grafana interface or add them as JSON files in `grafana/dashboards/`.

## Maintenance

- **Update images**: `docker-compose pull && docker-compose up -d`
- **Restart the stack**: `docker-compose restart`
- **Stop the stack**: `docker-compose down`
- **Remove volumes**: `docker-compose down -v` 