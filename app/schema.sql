-- TrackWell SQLite schema (version 1)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    username             TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash        TEXT NOT NULL,
    full_name            TEXT NOT NULL,
    role                 TEXT NOT NULL CHECK (role IN ('admin', 'faculty', 'student')),
    student_fk           INTEGER UNIQUE REFERENCES students(id) ON DELETE SET NULL,
    is_active            INTEGER NOT NULL DEFAULT 1,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at        TEXT
);

CREATE TABLE IF NOT EXISTS students (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id                TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name                      TEXT NOT NULL,
    class_name                TEXT NOT NULL,
    semester                  INTEGER NOT NULL CHECK (semester BETWEEN 1 AND 8),
    attendance_pct            REAL NOT NULL CHECK (attendance_pct BETWEEN 0 AND 100),
    previous_gpa              REAL CHECK (previous_gpa IS NULL OR previous_gpa BETWEEN 0 AND 10),
    quiz_score                REAL CHECK (quiz_score IS NULL OR quiz_score BETWEEN 0 AND 100),
    test_score                REAL CHECK (test_score IS NULL OR test_score BETWEEN 0 AND 100),
    assignment_completion_pct REAL NOT NULL CHECK (assignment_completion_pct BETWEEN 0 AND 100),
    study_hours               REAL CHECK (study_hours IS NULL OR study_hours BETWEEN 0 AND 16),
    participation             TEXT NOT NULL CHECK (participation IN ('Low', 'Medium', 'High')),
    engagement_level          TEXT NOT NULL CHECK (engagement_level IN ('Low', 'Medium', 'High')),
    self_understanding        INTEGER CHECK (self_understanding IS NULL OR self_understanding BETWEEN 1 AND 5),
    created_at                TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at                TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_students_class ON students(class_name, semester);
CREATE INDEX IF NOT EXISTS idx_students_name ON students(name);

-- Historical assessment scores (quizzes / tests) used for score-trend features.
CREATE TABLE IF NOT EXISTS assessments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_fk      INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    assessment_type TEXT NOT NULL CHECK (assessment_type IN ('quiz', 'test', 'assignment')),
    title           TEXT NOT NULL,
    score_pct       REAL NOT NULL CHECK (score_pct BETWEEN 0 AND 100),
    recorded_on     TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_assessments_student ON assessments(student_fk, recorded_on);

CREATE TABLE IF NOT EXISTS model_versions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    version             TEXT NOT NULL UNIQUE,
    algorithm           TEXT NOT NULL,
    trained_at          TEXT NOT NULL,
    trained_by_user_fk  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    dataset_source      TEXT NOT NULL,
    dataset_rows        INTEGER NOT NULL,
    metrics_json        TEXT NOT NULL,
    candidates_json     TEXT NOT NULL,
    feature_schema_json TEXT NOT NULL,
    artifact_path       TEXT NOT NULL,
    artifact_sha256     TEXT NOT NULL,
    is_active           INTEGER NOT NULL DEFAULT 0,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS predictions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    student_fk       INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    model_version_fk INTEGER NOT NULL REFERENCES model_versions(id) ON DELETE CASCADE,
    risk_level       TEXT NOT NULL CHECK (risk_level IN ('Low', 'Medium', 'High')),
    prob_low         REAL NOT NULL,
    prob_medium      REAL NOT NULL,
    prob_high        REAL NOT NULL,
    risk_score       REAL NOT NULL,
    explanation_json TEXT NOT NULL,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_predictions_student ON predictions(student_fk, created_at DESC);

CREATE TABLE IF NOT EXISTS interventions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    student_fk        INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    faculty_user_fk   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    intervention_date TEXT NOT NULL,
    intervention_type TEXT NOT NULL,
    notes             TEXT,
    follow_up_date    TEXT,
    status            TEXT NOT NULL CHECK (status IN ('Planned', 'In Progress', 'Completed', 'Cancelled')),
    follow_up_outcome TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_interventions_student ON interventions(student_fk, intervention_date DESC);
CREATE INDEX IF NOT EXISTS idx_interventions_status ON interventions(status);

CREATE TABLE IF NOT EXISTS alerts (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    student_fk         INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    prediction_fk      INTEGER REFERENCES predictions(id) ON DELETE SET NULL,
    alert_type         TEXT NOT NULL CHECK (alert_type IN ('new_high_risk', 'risk_increase')),
    message            TEXT NOT NULL,
    previous_level     TEXT,
    new_level          TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'reviewed')),
    reviewed_by_fk     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at        TEXT,
    intervention_fk    INTEGER REFERENCES interventions(id) ON DELETE SET NULL,
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status, created_at DESC);

CREATE TABLE IF NOT EXISTS audit_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_fk     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,
    entity_type TEXT,
    entity_id   TEXT,
    details     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at DESC);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
