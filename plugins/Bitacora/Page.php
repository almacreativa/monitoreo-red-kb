<?php

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
            'devices' => Device::orderBy('display')->orderBy('hostname')->get(['device_id', 'hostname', 'sysName', 'display']),
            'groups' => DeviceGroup::orderBy('name')->get(['id', 'name']),
            'preset' => request('code'),
        ];
    }
}
