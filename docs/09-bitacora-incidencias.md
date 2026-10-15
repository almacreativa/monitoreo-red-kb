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

## 4. A escala de ISP (1.000–1.500 equipos)

A esta escala el problema no es "dónde anotar", sino **tormentas de alertas**: una caída de un nodo de
distribución puede disparar cientos de alertas a la vez. Conectar LibreNMS directo a un sistema de tickets
sin ordenar antes llena la mesa de tickets basura y el equipo deja de confiar en ella.

### 4.1 Ordenar LibreNMS primero (en este orden)

| # | Qué | Por qué | En esta KB |
|---|---|---|---|
| 1 | **Colecta estable:** RRDCached + Dispatcher Service; pollers distribuidos si un ciclo supera 5 min (un poller rinde ~1.000 equipos según latencia) | Si la colecta se atrasa, las alertas llegan tarde o se pierden | — |
| 2 | **Nombres y ubicaciones normalizados** | Todo lo de abajo se apoya en eso | [05](05-nomenclatura.md) |
| 3 | **Grupos dinámicos** por rol y por sitio/POP | Equipos nuevos entran solos a su grupo | [05](05-nomenclatura.md) |
| 4 | **Dependencias padre→hijo** | Una caída de nodo = **una** alerta. Es la base de cualquier correlación | [02](02-topologia-dependencias.md) + `tools/infer-dependencies.py` |
| 5 | **Reglas por grupo** (no globales) | Umbrales distintos para core y acceso | [07](07-alertas-sin-ruido.md) |
| 6 | **Plantillas y transports por grupo**, con datos estructurados (equipo, sitio, regla, severidad) | El sistema de incidentes necesita esos campos para agrupar | — |
| 7 | **Mantenimientos programados** como hábito | No ensuciar métricas ni bitácora con trabajos planificados | — |

### 4.2 Arquitectura en tres capas

```
LibreNMS (colecta + supresión por dependencias)
   │ webhook / transport
   ▼
Correlación (Keep o Alerta): agrupa ráfagas por sitio/servicio/ventana de tiempo → 1 evento
   │
   ▼
ITSM (GLPI o iTop): ticket/Problema con responsable, causa raíz, cierre y métricas (MTTR, SLA)
```

| Capa | Opciones | Nota |
|---|---|---|
| Correlación | **Keep** (reglas o IA, incidentes), **Alerta** (deduplicación, liviano) | Verificar estado y actividad del proyecto antes de adoptar |
| ITSM / bitácora | **GLPI** (transport nativo; Problemas para agrupar; reportes de SLA), **iTop** (fuerte en CMDB e impacto en servicios, más esfuerzo de mantener), Znuny/OTRS | GLPI no correlaciona solo: deduplica por equipo+regla; la agrupación en Problema es humana |
| Guardias y escalamiento | Opsgenie / JSM (pago, SaaS), Grafana OnCall | Solo si hay guardias 24/7 formales |

### 4.3 Fases sugeridas

1. **Diagnóstico** de la instancia actual (solo lectura): reglas, grupos, transports, cobertura de
   dependencias, tiempos de polling, top de alertas ruidosas.
2. **Saneamiento** (4.1). Se mide el antes y el después en cantidad de alertas por evento.
3. **Bitácora mínima:** convención de código de incidencia (sección 2) mientras tanto.
4. **Piloto de correlación + ITSM** con un subconjunto (un POP), luego extender.
5. **Métricas:** MTTA, MTTR, SLA, causas más frecuentes.

**Riesgos:**
- Dependencias desactualizadas silencian alertas reales (falsos negativos). Revisar el diff de
  dependencias periódicamente; no reescribir a ciegas.
- La causa raíz no se automatiza: requiere campos obligatorios al cerrar y disciplina.
