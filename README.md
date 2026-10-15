# Monitoreo de red con LibreNMS — base de conocimiento

Conocimiento práctico, probado en una red real de laboratorio, para **desplegar, operar y escalar
LibreNMS**. El foco está puesto en lo que le importa a un **proveedor de internet (ISP)**: topología
padre→hijo automática, medición por proveedor y alertas sin ruido.

> Todo el contenido está **anonimizado**: las direcciones de ejemplo son de los rangos reservados para
> documentación (RFC 5737: `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) y los proveedores se
> llaman ISP-A / ISP-B. Ver [Cómo contribuir](#cómo-contribuir).

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
| [90 · Gotchas](docs/90-gotchas.md) | Problemas reales encontrados: causa → solución |

## Herramientas

| Herramienta | Uso |
|---|---|
| [`tools/infer-dependencies.py`](tools/infer-dependencies.py) | Propone dependencias padre→hijo con evidencia y nivel de confianza; `--apply` las escribe |
| [`tools/diagnostico-librenms.py`](tools/diagnostico-librenms.py) | **Diagnóstico de solo lectura** de una instancia: colecta, nomenclatura, grupos, dependencias, reglas, ruido y carrera padre/hijo, con un resumen "por dónde empezar". `--anonimo` para compartir el reporte |
| [`tools/shot.js`](tools/shot.js) | Captura headless (Playwright) logueada, para verificar dashboards y mapas |
| [`ejemplos/`](ejemplos/) | Compose, agente SNMP dedicado para UPS, nomenclatura en SQL |

## Versiones probadas

LibreNMS **26.9.1.1** (imagen `librenms/librenms`), MariaDB 10.11, Redis 7.4, net-snmp 5.9, NUT 2.8,
RouterOS 7.20 (MikroTik).

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
