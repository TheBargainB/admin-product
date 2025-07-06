-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_stat_statements for query performance monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Stores table
CREATE TABLE stores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(100) NOT NULL,
  slug VARCHAR(50) UNIQUE NOT NULL,
  logo_url TEXT,
  base_url TEXT,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

-- Categories table
CREATE TABLE categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(100) NOT NULL,
  slug VARCHAR(100) UNIQUE NOT NULL,
  parent_id UUID REFERENCES categories(id),
  description TEXT,
  created_at TIMESTAMP DEFAULT now()
);

-- Products table
CREATE TABLE products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(200) NOT NULL,
  normalized_name VARCHAR(200) NOT NULL,
  brand VARCHAR(100),
  category_id UUID REFERENCES categories(id),
  barcode VARCHAR(50),
  unit_type VARCHAR(20), -- 'kg', 'liter', 'piece', etc.
  unit_size DECIMAL(10,3),
  description TEXT,
  image_url TEXT,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

-- Store Products (linking products to stores)
CREATE TABLE store_products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id UUID REFERENCES stores(id),
  product_id UUID REFERENCES products(id),
  store_product_id VARCHAR(100), -- Store's internal product ID
  store_url TEXT,
  is_available BOOLEAN DEFAULT true,
  last_seen TIMESTAMP DEFAULT now(),
  created_at TIMESTAMP DEFAULT now(),
  UNIQUE(store_id, product_id)
);

-- Price History table
CREATE TABLE price_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  store_product_id UUID REFERENCES store_products(id),
  price DECIMAL(10,2) NOT NULL,
  original_price DECIMAL(10,2), -- Before discount
  discount_percentage DECIMAL(5,2),
  is_promotion BOOLEAN DEFAULT false,
  promotion_text TEXT,
  scraped_at TIMESTAMP DEFAULT now(),
  created_at TIMESTAMP DEFAULT now()
);

-- Current Prices (for quick access)
CREATE TABLE current_prices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  store_product_id UUID REFERENCES store_products(id),
  price DECIMAL(10,2) NOT NULL,
  original_price DECIMAL(10,2),
  discount_percentage DECIMAL(5,2),
  is_promotion BOOLEAN DEFAULT false,
  promotion_text TEXT,
  last_updated TIMESTAMP DEFAULT now(),
  UNIQUE(store_product_id)
);

-- Scraping Jobs table
CREATE TABLE scraping_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id UUID REFERENCES stores(id),
  job_type VARCHAR(50) NOT NULL, -- 'full_scrape', 'price_update', 'validation'
  status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  products_processed INTEGER DEFAULT 0,
  products_updated INTEGER DEFAULT 0,
  errors_count INTEGER DEFAULT 0,
  error_details JSONB,
  created_at TIMESTAMP DEFAULT now()
);

-- System Logs table
CREATE TABLE system_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  level VARCHAR(20) NOT NULL, -- 'info', 'warning', 'error', 'critical'
  message TEXT NOT NULL,
  component VARCHAR(100), -- 'scraper', 'processor', 'database', etc.
  store_id UUID REFERENCES stores(id),
  job_id UUID REFERENCES scraping_jobs(id),
  metadata JSONB,
  created_at TIMESTAMP DEFAULT now()
);

-- Performance indexes
-- Price history indexes
CREATE INDEX idx_price_history_store_product ON price_history(store_product_id);
CREATE INDEX idx_price_history_scraped_at ON price_history(scraped_at);

-- Current prices indexes
CREATE INDEX idx_current_prices_store_product ON current_prices(store_product_id);
CREATE INDEX idx_current_prices_price ON current_prices(price);

-- Products indexes
CREATE INDEX idx_products_normalized_name ON products(normalized_name);
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_brand ON products(brand);
CREATE INDEX idx_products_barcode ON products(barcode);

-- Store products indexes
CREATE INDEX idx_store_products_store ON store_products(store_id);
CREATE INDEX idx_store_products_product ON store_products(product_id);
CREATE INDEX idx_store_products_available ON store_products(is_available);

-- Scraping jobs indexes
CREATE INDEX idx_scraping_jobs_store ON scraping_jobs(store_id);
CREATE INDEX idx_scraping_jobs_status ON scraping_jobs(status);
CREATE INDEX idx_scraping_jobs_created ON scraping_jobs(created_at);

-- System logs indexes
CREATE INDEX idx_system_logs_level ON system_logs(level);
CREATE INDEX idx_system_logs_component ON system_logs(component);
CREATE INDEX idx_system_logs_created ON system_logs(created_at);

-- Full text search index for products
CREATE INDEX idx_products_search ON products USING gin(to_tsvector('english', name || ' ' || COALESCE(description, '') || ' ' || COALESCE(brand, '')));

-- Add triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_stores_updated_at BEFORE UPDATE ON stores FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_products_updated_at BEFORE UPDATE ON products FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- Insert initial store data
INSERT INTO stores (name, slug, base_url, logo_url) VALUES
('Albert Heijn', 'albert_heijn', 'https://www.ah.nl', 'https://ah.nl/logo.png'),
('Dirk', 'dirk', 'https://www.dirk.nl', 'https://dirk.nl/logo.png'),
('Hoogvliet', 'hoogvliet', 'https://www.hoogvliet.com', 'https://hoogvliet.com/logo.png'),
('Jumbo', 'jumbo', 'https://www.jumbo.com', 'https://jumbo.com/logo.png');

-- Insert initial categories
INSERT INTO categories (name, slug, description) VALUES
('Dairy & Eggs', 'dairy-eggs', 'Milk, cheese, yogurt, and egg products'),
('Meat & Fish', 'meat-fish', 'Fresh meat, poultry, and seafood'),
('Fruits & Vegetables', 'fruits-vegetables', 'Fresh produce and organic options'),
('Bread & Bakery', 'bread-bakery', 'Fresh bread, pastries, and bakery items'),
('Pantry', 'pantry', 'Canned goods, pasta, rice, and dry goods'),
('Frozen Foods', 'frozen-foods', 'Frozen meals, ice cream, and frozen vegetables'),
('Beverages', 'beverages', 'Soft drinks, juices, coffee, and tea'),
('Snacks & Sweets', 'snacks-sweets', 'Chips, cookies, candy, and snack foods'),
('Health & Beauty', 'health-beauty', 'Personal care and health products'),
('Household', 'household', 'Cleaning supplies and household items'),
('Baby & Kids', 'baby-kids', 'Baby food, diapers, and children products'),
('Pet Supplies', 'pet-supplies', 'Pet food and accessories');

-- Enable Row Level Security (RLS) on sensitive tables
ALTER TABLE stores ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE current_prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraping_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_logs ENABLE ROW LEVEL SECURITY;

-- Create policies for public read access
CREATE POLICY "Public read access on stores" ON stores FOR SELECT USING (true);
CREATE POLICY "Public read access on categories" ON categories FOR SELECT USING (true);
CREATE POLICY "Public read access on products" ON products FOR SELECT USING (true);
CREATE POLICY "Public read access on store_products" ON store_products FOR SELECT USING (true);
CREATE POLICY "Public read access on current_prices" ON current_prices FOR SELECT USING (true);
CREATE POLICY "Public read access on price_history" ON price_history FOR SELECT USING (true);

-- Admin policies (will be configured with proper authentication later)
CREATE POLICY "Admin full access on stores" ON stores FOR ALL USING (auth.jwt() ->> 'role' = 'admin');
CREATE POLICY "Admin full access on scraping_jobs" ON scraping_jobs FOR ALL USING (auth.jwt() ->> 'role' = 'admin');
CREATE POLICY "Admin full access on system_logs" ON system_logs FOR ALL USING (auth.jwt() ->> 'role' = 'admin'); 