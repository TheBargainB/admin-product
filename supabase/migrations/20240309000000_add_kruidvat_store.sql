-- Add Kruidvat store to the stores table
INSERT INTO stores (name, slug, base_url, logo_url) VALUES
('Kruidvat', 'kruidvat', 'https://www.kruidvat.nl', 'https://www.kruidvat.nl/logo.png')
ON CONFLICT (slug) DO NOTHING; 