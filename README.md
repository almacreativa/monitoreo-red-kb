# Monitoreo de red con LibreNMS — base de conocimiento

Conocimiento práctico, probado en una red real de laboratorio, para **desplegar, operar y escalar
LibreNMS**. El foco está puesto en lo que le importa a un **proveedor de internet (ISP)**: topología
padre→hijo automática, medición por proveedor y alertas sin ruido.

> Todo el contenido está **anonimizado**: las direcciones de ejemplo son de los rangos reservados para
> documentación (RFC 5737: `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) y los proveedores se
> llaman ISP-A / ISP-B. Ver [Cómo contribuir](#cómo-contribuir).

## Qué se puede usar (no solo leer)

Todo está probado contra LibreNMS 26.9.1.1. Ordenado de menor a mayor impacto sobre la instancia:

| Pieza | Qué resuelve | ¿Modifica LibreNMS? | Requisitos | Cómo se usa |
|---|---|---|---|---|
| [`tools/diagnostico-librenms.py`](tools/diagnostico-librenms.py) | Foto del estado de la instancia y **por dónde empezar** (colecta, nombres, grupos, dependencias, reglas, ruido, carrera padre/hijo) | **No.** Sesión de base `READ ONLY` | Python 3 + acceso a la base (Docker o cliente `mysql`) | `python3 diagnostico-librenms.py --anonimo --salida diag.md` |
| [`tools/infer-dependencies.py`](tools/infer-dependencies.py) | Propone el árbol **padre→hijo** con evidencia (FDB/ARP/LLDP) y nivel de confianza | No, salvo `--apply` | Python 3 + base | `--root <id>` muestra propuesta y diff; `--apply` escribe |
| [`plugins/Bitacora`](plugins/Bitacora) | **Bitácora de incidencias** (beta 0.1) dentro de LibreNMS: agrupa alertas de varios equipos con un código `INC-…` | Sí: agrega una página y un panel; escribe en el eventlog. Sin tablas nuevas | Copiar la carpeta (o montarla en Docker) | Ver su [README](plugins/Bitacora/README.md). Overview → Bitácora |
| [`ejemplos/nomenclatura.sql`](ejemplos/nomenclatura.sql) | Nombres `SITIO-ROL-NN`, tipo fijo y ubicación única | Sí (`devices`) | Ajustar los `device_id` | `mariadb … < nomenclatura.sql` (idempotente) |
| [`ejemplos/sensores-limites.sql`](ejemplos/sensores-limites.sql) | Límites de temperatura del fabricante, no "valor + 20" | Sí (`sensors`) | Ajustar `device_id` y valores | Idem (idempotente) |
| [`ejemplos/snmpd-ups.conf`](ejemplos/snmpd-ups.conf) + [`.service`](ejemplos/snmpd-ups.service) | UPS por NUT como **equipo propio** en LibreNMS | No (va en el host de la UPS) | NUT funcionando | Ver [04](docs/04-energia-ups-nut.md) |
| [`ejemplos/docker-compose.yml`](ejemplos/docker-compose.yml) | Stack completo de referencia (web, dispatcher, syslog, traps, DB, Redis) | — | Docker | Ver [01](docs/01-despliegue-docker.md) |
| [`tools/shot.js`](tools/shot.js) | Captura logueada para verificar dashboards, mapas o el plugin | No | Node + playwright-core | `node shot.js /overview out.png 1600 1000` |
| [`scripts/check-anonimato.sh`](scripts/check-anonimato.sh) | Impide commitear IPs, MACs o nombres reales | — | — | Automático con `git config core.hooksPath .githooks` |

**Ruta sugerida para una instancia existente:** diagnóstico → nomenclatura y grupos → dependencias
(propuesta, revisión humana, `--apply`) → límites de sensores → plugin Bitácora.
Antes de cualquier pieza que escriba: **backup de la base**.

## Contenido

| Guía | De qué trata |
|---|---|
| [01 · Despliegue en Docker](docs/01-despliegue-docker.md) | Stack de 6 containers, puertos, secretos, primer arranque |
| [02 · Topología y dependencias](docs/02-topologia-dependencias.md) | **Inferir padre→hijo desde FDB/ARP/LLDP** y llevarlo a un ISP |
| [03 · WAN y múltiples ISP](docs/03-wan-multi-isp.md) | Medir cada proveedor por separado, identificar ISPs, consumo |
| [04 · Energía: UPS con NUT](docs/04-energia-ups-nut.md) | UPS USB → NUT → LibreNMS como equipo propio |
| [05 · Nomenclatura](docs/05-nomenclatura.md) | `SITIO-ROL-NN`, grupos dinámicos, tipos y ubicaciones |
| [06 · Dashboards y mapas](docs/06-dashboards-mapas.md) | Dashboard y Custom Map reproducibles (SQL / Eloquent) |
| [07 · Alertas sin ruido](docs/07-alertas-sin-ruido.md) | Reglas, dependencias, interfaces virtuales, límites de sensores |
| [08 · Monitorear fuera de la red](docs/08-monitoreo-fuera-de-la-red.md) | VPS, servicios web y "quién vigila al vigilante" |
| [09 · Bitácora de incidencias](docs/09-bitacora-incidencias.md) | Agrupar varias alertas en un incidente: qué trae LibreNMS y qué conectarle |
| [10 · Bitácora liviana y fallas no-conectividad](docs/10-bitacora-liviana-y-fallas-no-conectividad.md) | Cambios de configuración, reinicios, errores, dBm, BGP/OSPF; el eventlog como bitácora; plugin local |
| [90 · Gotchas](docs/90-gotchas.md) | Problemas reales encontrados: causa → solución |

## Versiones probadas

LibreNMS **26.9.1.1** (imagen `librenms/librenms`), MariaDB 10.11, Redis 7.4, net-snmp 5.9, NUT 2.8,
RouterOS 7.20 (MikroTik).

## Licencias

| Contenido | Licencia | Texto completo |
|---|---|---|
| `docs/` — guías y documentación | **CC BY 4.0** | [`LICENSES/CC-BY-4.0.txt`](LICENSES/CC-BY-4.0.txt) |
| `tools/`, `scripts/`, `ejemplos/`, `.githooks/` — código y ejemplos | **MIT** | [`LICENSE`](LICENSE) |
| `plugins/Bitacora/` — plugin para LibreNMS | **GPL-3.0-or-later** | [`plugins/Bitacora/LICENSE`](plugins/Bitacora/LICENSE) |

© 2026 Alma Creativa. El plugin corre dentro de LibreNMS (GPL-3.0), de ahí su licencia; cada archivo de
código lleva su encabezado `SPDX-License-Identifier`. Las contribuciones se aceptan bajo la licencia
del directorio que tocan.

## Cómo contribuir

1. Activar el control de anonimato **una vez por clon**:
   ```bash
   git config core.hooksPath .githooks
   ```
2. (Recomendado) Crear tu denylist privada con los términos de **tu** red: IPs, hostnames, nombres,
   clientes, communities. Va **fuera** del repo:
   `~/.config/kb-anonimato/denylist.txt` (una regex por línea, `chmod 600`).
3. Escribir con datos de ejemplo:
   - IPs `192.0.2.x`, `198.51.100.x`, `203.0.113.x`;
   - MACs `00:00:5e:00:53:xx`;
   - nombres genéricos (`ISP-A`, `SRV-01`).
4. El *pre-commit* bloquea cualquier IP privada, IP de CGNAT o Tailscale, MAC real o término de tu
   denylist. Para revisar todo el repo: `scripts/check-anonimato.sh`.

Cada guía sigue el mismo formato: **qué pasó → por qué → cómo se resolvió**, con comandos verificados.
