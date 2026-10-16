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
]);
$app->register(SecurityEngineeringServiceProvider::class);
$kernel->prependMiddleware(HttpAccessMiddleware::class);
\Illuminate\Support\Facades\Route::group([], getcwd() . '/vendor/security-engineering-examples/routes.php');
$engine = $app->make(DecisionEngine::class);
$engine->storeFailure = (bool) ($sc['config']['store_failure'] ?? false);
$sink = $app->make(MemorySink::class);

$lines = [];
foreach ($sc['steps'] as $i => $s) {
    Carbon::setTestNow(Carbon::createFromTimestampUTC(1760000000 + $s['t']));
    if (($s['op'] ?? null) === 'sweep') { $engine->sweep(); continue; }
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
