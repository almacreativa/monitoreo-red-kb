<?php

// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (c) 2026 Alma Creativa

namespace App\Plugins\Bitacora;

use App\Plugins\Bitacora\Support\Incidents;
use App\Models\Device;
use App\Models\DeviceGroup;
use App\Plugins\Hooks\PageHook;

// Página "Bitácora": incidentes agrupados por código + formulario de registro.
class Page extends PageHook
{
    public function authorize(\Illuminate\Contracts\Auth\Authenticatable $user): bool
    {
        return $user->can('global-read');
    }

    public function data(): array
    {
        $messages = Incidents::flushPending();
        $filter = request('estado', 'abierto');
        $incidents = Incidents::all();

        return [
            'title' => 'Bitácora de incidencias',
            'messages' => $messages,
            'filter' => $filter,
            'incidents' => $filter === 'todos' ? $incidents : $incidents->where('status', $filter)->values(),
            'counts' => $incidents->countBy('status'),
            'canWrite' => auth()->user()->can('plugin.admin'),
            'nextCode' => Incidents::nextCode(),
            'actions' => Incidents::ACTIONS,
            'causes' => Incidents::CAUSES,
            'groups' => DeviceGroup::orderBy('name')->get(['id', 'name']),
            'preset' => request('code'),
            'deviceIndex' => auth()->user()->can('plugin.admin') ? self::deviceIndex() : [],
        ];
    }

    /**
     * Índice compacto para el buscador del formulario (se filtra en el navegador, de a 30 resultados).
     * Incluye nombre visible (nomenclatura), hostname, sysName, IP y ubicación. Respeta permisos.
     * Nota: un hook no puede devolver JSON lanzando una excepción: LibreNMS desactiva el plugin.
     */
    private static function deviceIndex(): array
    {
        return Device::hasAccess(auth()->user())->with('location')->orderBy('display')->orderBy('hostname')
            ->get(['device_id', 'hostname', 'sysName', 'display', 'ip', 'location_id'])
            ->map(function (Device $d) {
                $name = $d->displayName();
                $text = $name . ($name !== $d->hostname ? " ({$d->hostname})" : '') . ($d->location ? ' · ' . $d->location->location : '');

                return ['id' => $d->device_id, 'text' => $text,
                    's' => mb_strtolower(implode(' ', [$text, $d->sysName, $d->ip]))];
            })->values()->all();
    }
}
