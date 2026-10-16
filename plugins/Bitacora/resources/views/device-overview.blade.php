{{-- SPDX-License-Identifier: GPL-3.0-or-later · Copyright (c) 2026 Alma Creativa --}}
<div class="tw:mb-5 tw:rounded-lg tw:border tw:border-gray-300 tw:shadow-sm tw:dark:border-dark-gray-200">
    <div class="tw:px-4 tw:py-2.5 tw:bg-neutral-100 tw:border-b tw:border-gray-300 tw:text-neutral-700 tw:dark:bg-dark-gray-200 tw:dark:border-zinc-800 tw:dark:text-dark-white-200">
        <i class="fa fa-book fa-fw"></i> <strong>{{ $title }}</strong>
        <a href="{{ url('plugin/Bitacora') }}?estado=todos" class="pull-right">ver todas</a>
    </div>
    <div class="tw:flex tw:min-w-0 tw:flex-col tw:bg-white tw:divide-y tw:divide-gray-300 tw:dark:bg-dark-gray-400 tw:dark:divide-zinc-800">
        @forelse($incidents as $i)
            <div class="tw:px-4 tw:py-2">
                <span class="label label-{{ $i['status'] === 'abierto' ? 'danger' : 'success' }}">{{ $i['status'] }}</span>
                <a href="{{ url('plugin/Bitacora') }}?estado=todos#{{ $i['code'] }}"><strong>{{ $i['code'] }}</strong></a>
                · {{ $i['title'] }}
                <span class="text-muted">· {{ $i['opened'] }} · {{ $i['duration'] }} · {{ count($i['devices']) }} equipo(s)</span>
            </div>
        @empty
            <div class="tw:px-4 tw:py-2 text-muted">Sin incidencias registradas para este equipo.</div>
        @endforelse
    </div>
</div>
