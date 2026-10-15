# 09 · Bitácora de incidencias: agrupar alertas en un incidente

**Pregunta:** ¿se puede llevar en LibreNMS una bitácora ordenada, donde varias alertas (de distintos
equipos) queden asociadas a **un solo registro de incidencia**, con notas, responsable, causa y cierre?

**Respuesta corta:** LibreNMS **no tiene una entidad "incidente"**. Gestiona alertas individuales
(una por regla y equipo). Para agrupar hace falta una de dos cosas: una **convención** sobre lo que
LibreNMS ya trae, o una **herramienta externa** conectada por un transport.

## 1. Lo que trae LibreNMS (verificado en el código de la 26.9.1.1)

| Función | Qué hace | Límite |
|---|---|---|
| **Ack** (ícono en la tabla de alertas) | Reconoce la alerta y frena las re-notificaciones. Pide una **nota** | La nota es de esa alerta (equipo + regla), no de un incidente |
| **Ack until clear** | El ack dura hasta que la alerta se resuelve; si vuelve, notifica de nuevo | — |
| **Notas de la alerta** | Cada ack/unack **agrega** una línea `fecha - Ack (usuario) nota` a `alerts.note`; no se borra la anterior | Ligada al par equipo+regla |
| **Eventlog** | Registra cada ack con usuario y nota (tipo `alert`) | Por API, el ack no siempre deja rastro en el eventlog (reporte de la comunidad) |
| **Alert log** | Historial de aperturas y cierres con el detalle | No agrupa entre equipos |
| **Dependencias** ([02](02-topologia-dependencias.md)) | Si cae el padre, los hijos no alertan | Reduce el ruido; no crea un registro |
| **Mantenimientos programados** | Silencian alertas en una ventana planificada | — |

## 2. Opción 0 — convención, sin instalar nada

Asignar un **código de incidencia** y usarlo en la nota de **cada** ack relacionado:

```
INC-2026-014 · corte de fibra tramo norte · responsable: <técnico> · causa: en revisión
```

- Todas las alertas del mismo evento quedan con el mismo código en su nota y en el eventlog.
- Buscando `INC-2026-014` en el eventlog se reconstruye la línea de tiempo.
- El registro "maestro" (causa raíz, cierre, lecciones) va en una planilla o documento con el mismo código.

Sirve para empezar **hoy** y crear el hábito. Su límite: depende de la disciplina y no da reportes.

## 3. Herramientas externas (self-hosted, gratis)

| Herramienta | Integración | ¿Agrupa alertas en un incidente? | Comentario |
|---|---|---|---|
| **GLPI** (tickets + Problemas) | **Transport nativo** | Sí, vía ITIL: cada alerta abre un ticket y varios tickets se vinculan a un **Problema** con causa raíz y responsable | Muy usado en la región; además da inventario. El transport busca un ticket abierto con el mismo título (`[LibreNMS: equipo] regla`): si existe agrega un **seguimiento** en vez de duplicar (la recuperación también entra como seguimiento). Si el técnico lo marcó *Resuelto*: una nueva alerta lo **reabre** y una recuperación lo pasa a **Cerrado**. No lo cierra solo si nadie lo resolvió: el cierre es una decisión humana |
| **Alerta** (alerta.io) | Transport nativo | Sí: deduplica y agrupa por recurso/servicio en una consola | Liviano; es consola de NOC más que bitácora formal |
| **Keep** (keephq) | Provider/webhook | Sí: correlación por reglas (o IA) en incidentes | Moderno, más pesado; verificar estado del proyecto antes de adoptarlo |
| **Grafana OnCall** | Transport nativo | Sí, con guardias y escalamiento | Verificar estado de la versión open source antes de adoptarlo |
| **Zammad / osTicket** | Webhook / transport nativo (osTicket) | No correlaciona: un ticket por alerta; se agrupa a mano | Mesa de ayuda |

## 4. Recomendación para un equipo chico

1. **Primero, menos ruido:** dependencias bien cargadas (una caída de nodo = una alerta) y reglas sin ruido ([07](07-alertas-sin-ruido.md)).
2. **Hoy:** Opción 0 (código de incidencia en los ack).
3. **Cuando se quiera bitácora formal:** **GLPI** con el transport nativo, usando **Problemas** para agrupar.
   Probarlo primero en un laboratorio con alertas reales.
