DROP DATABASE IF EXISTS tfu3;
CREATE DATABASE tfu3;
USE tfu3;

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

CREATE TABLE sensor (
    id INT PRIMARY KEY AUTO_INCREMENT,
    activo BOOLEAN NOT NULL DEFAULT FALSE,
    roto BOOLEAN DEFAULT FALSE,
    version DECIMAL(10, 2) NOT NULL,
    ultimo_repuesto DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE sensor_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    sensor_id INT NOT NULL,
    lectura DECIMAL(10, 2) NOT NULL,
    log_fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sensor_id) REFERENCES sensor(id)
);

INSERT INTO sensor (activo, version) VALUES
(TRUE, 1.11),
(TRUE, 1.11),
(TRUE, 1.11),
(TRUE, 1.11),
(TRUE, 1.12),
(TRUE, 1.12);

INSERT INTO usuario VALUES
('operador@example.com', 'Operador', 'Operadorson', 'operador');

INSERT INTO operador VALUES
('operador@example.com');

-- operadoroperadorson
INSERT INTO login VALUES
('operador@example.com', '$2a$12$i5AMwSlTLmXSsRE2JLgv7.HGOE9ox0MCxQjEC4aoX6cAfTKmxrXAy');

DROP USER IF EXISTS 'ada2';
CREATE USER 'ada2'@'%' IDENTIFIED BY 'reallyStrongPassword123!';
GRANT ALL PRIVILEGES ON tfu3.* TO 'ada2'@'%';
FLUSH PRIVILEGES;