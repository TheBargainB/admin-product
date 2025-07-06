-- Add Etos store to the stores table
INSERT INTO stores (name, slug, base_url, logo_url) VALUES
('Etos', 'etos', 'https://www.etos.nl', 'https://www.etos.nl/logo.png')
ON CONFLICT (slug) DO NOTHING; 