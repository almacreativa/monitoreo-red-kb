# 08 · Monitorear lo que está fuera de la red local

¿Conviene monitorear servidores y servicios en internet desde la misma instancia de LibreNMS?

| Qué | Herramienta recomendada | Por qué |
|---|---|---|
| Servidores propios (VPS): CPU, RAM, disco, red | **LibreNMS por VPN overlay** (WireGuard/Tailscale), con snmpd y ACL a la IP de la VPN del poller | Mismo panel y mismas alertas; SNMP nunca queda expuesto a internet |
| ¿Responde el sitio o la API? Keyword, código HTTP, certificado | **Uptime Kuma** (o similar) | Está hecho para eso. Los *Services* de LibreNMS sirven como complemento, con gráficos de tiempo de respuesta |
| Errores y lentitud **dentro** de la app | APM / Sentry / OpenTelemetry | Fuera del alcance de LibreNMS |
| **¿Quién vigila al vigilante?** | Un **punto de vista externo** | Si cae el sitio donde corre el monitoreo, nada de lo anterior avisa |

## El hueco más común

Todo el monitoreo vive en el mismo lugar que lo monitoreado. Un corte de luz o de los enlaces apaga
**a la vez** los ojos y el aviso. Opciones, de menor a mayor esfuerzo:

1. **Dead-man switch** externo (healthchecks.io, UptimeRobot): el poller hace "ping" cada pocos
   minutos y, si deja de hacerlo, el servicio externo avisa.
2. Un monitor liviano en un VPS que vigile la instancia principal y los servicios públicos (vigilancia mutua).
3. **Poller distribuido** de LibreNMS en otra ubicación. Es más complejo; se justifica con muchos equipos remotos.

**Recomendación:** monitorear por capas.
- LibreNMS para la **infraestructura**, incluidos los VPS por VPN.
- Uptime Kuma para la **disponibilidad de servicios**.
- Un **vigilante externo** para la propia plataforma de monitoreo.
