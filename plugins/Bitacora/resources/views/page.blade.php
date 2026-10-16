{{-- SPDX-License-Identifier: GPL-3.0-or-later · Copyright (c) 2026 Alma Creativa --}}
<div class="container-fluid">
    @foreach($messages as $m)
        <div class="alert alert-warning">{{ $m }}</div>
    @endforeach

    <div class="row">
        <div class="col-md-8">
            <div class="btn-group" role="group" style="margin-bottom:12px">
                @foreach(['abierto' => 'Abiertos', 'cerrado' => 'Cerrados', 'todos' => 'Todos'] as $k => $label)
                    <a class="btn btn-default {{ $filter === $k ? 'active' : '' }}" href="{{ url('plugin/Bitacora') }}?estado={{ $k }}">
                        {{ $label }} @if($k !== 'todos')<span class="badge">{{ $counts[$k] ?? 0 }}</span>@endif
                    </a>
                @endforeach
            </div>

            @forelse($incidents as $i)
                <div class="panel panel-{{ $i['status'] === 'abierto' ? 'danger' : 'success' }}" id="{{ $i['code'] }}">
                    <div class="panel-heading">
                        <strong>{{ $i['code'] }}</strong> · {{ $i['title'] }}
                        <span class="pull-right">
                            <span class="label label-{{ $i['status'] === 'abierto' ? 'danger' : 'success' }}">{{ $i['status'] }}</span>
                            {{ $i['duration'] }}
                        </span>
                    </div>
                    <div class="panel-body">
                        <p><strong>Equipos ({{ count($i['devices']) }}):</strong>
                            @foreach($i['devices'] as $d)
                                <a href="{{ url('device/' . $d['id']) }}" class="label label-default" style="display:inline-block;margin:2px">{{ $d['name'] }}</a>
                            @endforeach
                        </p>
                        <p class="text-muted">Abierto: {{ $i['opened'] }} @if($i['closed']) · Cerrado: {{ $i['closed'] }} @endif</p>

                        <strong>Línea de tiempo</strong>
                        <table class="table table-condensed">
                            @foreach($i['timeline'] as $t)
                                <tr>
                                    <td style="white-space:nowrap">{{ $t['datetime'] }}</td>
                                    <td>{{ $t['message'] }}</td>
                                    <td class="text-muted">{{ $t['username'] }}</td>
                                    <td class="text-muted">{{ count($t['devices']) }} equipo(s)</td>
                                </tr>
                            @endforeach
                        </table>

                        <strong>Alertas de esos equipos durante el incidente ({{ count($i['alerts']) }})</strong>
                        @if(count($i['alerts']))
                            <table class="table table-condensed table-striped">
                                @foreach($i['alerts'] as $a)
                                    <tr>
                                        <td style="white-space:nowrap">{{ $a['time'] }}</td>
                                        <td>{{ $a['device'] }}</td>
                                        <td>{{ $a['rule'] }}</td>
                                        <td><span class="label label-{{ $a['state'] === 'recuperada' ? 'success' : 'warning' }}">{{ $a['state'] }}</span></td>
                                    </tr>
                                @endforeach
                            </table>
                        @else
                            <p class="text-muted">Ninguna.</p>
                        @endif

                        @if($canWrite)
                            <a class="btn btn-xs btn-default" href="{{ url('plugin/Bitacora') }}?estado={{ $filter }}&code={{ $i['code'] }}#form">Agregar nota o cerrar</a>
                        @endif
                    </div>
                </div>
            @empty
                <p class="text-muted">No hay incidentes en esta vista.</p>
            @endforelse
        </div>

        <div class="col-md-4" id="form">
            @if($canWrite)
                <div class="panel panel-default">
                    <div class="panel-heading"><strong>Registrar</strong></div>
                    <div class="panel-body">
                        <form method="post" action="{{ route('plugin.update', 'Bitacora') }}">
                            @csrf
                            <div class="form-group">
                                <label>Acción</label>
                                <select name="settings[pending][0][action]" class="form-control" id="bit-action">
                                    @foreach($actions as $k => $label)
                                        <option value="{{ $k }}" @if($preset && $k === 'nota') selected @endif>{{ ucfirst(strtolower($label)) }}</option>
                                    @endforeach
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Código</label>
                                <input name="settings[pending][0][code]" class="form-control" value="{{ $preset }}" placeholder="{{ $nextCode }} (vacío = nuevo)">
                            </div>
                            <div class="form-group">
                                <label>Equipos</label>
                                <select name="settings[pending][0][devices][]" id="bit-devices" class="form-control" multiple style="width:100%"></select>
                                <small class="text-muted">Escribí parte del nombre, código, IP o sitio; podés elegir varios.
                                    En notas y cierres, vacío = los del incidente.</small>
                            </div>
                            <div class="form-group">
                                <label>… o todo un grupo</label>
                                <select name="settings[pending][0][group]" id="bit-group" class="form-control" style="width:100%">
                                    <option value="">—</option>
                                    @foreach($groups as $g)
                                        <option value="{{ $g->id }}">{{ $g->name }}</option>
                                    @endforeach
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Cuándo ocurrió (opcional)</label>
                                <input type="datetime-local" name="settings[pending][0][start]" class="form-control">
                                <small class="text-muted">Para registrar a posteriori. Vacío = ahora.</small>
                            </div>
                            <div class="form-group" id="bit-cause">
                                <label>Causa (al cerrar)</label>
                                <select name="settings[pending][0][cause]" class="form-control">
                                    <option value="">—</option>
                                    @foreach($causes as $k => $label)
                                        <option value="{{ $k }}">{{ $label }}</option>
                                    @endforeach
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Descripción</label>
                                <textarea name="settings[pending][0][text]" class="form-control" rows="3" maxlength="500" required
                                          placeholder="Qué pasó / qué se hizo / quién se encarga"></textarea>
                            </div>
                            <button class="btn btn-primary" type="submit">Registrar</button>
                        </form>
                    </div>
                </div>
            @endif
            <div class="panel panel-default">
                <div class="panel-body text-muted small">
                    Cada registro se guarda en el <a href="{{ url('eventlog') }}">eventlog</a> de los equipos elegidos
                    (tipo <code>incidencia</code>, referencia = código). Un mismo código en varios equipos agrupa sus alertas
                    en un solo incidente. Prototipo — repo KB, docs/10.
                </div>
            </div>
        </div>
    </div>
</div>

<script>
    $(function () {
        // Equipos: índice local filtrado en el navegador (palabras en AND), paginado de a 30
        var equipos = @json($deviceIndex);
        $('#bit-devices').select2({
            theme: 'bootstrap', width: '100%', multiple: true, closeOnSelect: false,
            placeholder: 'Buscar equipos (' + equipos.length + ')…',
            ajax: {
                delay: 150,
                transport: function (params, success) {
                    var words = (params.data.term || '').toLowerCase().split(/\s+/).filter(Boolean);
                    var hits = equipos.filter(function (e) {
                        return words.every(function (w) { return e.s.indexOf(w) !== -1; });
                    });
                    var page = params.data.page || 1, per = 30;
                    success({results: hits.slice((page - 1) * per, page * per), pagination: {more: hits.length > page * per}});
                    return {abort: function () {}};
                }
            }
        });
        $('#bit-group').select2({theme: 'bootstrap', width: '100%', placeholder: '—', allowClear: true});
    });
</script>
