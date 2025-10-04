IF DB_ID(N'PlaygroupPiececitas') IS NULL
BEGIN
    CREATE DATABASE PlaygroupPiececitas;
END
GO
USE PlaygroupPiececitas;
GO


-- SCHEMA
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'pg')
    EXEC('CREATE SCHEMA pg');
GO

/* =========================
   IDENTIDAD / ROLES
========================= */
CREATE TABLE pg.[User] (
    UserId           INT IDENTITY(1,1) PRIMARY KEY,
    Email            VARCHAR(120) NOT NULL UNIQUE,
    PasswordHash     VARCHAR(255) NOT NULL,
    Role             VARCHAR(20)  NOT NULL CHECK (Role IN ('admin','therapist','collaborator','guardian')),
    FirstName        VARCHAR(80)  NOT NULL,
    LastName         VARCHAR(80)  NOT NULL,
    Phone            VARCHAR(30)  NULL,
    IsActive         BIT NOT NULL DEFAULT 1,
    CreatedAt        DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
    LastLoginAt      DATETIME2(0) NULL
);
GO
CREATE INDEX IX_User_Role ON pg.[User](Role, IsActive);

-- Perfil de terapeuta (1:1 con User cuando es therapist/collaborator)
CREATE TABLE pg.TherapistProfile (
    UserId           INT PRIMARY KEY,            -- FK = User
    Specialty        VARCHAR(100) NULL,
    Certifications   VARCHAR(400) NULL,          -- texto simple (archivos se manejan por fuera en MVP)
    Bio              VARCHAR(500) NULL,
    RatingAvg        DECIMAL(3,2) NULL CHECK (RatingAvg BETWEEN 0 AND 5),
    CONSTRAINT FK_TP_User FOREIGN KEY (UserId) REFERENCES pg.[User](UserId)
);
GO

/* =========================
   CLIENTES / NIÑOS
========================= */
CREATE TABLE pg.Guardian (
    GuardianId       INT IDENTITY(1,1) PRIMARY KEY,
    UserId           INT NULL UNIQUE,           -- si el apoderado tiene cuenta
    PreferredContact VARCHAR(20)  NULL CHECK (PreferredContact IN ('phone','email','whatsapp')),
    CreatedAt        DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
    IsActive         BIT NOT NULL DEFAULT 1,
    CONSTRAINT FK_Guardian_User FOREIGN KEY (UserId) REFERENCES pg.[User](UserId)
);
GO

CREATE TABLE pg.Child (
    ChildId     INT IDENTITY(1,1) PRIMARY KEY,
    FirstName   VARCHAR(80)  NOT NULL,
    LastName    VARCHAR(80)  NOT NULL,
    BirthDate   DATE         NOT NULL,
    Notes       VARCHAR(500) NULL,
    CreatedAt   DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
    IsActive    BIT NOT NULL DEFAULT 1
);
GO
CREATE INDEX IX_Child_Name ON pg.Child(LastName, FirstName);

CREATE TABLE pg.ChildGuardian (
    ChildId    INT NOT NULL,
    GuardianId INT NOT NULL,
    Relation   VARCHAR(40) NULL,  -- madre, padre, tutor, etc.
    IsPrimary  BIT NOT NULL DEFAULT 0,
    CONSTRAINT PK_ChildGuardian PRIMARY KEY (ChildId, GuardianId),
    CONSTRAINT FK_CG_Child FOREIGN KEY (ChildId) REFERENCES pg.Child(ChildId),
    CONSTRAINT FK_CG_Guardian FOREIGN KEY (GuardianId) REFERENCES pg.Guardian(GuardianId)
);
GO
CREATE INDEX IX_CG_Guardian ON pg.ChildGuardian(GuardianId);

CREATE TABLE pg.AllergyNote (
    AllergyNoteId INT IDENTITY(1,1) PRIMARY KEY,
    ChildId       INT NOT NULL,
    Description   VARCHAR(300) NOT NULL,
    Severity      VARCHAR(20)  NULL CHECK (Severity IN ('low','medium','high')),
    CreatedAt     DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_AN_Child FOREIGN KEY (ChildId) REFERENCES pg.Child(ChildId)
);
GO

CREATE TABLE pg.Consent (
    ConsentId    INT IDENTITY(1,1) PRIMARY KEY,
    ChildId      INT NOT NULL,
    ConsentType  VARCHAR(50) NOT NULL,  -- imagen, participación, información, etc.
    GivenBy      INT NOT NULL,          -- GuardianId
    GivenAt      DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
    IsGranted    BIT NOT NULL,
    Notes        VARCHAR(300) NULL,
    CONSTRAINT FK_Consent_Child FOREIGN KEY (ChildId) REFERENCES pg.Child(ChildId),
    CONSTRAINT FK_Consent_Guard FOREIGN KEY (GivenBy) REFERENCES pg.Guardian(GuardianId),
    CONSTRAINT UQ_Consent UNIQUE (ChildId, ConsentType)
);
GO

/* =========================
   ORGANIZACIÓN (opcional)
========================= */
CREATE TABLE pg.[Group] (
    GroupId     INT IDENTITY(1,1) PRIMARY KEY,
    Name        VARCHAR(80) NOT NULL UNIQUE,
    Description VARCHAR(200) NULL,
    MaxSize     INT NOT NULL CHECK (MaxSize BETWEEN 2 AND 10),
    IsActive    BIT NOT NULL DEFAULT 1,
    CreatedAt   DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

CREATE TABLE pg.GroupMember (
    GroupId    INT NOT NULL,
    ChildId    INT NOT NULL,
    JoinedAt   DATE NOT NULL DEFAULT CONVERT(date, SYSUTCDATETIME()),
    LeftAt     DATE NULL,
    CONSTRAINT PK_GroupMember PRIMARY KEY (GroupId, ChildId),
    CONSTRAINT FK_GM_Group FOREIGN KEY (GroupId) REFERENCES pg.[Group](GroupId),
    CONSTRAINT FK_GM_Child FOREIGN KEY (ChildId) REFERENCES pg.Child(ChildId),
    CONSTRAINT CK_GM_Dates CHECK (LeftAt IS NULL OR LeftAt >= JoinedAt)
);
GO
CREATE INDEX IX_GM_Child ON pg.GroupMember(ChildId);

/* =========================
   UBICACIONES Y DISPONIBILIDAD
========================= */
CREATE TABLE pg.[Location] (
    LocationId     INT IDENTITY(1,1) PRIMARY KEY,
    Label          VARCHAR(100) NOT NULL,   -- "Casa Ana"
    AddressLine1   VARCHAR(120) NULL,
    AddressLine2   VARCHAR(120) NULL,
    City           VARCHAR(80)  NULL,
    Notes          VARCHAR(200) NULL,
    OwnerGuardianId INT NULL,
    CONSTRAINT FK_Loc_Guard FOREIGN KEY (OwnerGuardianId) REFERENCES pg.Guardian(GuardianId)
);
GO

CREATE TABLE pg.AvailabilityBlock (
    AvailabilityId INT IDENTITY(1,1) PRIMARY KEY,
    TherapistUserId INT NOT NULL,
    Weekday        TINYINT NOT NULL CHECK (Weekday BETWEEN 1 AND 7),   -- 1=Lunes ... 7=Domingo
    StartTime      TIME NOT NULL,
    EndTime        TIME NOT NULL,
    IsActive       BIT NOT NULL DEFAULT 1,
    CONSTRAINT CK_Avail_Time CHECK (EndTime > StartTime),
    CONSTRAINT FK_Avail_User FOREIGN KEY (TherapistUserId) REFERENCES pg.[User](UserId)
);
GO
CREATE INDEX IX_Avail_UserDay ON pg.AvailabilityBlock(TherapistUserId, Weekday);

/* =========================
   SESIONES / ACTIVIDADES
========================= */
CREATE TABLE pg.[Session] (
    SessionId       INT IDENTITY(1,1) PRIMARY KEY,
    GroupId         INT NULL,
    TherapistUserId INT NOT NULL,       -- titular
    ScheduledAt     DATETIME2(0) NOT NULL,
    DurationMin     INT NOT NULL CHECK (DurationMin BETWEEN 30 AND 240),
    GoalSummary     VARCHAR(200) NULL,
    Notes           VARCHAR(500) NULL,
    CreatedByUserId INT NULL,
    CreatedAt       DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_Session_Group FOREIGN KEY (GroupId) REFERENCES pg.[Group](GroupId),
    CONSTRAINT FK_Session_Therapist FOREIGN KEY (TherapistUserId) REFERENCES pg.[User](UserId),
    CONSTRAINT FK_Session_CreatedBy FOREIGN KEY (CreatedByUserId) REFERENCES pg.[User](UserId)
);
GO
CREATE INDEX IX_Session_TherapistTime ON pg.[Session](TherapistUserId, ScheduledAt);

CREATE TABLE pg.SessionLocation (
    SessionId  INT NOT NULL PRIMARY KEY,
    LocationId INT NOT NULL,
    CONSTRAINT FK_SL_Session FOREIGN KEY (SessionId) REFERENCES pg.[Session](SessionId),
    CONSTRAINT FK_SL_Location FOREIGN KEY (LocationId) REFERENCES pg.[Location](LocationId)
);
GO

CREATE TABLE pg.ActivityCatalog (
    ActivityId INT IDENTITY(1,1) PRIMARY KEY,
    Name       VARCHAR(100) NOT NULL UNIQUE,
    Area       VARCHAR(32)  NOT NULL CHECK (Area IN ('motricidad_gruesa','motricidad_fina','sensorial','lenguaje','emocional','social')),
    Description VARCHAR(400) NULL
);
GO

CREATE TABLE pg.SessionActivity (
    SessionId  INT NOT NULL,
    ActivityId INT NOT NULL,
    Notes      VARCHAR(300) NULL,
    CONSTRAINT PK_SessionActivity PRIMARY KEY (SessionId, ActivityId),
    CONSTRAINT FK_SA_Session FOREIGN KEY (SessionId) REFERENCES pg.[Session](SessionId),
    CONSTRAINT FK_SA_Activity FOREIGN KEY (ActivityId) REFERENCES pg.ActivityCatalog(ActivityId)
);
GO

CREATE TABLE pg.Attendance (
    SessionId  INT NOT NULL,
    ChildId    INT NOT NULL,
    Status     VARCHAR(12) NOT NULL CHECK (Status IN ('present','absent','late')),
    Comment    VARCHAR(300) NULL,
    CONSTRAINT PK_Attendance PRIMARY KEY (SessionId, ChildId),
    CONSTRAINT FK_Att_Session FOREIGN KEY (SessionId) REFERENCES pg.[Session](SessionId),
    CONSTRAINT FK_Att_Child FOREIGN KEY (ChildId) REFERENCES pg.Child(ChildId)
);
GO
CREATE INDEX IX_Att_Child ON pg.Attendance(ChildId);

/* =========================
   CLÍNICO / REEMPLAZOS / EXPORTES
========================= */
CREATE TABLE pg.ClinicalNote (
    ClinicalNoteId  INT IDENTITY(1,1) PRIMARY KEY,
    SessionId       INT NOT NULL,
    ChildId         INT NOT NULL,
    Objectives      VARCHAR(600) NULL,
    Observations    VARCHAR(1000) NULL,
    Homework        VARCHAR(600) NULL,
    Visibility      VARCHAR(12) NOT NULL DEFAULT 'internal' CHECK (Visibility IN ('internal','shared')),
    CreatedByUserId INT NOT NULL,
    CreatedAt       DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_CN_Session FOREIGN KEY (SessionId) REFERENCES pg.[Session](SessionId),
    CONSTRAINT FK_CN_Child FOREIGN KEY (ChildId) REFERENCES pg.Child(ChildId),
    CONSTRAINT FK_CN_User FOREIGN KEY (CreatedByUserId) REFERENCES pg.[User](UserId),
    CONSTRAINT UQ_CN UNIQUE (SessionId, ChildId)   -- una nota por niño en sesión
);
GO

CREATE TABLE pg.ReplacementLog (
    ReplacementId     INT IDENTITY(1,1) PRIMARY KEY,
    SessionId         INT NOT NULL,
    FromTherapistUserId INT NOT NULL,
    ToTherapistUserId   INT NOT NULL,
    Reason            VARCHAR(200) NULL,
    CreatedByUserId   INT NOT NULL,
    CreatedAt         DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_RL_Session FOREIGN KEY (SessionId) REFERENCES pg.[Session](SessionId),
    CONSTRAINT FK_RL_From   FOREIGN KEY (FromTherapistUserId) REFERENCES pg.[User](UserId),
    CONSTRAINT FK_RL_To     FOREIGN KEY (ToTherapistUserId)   REFERENCES pg.[User](UserId),
    CONSTRAINT FK_RL_By     FOREIGN KEY (CreatedByUserId)     REFERENCES pg.[User](UserId)
);
GO
CREATE INDEX IX_RL_Session ON pg.ReplacementLog(SessionId);

CREATE TABLE pg.DocumentExport (
    ExportId       INT IDENTITY(1,1) PRIMARY KEY,
    ExportType     VARCHAR(30) NOT NULL CHECK (ExportType IN ('child_summary','session_report','attendance')),
    EntityId       INT NOT NULL,                -- ChildId / SessionId, según tipo
    FilePath       VARCHAR(260) NOT NULL,       -- ruta/uuid
    CreatedByUserId INT NOT NULL,
    CreatedAt      DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_DE_User FOREIGN KEY (CreatedByUserId) REFERENCES pg.[User](UserId)
);
GO

/* =========================
   SEED MÍNIMO
========================= */
INSERT INTO pg.ActivityCatalog (Name, Area, Description) VALUES
('Circuito de motricidad', 'motricidad_gruesa', 'Saltos, equilibrio, coordinación'),
('Pinzas con cuentas', 'motricidad_fina', 'Fortalecimiento pinza fina'),
('Bandeja sensorial', 'sensorial', 'Texturas y reconocimiento'),
('Juego de rimas', 'lenguaje', 'Conciencia fonológica'),
('Semáforo emocional', 'emocional', 'Identificación de emociones'),
('Turnos con pelotas', 'social', 'Espera activa y colaboración');

/* ============================================= */

USE PlaygroupPiececitas;
GO

SELECT COUNT(*) AS TablesCount
FROM sys.tables
WHERE schema_id = SCHEMA_ID('pg');

/* ============================================= */

SELECT t.name AS TableName
FROM sys.tables t
WHERE t.schema_id = SCHEMA_ID('pg')
ORDER BY t.name;

/* ============================================= */

SELECT TOP (10) *
FROM pg.ActivityCatalog
ORDER BY ActivityId;

/* ============================================= */

SELECT
  fk.name AS FK_Name,
  OBJECT_SCHEMA_NAME(fk.parent_object_id) AS SchemaName,
  OBJECT_NAME(fk.parent_object_id) AS TableName
FROM sys.foreign_keys fk
WHERE OBJECT_SCHEMA_NAME(fk.parent_object_id) = 'pg'
ORDER BY TableName, FK_Name;

/* ============================================= */

SELECT
  OBJECT_SCHEMA_NAME(i.object_id) AS SchemaName,
  OBJECT_NAME(i.object_id) AS TableName,
  i.name AS IndexName,
  i.type_desc
FROM sys.indexes i
WHERE OBJECT_SCHEMA_NAME(i.object_id) = 'pg'
ORDER BY TableName, IndexName;

/* ============================================= */


