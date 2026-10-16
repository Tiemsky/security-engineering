<?php
/**
 * Boots a REAL Laravel application, registers the runtime, and replays one shared scenario through the HTTP kernel
 * (global middleware → router → controller → terminate). Usage: php run_scenario.php <scenario.json> <out.jsonl>
 * Env: SE_POLICY_DIR (compiled policies). No PHPUnit needed (ext-xml unavailable on some hosts).
 */
use Carbon\Carbon;
use Illuminate\Contracts\Http\Kernel;
use Illuminate\Http\Request;
use SecurityEngineering\{DecisionEngine, HttpAccessMiddleware, MemorySink, SecurityEngineeringServiceProvider};

require getcwd() . '/vendor/autoload.php';
require getcwd() . '/vendor/security-engineering-examples/AuthProbeController.php';
$sc = json_decode(file_get_contents($argv[1]), true);
$app = require getcwd() . '/bootstrap/app.php';
$kernel = $app->make(Kernel::class);
$kernel->bootstrap();
config([
    'security-engineering.policy_dir' => getenv('SE_POLICY_DIR'),
    'security-engineering.mode' => $sc['config']['mode'] ?? null,
    'security-engineering.trusted_proxies' => $sc['config']['trusted_proxies'] ?? [],
    'security-engineering.allowlist_cidrs' => $sc['config']['allowlist_cidrs'] ?? [],
    'security-engineering.extra_rules' => $sc['config']['extra_rules'] ?? [],
]);
$app->register(SecurityEngineeringServiceProvider::class);
$kernel->prependMiddleware(HttpAccessMiddleware::class);
\Illuminate\Support\Facades\Route::group([], getcwd() . '/vendor/security-engineering-examples/routes.php');
if (!empty($sc['config']['sink_failure'])) {   // every sink write throws: the engine and middleware must survive it
    $app->singleton(\SecurityEngineering\Sink::class, fn() => new class implements \SecurityEngineering\Sink { public function emit(array $e): void { throw new \RuntimeException('sink down'); } });   // RAW throwing sink: the engine must guard itself
}
$engine = $app->make(DecisionEngine::class);
$engine->storeFailure = (bool) ($sc['config']['store_failure'] ?? false);
$sink = $app->make(MemorySink::class);

$tpl = function ($v, int $i) use (&$tpl) {   // "{i}" / "{i%N}" placeholders for burst templates
    if (is_array($v)) return array_map(fn($x) => $tpl($x, $i), $v);
    return is_string($v) ? preg_replace_callback('/\{i(?:%(\d+))?\}/', fn($m) => (string) (isset($m[1]) ? $i % (int) $m[1] : $i), $v) : $v;
};
$lines = [];
foreach ($sc['steps'] as $i => $s) {
    Carbon::setTestNow(Carbon::createFromTimestampUTC(1760000000 + $s['t']));
    switch ($s['op'] ?? 'http') {
        case 'sweep': $engine->sweep(); continue 2;
        case 'signal': $engine->observe($s['event']); continue 2;
        case 'burst':
            for ($k = 0; $k < $s['n']; $k++) { Carbon::setTestNow(Carbon::createFromTimestampUTC(1760000000 + $s['t'] + intdiv($k, $s['per_second'] ?? 1))); $engine->observe($tpl($s['event'], $k)); }
            continue 2;
        case 'rollback': $engine->rollback($s['kind'], $s['value']); continue 2;
        case 'store_failure': $engine->storeFailure = (bool) $s['value']; continue 2;
        case 'assert':
            $st = $engine->stats();
            $got = match ($s['what']) { 'active' => $engine->isActive($s['kind'], $s['value']), default => $st[$s['what']] };
            $lines[] = ['type' => 'assert', 'step' => $i, 'what' => $s['what'], 'got' => $got]; continue 2;
    }
    $server = ['REMOTE_ADDR' => $s['peer'] ?? $s['ip'], 'CONTENT_TYPE' => 'application/json', 'HTTP_ACCEPT' => 'application/json'];
    if (isset($s['xff'])) $server['HTTP_X_FORWARDED_FOR'] = $s['xff'];
    foreach ($s['headers'] ?? [] as $k => $v) $server['HTTP_' . strtoupper(str_replace('-', '_', $k))] = $v;
    $request = Request::create($s['path'], $s['method'], [], [], [], $server, isset($s['json']) ? json_encode($s['json']) : null);
    $before = count($sink->events);
    $response = $kernel->handle($request);
    $kernel->terminate($request, $response);
    $access = array_values(array_filter(array_slice($sink->events, $before), fn($e) => $e['event_type'] === 'http_access'));
    $lines[] = ['type' => 'http', 'step' => $i, 'status' => $response->getStatusCode(), 'client_ip' => $access[0]['client_ip'] ?? null, 'route' => $access[0]['route'] ?? null];
}
foreach ($sink->events as $e) $lines[] = ['type' => 'event', 'event' => $e];
file_put_contents($argv[2], implode("\n", array_map('json_encode', $lines)) . "\n");
