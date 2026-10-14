# 05 · Nomenclatura de equipos

## Formato

`SITIO-ROL-NN · nombre de siempre`, en el campo **display** de LibreNMS. El `hostname` y el `sysName`
reales no se tocan: el código es una capa de orden encima.

| Parte | Qué es | Ejemplos |
|---|---|---|
| `SITIO` | Dónde está físicamente | `LAB`; en un ISP, el POP o nodo (`POP1`, `NODO-N`) |
| `ROL` | Qué función cumple | `RTR` router/core · `SW` switch · `AP` access point · `OLT` · `MDM` módem/CPE de upstream · `PRB` sonda de medición · `SRV` servidor · `WKS` estación · `UPS` energía |
| `NN` | Correlativo por sitio y rol | `01`, `02`… Un número dado de baja no se reusa |

Ejemplo (caso de estudio):
| Código | Equipo | `devices.type` |
|---|---|---|
| LAB-RTR-01 | Router de borde | network |
| LAB-SW-01 | Switch de acceso | network |
| LAB-AP-01 | Access point | wireless |
| LAB-MDM-01 / 02 | Módem ISP-A / ISP-B | network |
| LAB-PRB-01 / 02 | Sonda ISP-A / ISP-B | network |
| LAB-SRV-01…03 | Servidores | server |
| LAB-WKS-01 | Estación Windows | workstation |
| LAB-UPS-01 | UPS | power |

## Lo que se apoya en la nomenclatura

- **Grupos dinámicos** por regex sobre el display. Un equipo nuevo bien nombrado **entra solo** en su
  grupo, y sus alertas, vistas y permisos se pueden asignar por grupo:
  | Grupo | Regla |
  |---|---|
  | Red (core y acceso) | `devices.display REGEXP '^LAB-(RTR|SW|AP)-'` |
  | WAN (proveedores) | `^LAB-(MDM|PRB)-` |
  | Cómputo | `^LAB-(SRV|WKS)-` |
  | Energía | `^LAB-UPS-` |

  **Gotcha de API:** en `POST /api/v0/devicegroups`, el campo `rules` tiene que ser un **string JSON**,
  no un objeto.
- **Tipo** (`devices.type`): define el ícono y las agrupaciones.
- **Ubicación única** por sitio, con `override_sysLocation = 1`. Si no, cada snmpd informa su propio
  `syslocation` y aparece una "ubicación" por equipo.

Script de ejemplo idempotente: [`ejemplos/nomenclatura.sql`](../ejemplos/nomenclatura.sql).

## Escalarlo a un ISP

Agregar la **capa**: `POP-CAPA-ROL-NN` (`POP1-CORE-RTR-01`, `POP1-DIST-SW-03`, `POP1-ACC-OLT-02`).
La capa refleja el árbol padre→hijo de [02](02-topologia-dependencias.md): un `ACC` debería tener un
padre `DIST`, y un `DIST` un padre `CORE`. **Si el código y la dependencia inferida no coinciden, uno
de los dos está mal.** Es un control cruzado gratis.
