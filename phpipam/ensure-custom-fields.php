#!/usr/bin/env php
<?php
/* Idempotently create the standard phpIPAM fields and native type required by gr. */

if (PHP_SAPI !== 'cli') {
    fwrite(STDERR, "This helper must be run from the command line.\n");
    exit(2);
}

$configPath = $argv[1] ?? '/var/www/html/phpipam/config.php';
if (!is_file($configPath) || !is_readable($configPath)) {
    fwrite(STDERR, "Cannot read phpIPAM config: {$configPath}\n");
    exit(2);
}

require $configPath;
if (!isset($db) || !is_array($db)) {
    fwrite(STDERR, "phpIPAM config did not define the expected \$db array.\n");
    exit(2);
}

$requiredDbKeys = ['host', 'user', 'pass', 'name'];
foreach ($requiredDbKeys as $key) {
    if (!array_key_exists($key, $db)) {
        fwrite(STDERR, "phpIPAM database configuration is missing: {$key}\n");
        exit(2);
    }
}

$fields = [
    'ipaddresses' => [
        'custom_ssh_enabled'   => ['tinyint', "TINYINT(1) NULL DEFAULT 0"],
        'custom_ssh_user'      => ['varchar', "VARCHAR(64) NULL DEFAULT NULL"],
        'custom_ssh_port'      => ['int',     "INT(5) NULL DEFAULT NULL"],
        'custom_ssh_profile'   => ['varchar', "VARCHAR(64) NULL DEFAULT NULL"],
        'custom_ssh_jump'      => ['varchar', "VARCHAR(255) NULL DEFAULT NULL"],
        'custom_ssh_client'    => ['varchar', "VARCHAR(16) NULL DEFAULT NULL"],
        'custom_device_driver' => ['varchar', "VARCHAR(64) NULL DEFAULT NULL"],
        'custom_device_vendor' => ['varchar', "VARCHAR(64) NULL DEFAULT NULL"],
        'custom_os_version'    => ['varchar', "VARCHAR(128) NULL DEFAULT NULL"],
        'custom_device_model'  => ['varchar', "VARCHAR(128) NULL DEFAULT NULL"],
        'custom_snmp_enabled'  => ['tinyint', "TINYINT(1) NULL DEFAULT 0"],
        'custom_snmp_profile'  => ['varchar', "VARCHAR(64) NULL DEFAULT NULL"],
        'custom_snmp_template' => ['varchar', "VARCHAR(128) NULL DEFAULT NULL"],
        'custom_monitoring_enabled' => ['tinyint', "TINYINT(1) NULL DEFAULT 0"],
        'custom_monitoring_profile' => ['varchar', "VARCHAR(64) NULL DEFAULT NULL"],
        'custom_monitoring_device_id' => ['varchar', "VARCHAR(64) NULL DEFAULT NULL"],
    ],
    'devices' => [
        'custom_device_os'     => ['varchar', "VARCHAR(128) NULL DEFAULT NULL"],
    ],
];

mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
try {
    $port = isset($db['port']) ? (int)$db['port'] : 3306;
    $mysqli = new mysqli($db['host'], $db['user'], $db['pass'], $db['name'], $port);
    $mysqli->set_charset('utf8mb4');
    $schema = $mysqli->real_escape_string($db['name']);
    if (!$mysqli->query("SELECT GET_LOCK('gr_phpipam_custom_fields', 15) AS acquired")->fetch_assoc()['acquired']) {
        throw new RuntimeException('Could not acquire the schema installation lock');
    }
    foreach ($fields as $table => $tableFields) {
        $result = $mysqli->query(
            "SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS " .
            "WHERE TABLE_SCHEMA='{$schema}' AND TABLE_NAME='" . $mysqli->real_escape_string($table) . "'"
        );
        $existing = [];
        while ($row = $result->fetch_assoc()) {
            $existing[$row['COLUMN_NAME']] = strtolower($row['DATA_TYPE']);
        }
        if (!$existing) {
            throw new RuntimeException("Required phpIPAM table is missing: {$table}");
        }
        foreach ($tableFields as $name => [$expectedType, $definition]) {
            if (isset($existing[$name])) {
                if ($existing[$name] !== $expectedType) {
                    throw new RuntimeException(
                        "Incompatible existing field {$table}.{$name}: {$existing[$name]} (expected {$expectedType})"
                    );
                }
                echo "OK      {$table}.{$name} ({$existing[$name]})\n";
                continue;
            }
            $mysqli->query("ALTER TABLE `{$table}` ADD COLUMN `{$name}` {$definition}");
            echo "CREATED {$table}.{$name} ({$expectedType})\n";
        }
    }
    $server = $mysqli->query(
        "SELECT tid FROM `deviceTypes` WHERE LOWER(tname)='server' LIMIT 1"
    )->fetch_assoc();
    if ($server) {
        echo "OK      deviceTypes.Server (tid={$server['tid']})\n";
    } else {
        $mysqli->query(
            "INSERT INTO `deviceTypes` (tname, tdescription, bgcolor, fgcolor) " .
            "VALUES ('Server', 'Server', '#E6E6E6', '#000')"
        );
        echo "CREATED deviceTypes.Server (tid={$mysqli->insert_id})\n";
    }
    $mysqli->query("SELECT RELEASE_LOCK('gr_phpipam_custom_fields')");
    echo "PHPIPAM_CUSTOM_FIELDS_OK\n";
} catch (Throwable $error) {
    fwrite(STDERR, "Schema preparation failed: {$error->getMessage()}\n");
    exit(2);
}
