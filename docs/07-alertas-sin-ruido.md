# 07 · Alertas sin ruido

Un sistema que alerta de más se termina ignorando. Lo que encontramos y cómo se resolvió:

## Interfaces virtuales de Docker

Cada vez que un container se recrea, aparecen interfaces `veth*` y `br-*` nuevas y las viejas quedan
"down". Resultado: alertas "Port status change" en cada reinicio.
```bash
lnms config:set bad_if_regexp.+ '/^veth/'
lnms config:set bad_if_regexp.+ '/^br-[0-9a-f]{12}$/'
lnms config:set bad_if_regexp.+ '/^docker[0-9]/'
lnms device:discover <id> -m ports      # las marca como eliminadas
```

## La regla de puertos no filtra puertos eliminados

La regla de ejemplo *Port status change from up to down* **no** filtra `ports.deleted`. Los puertos
recién eliminados siguen disparando. Hay que agregar dos condiciones:
`ports.deleted = 0` y `ports.ignore = 0`.

## Editar reglas por API resetea el intervalo

`PUT /api/v0/rules` crea una **operación nueva** (`alert_operations`) con el intervalo de
re-notificación por defecto. Después de editar, revisar `alert_operations.default_operation_step_duration_seconds`.

## Límites de sensores por defecto

Los defaults pueden no corresponder a tu realidad. Por ejemplo, el voltaje de la UPS viene con valores
europeos (ver [04](04-energia-ups-nut.md)). Ajustar con `sensor_custom='Yes'`.

## "Warn" naranja sin alertas

El mapa de disponibilidad marca *warn* a los equipos **reiniciados hace menos de 24 h**
(`uptime_warning`, default 86400). Es normal y se limpia solo.

## Dependencias = menos alertas

Con el árbol padre→hijo cargado ([02](02-topologia-dependencias.md)), la caída de un switch genera **una**
alerta y no una por cada equipo de abajo. Recordar: la supresión aplica cuando **todos** los padres están caídos.

## Probar cada regla con un control positivo

Copiar la consulta de la regla (`alert_rules.query`), reemplazar `?` por el `device_id` y ejecutarla:
- en estado normal, la condición de alerta debe dar **0 filas**;
- cambiando la condición por su opuesto (por ejemplo `UPSOnBattery` → `UPSOnLine`), debe dar **≥ 1**.

Así se sabe que la regla está bien armada sin esperar a que pase el incidente real.
