// ============================================================
// SURAKSHA — DATA MODEL
// JSDoc typedefs for API response shapes used by the frontend.
// ============================================================

/**
 * @typedef {Object} Worker
 * @property {string} id
 * @property {string} name
 * @property {string} department
 * @property {'A'|'B'|'C'} shift
 * @property {string} rfidId
 * @property {number} ppeScore
 * @property {'LOW'|'MEDIUM'|'HIGH'} risk
 * @property {'ACTIVE'|'ON LEAVE'} status
 */

/**
 * @typedef {Object} PPEItem
 * @property {string} key
 * @property {string} label
 * @property {'REQUIRED'|'OPTIONAL'|'DISABLED'} state
 */

/**
 * @typedef {Object} PPEVerification
 * @property {string} id
 * @property {string} workerId
 * @property {string} gateId
 * @property {string} timestamp
 * @property {boolean} helmet
 * @property {boolean} capLamp
 * @property {boolean} safetyBoots
 * @property {boolean} reflectiveVest
 * @property {boolean} gasDetector
 * @property {boolean} selfRescuer
 * @property {number} aiConfidence
 * @property {'ALLOWED'|'DENIED'|'WARNING'} decision
 */

/**
 * @typedef {Object} EntryEvent
 * @property {string} id
 * @property {string} workerId
 * @property {string} gateId
 * @property {string} timestamp
 * @property {'ALLOWED'|'DENIED'|'WARNING'} decision
 * @property {'AI CAMERA'|'AI + RFID'|'RFID'} source
 * @property {string} location
 * @property {boolean} offline
 * @property {boolean} synced
 */

/**
 * @typedef {Object} Gate
 * @property {string} id
 * @property {string} name
 * @property {'ONLINE'|'OFFLINE'|'MAINTENANCE'} status
 * @property {number} workers
 */

/**
 * @typedef {Object} Device
 * @property {string} id
 * @property {'AI CAMERA'|'RFID READER'|'GATE CONTROLLER'} type
 * @property {string} gate
 * @property {'ONLINE'|'OFFLINE'} status
 * @property {string} heartbeat
 */

/**
 * @typedef {Object} Alert
 * @property {string} id
 * @property {'CRITICAL'|'WARNING'|'RESOLVED'} severity
 * @property {string} title
 * @property {string|null} worker
 * @property {string|null} workerId
 * @property {string} detail
 * @property {string} gate
 * @property {string} time
 * @property {'OPEN'|'ACKNOWLEDGED'|'ESCALATED'|'RESOLVED'} status
 */

/**
 * @typedef {Object} AttendanceRecord
 * @property {string} worker
 * @property {string} workerId
 * @property {string} entry
 * @property {string} exit
 * @property {string} ppe
 * @property {string} location
 * @property {string} status
 */

/**
 * @typedef {Object} SafetyInsight
 * @property {string} statement
 * @property {string} kind
 */

/**
 * @typedef {Object} Report
 * @property {string} id
 * @property {string} name
 * @property {string} description
 * @property {string} lastGenerated
 * @property {number} records
 */

/**
 * @typedef {Object} User
 * @property {string} name
 * @property {string} role
 * @property {string} mine
 * @property {string} lastLogin
 * @property {'ACTIVE'|'INACTIVE'} status
 */

/**
 * @typedef {Object} AuditEvent
 * @property {string} time
 * @property {string} eventId
 * @property {string} worker
 * @property {string} gate
 * @property {'ALLOWED'|'DENIED'|'WARNING'} decision
 * @property {string} source
 */

export {};
