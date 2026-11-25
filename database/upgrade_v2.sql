-- Upgrade a database created with the first AquaSense schema.
-- Safe to run once. If a column already exists (e.g. latitude), delete that line and re-run.
USE aquasense;
ALTER TABLE fields
  ADD latitude DECIMAL(9,6) NULL AFTER location,
  ADD longitude DECIMAL(9,6) NULL AFTER latitude,
  ADD boundary TEXT NULL AFTER longitude,
  ADD owner_id INT NULL,
  ADD contact_phone VARCHAR(24) NULL,
  ADD language ENUM('en','hi','te') NOT NULL DEFAULT 'en',
  ADD planted_on DATE NULL,
  ADD valve_mode ENUM('auto','off') NOT NULL DEFAULT 'auto',
  ADD valve_state ENUM('closed','open') NOT NULL DEFAULT 'closed',
  ADD valve_until DATETIME NULL,
  ADD max_run_min INT NOT NULL DEFAULT 180;
ALTER TABLE fields MODIFY flow_lph INT NOT NULL DEFAULT 20000;
ALTER TABLE sensors
  ADD device_key VARCHAR(64) NULL,
  ADD cal_offset DECIMAL(6,2) NOT NULL DEFAULT 0,
  ADD cal_scale DECIMAL(6,3) NOT NULL DEFAULT 1,
  ADD last_seen DATETIME NULL;
ALTER TABLE irrigation_schedules MODIFY status ENUM('pending','running','done','skipped') NOT NULL DEFAULT 'pending';
CREATE TABLE IF NOT EXISTS valve_commands (
  id INT AUTO_INCREMENT PRIMARY KEY, field_id INT NOT NULL, action ENUM('open','close') NOT NULL,
  duration_min INT NULL, source VARCHAR(20) NOT NULL DEFAULT 'manual',
  status ENUM('pending','sent','done','failed') NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (field_id) REFERENCES fields(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS notifications (
  id INT AUTO_INCREMENT PRIMARY KEY, field_id INT NOT NULL, phone VARCHAR(24) NULL, channel VARCHAR(12) NOT NULL,
  message VARCHAR(500) NOT NULL, status VARCHAR(12) NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (field_id) REFERENCES fields(id) ON DELETE CASCADE);
