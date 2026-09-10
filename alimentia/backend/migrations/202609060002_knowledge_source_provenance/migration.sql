-- Additive migration: no existing table or record is replaced.
BEGIN TRANSACTION;
ALTER TABLE KnowledgeSource ADD COLUMN checksum TEXT;
ALTER TABLE KnowledgeSource ADD COLUMN originalFilename TEXT;
COMMIT;
