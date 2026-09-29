-- Additive migration: no existing table or record is replaced.
BEGIN TRANSACTION;
ALTER TABLE NutritionConsultation ADD COLUMN status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','READY'));
ALTER TABLE NutritionConsultation ADD COLUMN requiresProfessionalReview BOOLEAN NOT NULL DEFAULT false;
CREATE TABLE PatientCreateRequest (
  key TEXT NOT NULL PRIMARY KEY,
  requestHash TEXT NOT NULL,
  patientId TEXT NOT NULL,
  CONSTRAINT PatientCreateRequest_patientId_fkey FOREIGN KEY(patientId) REFERENCES Patient(id) ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE INDEX PatientCreateRequest_patientId_idx ON PatientCreateRequest(patientId);
CREATE TABLE ConsultationCreateRequest (
  key TEXT NOT NULL PRIMARY KEY,
  requestHash TEXT NOT NULL,
  consultationId TEXT NOT NULL,
  CONSTRAINT ConsultationCreateRequest_consultationId_fkey FOREIGN KEY(consultationId) REFERENCES NutritionConsultation(id) ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE INDEX ConsultationCreateRequest_consultationId_idx ON ConsultationCreateRequest(consultationId);
COMMIT;
