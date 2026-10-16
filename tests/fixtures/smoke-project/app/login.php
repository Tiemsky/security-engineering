<?php
// FIXTURE ONLY (fictional). Intentional vulnerabilities for audit smoke test.
$u = $_GET['user'];
$row = $db->query("SELECT * FROM users WHERE name = '$u'");   // SQL injection
if ($row['password'] == $_POST['password']) { echo "ok"; }     // plaintext compare
