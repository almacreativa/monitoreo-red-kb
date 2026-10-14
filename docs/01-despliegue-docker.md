# 01 · Despliegue de LibreNMS en Docker

## Arquitectura (6 containers)

| Container | Rol | Puertos publicados |
|---|---|---|
| `librenms` | Web UI + API + scheduler | UI (bind a una IP de gestión, nunca `0.0.0.0` en un host expuesto) |
| `librenms_dispatcher` | Polling, discovery, alertas y fast ping (coordinado por Redis) | — |
| `librenms_syslogng` | Receptor de syslog | `514/tcp+udp` solo en la IP de LAN |
| `librenms_snmptrapd` | Receptor de traps SNMP | `162/tcp+udp` solo en la IP de LAN |
| `librenms_db` | MariaDB 10.11 | — |
| `librenms_redis` | Cola y caché | — |

Ejemplo completo: [`ejemplos/docker-compose.yml`](../ejemplos/docker-compose.yml).

## Decisiones que conviene tomar desde el día 1

- **Imágenes con versión fija** (no `latest`). Las migraciones de schema corren solas al arrancar `librenms`.
- **Red Docker con subnet fija** (por ejemplo `10.0.0.0/8` → una /24 propia). Cuando el container
  pollea **a su propio host**, sale por el bridge con IP de esa subnet, y el snmpd del host tiene que autorizarla.
- **Secretos solo en `.env`** (`chmod 600`): DB, admin, token de API, community. Un segundo archivo
  `librenms.env` con el tuning de la imagen, sin secretos, se puede versionar.
- **Datos en bind mounts** (`db/` y `data/`). Para backup, **no** copiar el datadir crudo de MariaDB:
  hacer `mariadb-dump --single-transaction` y excluir el datadir. Los archivos son uid 999 y en caliente no son consistentes.

## Primer arranque

1. `docker compose up -d`.
2. Crear el admin **por CLI** (sin el instalador web):
   `docker exec -u librenms librenms lnms user:add -r admin -p '<password>' admin`.
3. **Gotcha:** con la DB vacía, el primer arranque deja la UI redirigiendo a `/install`. Con el admin
   ya creado: `docker compose restart librenms`.
4. Activar lo que viene apagado:
   - `lnms config:set enable_syslog true`
   - `lnms config:set snmp.community.+ '<community>'`
5. Validar: `docker exec -u librenms librenms php /opt/librenms/validate.php`.

## Alta de equipos

```bash
L="docker exec -u librenms librenms lnms"
$L device:add --v2c 192.0.2.1                                  # usa la community global
$L device:add --ping-only --os=ping --hardware="Módem ISP-A" 198.51.100.1   # sin SNMP
$L device:discover <id> ; $L device:poll <id>                  # forzar sin esperar al scheduler
```

- **Pollear el host por su IP de LAN, no por `localhost`.** `localhost` apunta al snmpd del container
  y muestra discos y NICs que no son los reales.
- Un **switch sin SNMP** (administrado por nube) se da de alta solo por ping: tenés disponibilidad y
  latencia, pero no puertos.
- **Windows:** el servicio SNMP es una *capability* opcional. Ver los gotchas 8 y 9 en [90](90-gotchas.md).

## Fast ping (detección de caídas en ~1 min)

En la imagen Docker, `lnms config:set schedule_type.ping dispatcher` **no** lo activa: el dispatcher
lee su configuración de la tabla `poller_cluster`.
```sql
UPDATE poller_cluster SET ping_enabled = 1, ping_frequency = 60;
```
Después, `docker compose restart dispatcher`. En el log tiene que aparecer `Ping=enabled`.
El fast ping actualiza **solo la disponibilidad**. Los gráficos de latencia siguen saliendo del poll de
5 min (`fping_options.count` define cuántos pings se promedian).
