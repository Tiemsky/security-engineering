import { CallHandler, Catch, ExceptionFilter, ArgumentsHost, ExecutionContext, HttpException, Inject, Injectable, Module, NestInterceptor, NestMiddleware, DynamicModule } from '@nestjs/common';
import { randomUUID } from 'node:crypto';
import { tap } from 'rxjs';
import { DecisionEngine } from './decision-engine';
import { EventFactory, SafeSink, Sink } from './events';
import { prefix64, resolveClientIp } from './ip';

export const SE_OPTIONS = 'SE_OPTIONS', SE_ENGINE = 'SE_ENGINE', SE_FACTORY = 'SE_FACTORY', SE_SINK = 'SE_SINK';
export interface SeOptions {
  trustedProxies: string[]; retentionDaysHttp: number;
  /** TEST SEAM ONLY: lets integration tests choose the TCP peer address via header. Never enable in production. */
  testPeerHeader?: string;
}

function emitAccess(o: SeOptions, f: EventFactory, sink: Sink, req: any, status: number) {
  try {
    sink.emit(f.make('http_access', {
      request_id: req.seRequestId ?? 'n/a', client_ip: req.seClientIp, method: req.method,
      route: req.seRoute ?? ('/' + String(req.route?.path ?? 'unmatched').replace(/^\//, '')),   // route TEMPLATE, never raw URL/query
      status, duration_ms: Math.round(Number(process.hrtime.bigint() - (req.seStarted ?? process.hrtime.bigint())) / 1e3) / 1e3,
      user_agent: String(req.headers['user-agent'] ?? '').slice(0, 256),
    }, 'short', o.retentionDaysHttp));
  } catch { /* observability must never break the response */ }
}

/** Request id, trusted-proxy client IP, enforcement gate. */
@Injectable()
export class SecurityMiddleware implements NestMiddleware {
  constructor(@Inject(SE_OPTIONS) private o: SeOptions, @Inject(SE_ENGINE) private engine: DecisionEngine, @Inject(SE_FACTORY) private f: EventFactory, @Inject(SE_SINK) private sink: Sink) {}
  use(req: any, res: any, next: () => void) {
    const peer = (this.o.testPeerHeader && req.headers[this.o.testPeerHeader]) || req.socket.remoteAddress || '';
    req.seClientIp = resolveClientIp(String(peer), req.headers['x-forwarded-for'], this.o.trustedProxies);
    req.seRequestId = randomUUID(); req.seStarted = process.hrtime.bigint();
    res.setHeader('X-Request-Id', req.seRequestId);
    if (this.engine.isActive('ip', req.seClientIp) || this.engine.isActive('ip_prefix64', prefix64(req.seClientIp))) {
      res.status(429).set('Retry-After', '900').json({ message: 'Too Many Requests' });
      emitAccess(this.o, this.f, this.sink, req, 429); return;
    }
    next();
  }
}

/** Captures the route template and emits the access event for handled responses. */
@Injectable()
export class AccessInterceptor implements NestInterceptor {
  constructor(@Inject(SE_OPTIONS) private o: SeOptions, @Inject(SE_FACTORY) private f: EventFactory, @Inject(SE_SINK) private sink: Sink) {}
  intercept(ctx: ExecutionContext, next: CallHandler) {
    const http = ctx.switchToHttp(); const req = http.getRequest(), res = http.getResponse();
    return next.handle().pipe(tap(() => emitAccess(this.o, this.f, this.sink, req, res.statusCode)));
  }
}

/** Emits the access event for errors (HttpException → its status; others → 500 with a generic body). */
@Catch()
export class AccessExceptionFilter implements ExceptionFilter {
  constructor(@Inject(SE_OPTIONS) private o: SeOptions, @Inject(SE_FACTORY) private f: EventFactory, @Inject(SE_SINK) private sink: Sink) {}
  catch(ex: unknown, host: ArgumentsHost) {
    const http = host.switchToHttp(); const req = http.getRequest(), res = http.getResponse();
    const status = ex instanceof HttpException ? ex.getStatus() : 500;
    emitAccess(this.o, this.f, this.sink, req, status);
    res.status(status).json({ message: ex instanceof HttpException ? ex.message : 'Internal server error', request_id: req.seRequestId });
  }
}

@Module({})
export class SecurityModule {
  static register(p: { options: SeOptions; engine: DecisionEngine; factory: EventFactory; sink: Sink }): DynamicModule {
    return {
      module: SecurityModule, global: true,
      providers: [
        { provide: SE_OPTIONS, useValue: p.options }, { provide: SE_ENGINE, useValue: p.engine },
        { provide: SE_FACTORY, useValue: p.factory }, { provide: SE_SINK, useValue: new SafeSink(p.sink) },
        SecurityMiddleware, AccessInterceptor, AccessExceptionFilter,
      ],
      exports: [SE_OPTIONS, SE_ENGINE, SE_FACTORY, SE_SINK, SecurityMiddleware, AccessInterceptor, AccessExceptionFilter],
    };
  }
}
