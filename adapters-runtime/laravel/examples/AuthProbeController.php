<?php
namespace SecurityEngineering\Examples;

use Illuminate\Http\Request;
use SecurityEngineering\DecisionEngine;

/** Sample integration: feeds *real* request outcomes into the decision engine. Account ids are opaque hashes, never raw. */
final class AuthProbeController
{
    public function login(Request $r, DecisionEngine $engine)
    {
        $ok = hash_equals('correct-horse', (string) $r->input('password'));   // demo credential check
        $engine->observe([
            'kind' => $ok ? 'login_success' : 'login_failed',
            'ip' => $r->attributes->get('se.client_ip'),
            'account' => substr(hash('sha256', (string) $r->input('account')), 0, 16),
            'request_id' => $r->attributes->get('se.request_id'),
        ]);
        return $ok ? response()->json(['ok' => true]) : response()->json(['message' => 'Invalid credentials'], 401);
    }

    public function honeypot(Request $r, DecisionEngine $engine)
    {
        $engine->observe(['kind' => 'honeypot', 'ip' => $r->attributes->get('se.client_ip'), 'request_id' => $r->attributes->get('se.request_id')]);
        return response('Not Found', 404);
    }
}
