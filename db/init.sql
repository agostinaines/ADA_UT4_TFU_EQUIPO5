DROP DATABASE IF EXISTS auth_db;
DROP DATABASE IF EXISTS sensor_db;
DROP DATABASE IF EXISTS statistics_db;
CREATE DATABASE auth_db;
CREATE DATABASE sensor_db;
CREATE DATABASE statistics_db;

USE auth_db;

CREATE TABLE usuario (
    mail VARCHAR(320) PRIMARY KEY,
    nombre VARCHAR(32) NOT NULL CHECK ( CHAR_LENGTH(nombre) >= 3 ),
    apellido VARCHAR(32) NOT NULL CHECK ( CHAR_LENGTH(apellido) >= 3 ),
    rol ENUM('operador', 'ciudadano') NOT NULL DEFAULT 'ciudadano'
);

CREATE TABLE ciudadano (
    mail VARCHAR(320) PRIMARY KEY,
    FOREIGN KEY (mail) REFERENCES usuario(mail)
);

CREATE TABLE operador (
    mail VARCHAR(320) PRIMARY KEY,
    FOREIGN KEY (mail) REFERENCES usuario(mail)
);

CREATE TABLE login (
    mail VARCHAR(50) PRIMARY KEY,
    contrasenia VARCHAR(60) NOT NULL,
    FOREIGN KEY (mail) REFERENCES usuario(mail)
);

INSERT INTO usuario VALUES
('operador@example.com', 'Operador', 'Operadorson', 'operador');
INSERT INTO operador VALUES ('operador@example.com');
-- operadoroperadorson
INSERT INTO login VALUES
('operador@example.com', '$2a$12$i5AMwSlTLmXSsRE2JLgv7.HGOE9ox0MCxQjEC4aoX6cAfTKmxrXAy');

USE sensor_db;

CREATE TABLE sensor (
    id INT PRIMARY KEY AUTO_INCREMENT,
    activo BOOLEAN NOT NULL DEFAULT FALSE,
    roto BOOLEAN DEFAULT FALSE,
    region ENUM('Norte', 'Sur', 'Este', 'Oeste') NOT NULL,
    version DECIMAL(10, 2) NOT NULL,
    ultimo_repuesto DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
);

INSERT INTO sensor (activo, region, version) VALUES
(TRUE, 'Norte', 1.11),
(TRUE, 'Sur', 1.11),
(TRUE, 'Este', 1.11),
(TRUE, 'Oeste', 1.11),
(TRUE, 'Norte', 1.12),
(TRUE, 'Sur', 1.12);

CREATE TABLE sensor_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    sensor_id INT NOT NULL,
    lectura DECIMAL(10, 2) NOT NULL,
    log_fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sensor_id) REFERENCES sensor(id),
    INDEX idx_logs_sensor (sensor_id),
    INDEX idx_logs_fecha (log_fecha)
);

CREATE TABLE alerta (
    id VARCHAR(36) PRIMARY KEY,
    sensor_id INT NOT NULL,
    lectura DECIMAL(10, 2) NOT NULL,
    estado ENUM('pendiente', 'confirmada') NOT NULL DEFAULT 'pendiente',
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmada_en DATETIME NULL,
    FOREIGN KEY (sensor_id) REFERENCES sensor(id)
);

USE statistics_db;

CREATE TABLE monthly_region_stats (
    region ENUM('Norte', 'Sur', 'Este', 'Oeste') PRIMARY KEY,
    promedio DECIMAL(10, 2) NOT NULL,
    minimo DECIMAL(10, 2) NOT NULL,
    maximo DECIMAL(10, 2) NOT NULL,
    cantidad_lecturas BIGINT NOT NULL,
    ultima_actualizacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

DROP USER IF EXISTS 'auth_svc'@'%';
DROP USER IF EXISTS 'sensor_svc'@'%';
DROP USER IF EXISTS 'stats_svc'@'%';
CREATE USER 'auth_svc'@'%'    IDENTIFIED BY 'authSvcPassword123!';
CREATE USER 'sensor_svc'@'%'  IDENTIFIED BY 'sensorSvcPassword123!';
CREATE USER 'stats_svc'@'%' IDENTIFIED BY 'statsSvcPassword123!';
GRANT ALL PRIVILEGES ON auth_db.*    TO 'auth_svc'@'%';
GRANT ALL PRIVILEGES ON sensor_db.*  TO 'sensor_svc'@'%';
GRANT ALL PRIVILEGES ON statistics_db.* TO 'stats_svc'@'%';
FLUSH PRIVILEGES;
