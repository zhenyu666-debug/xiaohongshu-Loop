CREATE CATALOG iceberg_catalog WITH (connector = "jdbc", jdbc.url = "jdbc:postgresql://postgres:5432/iceberg_catalog", jdbc.user = "admin", jdbc.password = "password");
USE CATALOG iceberg_catalog;
CREATE DATABASE IF NOT EXISTS `default`;