DROP TABLE IF EXISTS calls;
DROP TABLE IF EXISTS contacts;
DROP TABLE IF EXISTS texts;
DROP TABLE IF EXISTS engagements;

CREATE TABLE calls (
  time_created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,	
	id INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
	time_scheduled TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  contact_a_id INT NOT NULL,
	contact_b_id INT NOT NULL,
  time_call_connected TIMESTAMP NULL DEFAULT NULL,
  time_call_ended TIMESTAMP NULL DEFAULT NULL,
	processor_id BIGINT UNSIGNED,
  status_detail VARCHAR(1024),
  status VARCHAR(20),
	time_dispatcher_processed TIMESTAMP NULL DEFAULT NULL,
	engagement_id INT
);

CREATE TABLE contacts (
  id INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(100),
  phone_number VARCHAR(60),
  time_created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE contacts ADD CONSTRAINT contacts_phone_unique UNIQUE KEY (phone_number);

CREATE TABLE texts (
  id INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
  contact_id INT NOT NULL,
  message VARCHAR(1024) NOT NULL,
  time_dispatcher_processed TIMESTAMP NULL DEFAULT NULL,
  time_scheduled TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status_detail VARCHAR(1024),
  status VARCHAR(20),
  processor_id BIGINT UNSIGNED,
  engagement_id INT,
  time_created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE engagements (
	id INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
  schedule_file_path VARCHAR(2048),
  time_scheduled TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,	
  time_created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	engagement_number INT NOT NULL DEFAULT 1
);

CREATE TABLE pairings (
	id INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
	contact_a_id INT NOT NULL,
	contact_b_id INT NOT NULL,
  time_created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  time_status_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	time_latest_call TIMESTAMP NULL DEFAULT NULL,
	comment MEDIUMTEXT,
	status INT NOT NULL default 1
);
ALTER TABLE pairings ADD CONSTRAINT pairing_unique UNIQUE KEY (contact_a_id, contact_b_id);

INSERT INTO pairings (contact_a_id, contact_b_id, time_latest_call)
  SELECT contact_a_id, contact_b_id, max(time_scheduled)
	FROM calls
	WHERE CONCAT(contact_a_id, contact_b_id) NOT IN (SELECT CONCAT(contact_a_id, contact_b_id) FROM pairings) GROUP BY contact_a_id, contact_b_id;
