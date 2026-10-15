# Plugin local "Bitácora" para LibreNMS (prototipo)

Bitácora de incidencias **dentro de LibreNMS**, sin tablas propias ni plataforma externa.

- **Modelo:** cada registro es una entrada del eventlog con `type = incidencia`, `reference = INC-AAAA-NNN` y
  `message = [APERTURA|NOTA|CIERRE · causa: …] texto`. Un mismo código en varios equipos agrupa sus alertas
  en un solo incidente.
- **Vistas:**
  - *Overview → Bitácora*: incidentes abiertos y cerrados, equipos, línea de tiempo, duración y **alertas de esos equipos durante el incidente** (del `alert_log`).
  - Panel en la ficha de cada equipo.
  - Las entradas también aparecen en *Recent Events* y en el eventlog.
- **Registro:** el formulario permite apertura, nota y cierre con causa tipificada. Se pueden elegir equipos o un grupo completo, y una fecha opcional para registrar a posteriori.
- **Seguridad:** escribe por la ruta oficial `plugin.update` (CSRF + permiso `plugin.admin`). Lectura con `global-read`. Sin migraciones.

## Instalación (Docker)
```yaml
  librenms:
    volumes:
      - ./plugins/Bitacora:/opt/librenms/app/Plugins/Bitacora:ro
```
`docker compose up -d librenms`. El plugin se registra y activa solo (tabla `plugins`).
Instalación nativa: copiar la carpeta a `/opt/librenms/app/Plugins/Bitacora`.

## Gotchas
- En la raíz del plugin **toda clase debe ser un hook**: el provider recorre `app/Plugins/*/*.php` y falla con otra
  clase. Los helpers van en una subcarpeta (`Support/`).
- La página de plugin solo acepta GET: para escribir se usa la ruta de *settings* del plugin y la página vuelca
  `settings['pending']` al eventlog en el redirect.
- PHP-FPM con `opcache.revalidate_freq=60`: después de editar el PHP, esperar ~1 min (o reiniciar) antes de probar.
- Un incidente está cerrado si su último CIERRE es posterior a su última APERTURA: las notas posteriores
  (post-mortem) no lo reabren.

## Límites del prototipo
- Selector de equipos plano (con 1.500 equipos conviene buscador o filtrar por grupo/sitio).
- Sin reportes de MTTR/causas todavía (los datos están: duración y causa tipificada por incidente).
- Solo administradores registran (`plugin.admin`).
