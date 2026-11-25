-- AquaSense schema (MySQL 8)
CREATE DATABASE IF NOT EXISTS aquasense CHARACTER SET utf8mb4;
USE aquasense;

CREATE TABLE IF NOT EXISTS fields (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(80) NOT NULL,
  crop VARCHAR(60) NOT NULL,
  location VARCHAR(120) NOT NULL,
  latitude DECIMAL(9,6) NULL,
  longitude DECIMAL(9,6) NULL,
  boundary TEXT NULL,                           -- JSON [[lat,lng],...] of the field outline
  owner_id INT NULL,                            -- Django auth_user.id; NULL = visible to staff only
  contact_phone VARCHAR(24) NULL,               -- E.164, receives SMS / WhatsApp alerts
  language ENUM('en','hi','te') NOT NULL DEFAULT 'en',
  planted_on DATE NULL,                         -- drives crop growth-stage thresholds
  valve_mode ENUM('auto','off') NOT NULL DEFAULT 'auto',
  valve_state ENUM('closed','open') NOT NULL DEFAULT 'closed',
  valve_until DATETIME NULL,
  max_run_min INT NOT NULL DEFAULT 180,         -- safety cap for one valve run
  area_ha DECIMAL(6,2) NOT NULL DEFAULT 0.50,
  root_depth_mm INT NOT NULL DEFAULT 300,
  flow_lph INT NOT NULL DEFAULT 20000,           -- drip system flow, litres/hour
  moisture_low DECIMAL(5,2) NOT NULL DEFAULT 28, -- irrigate below this (%)
  moisture_high DECIMAL(5,2) NOT NULL DEFAULT 40,-- refill target (%)
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sensors (
  id INT AUTO_INCREMENT PRIMARY KEY,
  field_id INT NOT NULL,
  device_code VARCHAR(40) NOT NULL UNIQUE,
  device_key VARCHAR(64) NULL,                  -- per-device API key (falls back to global API_KEY if NULL)
  cal_offset DECIMAL(6,2) NOT NULL DEFAULT 0,   -- calibrated = raw * cal_scale + cal_offset
  cal_scale DECIMAL(6,3) NOT NULL DEFAULT 1,
  last_seen DATETIME NULL,
  FOREIGN KEY (field_id) REFERENCES fields(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sensor_readings (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  field_id INT NOT NULL,
  recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  soil_moisture DECIMAL(5,2) NOT NULL,
  soil_temp DECIMAL(5,2) NULL,
  air_temp DECIMAL(5,2) NULL,
  humidity DECIMAL(5,2) NULL,
  battery DECIMAL(5,2) NULL,
  predicted_6h DECIMAL(5,2) NULL,
  INDEX idx_field_time (field_id, recorded_at),
  FOREIGN KEY (field_id) REFERENCES fields(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS irrigation_schedules (
  id INT AUTO_INCREMENT PRIMARY KEY,
  field_id INT NOT NULL,
  scheduled_for DATETIME NOT NULL,
  duration_min INT NOT NULL,
  volume_l INT NOT NULL,
  source ENUM('ai','manual') NOT NULL DEFAULT 'ai',
  status ENUM('pending','running','done','skipped') NOT NULL DEFAULT 'pending',
  reason VARCHAR(255) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (field_id) REFERENCES fields(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alerts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  field_id INT NOT NULL,
  level ENUM('info','warning','critical') NOT NULL DEFAULT 'info',
  message VARCHAR(255) NOT NULL,
  is_read TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (field_id) REFERENCES fields(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS valve_commands (
  id INT AUTO_INCREMENT PRIMARY KEY,
  field_id INT NOT NULL,
  action ENUM('open','close') NOT NULL,
  duration_min INT NULL,
  source VARCHAR(20) NOT NULL DEFAULT 'manual',
  status ENUM('pending','sent','done','failed') NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (field_id) REFERENCES fields(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
  id INT AUTO_INCREMENT PRIMARY KEY,
  field_id INT NOT NULL,
  phone VARCHAR(24) NULL,
  channel VARCHAR(12) NOT NULL,
  message VARCHAR(500) NOT NULL,
  status VARCHAR(12) NOT NULL,                  -- sent | logged | failed
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (field_id) REFERENCES fields(id) ON DELETE CASCADE
);

-- Demo data
INSERT INTO fields (name, crop, location, latitude, longitude, area_ha, moisture_low, moisture_high) VALUES
 ('North Terrace', 'Millet',    'Kutch, Gujarat',     23.7337, 69.8597, 0.60, 26, 38),
 ('River Bend',    'Tomato',    'Anantapur, AP',      14.6819, 77.6006, 0.35, 30, 42),
 ('Hill Plot',     'Groundnut', 'Jodhpur, Rajasthan', 26.2389, 73.0243, 0.80, 24, 36);
INSERT INTO sensors (field_id, device_code) VALUES (1,'SM-NT-001'),(2,'SM-RB-002'),(3,'SM-HP-003');

-- Upgrading an existing v1 database? Run database/upgrade_v2.sql
