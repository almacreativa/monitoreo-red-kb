# 06 · Dashboards y mapas reproducibles

Armarlos por la UI está bien para explorar. Para replicarlos en otra instancia, o reconstruirlos
después de un error, conviene tenerlos **como código**.

## Dashboard por SQL

Tablas `dashboards` y `users_widgets`. Los gotchas que hacen que "no funcione" sin ningún error a la vista:

| Síntoma | Causa | Correcto |
|---|---|---|
| Widget: "Problem with backend" (404) | El widget de gráficos se llama `generic-graph` | `widget = 'generic-graph'` |
| Gráficos vacíos (`-nan`) | `graph_range: "oneday"` no existe | `day`, `twoday`, `week`, `month`, `year`… |
| Dashboard a media pantalla | La grilla GridStack tiene **20** columnas | Diseñar en 20 (`col` es 1-based) |
| El insert falla | `refresh` es `tinyint` (máx. 127) | ≤ 120 |

Ejemplo de widget de gráfico:
```sql
INSERT INTO users_widgets (user_id, widget, col, `row`, size_x, size_y, title, refresh, settings, dashboard_id)
VALUES (1,'generic-graph',1,3,10,3,'WAN1 · tráfico',60,
 '{"title":"WAN1 · tráfico","graph_type":"port_bits","graph_port":<port_id>,"graph_range":"day","graph_legend":"yes"}',@d);
```
Tipos útiles:
- `port_bits` (con `graph_port`);
- `device_icmp_perf` (latencia y pérdida, con `graph_device`);
- `bill_bits` (con `graph_bill`, rango `month`);
- `application_ups-nut_charge`, `_load` y `_voltage_input` (con `graph_application`).

Para que sea el dashboard por defecto:
`INSERT INTO users_prefs (user_id,pref,value) VALUES (1,'dashboard',@d) ON DUPLICATE KEY UPDATE value=@d;`

## Custom Map por Eloquent (no por SQL)

Las columnas `options`, `newnodeconfig` y `newedgeconfig` las arma el controller. Crear el mapa por SQL
crudo deja los defaults incompletos. Conviene crearlo con los **modelos** vía `artisan tinker`:
```bash
docker cp mapa.php librenms:/tmp/ && docker exec -u librenms librenms php /opt/librenms/artisan tinker --execute="require '/tmp/mapa.php';"
```
- **Nodos** (`CustomMapNode`): con `device_id` toman el color de estado del equipo. Sin `device_id`
  son decorativos ("Internet", "Wi-Fi").
- **Aristas** (`CustomMapEdge`): con `port_id` + `showbps` / `showpct` muestran **tráfico en vivo** y se
  colorean por carga. El % se calcula sobre `ifSpeed`: cargar la velocidad contratada en los puertos WAN.
- **Gotcha:** el widget de dashboard referencia el mapa por `custom_map_id`. Un script que **borra y
  recrea** el mapa rompe el widget. Hay que actualizarlo **en el lugar**: borrar solo nodos y aristas, y conservar el registro del mapa.

## Verificación visual

Varios de estos problemas **no se ven en la base de datos**: todo parece cargado bien y la página
muestra errores. Conviene una captura headless logueada después de cada cambio:
```bash
PWCORE=<ruta>/playwright-core LU=admin LP='<password>' LNMS_URL=http://<librenms> \
  node tools/shot.js /overview /tmp/dash.png 1600 1000
```
