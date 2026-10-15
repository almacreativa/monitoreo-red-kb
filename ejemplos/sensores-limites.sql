-- Límites de temperatura según el dato del fabricante (salida de `sensors`: high / crit),
-- en vez del default de LibreNMS ("valor al descubrir + 20"). Ver docs/07 y gotchas 26, 33, 34.
-- Se identifican por equipo + descripción (no por índice: net-snmp renumera LM-SENSORS).
-- sensor_custom='Yes' evita que discovery los pise. Idempotente. Ajustar device_id y valores.

-- CPU (coretemp): warn = high del fabricante, límite = crit
UPDATE sensors s JOIN (
  SELECT 101 d, 80 w, 100 l UNION ALL   -- SRV-01: high 80 / crit 100
  SELECT 102,   94,   100               -- SRV-02: high 94 / crit 100
) m ON m.d = s.device_id
SET s.sensor_limit_warn = m.w, s.sensor_limit = m.l, s.sensor_limit_low = 5, s.sensor_limit_low_warn = NULL, s.sensor_custom = 'Yes'
WHERE s.sensor_class = 'temperature' AND s.sensor_type = 'lmsensors'
  AND s.sensor_descr REGEXP '^(Package id [0-9]+|Core [0-9]+)$';

-- Disco NVMe (crit típico ~85 °C): aviso temprano 70, límite 84
UPDATE sensors SET sensor_limit_warn = 70, sensor_limit = 84, sensor_limit_low = 5, sensor_limit_low_warn = NULL, sensor_custom = 'Yes'
WHERE device_id IN (101, 102) AND sensor_class = 'temperature' AND sensor_type = 'lmsensors'
  AND sensor_descr REGEXP '^(Composite|Sensor [0-9]+)$';

-- Resto de sensores de placa sin dato de fabricante: 70 / 85
UPDATE sensors SET sensor_limit_warn = 70, sensor_limit = 85, sensor_limit_low = 5, sensor_limit_low_warn = NULL, sensor_custom = 'Yes'
WHERE device_id IN (101, 102) AND sensor_class = 'temperature' AND sensor_type = 'lmsensors'
  AND sensor_descr NOT REGEXP '^(Package id [0-9]+|Core [0-9]+|Composite|Sensor [0-9]+)$';
