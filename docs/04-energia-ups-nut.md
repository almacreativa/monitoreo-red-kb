# 04 · Energía: UPS por USB con NUT → LibreNMS

## Lo primero: qué puerto sirve

En UPS económicas, los puertos **RJ45/RJ11 son solo protección contra picos** (pasa-cables de entrada y
salida): **no** sirven para monitorear. El monitoreo es por **USB-B** hacia una PC.

## Driver

`lsusb` indica el driver a usar:
| USB ID | Chip | Driver NUT |
|---|---|---|
| `0665:5161` | Cypress USB-serial (protocolo Megatec/Q1, muy común en UPS económicas) | `nutdrv_qx` (alternativas: `subdriver = cypress`, `blazer_usb`) |
| HID (APC, CyberPower, Eaton…) | USB HID Power Device | `usbhid-ups` |

## Etapa 1: solo monitoreo

`/etc/nut/ups.conf`:
```ini
[ups1]
  driver = nutdrv_qx
  port = auto
  vendorid = 0665
  productid = 5161
```
`/etc/nut/upsmon.conf`, con **power value 0** (este host NUNCA se apaga por la UPS):
```
MONITOR ups1@localhost 0 upsmon <password> primary
MINSUPPLIES 0
```
Con `upsc ups1` se ve `ups.status` (OL = en red, OB = en batería, LB = batería baja), `battery.charge`,
`battery.voltage`, `input.voltage` y `ups.load`.

**Gotcha de sudo:** `sudo DEBIAN_FRONTEND=noninteractive apt-get …` falla con `env_reset`.
Usar `sudo env DEBIAN_FRONTEND=noninteractive apt-get …`.

## La UPS como equipo propio en LibreNMS

Como *aplicación* dentro del host que la tiene conectada, la UPS queda escondida, y depende de que
alguien entre a ese host. Mejor que sea un **equipo propio**:

1. **Un segundo snmpd** dedicado (`udp/1161`) que expone **solo** `system` + `nsExtend`. Ver
   [`ejemplos/snmpd-ups.conf`](../ejemplos/snmpd-ups.conf) y [`ejemplos/snmpd-ups.service`](../ejemplos/snmpd-ups.service).
   - `-C -c <conf>`: no lee el `snmpd.conf` principal.
   - `SNMP_PERSISTENT_DIR` propio, para no pisar los archivos persistentes del snmpd principal.
   - Una `view` limitada a `system` + `nsExtend`, así no aparecen interfaces ni discos del host.
   - Una ACL solo para la red Docker de LibreNMS, y el firewall abierto solo para esa red.
2. El extend oficial: `extend ups-nut /etc/snmp/ups-nut.sh ups1`
   (script de [librenms-agent](https://github.com/librenms/librenms-agent/blob/master/snmp/ups-nut.sh), que solo ejecuta `upsc`).
3. Alta en LibreNMS apuntando a la IP del bridge Docker en el host, con puerto 1161:
   ```bash
   lnms device:add --v2c -r 1161 -f -d "UPS-01 · <modelo>" <ip-bridge>
   ```
   **Gotcha:** `--force` es necesario (la IP ya pertenece al host), pero **saltea la carga de la
   community**. Hay que cargarla después: `UPDATE devices SET community=… WHERE device_id=…`.
4. LibreNMS descubre la app `ups-nut` y **crea sensores de Health**: carga, voltajes, consumo y
   estados como "UPS on battery" o "UPS low battery".

## Ajustar límites de sensores (alerta falsa evitada)

LibreNMS pone para el voltaje de entrada límites **europeos (200–280 V)**. En una red de 120 V, la UPS
aparece "fuera de rango" y dispara *Sensor over limit*. Ejemplo para 120 V (la UPS opera entre 81 y 145 V):
```sql
UPDATE sensors SET sensor_limit_low=105, sensor_limit_low_warn=110, sensor_limit_warn=135, sensor_limit=140,
       sensor_custom='Yes' WHERE sensor_descr='Input Voltage' AND device_id=<ups>;
```
`sensor_custom='Yes'` evita que el próximo discovery pise los límites.

## Reglas de alerta

| Regla | Condición | Severidad |
|---|---|---|
| UPS en batería (corte de luz) | `application_metrics.metric = 'UPSOnBattery' AND value = 1` | crítica |
| UPS batería baja | `metric = 'UPSLowBattery' AND value = 1` | crítica |
| UPS sobrecarga | `metric = 'load' AND value > 80` | warning |

**Probar la consulta con un control positivo:** reemplazar `UPSOnBattery` por `UPSOnLine` tiene que
devolver la UPS. Si devuelve 0 filas, la regla está mal armada.

## Etapa 2 (diseño): apagado ordenado

- **NUT servidor** en el host con USB; **clientes** `upsmon` en los demás (Windows: WinNUT-Client).
- **Escalones:**
  - en batería → alerta;
  - a los N minutos → apagar los equipos no críticos;
  - batería baja → apagar los críticos y por último el servidor NUT.
- **Gotchas a resolver:**
  - **BIOS "AC power recovery = On"**, para que los equipos enciendan solos al volver la luz;
  - **`upsdrvctl shutdown`** al final, para que la UPS corte su salida y los equipos reciban
    "luz nueva" aunque la luz vuelva antes de agotarse la batería.
- Muchas UPS económicas **no reportan autonomía** (`battery.runtime`). NUT la estima con `runtimecal`,
  después de calibrarla con un corte controlado.
