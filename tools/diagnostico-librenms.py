#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Alma Creativa
"""Diagnóstico de una instancia de LibreNMS — SOLO LECTURA.

Responde, en una página, "¿qué tan ordenada está nuestra instancia y por dónde empezar?":
colecta, nomenclatura, grupos, dependencias padre→hijo, reglas, transports, alertas abiertas,
ruido de los últimos N días y la carrera padre/hijo (el hijo alerta antes que su padre).

Garantías:
  - Solo ejecuta SELECT, dentro de una sesión `SET SESSION TRANSACTION READ ONLY`.
  - Nunca lee columnas de credenciales (community, authpass, cryptopass, transport_config).
  - La contraseña de la base viaja por stdin, no por la línea de comandos.
  - Con --anonimo reemplaza nombres de equipos y ubicaciones por IDs (para compartir el reporte).
  - Si una tabla o columna no existe en esta versión, la sección dice "n/d" y sigue.

Uso:
  diagnostico-librenms.py                      # reporte Markdown por stdout
  diagnostico-librenms.py --dias 30 --top 20   # ventana de ruido y tamaño de los rankings
  diagnostico-librenms.py --anonimo --salida diagnostico.md

Conexión (se detecta sola):
  Docker:   LNMS_DB_CONTAINER (default: librenms_db) + LNMS_ENV_FILE (default: ./.env)
  Nativo:   LNMS_DB_HOST=127.0.0.1 [LNMS_DB_PORT=3306] + LNMS_ENV_FILE=/opt/librenms/.env
  Credenciales: MYSQL_USER/MYSQL_PASSWORD o DB_USERNAME/DB_PASSWORD (del .env o del entorno).
  Base: LNMS_DB_NAME, o DB_DATABASE/MYSQL_DATABASE del .env (default: librenms).
  Recomendado: un usuario de base con permiso SELECT únicamente.
"""
import argparse
import os
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

ENV_FILE = os.path.expanduser(os.environ.get("LNMS_ENV_FILE", ".env"))


def load_env():
    vals = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.rstrip("\n").split("=", 1)
                    vals[k.strip()] = v.strip().strip("'\"")
    vals.update({k: v for k, v in os.environ.items()
                 if k.startswith(("MYSQL_", "DB_"))})
    user = vals.get("MYSQL_USER") or vals.get("DB_USERNAME")
    pwd = vals.get("MYSQL_PASSWORD") or vals.get("DB_PASSWORD")
    if not user or pwd is None:
        raise SystemExit("Faltan credenciales: definir LNMS_ENV_FILE o exportar MYSQL_USER/MYSQL_PASSWORD")
    db = os.environ.get("LNMS_DB_NAME") or vals.get("DB_DATABASE") or vals.get("MYSQL_DATABASE") or "librenms"
    host = os.environ.get("LNMS_DB_HOST")  # sin host explícito: modo Docker
    port = os.environ.get("LNMS_DB_PORT") or vals.get("DB_PORT") or "3306"
    return user, pwd, db, host, port


USER, PWD, DB, HOST, PORT = load_env()
CONTAINER = os.environ.get("LNMS_DB_CONTAINER", "librenms_db")


class Missing(Exception):
    pass


def q(sql):
    """Ejecuta una consulta de solo lectura. Devuelve filas (listas de str; NULL -> None)."""
    if HOST:
        client = shutil.which("mariadb") or shutil.which("mysql")
        if not client:
            raise SystemExit("No encuentro el cliente mariadb/mysql")
        cmd = [client, "--defaults-extra-file=/dev/stdin", "-h", HOST, "-P", str(PORT)]
    else:
        cmd = ["docker", "exec", "-i", CONTAINER, "mariadb", "--defaults-extra-file=/dev/stdin"]
    cmd += ["-N", "-B", DB, "-e", "SET SESSION TRANSACTION READ ONLY; " + sql]
    creds = f"[client]\nuser={USER}\npassword={PWD}\n"
    r = subprocess.run(cmd, input=creds, capture_output=True, text=True)
    if r.returncode != 0:
        raise Missing(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "error")
    return [[None if c == "NULL" else c for c in line.split("\t")] for line in r.stdout.splitlines()]


def one(sql, default=None):
    rows = q(sql)
    return rows[0][0] if rows and rows[0] else default


def has_table(t):
    return one(f"SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='{t}'") == "1"


def has_col(t, c):
    return one("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
               f"AND TABLE_NAME='{t}' AND COLUMN_NAME='{c}'") == "1"


# --------------------------------------------------------------------------- salida
OUT = []
FLAGS = []  # (nivel, texto) para el resumen


def w(s=""):
    OUT.append(s)


def table(headers, rows):
    if not rows:
        w("_(sin datos)_")
        return
    w("| " + " | ".join(headers) + " |")
    w("|" + "---|" * len(headers))
    for r in rows:
        w("| " + " | ".join("" if c is None else str(c).replace("|", "/") for c in r) + " |")


def flag(level, text):
    FLAGS.append((level, text))


def pct(a, b):
    return f"{(100.0 * a / b):.0f} %" if b else "n/d"


def section(title, fn):
    w(f"\n## {title}\n")
    try:
        fn()
    except Missing as e:
        w(f"_n/d en esta versión ({e})_")


# --------------------------------------------------------------------------- nombres
NAMES = {}
LOCS = {}
ANON = False


def dev(i):
    return NAMES.get(str(i), f"dev#{i}")


def load_names(anon):
    global ANON
    ANON = anon
    disp = "COALESCE(NULLIF(display,''), sysName, hostname)" if has_col("devices", "display") else "COALESCE(sysName, hostname)"
    for i, n in q(f"SELECT device_id, {disp} FROM devices"):
        NAMES[i] = f"dev#{i}" if anon else n
    if has_table("locations"):
        for i, n in q("SELECT id, location FROM locations"):
            LOCS[i] = f"loc#{i}" if anon else n


# --------------------------------------------------------------------------- secciones
def s_inventario():
    r = q("SELECT COUNT(*), SUM(disabled=0 AND `ignore`=0), SUM(status=1 AND disabled=0), SUM(status=0 AND disabled=0 AND `ignore`=0),"
          " SUM(disabled=1), SUM(`ignore`=1), SUM(snmp_disable=1) FROM devices")[0]
    tot, act, up, down, dis, ign, ping = (int(x or 0) for x in r)
    table(["Equipos", "Activos", "Up", "Down", "Deshabilitados", "Ignorados", "Solo ping"],
          [[tot, act, up, down, dis, ign, ping]])
    if act and down / act > 0.05:
        flag("🔴", f"{down} equipos activos están caídos ({pct(down, act)}): ¿caídos de verdad o dados de baja sin deshabilitar?")
    ports = q("SELECT COUNT(*), SUM(`ignore`=1), SUM(disabled=1) FROM ports WHERE deleted=0")[0]
    w(f"\nPuertos: {ports[0]} (ignorados: {ports[1] or 0}, deshabilitados: {ports[2] or 0})\n")
    w("**Sistemas operativos (top 10)**\n")
    table(["OS", "Equipos"], q("SELECT os, COUNT(*) c FROM devices GROUP BY os ORDER BY c DESC LIMIT 10"))
    if has_col("devices", "poller_group"):
        w("\n**Por poller group**\n")
        table(["poller_group", "Equipos"], q("SELECT poller_group, COUNT(*) FROM devices GROUP BY poller_group ORDER BY 1"))
    return act


def s_colecta(args):
    if has_table("poller_cluster"):
        rows = q("SELECT poller_name, last_report, poller_workers, discovery_workers, ping_enabled, ping_frequency,"
                 " alerting_enabled FROM poller_cluster ORDER BY poller_name")
        w("**Dispatcher Service (poller_cluster)**\n")
        table(["Nodo", "Último reporte", "Workers poller", "Workers discovery", "Fast ping", "Cada (s)", "Alerting"], rows)
        if not rows:
            flag("🟠", "No hay nodos del Dispatcher Service: la colecta corre por cron (no recomendado a esta escala)")
        elif not any(r[4] == "1" for r in rows):
            flag("🟠", "Fast ping desactivado: las caídas se detectan recién en el ciclo de polling")
    if has_table("pollers"):
        rows = q("SELECT poller_name, devices, time_taken, last_polled FROM pollers ORDER BY poller_name")
        if rows:
            w("\n**Pollers por cron (tabla pollers)**\n")
            table(["Poller", "Equipos", "Duración ciclo (s)", "Último"], rows)
            for r in rows:
                if r[2] and float(r[2]) > 280:
                    flag("🔴", f"El poller {r[0]} tarda {float(r[2]):.0f} s por ciclo (≥ 5 min): faltan pollers o workers")
    t = [float(x[0]) for x in q("SELECT last_polled_timetaken FROM devices WHERE disabled=0 AND snmp_disable=0"
                                " AND last_polled_timetaken IS NOT NULL") if x[0]]
    if t:
        t.sort()
        p95 = t[max(0, -(-95 * len(t) // 100) - 1)]  # percentil por rango más cercano
        w(f"\nTiempo de polling por equipo: promedio {sum(t)/len(t):.1f} s · p95 {p95:.1f} s · máx {t[-1]:.1f} s"
          f" · suma {sum(t):.0f} s de trabajo por ciclo\n")
    stale = q("SELECT device_id, last_polled FROM devices WHERE disabled=0 AND `ignore`=0 AND snmp_disable=0"
              " AND (last_polled IS NULL OR last_polled < NOW() - INTERVAL 15 MINUTE) ORDER BY last_polled LIMIT 200")
    w(f"Equipos SNMP sin pollear hace > 15 min: **{len(stale)}**\n")
    if stale:
        flag("🔴", f"{len(stale)} equipos no se pollean hace más de 15 min")
        table(["Equipo", "Último poll"], [[dev(i), lp] for i, lp in stale[:args.top]])
    w("\n**Equipos más lentos**\n")
    table(["Equipo", "Polling (s)", "Discovery (s)"],
          [[dev(i), f"{float(a or 0):.1f}", f"{float(b or 0):.1f}"] for i, a, b in q("SELECT device_id, last_polled_timetaken, last_discovered_timetaken FROM devices"
                                            f" WHERE disabled=0 ORDER BY last_polled_timetaken DESC LIMIT {args.top}")])
    if has_table("config"):
        rc = one("SELECT config_value FROM config WHERE config_name='rrdcached'")
        w(f"\nrrdcached en la config de la base: {rc or 'no definido (puede estar en config.php o en variables de entorno)'}")


def s_nomenclatura(act):
    noloc = int(one("SELECT COUNT(*) FROM devices WHERE disabled=0 AND (location_id IS NULL OR location_id=0)", 0))
    nloc = int(one("SELECT COUNT(DISTINCT location_id) FROM devices WHERE disabled=0 AND location_id IS NOT NULL", 0))
    single = int(one("SELECT COUNT(*) FROM (SELECT location_id FROM devices WHERE disabled=0 AND location_id IS NOT NULL"
                     " GROUP BY location_id HAVING COUNT(*)=1) x", 0))
    dupe = int(one("SELECT COUNT(*) FROM (SELECT sysName FROM devices WHERE sysName<>'' GROUP BY sysName HAVING COUNT(*)>1) x", 0))
    rows = [["Equipos activos sin ubicación", noloc, pct(noloc, act)],
            ["Ubicaciones en uso", nloc, ""],
            ["Ubicaciones con un solo equipo", single, pct(single, nloc)],
            ["sysName repetidos", dupe, ""]]
    if has_col("devices", "display"):
        d = int(one("SELECT COUNT(*) FROM devices WHERE disabled=0 AND display IS NOT NULL AND display<>'' AND display<>hostname", 0))
        rows.append(["Con nombre visible (display) propio", d, pct(d, act)])
    if has_col("devices", "override_sysLocation"):
        o = int(one("SELECT COUNT(*) FROM devices WHERE disabled=0 AND override_sysLocation=1", 0))
        rows.append(["Con ubicación fijada a mano (override)", o, pct(o, act)])
    table(["Indicador", "Valor", "%"], rows)
    if act and noloc / act > 0.10:
        flag("🟠", f"{pct(noloc, act)} de los equipos no tiene ubicación: sin sitio no se puede agrupar por POP")
    if nloc and single / nloc > 0.5:
        flag("🟠", "Más de la mitad de las ubicaciones tiene un solo equipo: probable sysLocation sin normalizar")
    w("\n**Ubicaciones con más equipos**\n")
    table(["Ubicación", "Equipos"], [[LOCS.get(i, f"loc#{i}"), c] for i, c in
                                      q("SELECT location_id, COUNT(*) c FROM devices WHERE disabled=0 AND location_id IS NOT NULL"
                                        " GROUP BY location_id ORDER BY c DESC LIMIT 10")])


def s_grupos(act):
    rows = q("SELECT g.id, g.name, g.type, COUNT(d.device_id) FROM device_groups g LEFT JOIN device_group_device d"
             " ON d.device_group_id=g.id GROUP BY g.id, g.name, g.type ORDER BY 4 DESC")
    nogroup = int(one("SELECT COUNT(*) FROM devices WHERE disabled=0 AND device_id NOT IN"
                      " (SELECT device_id FROM device_group_device)", 0))
    types = Counter(r[2] for r in rows)
    empty = [r for r in rows if r[3] == "0"]
    w(f"Grupos: **{len(rows)}** (dinámicos: {types.get('dynamic', 0)}, estáticos: {types.get('static', 0)}) ·"
      f" vacíos: {len(empty)} · equipos activos sin grupo: **{nogroup}** ({pct(nogroup, act)})\n")
    table(["Grupo", "Tipo", "Equipos"], [[f"grp#{r[0]}" if ANON else r[1], r[2], r[3]] for r in rows[:30]])
    if act and nogroup / act > 0.2:
        flag("🟠", f"{pct(nogroup, act)} de los equipos no está en ningún grupo: no le aplican reglas por grupo")
    if types.get("static", 0) > types.get("dynamic", 0):
        flag("🟡", "Predominan los grupos estáticos: los equipos nuevos no entran solos")


def s_dependencias(act, args):
    rel = q("SELECT parent_device_id, child_device_id FROM device_relationships")
    state = {i: (s, d, ig) for i, s, d, ig in q("SELECT device_id, status, disabled, `ignore` FROM devices")}
    active = {i for i, (s, d, ig) in state.items() if d == "0" and ig == "0"}
    parents = defaultdict(set)
    children = defaultdict(set)
    for p, c in rel:
        parents[c].add(p)
        children[p].add(c)
    withp = [c for c in active if parents.get(c)]
    multi = [c for c in active if len(parents.get(c, ())) > 1]
    is_parent = {p for p in children if p in active}
    orphans = [d for d in active if not parents.get(d) and d not in is_parent]
    bad_par = sorted({p for p in children if state.get(p, ("", "1", "1"))[1] == "1" or state.get(p, ("", "1", "1"))[2] == "1"})
    # profundidad y ciclos
    depth, cycles = {}, set()

    def d_of(n, seen=()):
        if n in seen:
            cycles.add(n)
            return 0
        if n in depth:
            return depth[n]
        ps = parents.get(n)
        depth[n] = 0 if not ps else 1 + max(d_of(p, seen + (n,)) for p in ps)
        return depth[n]
    for n in active:
        d_of(n)
    hist = Counter(depth[n] for n in active)
    table(["Indicador", "Valor", "%"], [
        ["Equipos activos con padre", len(withp), pct(len(withp), act)],
        ["Con más de un padre (anillos/redundancia)", len(multi), pct(len(multi), act)],
        ["Equipos que son padre de alguien", len(is_parent), ""],
        ["Sueltos (ni padre ni hijo)", len(orphans), pct(len(orphans), act)],
        ["Padres deshabilitados o ignorados", len(bad_par), ""],
        ["Ciclos detectados", len(cycles), ""],
        ["Profundidad máxima del árbol", max(hist) if hist else 0, ""],
    ])
    w("\nEquipos por nivel del árbol (0 = raíz o sin padre): " +
      " · ".join(f"nivel {k}: {v}" for k, v in sorted(hist.items())))
    if act and len(withp) / act < 0.5:
        flag("🔴", f"Solo {pct(len(withp), act)} de los equipos tiene padre: una caída de nodo dispara una alerta por equipo")
    if bad_par:
        flag("🟠", f"{len(bad_par)} padres están deshabilitados/ignorados: LibreNMS no los cuenta como caídos y sus hijos alertan igual")
        table(["Padre deshabilitado/ignorado", "Hijos"], [[dev(p), len(children[p])] for p in bad_par[:args.top]])
    if cycles:
        flag("🔴", f"Hay {len(cycles)} equipos en ciclos de dependencia")
    sup = one("SELECT COUNT(*) FROM eventlog WHERE message LIKE 'Skipped alerts because all parent%'"
              f" AND datetime > NOW() - INTERVAL {args.dias} DAY", 0)
    w(f"\nAlertas suprimidas por padre caído (últimos {args.dias} días): **{sup}**")
    return parents


def rule_delays():
    """rule_id -> demora (s) antes de la primera notificación."""
    if has_table("alert_operation_segments") and has_col("alert_rules", "alert_operation_id"):
        return {r: int(float(s or 0)) for r, s in q(
            "SELECT r.id, MIN(s.start_in_seconds) FROM alert_rules r LEFT JOIN alert_operation_segments s"
            " ON s.alert_operation_id=r.alert_operation_id AND s.operation_phase='problem' GROUP BY r.id")}
    out = {}
    for r, d in q("SELECT id, JSON_UNQUOTE(JSON_EXTRACT(extra,'$.delay')) FROM alert_rules"):
        out[r] = int(float(d)) if d and d.replace(".", "", 1).isdigit() else 0
    return out


def down_rule_ids():
    return {r for r, in q("SELECT id FROM alert_rules WHERE query REGEXP 'devices\\\\.status *= *0'")}


def s_reglas(args):
    rules = q("SELECT id, name, disabled, severity FROM alert_rules ORDER BY id")
    scoped = set()
    for t, c in (("alert_device_map", "rule_id"), ("alert_group_map", "rule_id"), ("alert_location_map", "rule_id")):
        if has_table(t):
            scoped |= {r for r, in q(f"SELECT DISTINCT {c} FROM {t}")}
    delays = rule_delays()
    downs = down_rule_ids()
    with_tr = set()
    if has_table("alert_operation_transport_map") and has_col("alert_rules", "alert_operation_id"):
        with_tr |= {r for r, in q("SELECT DISTINCT r.id FROM alert_rules r JOIN alert_operation_segments s"
                                  " ON s.alert_operation_id=r.alert_operation_id JOIN alert_operation_transport_map m"
                                  " ON m.segment_id=s.id")}
    if has_table("alert_transport_map"):
        with_tr |= {r for r, in q("SELECT DISTINCT rule_id FROM alert_transport_map")}
    defaults = int(one("SELECT COUNT(*) FROM alert_transports WHERE is_default=1", 0)) if has_table("alert_transports") else 0
    active = [r for r in rules if r[2] == "0"]
    glob = [r for r in active if r[0] not in scoped]
    w(f"Reglas: **{len(rules)}** (activas: {len(active)}) · globales (aplican a todos los equipos): **{len(glob)}**"
      f" · transports por defecto: {defaults}\n")
    table(["#", "Regla", "Activa", "Severidad", "Alcance", "Demora 1ª notif.", "Transport"],
          [[r[0], r[1], "sí" if r[2] == "0" else "no", r[3], "por grupo/equipo" if r[0] in scoped else "GLOBAL",
            f"{delays.get(r[0], 0)} s", "propio" if r[0] in with_tr else ("default" if defaults else "NINGUNO")]
           for r in rules])
    if active and len(glob) / len(active) > 0.5:
        flag("🟠", f"{len(glob)} de {len(active)} reglas activas son globales: mismos umbrales para core y acceso")
    for r in active:
        if r[0] in downs and delays.get(r[0], 0) < 120:
            flag("🔴", f"La regla de caída «{r[1]}» notifica con {delays.get(r[0], 0)} s de demora:"
                       " la carrera padre/hijo hará que los hijos alerten antes que el padre (sugerido: 120–300 s)")
        if r[0] not in with_tr and not defaults:
            flag("🔴", f"La regla «{r[1]}» no tiene transport ni hay uno por defecto: nadie se entera")
    if has_table("alert_transports"):
        w("\n**Transports**\n")
        table(["Tipo", "Cantidad", "Por defecto"],
              q("SELECT transport_type, COUNT(*), SUM(is_default) FROM alert_transports GROUP BY transport_type ORDER BY 2 DESC"))


def s_alertas_abiertas(args):
    rows = q("SELECT state, COUNT(*) FROM alerts GROUP BY state")
    names = {"0": "ok", "1": "activa", "2": "reconocida (ack)", "3": "empeoró", "4": "mejoró", "5": "cambió"}
    table(["Estado", "Alertas"], [[names.get(s, s), c] for s, c in rows])
    old = q("SELECT a.device_id, r.name, a.timestamp, a.state FROM alerts a JOIN alert_rules r ON r.id=a.rule_id"
            " WHERE a.state IN (1,2) AND a.timestamp < NOW() - INTERVAL 7 DAY ORDER BY a.timestamp LIMIT 500")
    nonote = int(one("SELECT COUNT(*) FROM alerts WHERE state=2 AND (note IS NULL OR note='')", 0)) if has_col("alerts", "note") else 0
    w(f"\nAlertas abiertas hace más de 7 días: **{len(old)}** · reconocidas sin nota: **{nonote}**\n")
    if old:
        flag("🟠", f"{len(old)} alertas siguen abiertas hace más de 7 días: o se resuelven o la regla está mal")
        table(["Equipo", "Regla", "Desde", "Estado"], [[dev(d), n, t, names.get(s, s)] for d, n, t, s in old[:args.top]])


def s_ruido(args):
    rows = q("SELECT rule_id, device_id, state, time_logged FROM alert_log"
             f" WHERE time_logged > NOW() - INTERVAL {args.dias} DAY ORDER BY time_logged")
    rname = dict(q("SELECT id, name FROM alert_rules"))
    opens = [r for r in rows if r[2] == "1"]
    w(f"Alertas disparadas en {args.dias} días: **{len(opens)}** (≈ {len(opens)/max(args.dias, 1):.1f} por día)\n")
    w("**Reglas más ruidosas**\n")
    table(["Regla", "Disparos"], [[rname.get(r, r), c] for r, c in Counter(r[0] for r in opens).most_common(args.top)])
    w("\n**Equipos más ruidosos**\n")
    table(["Equipo", "Disparos"], [[dev(d), c] for d, c in Counter(r[1] for r in opens).most_common(args.top)])
    # microcortes: alerta que se recupera en < 5 min
    start, short = {}, Counter()
    for rid, did, st, t in rows:
        ts = datetime.strptime(t[:19], "%Y-%m-%d %H:%M:%S")
        if st == "1":
            start[(rid, did)] = ts
        elif st == "0" and (rid, did) in start:
            if ts - start.pop((rid, did)) < timedelta(minutes=5):
                short[(rid, did)] += 1
    total_short = sum(short.values())
    w(f"\nAlertas que se recuperaron solas en menos de 5 min (flapping/microcortes): **{total_short}**"
      f" ({pct(total_short, len(opens))} de los disparos)\n")
    if opens and total_short / len(opens) > 0.3:
        flag("🟠", f"{pct(total_short, len(opens))} de las alertas se recuperan solas en < 5 min: ruido que falsea MTTR")
    table(["Equipo", "Regla", "Microcortes"], [[dev(d), rname.get(r, r), c] for (r, d), c in short.most_common(args.top)])
    return opens


def s_carrera(parents, opens, args):
    downs = down_rule_ids()
    if not downs:
        w("_No se encontró una regla de caída de equipo (devices.status = 0)._")
        return
    by_dev = defaultdict(list)
    for rid, did, _, t in opens:
        if rid in downs:
            by_dev[did].append(datetime.strptime(t[:19], "%Y-%m-%d %H:%M:%S"))
    win = timedelta(minutes=10)
    early, pairs = 0, Counter()
    total_child_downs = 0
    for c, times in by_dev.items():
        ps = parents.get(c)
        if not ps:
            continue
        for tc in times:
            total_child_downs += 1
            for p in ps:
                if any(tc <= tp <= tc + win for tp in by_dev.get(p, ())):
                    early += 1
                    pairs[(p, c)] += 1
                    break
    w(f"Caídas de equipos con padre en {args.dias} días: {total_child_downs} · **el hijo se registró caído ANTES que su padre"
      f" (≤ 10 min): {early}**\n")
    w("Cada una de esas es una alerta que la supresión por dependencias no pudo frenar"
      " (el padre todavía no figuraba caído). Se corrige con demora en la regla de caída y fast ping.\n")
    if early:
        flag("🔴", f"{early} veces el hijo alertó antes que su padre: subir la demora de la regla de caída")
    table(["Padre", "Hijo", "Veces"], [[dev(p), dev(c), n] for (p, c), n in pairs.most_common(args.top)])


def s_mantenimientos(args):
    if not has_table("alert_schedule"):
        raise Missing("sin tabla alert_schedule")
    tot = int(one("SELECT COUNT(*) FROM alert_schedule", 0))
    rec = int(one("SELECT COUNT(*) FROM alert_schedule WHERE recurring=1", 0))
    now = int(one("SELECT COUNT(*) FROM alert_schedule WHERE recurring=0 AND NOW() BETWEEN start AND end", 0))
    recent = int(one(f"SELECT COUNT(*) FROM alert_schedule WHERE start > NOW() - INTERVAL {args.dias} DAY", 0))
    table(["Mantenimientos", "Recurrentes", "Activos ahora (únicos)", f"Creados en {args.dias} días"], [[tot, rec, now, recent]])
    if recent == 0:
        flag("🟡", f"No se programó ningún mantenimiento en {args.dias} días: los trabajos planificados se registran como incidentes")


def main():
    ap = argparse.ArgumentParser(description="Diagnóstico de solo lectura de una instancia de LibreNMS")
    ap.add_argument("--dias", type=int, default=30, help="ventana para ruido y carrera padre/hijo (default 30)")
    ap.add_argument("--top", type=int, default=20, help="largo de los rankings (default 20)")
    ap.add_argument("--anonimo", action="store_true", help="reemplaza nombres de equipos y ubicaciones por IDs")
    ap.add_argument("--salida", help="escribir el reporte en este archivo (además de stdout)")
    args = ap.parse_args()

    try:
        ver = one("SELECT VERSION()")
        mig = one("SELECT migration FROM migrations ORDER BY id DESC LIMIT 1") if has_table("migrations") else None
    except Missing as e:
        raise SystemExit(f"No pude conectar a la base: {e}")
    load_names(args.anonimo)

    w("# Diagnóstico de LibreNMS (solo lectura)")
    w(f"\nGenerado: {datetime.now():%Y-%m-%d %H:%M} · base {ver} · última migración: {mig or 'n/d'}"
      f" · ventana: {args.dias} días{' · ANONIMIZADO' if args.anonimo else ''}")
    w("\n<!--RESUMEN-->")

    ctx = {}
    section("1. Inventario", lambda: ctx.update(act=s_inventario()))
    act = ctx.get("act") or 0
    section("2. Colecta (pollers)", lambda: s_colecta(args))
    section("3. Nomenclatura y ubicaciones", lambda: s_nomenclatura(act))
    section("4. Grupos", lambda: s_grupos(act))
    section("5. Dependencias padre→hijo", lambda: ctx.update(parents=s_dependencias(act, args)))
    section("6. Reglas y transports", lambda: s_reglas(args))
    section("7. Alertas abiertas", lambda: s_alertas_abiertas(args))
    section(f"8. Ruido (últimos {args.dias} días)", lambda: ctx.update(opens=s_ruido(args)))
    section("9. Carrera padre/hijo", lambda: s_carrera(ctx.get("parents", {}), ctx.get("opens", []), args))
    section("10. Mantenimientos programados", lambda: s_mantenimientos(args))

    order = {"🔴": 0, "🟠": 1, "🟡": 2}
    summ = ["## Resumen: por dónde empezar\n"]
    if FLAGS:
        summ += [f"- {lvl} {txt}" for lvl, txt in sorted(FLAGS, key=lambda f: order.get(f[0], 9))]
    else:
        summ.append("- ✅ Sin hallazgos relevantes con los umbrales actuales.")
    summ.append("\n_🔴 urgente · 🟠 importante · 🟡 mejora_")
    i = OUT.index("\n<!--RESUMEN-->")
    OUT[i:i + 1] = [""] + summ
    text = "\n".join(OUT) + "\n"
    sys.stdout.write(text)
    if args.salida:
        with open(args.salida, "w") as f:
            f.write(text)


if __name__ == "__main__":
    main()
