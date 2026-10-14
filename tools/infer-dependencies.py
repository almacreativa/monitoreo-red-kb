#!/usr/bin/env python3
"""Infiere dependencias padre→hijo entre dispositivos de LibreNMS a partir de L2/L3.

Fuentes (todas ya recolectadas por LibreNMS):
  links       vecinos LLDP/CDP/MNDP          → evidencia directa (confianza ALTA)
  ports_fdb   tabla MAC por puerto (bridge)  → quién está "detrás" de cada puerto
  ipv4_mac    ARP por interfaz del router    → equipos L3 adyacentes (módems, ping-only)
  ports.ifPhysAddress                        → MACs propias de los equipos con SNMP

Idea central (escala a topologías grandes):
  1. Cada switch tiene UN puerto de subida (uplink): el puerto donde ve la MAC de la raíz.
     Todo lo que ve en los demás puertos está "aguas abajo" de él.
  2. El padre directo de un equipo D es el switch MÁS PROFUNDO que lo ve aguas abajo,
     o sea, el que lo ve en el puerto con MENOS equipos detrás (conjunto mínimo).
  3. Si un puerto de bajada tiene detrás un equipo-switch sin SNMP (no da FDB) junto con
     otros hosts, esos hosts probablemente cuelgan de ese switch (confianza MEDIA).
  4. Lo que solo aparece por ARP en una interfaz del router cuelga del router (L3).
  5. Lo que no se ve en L2 ni en ARP (destinos remotos) queda sin inferir: definirlo a mano.

Uso:
  infer-dependencies.py --root 1                  # muestra propuesta y diff (no escribe)
  infer-dependencies.py --root 1 --apply          # reemplaza device_relationships
  infer-dependencies.py --root 1 --switch 4       # declara el 4 como switch (sin SNMP)
  infer-dependencies.py --root 1 --ip 6=192.0.2.15     # el 6 se pollea por otra IP (p.ej. VPN)

Conexión a la base (LibreNMS en docker):
  LNMS_ENV_FILE      .env del stack con MYSQL_USER / MYSQL_PASSWORD  (default: ./.env)
  LNMS_DB_CONTAINER  container de MariaDB                             (default: librenms_db)
  LNMS_DB_NAME       base de datos                                    (default: librenms)
  También se aceptan MYSQL_USER / MYSQL_PASSWORD directamente como variables de entorno.
"""
import argparse
import os
import subprocess
from collections import defaultdict

ENV_FILE = os.path.expanduser(os.environ.get("LNMS_ENV_FILE", ".env"))
DB_CONTAINER = os.environ.get("LNMS_DB_CONTAINER", "librenms_db")
DB_NAME = os.environ.get("LNMS_DB_NAME", "librenms")


def env():
    vals = {k: os.environ[k] for k in ("MYSQL_USER", "MYSQL_PASSWORD") if k in os.environ}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.rstrip("\n").split("=", 1)
                    vals.setdefault(k, v.strip("'\""))
    missing = [k for k in ("MYSQL_USER", "MYSQL_PASSWORD") if k not in vals]
    if missing:
        raise SystemExit(f"Faltan {missing}: definir LNMS_ENV_FILE o exportarlas")
    return vals


E = env()


def q(sql):
    out = subprocess.run(
        ["docker", "exec", DB_CONTAINER, "mariadb", "-N", "-B",
         f"-u{E['MYSQL_USER']}", f"-p{E['MYSQL_PASSWORD']}", DB_NAME, "-e", sql],
        capture_output=True, text=True, check=True).stdout
    return [r.split("\t") for r in out.splitlines() if r]


def norm(mac):
    return (mac or "").lower().replace(":", "").replace("-", "").replace(".", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=int, required=True, help="device_id de la raíz (router/core)")
    ap.add_argument("--switch", type=int, action="append", default=[],
                    help="device_id de un switch sin SNMP (repetible)")
    ap.add_argument("--ip", action="append", default=[], metavar="ID=IP",
                    help="IP extra de un equipo (p.ej. su IP LAN si se pollea por otra), repetible")
    ap.add_argument("--apply", action="store_true", help="escribe device_relationships")
    a = ap.parse_args()

    dev = {int(i): {"name": d or h, "host": h, "ip": ip or h, "snmp": s == "0"}
           for i, h, d, ip, s in q("select device_id, hostname, ifnull(display,''), "
                                    "ifnull(inet6_ntoa(ip),''), snmp_disable from devices")}

    # MAC -> device: MACs propias (SNMP) + ARP de cualquier equipo (ping-only incluidos)
    mac2dev = {}
    for i, m in q("select device_id, ifPhysAddress from ports where ifPhysAddress is not null"):
        if norm(m) and norm(m) != "000000000000":
            mac2dev.setdefault(norm(m), int(i))
    ip2dev = {d["ip"]: i for i, d in dev.items()} | {d["host"]: i for i, d in dev.items()}
    for extra in a.ip:
        i, ip = extra.split("=", 1)
        ip2dev[ip] = int(i)
    arp = q("select a.device_id, a.port_id, a.mac_address, a.ipv4_address from ipv4_mac a")
    for _, _, m, ip in arp:
        if ip in ip2dev:
            mac2dev.setdefault(norm(m), ip2dev[ip])

    pname = {int(p): n for p, n in q("select port_id, ifName from ports")}
    root_macs = {m for m, d in mac2dev.items() if d == a.root}

    # FDB: switch -> puerto -> {devices}
    fdb = defaultdict(lambda: defaultdict(set))
    for s, p, m in q("select device_id, port_id, mac_address from ports_fdb"):
        d = mac2dev.get(norm(m))
        if d is not None and d != int(s):
            fdb[int(s)][int(p)].add(d)
        if norm(m) in root_macs:
            fdb[int(s)][int(p)].add(a.root)

    proposals = {}  # child -> (parent, confidence, evidence)

    def propose(child, parent, conf, why, override=False):
        rank = {"ALTA": 3, "MEDIA": 2, "BAJA": 1}
        cur = proposals.get(child)
        if child != parent and child != a.root and (
                cur is None or rank[conf] > rank[cur[1]] or (override and rank[conf] >= rank[cur[1]])):
            proposals[child] = (parent, conf, why)

    # 1) LLDP/CDP: vecino directo. El que está más cerca de la raíz es el padre (se resuelve abajo).
    lldp = q("select local_device_id, local_port_id, remote_device_id from links "
             "where remote_device_id is not null and remote_device_id > 0")

    # 2) FDB: padre = switch que ve al equipo aguas abajo en el puerto con menos equipos
    best = {}  # child -> (size, switch, port)
    for s, ports in fdb.items():
        uplinks = {p for p, ds in ports.items() if a.root in ds and s != a.root}
        for p, ds in ports.items():
            if p in uplinks:
                continue
            for d in ds - {a.root}:
                cand = (len(ds), s, p)
                if d not in best or cand < best[d]:
                    best[d] = cand
    for d, (n, s, p) in best.items():
        propose(d, s, "ALTA" if n == 1 else "MEDIA",
                f"FDB: {dev[s]['name']} lo ve en {pname.get(p, p)} ({n} equipo(s) detrás)")

    # 3) Switch sin SNMP: si comparte puerto de bajada con otros hosts, éstos cuelgan de él
    for sw in a.switch:
        if sw not in best:
            continue
        _, s, p = best[sw]
        for d in fdb[s][p] - {sw, a.root}:
            if d not in a.switch:
                propose(d, sw, "MEDIA",
                        f"comparte {dev[s]['name']}:{pname.get(p, p)} con el switch sin SNMP {dev[sw]['name']}",
                        override=True)

    # 4) LLDP confirma/afina (gana por confianza ALTA si el vecino es más profundo)
    for l, _, r in lldp:
        l, r = int(l), int(r)
        if r in best or r not in proposals:
            propose(r, l, "ALTA", f"LLDP/CDP: vecino de {dev[l]['name']}")

    # 5) ARP en interfaces del router: equipos L3 adyacentes no vistos en FDB
    for s, p, m, ip in arp:
        d = ip2dev.get(ip)
        if d is not None and int(s) == a.root and d not in proposals and d != a.root:
            propose(d, a.root, "MEDIA", f"ARP: {dev[a.root]['name']} lo ve en {pname.get(int(p), p)}")

    current = {(int(p), int(c)) for p, c in q("select parent_device_id, child_device_id from device_relationships")}
    proposed = {(par, c) for c, (par, _, _) in proposals.items()}

    print(f"{'HIJO':38} {'PADRE':34} CONF   EVIDENCIA")
    for c, (par, conf, why) in sorted(proposals.items(), key=lambda x: (x[1][0], x[0])):
        mark = "  " if (par, c) in current else "+ "
        print(f"{mark}{dev[c]['name'][:36]:36} {dev[par]['name'][:34]:34} {conf:6} {why}")
    unknown = [i for i in dev if i not in proposals and i != a.root]
    if unknown:
        print("\nSin evidencia L2/L3 (definir a mano):", ", ".join(dev[i]["name"] for i in unknown))
    gone = current - proposed
    kept = {(p, c) for p, c in gone if c in unknown}
    if gone - kept:
        print("\nRelaciones actuales que la inferencia NO confirma:")
        for p, c in sorted(gone - kept):
            print(f"- {dev[c]['name']} ← {dev[p]['name']}")

    if a.apply:
        rows = proposed | kept  # conserva las manuales de equipos sin evidencia
        q("delete from device_relationships")
        if rows:
            q("insert into device_relationships (parent_device_id, child_device_id) values "
              + ",".join(f"({p},{c})" for p, c in sorted(rows)))
        print(f"\nAplicado: {len(rows)} relaciones ({len(kept)} manuales conservadas).")


if __name__ == "__main__":
    main()
