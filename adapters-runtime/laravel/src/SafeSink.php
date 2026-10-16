<?php
namespace SecurityEngineering;

/** Never lets sink failures reach the request (observability must not break traffic). */
final class SafeSink implements Sink
{
    public int $dropped = 0;
    public function __construct(private Sink $inner) {}
    public function emit(array $event): void
    {
        try { $this->inner->emit($event); } catch (\Throwable) { $this->dropped++; }
    }
}
