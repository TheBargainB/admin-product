# BargainB - Grocery Price Scraping Admin Panel

> A comprehensive Next.js admin panel for managing grocery price scraping across major Dutch supermarkets, powered by Python/LangGraph agents and Supabase.

## 🎯 Project Overview

BargainB is an intelligent grocery price monitoring system that automatically scrapes product data and prices from major Dutch supermarkets including Dirk, Albert Heijn, Hoogvliet, and Jumbo. The system features a modern React-based admin panel for managing scraping operations and a sophisticated Python backend with LangGraph agents for autonomous data processing.

### Key Features

- 🏪 **Multi-Store Support**: Scrapes from all major Dutch supermarkets
- 🤖 **Intelligent Agents**: LangGraph-powered autonomous scraping and processing
- 📊 **Real-time Dashboard**: Live monitoring of scraping operations and system health
- 💾 **Robust Database**: Supabase-powered with comprehensive product and pricing data
- 🔄 **Incremental Updates**: Smart change detection for efficient daily price updates
- 📈 **Price Analytics**: Historical price tracking and comparison tools
- 🛡️ **Error Recovery**: Intelligent error handling and automatic retry mechanisms

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ and npm/yarn/pnpm
- Python 3.11+ with pip
- Supabase account and project
- Git for version control

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/your-username/bargainb-admin.git
cd bargainb-admin
```

2. **Set up environment variables**
```bash
cp .env.example .env.local
# Edit .env.local with your Supabase credentials
```

3. **Install dependencies**
```bash
# Frontend dependencies
npm install

# Backend dependencies
cd backend
pip install -r requirements.txt
```

4. **Initialize the database**
```bash
# Run database migrations
npm run db:setup
```

5. **Start the development servers**
```bash
# Terminal 1: Start the Next.js admin panel
npm run dev

# Terminal 2: Start the Python backend
cd backend
python main.py
```

6. **Access the application**
   - Admin Panel: http://localhost:3000
   - API Documentation: http://localhost:8000/docs

## 📁 Project Structure

```
bargainb-admin/
├── README.md                          # This file
├── PROJECT_PLAN.md                    # Detailed project planning and roadmap
├── docs/                              # Documentation directory
│   ├── ARCHITECTURE.md               # LangGraph agents architecture
│   ├── DATABASE_SETUP.md             # Supabase setup and configuration
│   ├── API_REFERENCE.md              # API endpoints documentation
│   ├── DEPLOYMENT.md                 # Production deployment guide
│   └── TROUBLESHOOTING.md            # Common issues and solutions
├── frontend/                          # Next.js admin panel
│   ├── app/                          # App router pages
│   ├── components/                   # React components
│   ├── lib/                          # Utilities and configurations
│   └── public/                       # Static assets
├── backend/                           # Python/LangGraph backend
│   ├── agents/                       # LangGraph agent implementations
│   ├── scrapers/                     # Store-specific scrapers
│   ├── database/                     # Database operations
│   └── utils/                        # Shared utilities
└── scripts/                          # Setup and maintenance scripts
```

## 🏗️ System Architecture

BargainB follows a modern microservices architecture:

- **Frontend**: Next.js 14 with App Router, React Server Components, and Tailwind CSS
- **Backend**: Python with FastAPI and LangGraph for intelligent agent coordination
- **Database**: Supabase (PostgreSQL) with real-time subscriptions
- **Authentication**: Supabase Auth with Row Level Security
- **Deployment**: Vercel (frontend) + Railway/Fly.io (backend)

### Agent Architecture

The system employs specialized LangGraph agents:

- **Master Orchestrator**: Coordinates all scraping activities and system health
- **Store Scrapers**: Individual agents for each supermarket (Dirk, AH, Hoogvliet, Jumbo)
- **Data Processors**: Product standardization, price validation, and categorization
- **Database Managers**: Optimized data insertion and relationship management

## 📊 Current Status

### ✅ Completed
- [x] Scrapers for all target stores (Dirk, Albert Heijn, Hoogvliet, Jumbo)
- [x] Full product catalog scraping and data processing
- [x] Supabase database schema and setup
- [x] LangGraph agent architecture design
- [x] Project documentation and planning

### 🔄 In Progress
- [ ] Next.js admin panel development
- [ ] Agent implementation and integration
- [ ] Real-time dashboard and monitoring
- [ ] API development and testing

### 📋 Planned
- [ ] Production deployment and optimization
- [ ] Advanced analytics and reporting
- [ ] Mobile app for price comparison
- [ ] Public API for third-party integrations

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Project Plan](PROJECT_PLAN.md) | Comprehensive project overview, roadmap, and technical specifications |
| [Architecture](docs/ARCHITECTURE.md) | Detailed LangGraph agents architecture and implementation |
| [Database Setup](docs/DATABASE_SETUP.md) | Supabase configuration, schema, and setup instructions |
| [API Reference](docs/API_REFERENCE.md) | Complete API endpoint documentation |
| [Deployment Guide](docs/DEPLOYMENT.md) | Production deployment instructions |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and solutions |

## 🛠️ Development

### Running Tests
```bash
# Frontend tests
npm run test

# Backend tests
cd backend
pytest
```

### Code Quality
```bash
# Lint frontend code
npm run lint

# Format backend code
cd backend
black .
flake8 .
```

### Database Operations
```bash
# Reset database
npm run db:reset

# Generate types
npm run db:types

# Run migrations
npm run db:migrate
```

## 🚀 Deployment

### Development
The project is configured for easy local development with hot reloading and automatic database migrations.

### Production
- **Frontend**: Deploy to Vercel with automatic builds from main branch
- **Backend**: Deploy to Railway or Fly.io with Docker containerization
- **Database**: Supabase managed PostgreSQL with automatic backups

See [Deployment Guide](docs/DEPLOYMENT.md) for detailed instructions.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please read our [Contributing Guidelines](CONTRIBUTING.md) for details on our code of conduct and development process.

## 📊 Performance & Scale

- **Product Coverage**: 100k+ products across all stores
- **Update Frequency**: Daily price updates, weekly full validations
- **Response Time**: Sub-second search and filtering
- **Uptime Target**: 99.9% availability
- **Data Accuracy**: 99%+ price accuracy with validation

## 🔐 Security

- Environment variables for all sensitive data
- Row Level Security (RLS) policies in Supabase
- API rate limiting and authentication
- Regular security audits and dependency updates

## 📈 Roadmap

### Phase 1: Core Platform (Weeks 1-4)
- Complete admin panel development
- Implement all LangGraph agents
- Basic monitoring and alerting

### Phase 2: Advanced Features (Weeks 5-8)
- Price analytics and comparison tools
- Advanced error handling and recovery
- Performance optimization

### Phase 3: Scale & Expand (Weeks 9-12)
- Mobile application
- Public API development
- Additional store integrations

See [Project Plan](PROJECT_PLAN.md) for detailed timeline and milestones.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 💡 Support

- 📧 Email: support@bargainb.nl
- 💬 Discord: [BargainB Community](https://discord.gg/bargainb)
- 📖 Wiki: [Project Wiki](https://github.com/your-username/bargainb-admin/wiki)
- 🐛 Issues: [GitHub Issues](https://github.com/your-username/bargainb-admin/issues)

## 🙏 Acknowledgments

- Dutch supermarket chains for their publicly accessible product data
- LangGraph team for the agent framework
- Supabase for the backend-as-a-service platform
- Next.js and React communities for the frontend framework

---

**Made with ❤️ in the Netherlands** 🇳🇱 