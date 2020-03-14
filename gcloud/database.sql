CREATE TABLE calls (
  time_created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,	
	id INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
	time_scheduled TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  contact_a_id INT NOT NULL,
	contact_b_id INT NOT NULL,
  time_call_connected TIMESTAMP NULL DEFAULT NULL,
  time_call_ended TIMESTAMP NULL DEFAULT NULL,
	processor_id BIGINT UNSIGNED,
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
  message VARCHAR(160) NOT NULL,
  time_dispatcher_processed TIMESTAMP NULL DEFAULT NULL,
  time_scheduled TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  text_status_detail VARCHAR(1024),
  text_status INT,
  processor_id BIGINT UNSIGNED,
  engagement_id INT,
  time_created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);