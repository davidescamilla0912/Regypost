-- ============================================================================
-- 001_backend_spec.sql
-- Migración que soporta la ESPECIFICACION_BACKEND.md
-- Idempotente: se puede correr varias veces sin romper nada.
-- ============================================================================

-- ─── §6.1 Acompañantes: la tabla no existía y los endpoints fallaban ────────
CREATE TABLE IF NOT EXISTS acompanantes_reserva (
    id               INT(11)     NOT NULL AUTO_INCREMENT,
    reserva_id       INT(11)     NOT NULL,
    tipo_documento   VARCHAR(20) NOT NULL DEFAULT 'CC',
    numero_documento VARCHAR(30) NOT NULL,
    nombre           VARCHAR(60) NOT NULL,
    apellido         VARCHAR(60) NOT NULL,
    telefono         VARCHAR(30)     NULL,
    es_menor         TINYINT(1)  NOT NULL DEFAULT 0,
    creado_en        TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_acomp_reserva_doc (reserva_id, numero_documento),
    KEY idx_acomp_reserva (reserva_id),
    CONSTRAINT fk_acomp_reserva FOREIGN KEY (reserva_id)
        REFERENCES reservas (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─── §7.2 Categorización de consumos: el producto declara su tipo ──────────
-- Antes el frontend adivinaba el tipo_consumo comparando cadenas de texto y
-- caía al primer tipo de la lista cuando no acertaba (F43).
ALTER TABLE productos_inventario
    ADD COLUMN IF NOT EXISTS tipo_consumo_id INT(11) NULL AFTER categoria;

ALTER TABLE productos_inventario
    ADD CONSTRAINT fk_producto_tipo_consumo FOREIGN KEY (tipo_consumo_id)
        REFERENCES tipos_consumo (id);

-- Semilla razonable por categoría para los productos ya existentes.
UPDATE productos_inventario p
SET p.tipo_consumo_id = (
        SELECT tc.id FROM tipos_consumo tc
        WHERE tc.categoria = 'minibar' AND tc.activo = 1 LIMIT 1)
WHERE p.tipo_consumo_id IS NULL
  AND LOWER(COALESCE(p.categoria, '')) IN ('minibar', 'bebidas', 'licores');

UPDATE productos_inventario p
SET p.tipo_consumo_id = (
        SELECT tc.id FROM tipos_consumo tc
        WHERE tc.categoria = 'alimentos' AND tc.activo = 1 LIMIT 1)
WHERE p.tipo_consumo_id IS NULL
  AND LOWER(COALESCE(p.categoria, '')) IN ('alimentos', 'snacks', 'comida');

-- El resto queda en 'Adicional' (servicios) en vez de en un tipo al azar.
UPDATE productos_inventario p
SET p.tipo_consumo_id = (
        SELECT tc.id FROM tipos_consumo tc
        WHERE tc.nombre = 'Adicional' AND tc.activo = 1 LIMIT 1)
WHERE p.tipo_consumo_id IS NULL;

-- ─── §4.3 Trazabilidad consumo → pago ──────────────────────────────────────
-- Un consumo solo puede quedar 'cancelado' (pagado) apuntando al pago que lo
-- cubrió. Sin esto, marcar un consumo como pagado hacía desaparecer el dinero.
ALTER TABLE consumos
    ADD COLUMN IF NOT EXISTS pago_id INT(11) NULL AFTER estado;

ALTER TABLE consumos
    ADD CONSTRAINT fk_consumo_pago FOREIGN KEY (pago_id)
        REFERENCES pagos (id) ON DELETE SET NULL;

-- ─── §4.2 Anulación de pagos con traza (en vez de editar el monto) ─────────
ALTER TABLE pagos
    ADD COLUMN IF NOT EXISTS anulado           TINYINT(1) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS anulado_por       INT(11)        NULL,
    ADD COLUMN IF NOT EXISTS anulado_en        TIMESTAMP      NULL,
    ADD COLUMN IF NOT EXISTS motivo_anulacion  VARCHAR(255)   NULL;

-- ─── §6.4 Check-out forzado con saldo pendiente: quién y por qué ───────────
ALTER TABLE reservas
    ADD COLUMN IF NOT EXISTS checkout_forzado_por    INT(11)      NULL,
    ADD COLUMN IF NOT EXISTS checkout_forzado_en     TIMESTAMP    NULL,
    ADD COLUMN IF NOT EXISTS checkout_forzado_motivo VARCHAR(255) NULL,
    ADD COLUMN IF NOT EXISTS checkout_saldo_forzado  DECIMAL(10,2) NULL;

-- ─── §6.2 Índices que respaldan la detección de solapamiento ───────────────
ALTER TABLE reservas
    ADD INDEX IF NOT EXISTS idx_reservas_rango (fecha_entrada, fecha_salida, estado);
ALTER TABLE reserva_habitaciones
    ADD INDEX IF NOT EXISTS idx_rh_habitacion (habitacion_id, reserva_id);
ALTER TABLE pagos
    ADD INDEX IF NOT EXISTS idx_pagos_reserva (reserva_id, anulado);
ALTER TABLE pagos
    ADD INDEX IF NOT EXISTS idx_pagos_fecha (fecha_pago);
ALTER TABLE consumos
    ADD INDEX IF NOT EXISTS idx_consumos_rh_estado (reserva_habitacion_id, estado);

-- ─── §5 Permisos nuevos que exigen las reglas de negocio ───────────────────
INSERT IGNORE INTO permisos (nombre) VALUES
    ('pagos.anular'),          -- anular un pago (reemplaza editar el monto)
    ('pagos.ver_todos'),       -- listar pagos sin filtrar por reserva
    ('checkout.forzar'),       -- cerrar una reserva con saldo pendiente
    ('reservas.precio_especial'), -- aplicar un precio/noche fuera de rango
    ('reservas.forzar_estado'); -- saltarse la máquina de estados

-- Todo permiso nuevo va al rol admin.
INSERT IGNORE INTO rol_permiso (rol_id, permiso_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permisos p
WHERE r.nombre = 'admin'
  AND p.nombre IN ('pagos.anular', 'pagos.ver_todos', 'checkout.forzar',
                   'reservas.precio_especial', 'reservas.forzar_estado');

-- El gerente puede forzar check-out y ver todos los pagos, pero no saltarse
-- la máquina de estados.
INSERT IGNORE INTO rol_permiso (rol_id, permiso_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permisos p
WHERE r.nombre = 'gerente'
  AND p.nombre IN ('pagos.anular', 'pagos.ver_todos', 'checkout.forzar',
                   'reservas.precio_especial');

-- ─── Permiso que el código exigía pero no existía en la tabla ──────────────
-- `GET /consumos/fecha/<fecha>` está decorado con @requiere_permiso
-- ('consumos.consultar'), pero ese permiso nunca se dio de alta, así que el
-- endpoint respondía 403 a todo el mundo. Se crea y se concede a los mismos
-- roles que ya pueden registrar consumos.
INSERT IGNORE INTO permisos (nombre) VALUES ('consumos.consultar');

INSERT IGNORE INTO rol_permiso (rol_id, permiso_id)
SELECT rp.rol_id, (SELECT id FROM permisos WHERE nombre = 'consumos.consultar')
FROM rol_permiso rp
JOIN permisos p ON p.id = rp.permiso_id
WHERE p.nombre = 'consumos.registrar';
