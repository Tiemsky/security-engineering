<?php
namespace SecurityEngineering;

use Illuminate\Support\ServiceProvider;

/**
 * Config (config/security-engineering.php or env SE_POLICY_DIR): directory with compiled policy JSON
 * (scripts/compile-policies.py). Mode defaults to observe.
 */
final class SecurityEngineeringServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->singleton(MemorySink::class, fn() => new MemorySink());
        $this->app->singleton(Sink::class, fn($a) => new SafeSink($a->make(MemorySink::class)));
        $this->app->singleton('se.config', function () {
            $dir = config('security-engineering.policy_dir') ?? env('SE_POLICY_DIR');
            $load = fn($n) => json_decode(file_get_contents("$dir/$n.json"), true, 512, JSON_THROW_ON_ERROR);
            $defaults = $load('defaults');
            $defaults['exceptions']['allowlist_cidrs'] = array_merge($defaults['exceptions']['allowlist_cidrs'], config('security-engineering.allowlist_cidrs', []));
            return ['defaults' => $defaults, 'rules' => $load('detection-rules')['rules'], 'actions' => $load('response-actions'), 'redaction' => $load('redaction'),
                    'trusted_proxies' => config('security-engineering.trusted_proxies', []), 'mode' => config('security-engineering.mode')];
        });
        $this->app->singleton('se.clock', fn() => fn(): int => now()->getTimestamp());
        $this->app->singleton(EventFactory::class, function ($a) {
            $c = $a->make('se.config');
            return new EventFactory($a->make('se.clock'), new Redactor($c['redaction']), config('app.name', 'app'), config('app.env') === 'production' ? 'production' : 'local', $c['redaction']['policy_version']);
        });
        $this->app->singleton(DecisionEngine::class, function ($a) {
            $c = $a->make('se.config');
            return new DecisionEngine($c['rules'], $c['defaults'], $c['actions'], $a->make(EventFactory::class), $a->make(Sink::class), $a->make('se.clock'), $c['mode']);
        });
        $this->app->bind(HttpAccessMiddleware::class, function ($a) {
            return new HttpAccessMiddleware($a->make(DecisionEngine::class), $a->make(EventFactory::class), $a->make(Sink::class), $a->make('se.config'), $a->make('se.clock'));
        });
    }
}
