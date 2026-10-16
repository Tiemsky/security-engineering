<?php
namespace SecurityEngineering;

final class MemorySink implements Sink
{
    public array $events = [];
    public function emit(array $event): void { $this->events[] = $event; }
}
