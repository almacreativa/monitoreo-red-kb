<?php

namespace App\Plugins\Bitacora;

use App\Plugins\Bitacora\Support\Incidents;
use App\Plugins\Hooks\DeviceOverviewHook;

// Panel en la ficha del equipo: sus incidencias (abiertas primero).
class DeviceOverview extends DeviceOverviewHook
{
    public function authorize(\Illuminate\Contracts\Auth\Authenticatable $user, \App\Models\Device $device): bool
    {
        return $user->can('global-read');
    }

    public function data(\App\Models\Device $device): array
    {
        return [
            'title' => 'Bitácora de incidencias',
            'device' => $device,
            'incidents' => Incidents::all($device->device_id)->sortBy(fn ($i) => $i['status'] === 'abierto' ? 0 : 1)->take(5),
        ];
    }
}
