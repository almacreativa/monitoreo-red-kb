# 03 · WAN y múltiples ISP

## Leer el ruteo del router por SNMP

`ipCidrRouteTable` (OID `1.3.6.1.2.1.4.24.4`) muestra las rutas activas sin necesidad de entrar al router:
```bash
snmpwalk -v2c -c <community> -On 192.0.2.1 1.3.6.1.2.1.4.24.4.1.4.0.0.0.0     # defaults y sus next-hops
snmpwalk -v2c -c <community> -On 192.0.2.1 1.3.6.1.2.1.4.24.4.1.11.0.0.0.0    # métricas o distancias
```
En el caso de estudio aparecieron **rutas recursivas** (patrón clásico de failover en MikroTik):
- default vía `1.1.1.1` (distance 1) y vía `8.8.8.8` (distance 2);
- rutas /32 fijas `1.1.1.1 → módem ISP-A` y `8.8.8.8 → módem ISP-B`.

## Sondas por proveedor sin tocar el router

Con esas /32 fijas, un ping a `1.1.1.1` sale **siempre** por ISP-A y uno a `8.8.8.8` sale **siempre** por
ISP-B. Darlos de alta como equipos *ping-only* da latencia, pérdida y disponibilidad **por proveedor**:

| Equipo | Para qué |
|---|---|
| Sonda ISP-A (`1.1.1.1`) / Sonda ISP-B (`8.8.8.8`) | Latencia y pérdida por proveedor. Si cae, el ISP está caído |
| Módem ISP-A / Módem ISP-B | Distingue "se cayó el módem" de "se cayó el proveedor" |

Con dependencias `sonda → módem → router`, si el módem está caído no llega además la alerta de la sonda.

Si el router **no** tiene rutas fijas por WAN, se pueden agregar /32 hacia destinos de medición
dedicados. No uses los DNS que el propio router tiene configurados, para no romper su resolución
cuando caiga ese ISP.

## Identificar el ISP sin acceso al módem

| Pista | Cómo verla | Qué indica |
|---|---|---|
| MTU 1492 en el camino | `tracepath -n <destino>` | **PPPoE** (típico de fibra o DSL de telco) |
| Siguiente salto en `10.x` / `100.64.x` detrás del módem | `tracepath` | **CGNAT** (típico de cable) |
| Bloque del primer salto público | whois del ASN | Operador |
| Destinos distintos salen por WAN distintas | `tracepath` a varios destinos | Hay **balanceo**, no solo failover |

Un speedtest mide **una** WAN, la que toque el balanceo. Para medir cada una hay que forzar la ruta,
por ejemplo con una prueba desde el router por interfaz.

## Consumo mensual (bills)

```bash
curl -X POST -H "X-Auth-Token: $TOKEN" http://<librenms>/api/v0/bills -d '{
  "bill_name":"WAN1 · ISP-A","bill_type":"quota","bill_quota":0,"bill_day":1,
  "bill_custid":"lab","bill_ref":"ether1","bill_notes":"Consumo mensual","dir_95th":"max","ports":[<port_id>]}'
```
**Gotcha:** la API exige `bill_custid`, `bill_ref`, `bill_notes` y `dir_95th` aunque la documentación no lo diga.
Configurar `enable_billing true`.

## Alertas sugeridas

- **Sonda o módem caído:** la regla genérica *Devices up/down*, crítica.
- **Latencia alta:** `devices.last_ping_timetaken > 100` sobre las sondas, warning, 3 veces seguidas.
- **Enlace físico WAN caído:** *Port status change* sobre los puertos WAN.
- **Saturación:** requiere cargar la velocidad contratada del puerto. Si no, el % de uso se calcula sobre 1 Gbps.

## Correlación útil: corte de luz vs. caída del ISP

Si un módem **no tiene respaldo de energía** y otro sí, una caída simultánea del módem sin respaldo y
el paso de la UPS a batería indica **corte de luz**, no falla del proveedor. Ver [04](04-energia-ups-nut.md).
