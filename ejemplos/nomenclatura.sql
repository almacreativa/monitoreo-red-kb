-- Nomenclatura de equipos del LAB: display = "SITIO-ROL-NN · nombre".
-- Ver docs/05-nomenclatura.md. Idempotente. Ajustar los device_id a tu instancia.
-- Recrear: docker exec -i librenms_db sh -c 'exec mariadb -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" librenms' < inventory/nomenclatura-lab.sql
INSERT INTO locations (location, lat, lng, timestamp, fixed_coordinates)
  SELECT 'LAB · casa', NULL, NULL, NOW(), 0 FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM locations WHERE location = 'LAB · casa');
SET @loc = (SELECT id FROM locations WHERE location = 'LAB · casa');

UPDATE devices d JOIN (
  SELECT 1  id, 'LAB-RTR-01 · router borde'          n, 'network'     t UNION ALL
  SELECT 4,     'LAB-SW-01 · switch acceso',        'network'       UNION ALL
  SELECT 11,    'LAB-AP-01 · access point',            'wireless'      UNION ALL
  SELECT 9,     'LAB-MDM-01 · módem ISP-A (WAN1)',           'network'       UNION ALL
  SELECT 10,    'LAB-MDM-02 · módem ISP-B (WAN2)',             'network'       UNION ALL
  SELECT 7,     'LAB-PRB-01 · sonda ISP-A',          'network'       UNION ALL
  SELECT 8,     'LAB-PRB-02 · sonda ISP-B',            'network'       UNION ALL
  SELECT 2,     'LAB-SRV-01 · servidor monitoreo',                'server'        UNION ALL
  SELECT 3,     'LAB-SRV-02 · servidor producción',   'server'        UNION ALL
  SELECT 5,     'LAB-SRV-03 · servidor pruebas',                'server'        UNION ALL
  SELECT 6,     'LAB-WKS-01 · estación Windows',                'workstation'   UNION ALL
  SELECT 12,    'LAB-UPS-01 · UPS 1000VA',        'power'
) m ON m.id = d.device_id
SET d.display = m.n, d.type = m.t, d.location_id = @loc, d.override_sysLocation = 1;

SELECT device_id, display, type FROM devices ORDER BY display;
