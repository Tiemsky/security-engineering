<?php
namespace SecurityEngineering;

interface Sink { public function emit(array $event): void; }
