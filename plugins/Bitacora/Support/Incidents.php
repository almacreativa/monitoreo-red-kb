<?php

// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (c) 2026 Alma Creativa

/*
 * Bitácora de incidencias para LibreNMS (plugin local, prototipo).
 *
 * Modelo: no hay tablas propias. Cada registro es una entrada del eventlog con
 *   type = 'incidencia', reference = 'INC-AAAA-NNN', message = '[ACCIÓN] texto'.
 * Un mismo código en varios equipos = un incidente que agrupa varias alertas.
 *
 * Escritura: el formulario hace POST a la ruta oficial de settings del plugin
 * (plugin.update: CSRF + permiso plugin.admin). Los registros quedan en
 * settings['pending'] y se vuelcan al eventlog al volver a la página (redirect inmediato).
 */

namespace App\Plugins\Bitacora\Support;

use App\Models\Device;
use App\Models\DeviceGroup;
use App\Models\Eventlog;
use App\Models\Plugin;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;
use LibreNMS\Enum\Severity;

class Incidents
{
    public const TYPE = 'incidencia';
    public const ACTIONS = ['apertura' => 'APERTURA', 'nota' => 'NOTA', 'cierre' => 'CIERRE'];
    public const CAUSES = ['energia' => 'Energía', 'fibra' => 'Fibra / enlace', 'radio' => 'Radioenlace',
        'configuracion' => 'Configuración', 'hardware' => 'Hardware', 'proveedor' => 'Proveedor upstream',
        'mantenimiento' => 'Mantenimiento', 'otro' => 'Otro'];
    private const CODE_RE = '/^INC-\d{4}-\d{3,5}$/';

    /** Vuelca al eventlog lo que el formulario dejó en settings['pending']. Devuelve mensajes para la vista. */
    public static function flushPending(): array
    {
        $user = auth()->user();
        $plugin = Plugin::where('plugin_name', 'Bitacora')->first();
        $pending = $plugin?->settings['pending'] ?? [];
        if (! $plugin || ! $pending || ! $user || ! $user->can('plugin.admin')) {
            return [];
        }
        $msgs = [];
        foreach ((array) $pending as $p) {
            $msgs[] = self::apply((array) $p);
        }
        $plugin->settings = [];
        $plugin->save();

        return array_filter($msgs);
    }

    private static function apply(array $p): ?string
    {
        $action = $p['action'] ?? '';
        if (! isset(self::ACTIONS[$action])) {
            return 'Acción inválida: no se registró nada';
        }
        $text = trim(strip_tags((string) ($p['text'] ?? '')));
        if ($text === '') {
            return 'Falta la descripción: no se registró nada';
        }
        $text = mb_substr($text, 0, 500);
        $code = strtoupper(trim((string) ($p['code'] ?? '')));
        if ($code === '' && $action === 'apertura') {
            $code = self::nextCode();
        }
        if (! preg_match(self::CODE_RE, $code)) {
            return "Código inválido «{$code}» (formato INC-AAAA-NNN)";
        }

        $ids = collect($p['devices'] ?? [])->filter(fn ($v) => ctype_digit((string) $v))->map('intval');
        if (! empty($p['group']) && ctype_digit((string) $p['group'])) {
            $ids = $ids->merge(DeviceGroup::find((int) $p['group'])?->devices()->pluck('devices.device_id') ?? []);
        }
        if ($ids->isEmpty() && $action !== 'apertura') {
            $ids = self::devicesOf($code);
        }
        $ids = Device::whereIn('device_id', $ids->unique())->pluck('device_id');
        if ($ids->isEmpty()) {
            return "Sin equipos para {$code}: elegí equipos o un grupo";
        }

        $tag = self::ACTIONS[$action];
        if ($action === 'cierre') {
            $cause = self::CAUSES[$p['cause'] ?? ''] ?? 'Sin clasificar';
            $tag .= " · causa: {$cause}";
        }
        $sev = ['apertura' => Severity::Warning, 'nota' => Severity::Info, 'cierre' => Severity::Ok][$action];
        // Fecha opcional (registro a posteriori): solo en el pasado y dentro de 30 días
        $when = now();
        if (! empty($p['start'])) {
            try {
                $t = \Carbon\Carbon::parse((string) $p['start']);
                if ($t->lte(now()) && $t->gte(now()->subDays(30))) {
                    $when = $t;
                }
            } catch (\Throwable) {
                return 'Fecha de inicio inválida: no se registró nada';
            }
        }
        foreach ($ids as $id) {
            Eventlog::create([
                'device_id' => (int) $id,
                'datetime' => $when,
                'message' => "[{$tag}] {$text}",
                'type' => self::TYPE,
                'reference' => $code,
                'severity' => $sev,
                'username' => auth()->user()?->username ?? '',
            ]);
        }

        return null;
    }

    public static function nextCode(): string
    {
        $year = date('Y');
        $last = Eventlog::where('type', self::TYPE)->where('reference', 'like', "INC-{$year}-%")
            ->pluck('reference')->map(fn ($r) => (int) substr($r, 9))->max() ?? 0;

        return sprintf('INC-%s-%03d', $year, $last + 1);
    }

    public static function devicesOf(string $code): Collection
    {
        return Eventlog::where('type', self::TYPE)->where('reference', $code)->distinct()->pluck('device_id');
    }

    /** Incidentes agrupados por código, más recientes primero. */
    public static function all(?int $deviceId = null): Collection
    {
        $q = Eventlog::where('type', self::TYPE)->whereNotNull('reference')->orderBy('datetime');
        if ($deviceId) {
            $q->whereIn('reference', Eventlog::where('type', self::TYPE)->where('device_id', $deviceId)->select('reference'));
        }
        $names = [];

        return $q->get()->groupBy('reference')->map(function (Collection $rows, $code) use (&$names) {
            $devIds = $rows->pluck('device_id')->unique()->values();
            foreach ($devIds as $id) {
                $names[$id] ??= Device::find($id)?->displayName() ?? "#{$id}";
            }
            // una fila de la línea de tiempo por acción (misma hora + mismo texto = un registro sobre N equipos)
            $timeline = $rows->groupBy(fn ($r) => $r->datetime . '|' . $r->message)->map(fn ($g) => [
                'datetime' => $g->first()->datetime,
                'message' => $g->first()->message,
                'username' => $g->first()->username,
                'devices' => $g->pluck('device_id')->unique()->map(fn ($id) => $names[$id])->values(),
            ])->values();
            $timeline = $timeline->sortBy('datetime')->values();
            // cerrado = el último CIERRE es posterior a la última APERTURA (las notas posteriores no lo reabren)
            $lastClose = $timeline->filter(fn ($t) => str_starts_with($t['message'], '[CIERRE'))->last();
            $lastOpen = $timeline->filter(fn ($t) => str_starts_with($t['message'], '[APERTURA'))->last();
            $closed = $lastClose && (! $lastOpen || $lastClose['datetime'] >= $lastOpen['datetime']);
            $opened = $timeline->first()['datetime'];
            $end = $closed ? $lastClose['datetime'] : now();

            return [
                'code' => $code,
                'title' => preg_replace('/^\[[^\]]+\]\s*/', '', $timeline->first()['message']),
                'status' => $closed ? 'cerrado' : 'abierto',
                'opened' => $opened,
                'closed' => $closed ? $lastClose['datetime'] : null,
                'duration' => \Carbon\Carbon::parse($opened)->diffForHumans($end, true),
                'devices' => $devIds->map(fn ($id) => ['id' => $id, 'name' => $names[$id]]),
                'timeline' => $timeline,
                'alerts' => self::alertsFor($devIds, $opened, $end),
            ];
        })->sortByDesc('opened')->values();
    }

    /** Alertas (apertura y recuperación) de esos equipos durante el incidente (con 30 min de margen previo). */
    private static function alertsFor(Collection $devIds, $from, $to): Collection
    {
        return collect(DB::table('alert_log')
            ->join('alert_rules', 'alert_rules.id', '=', 'alert_log.rule_id')
            ->whereIn('alert_log.device_id', $devIds)
            ->whereBetween('alert_log.time_logged', [\Carbon\Carbon::parse($from)->subMinutes(30), \Carbon\Carbon::parse($to)->addMinutes(10)])
            ->orderBy('alert_log.time_logged')
            ->limit(200)
            ->get(['alert_log.time_logged', 'alert_log.device_id', 'alert_log.state', 'alert_rules.name']))
            ->map(fn ($a) => [
                'time' => $a->time_logged,
                'device' => Device::find($a->device_id)?->displayName() ?? "#{$a->device_id}",
                'rule' => $a->name,
                'state' => $a->state == 0 ? 'recuperada' : 'disparada',
            ]);
    }
}
