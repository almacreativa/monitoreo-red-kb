#!/usr/bin/env bash
# Control de anonimato: falla si algún archivo contiene datos reales de una red.
# 1) Reglas genéricas (en el repo): IPs privadas/CGNAT/Tailscale y MACs que NO sean de documentación.
#    Permitido en ejemplos: 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24 (RFC 5737), 2001:db8::/32,
#    MACs 00:00:5e:00:53:xx (RFC 7042), y 10.0.0.0/8 SOLO con la forma 10.x/10.0.0.0 genérica.
# 2) Denylist privada (FUERA del repo): $KB_DENYLIST o ~/.config/kb-anonimato/denylist.txt
# Uso: scripts/check-anonimato.sh [archivos…]   (sin args: todos los archivos versionados o en stage)
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
DENY="${KB_DENYLIST:-$HOME/.config/kb-anonimato/denylist.txt}"
if [ $# -gt 0 ]; then FILES=("$@"); else mapfile -t FILES < <(git ls-files --cached --others --exclude-standard); fi
FILES=($(printf '%s\n' "${FILES[@]}" | grep -v -E '^scripts/check-anonimato\.sh$' | while read -r f; do [ -f "$f" ] && echo "$f"; done))
[ ${#FILES[@]} -eq 0 ] && exit 0
fail=0
generic=(
  '\b192\.168\.[0-9]{1,3}\.[0-9]{1,3}\b'
  '\b172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3}\b'
  '\b10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\b'
  '\b100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.[0-9]{1,3}\.[0-9]{1,3}\b'
  '\b([0-9a-f]{2}:){5}[0-9a-f]{2}\b'
)
allow='(\b10\.0\.0\.0\b|\b00:00:5e:00:53:[0-9a-f]{2}\b)'
for re in "${generic[@]}"; do
  hits=$(grep -n -i -E -o "$re" "${FILES[@]}" 2>/dev/null | grep -v -i -E ":$allow\$" || true)
  if [ -n "$hits" ]; then echo "✗ dato de red real (regla genérica):"; echo "$hits" | sed 's/^/   /'; fail=1; fi
done
if [ -f "$DENY" ]; then
  while IFS= read -r re; do
    [[ -z "$re" || "$re" == \#* ]] && continue
    hits=$(grep -n -i -E -l -- "$re" "${FILES[@]}" 2>/dev/null || true)
    # no se imprime el término (puede ser un secreto): solo archivo y número de regla
    [ -n "$hits" ] && { echo "✗ término de la denylist privada en:"; echo "$hits" | sed 's/^/   /'; fail=1; }
  done < "$DENY"
else
  echo "⚠ sin denylist privada ($DENY): solo se aplicaron las reglas genéricas" >&2
fi
[ $fail -eq 0 ] && echo "✓ anonimato OK (${#FILES[@]} archivos)"
exit $fail
