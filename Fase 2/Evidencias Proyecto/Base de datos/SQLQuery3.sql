USE PlaygroupPiececitas;
GO

SELECT t.name AS TableName, c.name AS ColumnName, ty.name AS TypeName
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.columns c ON c.object_id = t.object_id
JOIN sys.types ty ON c.user_type_id = ty.user_type_id
WHERE s.name = 'pg' AND t.name IN ('AvailabilityBlock', 'Therapist', 'TherapySession', 'Session', 'Appointment')
ORDER BY t.name, c.column_id;


ALTER TABLE pg.AvailabilityBlock
ADD CONSTRAINT CK_AvailabilityBlock_BusinessHours
CHECK (StartTime >= '09:00' AND EndTime <= '18:00' AND StartTime < EndTime);
