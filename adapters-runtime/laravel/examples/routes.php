<?php
use Illuminate\Support\Facades\Route;
use SecurityEngineering\Examples\AuthProbeController;

Route::post('/login', [AuthProbeController::class, 'login']);
Route::get('/wp-admin.php', [AuthProbeController::class, 'honeypot']);
Route::get('/health', fn() => response()->json(['ok' => true]));
