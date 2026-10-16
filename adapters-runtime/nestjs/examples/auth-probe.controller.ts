import { Body, Controller, Get, HttpCode, Inject, NotFoundException, Post, Req, UnauthorizedException } from '@nestjs/common';
import { createHash, timingSafeEqual } from 'node:crypto';
import { DecisionEngine, SE_ENGINE } from '../src';

/** Sample integration: feeds *real* request outcomes into the decision engine. Account ids are opaque hashes, never raw. */
@Controller()
export class AuthProbeController {
  constructor(@Inject(SE_ENGINE) private engine: DecisionEngine) {}

  @Post('login') @HttpCode(200)
  login(@Req() req: any, @Body() body: { account?: string; password?: string }) {
    const a = Buffer.from(String(body.password ?? '')), b = Buffer.from('correct-horse');
    const ok = a.length === b.length && timingSafeEqual(a, b);   // demo credential check
    this.engine.observe({ kind: ok ? 'login_success' : 'login_failed', ip: req.seClientIp, account: createHash('sha256').update(String(body.account ?? '')).digest('hex').slice(0, 16), request_id: req.seRequestId });
    if (!ok) throw new UnauthorizedException('Invalid credentials');
    return { ok: true };
  }

  @Get('wp-admin.php')
  honeypot(@Req() req: any) {
    this.engine.observe({ kind: 'honeypot', ip: req.seClientIp, request_id: req.seRequestId });
    throw new NotFoundException('Not Found');
  }

  @Get('health') health() { return { ok: true }; }
}
