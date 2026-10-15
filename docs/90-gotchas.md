# 90 · Gotchas (problemas reales → causa → solución)

| # | Qué pasó | Causa | Solución |
|---|---|---|---|
| 1 | La UI redirige a `/install` | El primer arranque con DB vacía deja la marca `INSTALL` | Crear el admin por CLI y `docker compose restart librenms` |
| 2 | Syslog vacío | `enable_syslog` viene en `false` | `lnms config:set enable_syslog true` |
| 3 | RouterOS: el syslog no matchea | Los topics separados por coma en **una** regla son **AND** | Una regla por topic |
| 4 | RouterOS: no hay traps de interfaz | `trap-generators=interfaces` no alcanza | Además, `trap-interfaces=all` |
| 5 | La prueba de trap cortando un puerto no llega | El poller cuelga de ese mismo puerto: el trap no tiene por dónde viajar | Probar con un puerto que no esté en el camino |
| 6 | El host se ve sin discos ni NICs reales | Se polleó por `localhost` = snmpd **del container** | Pollear por la IP de LAN y autorizar la subred Docker en el snmpd del host |
| 7 | El backup falla al leer el datadir de MariaDB | Archivos uid 999 y no consistentes en caliente | `mariadb-dump --single-transaction` + excluir el datadir |
| 8 | Windows: `Add-WindowsCapability` por SSH → *Access denied* | Windows niega instalar capabilities en sesiones de red | Tarea programada como **SYSTEM**. Después exige **reinicio** antes de que exista el servicio SNMP |
| 9 | El script remoto dijo OK sin hacer nada | `powershell -Command -` por SSH no leyó stdin | Copiar un `.ps1`, ejecutarlo y validar con un marcador explícito |
| 10 | `schedule_type.ping dispatcher` no activa el fast ping | En Docker, el dispatcher lee `poller_cluster` | `UPDATE poller_cluster SET ping_enabled=1, ping_frequency=60` + restart |
| 11 | Fast ping cada 60 s, pero el gráfico sigue en 5 min | El fast ping solo actualiza disponibilidad | Para jitter fino: Smokeping |
| 12 | Widget: "Problem with backend" | El widget se llama `generic-graph` | Usar `generic-graph` |
| 13 | Gráficos `-nan` | `graph_range: "oneday"` no existe | `day`, `week`, `month`… |
| 14 | Dashboard a media pantalla | La grilla es de 20 columnas | Diseñar en 20 |
| 15 | El insert de widget falla | `refresh` es tinyint | ≤ 120 |
| 16 | A un mapa creado por SQL le faltan defaults | Los arma el controller | Crearlo con Eloquent vía `artisan tinker` |
| 17 | El error de `device:add` **muestra la community** | El mensaje la incluye | Filtrar la salida; nunca pegarla en tickets ni chats |
| 18 | `sudo VAR=… cmd` → *not allowed to set environment variables* | `env_reset` en sudoers | `sudo env VAR=… cmd` |
| 19 | Alerta de puerto caído después de cada reinicio de Docker | Interfaces `veth`/`br-` | `bad_if_regexp` (ver [07](07-alertas-sin-ruido.md)) |
| 20 | La alerta sigue con puertos ya eliminados | La regla default no filtra `ports.deleted` | Agregar `ports.deleted = 0 AND ports.ignore = 0` |
| 21 | Editar una regla por API cambia su intervalo | El PUT crea una `alert_operations` nueva | Revisar y restaurar después del PUT |
| 22 | El widget del mapa se rompe después de regenerarlo | Referencia el `custom_map_id` | Actualizar el mapa en el lugar |
| 23 | Las herramientas en `/tmp` desaparecen | `/tmp` se limpia en el boot | Guardarlas en el repo o en el stack |
| 24 | La UPS como app dentro del host queda escondida | Una app vive dentro de su host | snmpd dedicado → equipo propio (ver [04](04-energia-ups-nut.md)) |
| 25 | `device:add --force` deja el equipo sin community | `--force` saltea también la carga de la community global | Cargar la community después |
| 26 | Voltaje de UPS "fuera de rango" con 120 V | Límites europeos por defecto | Ajustar con `sensor_custom='Yes'` |
| 27 | Equipos en naranja sin alertas | `uptime_warning`: reiniciados hace < 24 h | Normal, se limpia solo |
| 28 | Un speedtest no dice cuál WAN es cuál | Con balanceo, cada conexión sale por una WAN distinta | Forzar la ruta o medir desde el router por interfaz |
| 29 | LibreNMS no arma el árbol padre→hijo | No existe inferencia nativa (solo UI/API/DB) | [`tools/infer-dependencies.py`](../tools/infer-dependencies.py) |
| 30 | Al pasar un equipo de ping a SNMP, el discovery le cambia el **tipo** | Core reescribe `devices.type` con el default del OS si no existe `override_device_type` | Atributo `override_device_type=1` en `devices_attribs` (ver [`ejemplos/nomenclatura.sql`](../ejemplos/nomenclatura.sql)) |
| 31 | Windows por SNMP: muchos puertos "down" | Adaptadores virtuales (WAN Miniport, filtros Wi-Fi) | `ports.ignore = 1` en esos puertos |
| 32 | Un servidor vuelve de un reinicio y LibreNMS lo marca caído por SNMP (el ping responde) | Se activó un firewall (UFW) sin regla para SNMP: `[UFW BLOCK] … DPT=161` en el log | Regla puntual: `ufw allow proto udp from <poller> to any port 161`. Toda línea base de firewall debe incluir el SNMP del poller |
