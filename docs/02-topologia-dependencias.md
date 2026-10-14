# 02 · Topología y dependencias padre → hijo

## Por qué importa

LibreNMS usa las dependencias para dos cosas:

- **Supresión de alertas:** si el padre está caído, no alerta por cada hijo. Llega **una** alerta, no cientos.
- **Diagnóstico y mapas:** el *Device Dependency Map* y la distinción entre "caído" e "inalcanzable".

En un ISP esto es crítico: si se cae un nodo de distribución, cientos de CPE aparecen "caídos" y la
causa real queda enterrada en la avalancha.

> **Detalle de la documentación oficial:** la supresión aplica solo cuando **todos** los padres de un
> equipo están caídos. Un equipo con dos padres (anillo, doble uplink) sigue alertando mientras quede uno vivo.

**LibreNMS no infiere dependencias automáticamente** (verificado en 26.9.1.1 contra la documentación
oficial *Device Dependencies*). Se cargan solo por UI, API o base de datos. El auto-discovery por
LLDP/CDP/xDP descubre **enlaces y equipos nuevos**, pero **no arma el árbol**. Este repo aporta un
método y un script para hacerlo.

## Las tres fuentes de evidencia

LibreNMS ya recolecta todo lo necesario; solo hay que cruzarlo.

| Fuente | Tabla | Qué dice | Confianza |
|---|---|---|---|
| **LLDP / CDP / MNDP** | `links` | "Mi puerto X está conectado al equipo Y": vecino **directo** | Alta |
| **FDB** (tabla MAC de cada bridge/switch) | `ports_fdb` | "Detrás de mi puerto X están estas MACs": vecino directo **o lejano** | Media (alta si hay una sola) |
| **ARP** del router | `ipv4_mac` | "Esta IP/MAC está en mi interfaz X": adyacencia **L3** | Media |

A eso se suman las MACs propias de cada equipo (`ports.ifPhysAddress`) para traducir MAC → equipo.

## El algoritmo

1. **Elegir la raíz:** el router o core del que cuelga todo. En un ISP, una raíz por POP.
2. **Encontrar el uplink de cada switch:** es el puerto donde ese switch ve la MAC de la raíz.
   Todo lo que ve en los **demás** puertos está aguas abajo de él.
3. **Padre directo = el switch más profundo que ve al equipo aguas abajo**, es decir, el que lo ve en
   el puerto con **menos** equipos detrás. Un equipo puede aparecer en la FDB de cinco switches de la
   cadena, y su padre es el último de los cinco.
4. **Switches sin SNMP** (no dan FDB): si su MAC aparece en un puerto de bajada del switch de arriba
   junto con otros hosts, esos hosts **probablemente** cuelgan de él. Se declara con `--switch`.
5. **Adyacencia L3:** lo que solo aparece en la ARP de una interfaz del router (módems, equipos ping-only) cuelga del router.
6. **LLDP manda:** cuando existe, confirma o corrige lo anterior.
7. **Lo que no se ve en L2 ni en L3** (destinos remotos como sondas de internet) se define a mano. El script lo conserva.

### Caso de estudio (laboratorio)

```
                    ┌──────── Router (raíz) ────────┐
          ether1 ── módem ISP-A        ether2 ── módem ISP-B
          ether3 ── switch SIN SNMP ── 4 servidores
          ether4 ── access point ── clientes Wi-Fi
```

La FDB del router mostraba en `ether3` las MACs del switch **y** de los cuatro servidores. Como el switch
no tiene SNMP, no hay forma de ver su propia FDB. Pero que su MAC compartiera el puerto con los
servidores alcanzó para inferir que cuelgan de él: `--switch` con confianza MEDIA. Los módems
aparecieron solo por ARP en `ether1` y `ether2`. El script reprodujo **exactamente** el árbol que se
había armado a mano.

## La herramienta: `tools/infer-dependencies.py`

```bash
# desde la carpeta del stack (donde está el .env con MYSQL_USER/MYSQL_PASSWORD)
python3 -I infer-dependencies.py --root 1                          # propuesta + diff, NO escribe
python3 -I infer-dependencies.py --root 1 --switch 4               # el 4 es un switch sin SNMP
python3 -I infer-dependencies.py --root 1 --switch 4 --ip 6=192.0.2.15   # el 6 se pollea por otra IP
python3 -I infer-dependencies.py --root 1 --switch 4 --apply       # escribe device_relationships
```

Salida de ejemplo:
```
HIJO                       PADRE                  CONF   EVIDENCIA
  SW-01 · switch acceso    RTR-01 · router core   MEDIA  FDB: RTR-01 lo ve en ether3 (5 equipo(s) detrás)
  MDM-01 · módem ISP-A     RTR-01 · router core   MEDIA  ARP: RTR-01 lo ve en ether1
+ SRV-01 · servidor        SW-01 · switch acceso  MEDIA  comparte RTR-01:ether3 con el switch sin SNMP SW-01

Sin evidencia L2/L3 (definir a mano): PRB-01 · sonda ISP-A
```

- `+` marca lo que **cambiaría** respecto a lo cargado.
- Lista aparte las relaciones actuales que la inferencia **no confirma**.
- `--apply` reemplaza `device_relationships` y **conserva** las manuales de equipos sin evidencia.

Configuración: `LNMS_ENV_FILE`, `LNMS_DB_CONTAINER` (default `librenms_db`), `LNMS_DB_NAME`.

## Llevarlo a un ISP: requisitos

| Requisito | Por qué |
|---|---|
| SNMP de lectura en **todo** switch, router y OLT | Sin FDB/ARP no hay evidencia. Un switch sin SNMP es un punto ciego |
| **LLDP** activado en el transporte (MikroTik: `/ip neighbor discovery-settings`) | Pasa de "probable" a "seguro" |
| FDB por **VLAN** (Q-BRIDGE-MIB) | En redes con VLANs una MAC puede aparecer en puertos distintos según la VLAN |
| Correr la inferencia **con tráfico real** | Las MACs envejecen (unos 300 s): un equipo callado no aparece en la FDB |
| **Una raíz por POP o anillo**, considerando STP | Con redundancia el "uplink" cambia según el camino activo |
| Radioenlaces y bridges transparentes | No aparecen en la FDB: declararlos (`--switch`) o leer su propio SNMP |
| Clientes PPPoE/DHCP | El padre del CPE sale de la sesión en el BRAS/OLT, no de la FDB |
| **Revisión humana** del diff antes de `--apply` | La inferencia propone y el operador confirma |

**Automatización sugerida:** un job semanal que corra el script en modo propuesta y mande el diff
(por ejemplo, "3 equipos cambiaron de padre") por chat. Aplicar solo con OK humano.

## Ideas para la siguiente versión (abiertas a contribución)

- Leer FDB por VLAN y elegir el uplink por VLAN.
- Usar `links` (LLDP) como fuente primaria y la FDB solo para lo que LLDP no cubre.
- Sesiones PPPoE/DHCP del BRAS u OLT como fuente de padre para CPEs.
- Exportar el árbol propuesto a Graphviz para revisión visual.
