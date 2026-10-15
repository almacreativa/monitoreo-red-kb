<?php

namespace App\Plugins\Bitacora;

use App\Plugins\Bitacora\Support\Incidents;
use App\Plugins\Hooks\MenuEntryHook;

class Menu extends MenuEntryHook
{
    public function authorize(\Illuminate\Contracts\Auth\Authenticatable $user, array $settings = []): bool
    {
        return $user->can('global-read');
    }

    public function data(array $settings = []): array
    {
        return ['open' => Incidents::all()->where('status', 'abierto')->count()];
    }
}
