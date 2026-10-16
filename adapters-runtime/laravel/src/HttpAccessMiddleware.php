<?php
namespace SecurityEngineering;

use Closure;
use Illuminate\Http\Request;

/** Request-lifecycle instrumentation: request id, trusted-proxy IP resolution, enforcement gate, access event on terminate(). */
final class HttpAccessMiddleware
{
    public function __construct(private DecisionEngine $engine, private EventFactory $events, private Sink $sink, private array $config, private \Closure $clock) {}

    public function handle(Request $request, Closure $next)
    {
        $ip = ClientIp::resolve($request->server('REMOTE_ADDR', ''), $request->header('X-Forwarded-For'), $this->config['trusted_proxies']);
        $request->attributes->set('se.client_ip', $ip);
        $request->attributes->set('se.request_id', (string) \Illuminate\Support\Str::uuid());
        $request->attributes->set('se.started', hrtime(true));
        if ($this->engine->isActive('ip', $ip) || $this->engine->isActive('ip_prefix64', ClientIp::prefix64($ip))) {
            return response()->json(['message' => 'Too Many Requests'], 429, ['Retry-After' => '900', 'X-Request-Id' => $request->attributes->get('se.request_id')]);
        }
        $response = $next($request);
        $response->headers->set('X-Request-Id', $request->attributes->get('se.request_id'));
        return $response;
    }

    public function terminate(Request $request, $response): void
    {
        try {
            $route = $request->route();
            $this->sink->emit($this->events->make('http_access', [
                'request_id' => $request->attributes->get('se.request_id', 'n/a'),
                'client_ip' => $request->attributes->get('se.client_ip', ClientIp::normalize($request->server('REMOTE_ADDR', '0.0.0.0'))),
                'method' => $request->method(),
                'route' => '/' . ltrim($route?->uri() ?? 'unmatched', '/'),   // route TEMPLATE, never raw URL/query
                'status' => $response->getStatusCode(),
                'duration_ms' => round((hrtime(true) - $request->attributes->get('se.started', hrtime(true))) / 1e6, 3),
                'user_agent' => mb_substr((string) $request->userAgent(), 0, 256),
            ], 'short', $this->config['defaults']['retention_days']['http_access']));
        } catch (\Throwable) { /* observability must never break the response */ }
    }
}
