CREATE DATABASE IF NOT EXISTS workforce_ai;
USE workforce_ai;

CREATE TABLE datasets (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	version INTEGER NOT NULL, 
	filename VARCHAR(200), 
	rows_ok INTEGER, 
	rows_failed INTEGER, 
	duplicates INTEGER, 
	accuracy FLOAT, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (version)
);

CREATE TABLE departments (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(80) NOT NULL, 
	description VARCHAR(255), 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(100) NOT NULL, 
	email VARCHAR(150) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	`role` VARCHAR(20) NOT NULL, 
	employee_id INTEGER, 
	reset_token VARCHAR(100), 
	reset_expires DATETIME, 
	created_at DATETIME, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE audit_logs (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER, 
	action VARCHAR(60) NOT NULL, 
	detail VARCHAR(300), 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);

CREATE TABLE employees (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(100) NOT NULL, 
	email VARCHAR(150) NOT NULL, 
	phone VARCHAR(30), 
	title VARCHAR(80), 
	department_id INTEGER, 
	salary FLOAT NOT NULL, 
	hire_date DATE, 
	status VARCHAR(10), 
	shift VARCHAR(15), 
	age INTEGER, 
	tenure FLOAT, 
	satisfaction INTEGER, 
	overtime FLOAT, 
	performance INTEGER, 
	absences INTEGER, 
	promo_gap FLOAT, 
	risk FLOAT, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id)
);
CREATE INDEX ix_employees_risk ON employees (risk);
CREATE INDEX ix_employees_status ON employees (status);
CREATE UNIQUE INDEX ix_employees_email ON employees (email);
CREATE INDEX ix_employees_department_id ON employees (department_id);

CREATE TABLE messages (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	sender_id INTEGER NOT NULL, 
	receiver_id INTEGER NOT NULL, 
	body TEXT NOT NULL, 
	`read` BOOL, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sender_id) REFERENCES users (id), 
	FOREIGN KEY(receiver_id) REFERENCES users (id)
);
CREATE INDEX ix_messages_receiver_id ON messages (receiver_id);
CREATE INDEX ix_messages_sender_id ON messages (sender_id);

CREATE TABLE notifications (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	message VARCHAR(300) NOT NULL, 
	priority VARCHAR(10), 
	kind VARCHAR(20), 
	`read` BOOL, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE INDEX ix_notifications_created_at ON notifications (created_at);
CREATE INDEX ix_notifications_user_id ON notifications (user_id);

CREATE TABLE training_rows (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	dataset_id INTEGER NOT NULL, 
	age FLOAT, 
	tenure FLOAT, 
	salary FLOAT, 
	satisfaction FLOAT, 
	overtime FLOAT, 
	performance FLOAT, 
	absences FLOAT, 
	promo_gap FLOAT, 
	attrition INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(dataset_id) REFERENCES datasets (id)
);
CREATE INDEX ix_training_rows_dataset_id ON training_rows (dataset_id);

CREATE TABLE attendance (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER NOT NULL, 
	day DATE NOT NULL, 
	check_in DATETIME NOT NULL, 
	check_out DATETIME, 
	hours FLOAT, 
	overtime FLOAT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id)
);
CREATE INDEX ix_attendance_employee_id ON attendance (employee_id);
CREATE INDEX ix_attendance_day ON attendance (day);

CREATE TABLE documents (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER NOT NULL, 
	filename VARCHAR(200) NOT NULL, 
	`stored` VARCHAR(200) NOT NULL, 
	size INTEGER, 
	uploaded_by INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	FOREIGN KEY(uploaded_by) REFERENCES users (id)
);
CREATE INDEX ix_documents_employee_id ON documents (employee_id);

CREATE TABLE interventions (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER NOT NULL, 
	action VARCHAR(300) NOT NULL, 
	status VARCHAR(15), 
	notes TEXT, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id)
);
CREATE INDEX ix_interventions_employee_id ON interventions (employee_id);
CREATE INDEX ix_interventions_status ON interventions (status);

CREATE TABLE leaves (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER NOT NULL, 
	kind VARCHAR(15) NOT NULL, 
	start DATE NOT NULL, 
	end DATE NOT NULL, 
	days INTEGER NOT NULL, 
	reason VARCHAR(255), 
	status VARCHAR(10), 
	decided_by INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	FOREIGN KEY(decided_by) REFERENCES users (id)
);
CREATE INDEX ix_leaves_status ON leaves (status);
CREATE INDEX ix_leaves_employee_id ON leaves (employee_id);

CREATE TABLE monitor_logs (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER, 
	old_risk FLOAT, 
	new_risk FLOAT, 
	message VARCHAR(300), 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id)
);
CREATE INDEX ix_monitor_logs_employee_id ON monitor_logs (employee_id);
CREATE INDEX ix_monitor_logs_created_at ON monitor_logs (created_at);

CREATE TABLE payroll (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER NOT NULL, 
	month VARCHAR(7) NOT NULL, 
	basic FLOAT, 
	bonus FLOAT, 
	tax FLOAT, 
	net FLOAT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id)
);
CREATE INDEX ix_payroll_employee_id ON payroll (employee_id);
CREATE INDEX ix_payroll_month ON payroll (month);

CREATE TABLE predictions (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	employee_id INTEGER NOT NULL, 
	risk FLOAT NOT NULL, 
	confidence FLOAT, 
	level VARCHAR(10), 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id)
);
CREATE INDEX ix_predictions_employee_id ON predictions (employee_id);
CREATE INDEX ix_predictions_created_at ON predictions (created_at);
