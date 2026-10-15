# 10 · Bitácora liviana y fallas que no son de conectividad

Pregunta de un equipo de ISP: *"¿hay algo simple, sin montar una plataforma grande, para llevar la
bitácora y detectar problemas que no son pérdida de conectividad (cambios de configuración,
comportamiento anómalo, estabilidad)?"*

**Respuesta corta:** sí, con piezas que LibreNMS ya trae. No hay un plugin de la comunidad para
bitácora de incidencias, pero el **eventlog** acepta entradas por API y el **sistema de plugins** permite
armar una vista propia sin tablas nuevas.

## 1. Detectar lo que no es conectividad

| Problema | Cómo | Origen |
|---|---|---|
| **Cambios de configuración** ("¿qué cambió?") | **Oxidized** integrado: historial y *diff* en la pestaña *Configs* de cada equipo; backup disparado por el **syslog** de "config changed" (script `syslog-notify-oxidized.php`); Oxidized puede escribir en el eventlog de LibreNMS | Integración nativa |
| Aviso inmediato de un cambio | Regla de alerta sobre el **syslog** del equipo con el patrón del vendor (p. ej. `changed by` en RouterOS, `%SYS-5-CONFIG_I` en IOS) | Regla propia sobre la tabla `syslog` |
| **Reinicios** | Regla *Device rebooted* | Colección de reglas |
| **Errores de interfaz** | Regla *Interface Errors Rate greater than 100* | Colección |
| **Potencia óptica (dBm), temperatura, voltajes** | *Sensor over/under limit* y *State Sensor Critical/Warning* (los dBm son sensores) | Colección |
| **BGP** | *BGP Session down* | Colección |
| **OSPF**, **flapping de puertos** | No vienen en la colección: regla propia (vecinos OSPF no `full`; cambios de estado repetidos de un puerto o syslog de link up/down) | Regla propia |

La colección trae **240 reglas** listas (*Alerts → Alert Rules → Create rule from collection*). A esta escala
conviene aplicarlas **por grupo** (core, distribución, acceso), no globales ([07](07-alertas-sin-ruido.md)).

## 2. Bitácora sin plataforma nueva: el eventlog como libro

Verificado en LibreNMS 26.9.1.1:

- `POST /api/v0/devices/:hostname/eventlog` con `text`, `type`, `severity` y `reference`.
- El eventlog ya recibe solo: alertas, acks con nota, reinicios, cambios de puertos y, con Oxidized, cambios de configuración.

**Convención propuesta:**
- `type = "incidencia"`
- `reference = INC-AAAA-NNN` (el código de incidencia de [09](09-bitacora-incidencias.md))
- `text` = qué pasó, qué se hizo, quién

Un mismo código cargado en **varios equipos** es "un incidente que agrupa varias alertas", sin salir de LibreNMS.

**Tres niveles de esfuerzo:**

| Nivel | Qué | Esfuerzo |
|---|---|---|
| 0 | Script o formulario mínimo (o un flujo n8n) que llama a la API para registrar `INC-…` en N equipos | Horas |
| 1 | **Plugin local** de LibreNMS ([prototipo funcionando: `plugins/Bitacora`](../plugins/Bitacora)) (`app/Plugins`, hooks `MenuEntry` + `Page` + `DeviceOverview`): página "Bitácora" que agrupa el eventlog por `reference`, muestra las alertas de esos equipos en la ventana del incidente y un formulario de alta/cierre | 1–2 días de desarrollo PHP/Laravel. Sin tablas propias (usa el eventlog) |
| 2 | ITSM / correlación ([09](09-bitacora-incidencias.md) §4) | Semanas |

**Límites de los transports "livianos" probados:**
- **GitLab:** abre un issue nuevo por cada alerta, sin buscar si ya existe y sin cerrar al recuperarse.
- **Chat (Slack, Mattermost, Teams):** sirve como bitácora informal, pero no deja métricas.
- **Tablas no-code (NocoDB, Baserow):** la recuperación entra como una fila nueva; hace falta un intermediario para actualizar la fila original.

## 3. Recomendación

1. **Oxidized** primero: la mayoría de los incidentes "raros" son cambios de configuración y el *diff* los explica.
2. Reglas de la colección **por grupo**: reinicio, errores, sensores (dBm), BGP; más OSPF y flapping propias.
3. Bitácora en el **eventlog** con código de incidencia; si funciona, el **plugin local** como vista.
4. Recién después, si hace falta escala, la capa de correlación + ITSM.
