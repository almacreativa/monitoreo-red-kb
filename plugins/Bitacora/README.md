# Plugin local "Bitácora" para LibreNMS — 0.1 (beta)

Bitácora de incidencias **dentro de LibreNMS**, sin tablas propias ni plataforma externa.

- **Modelo:** cada registro es una entrada del eventlog con `type = incidencia`, `reference = INC-AAAA-NNN` y
  `message = [APERTURA|NOTA|CIERRE · causa: …] texto`. Un mismo código en varios equipos agrupa sus alertas
  en un solo incidente.
- **Vistas:**
  - *Overview → Bitácora*: incidentes abiertos y cerrados, equipos, línea de tiempo, duración y **alertas de esos equipos durante el incidente** (del `alert_log`).
  - Panel en la ficha de cada equipo.
  - Las entradas también aparecen en *Recent Events* y en el eventlog.
- **Asociación de alertas (automática):** no se eligen una por una. El plugin muestra las alertas del
  `alert_log` de los **equipos del incidente** desde **30 min antes de la apertura** hasta **10 min después del
  cierre** (o hasta ahora si sigue abierto). Para sumar las de otro equipo, se lo agrega con una nota.
  Límite conocido: si ese equipo tuvo otro problema en la misma ventana, también aparece.
- **Registro:** el formulario permite apertura, nota y cierre con causa tipificada. Se pueden elegir equipos o un grupo completo, y una fecha opcional para registrar a posteriori.
- **Buscador de equipos** (Select2, el mismo componente de LibreNMS): busca por nombre visible (nomenclatura), hostname, sysName, IP y **ubicación/sitio**; varias palabras se combinan (`pop1 olt`); resultados de a 30. El índice respeta los permisos del usuario y se filtra en el navegador (1.500 equipos ≈ 100 KB).
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
- **Un hook no puede devolver JSON lanzando una excepción** (p. ej. `HttpResponseException`): el
  `PluginManager` atrapa toda excepción de un hook y **desactiva el plugin**. Reactivar con `lnms plugin:enable Bitacora`.
- `collect()->map('intval')` es un bug: Laravel pasa la clave como segundo argumento y `intval("5", 1)` (base 1)
  devuelve 0. Usar `map(fn ($v) => (int) $v)`.
- LibreNMS pone `<base href="/">`: los links relativos (`?estado=…`) van a la raíz. Usar `url('plugin/Bitacora')`.
- Un incidente está cerrado si su último CIERRE es posterior a su última APERTURA: las notas posteriores
  (post-mortem) no lo reabren.

## Límites de la beta
- Sin reportes de MTTR/causas todavía (los datos están: duración y causa tipificada por incidente).
- Solo administradores registran (`plugin.admin`).
- Sin asociación explícita alerta↔incidente (idea para una próxima versión: leer el código `INC-…` en la nota del Ack de cada alerta).

## Versiones
- **0.1 (beta, 2026-10-16):** registro de apertura/nota/cierre con causa, búsqueda de equipos por
  nombre/IP/sitio, asociación automática de alertas, panel por equipo, acciones según el estado del incidente.
  Probado en LibreNMS 26.9.1.1 con incidentes reales.
