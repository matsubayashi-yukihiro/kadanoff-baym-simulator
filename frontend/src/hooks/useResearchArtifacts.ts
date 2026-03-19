import { useEffect, useMemo, useState } from "react";

import {
  createDecisionNote,
  createStudy,
  listDecisionNotes,
  listEvidenceBundles,
  listStudies,
  patchRunMetadata,
} from "../api/client";
import type {
  DecisionNoteKind,
  DecisionNoteRecord,
  EvidenceBundleRecord,
  RunDetail,
  StudyRecord,
} from "../api/types";
import { toErrorMessage } from "../lib/helpers";

export type UseResearchArtifactsReturn = {
  studies: StudyRecord[];
  studiesLoading: boolean;
  studiesError: string | null;
  linkedStudy: StudyRecord | null;

  notes: DecisionNoteRecord[];
  notesLoading: boolean;
  notesError: string | null;

  bundles: EvidenceBundleRecord[];
  bundlesLoading: boolean;

  noteForm: { kind: DecisionNoteKind; body: string };
  setNoteForm: (form: { kind: DecisionNoteKind; body: string }) => void;
  isSubmittingNote: boolean;
  noteSubmitError: string | null;
  submitNote: () => Promise<void>;

  studyForm: { title: string; question: string };
  setStudyForm: (form: { title: string; question: string }) => void;
  isSubmittingStudy: boolean;
  studySubmitError: string | null;
  submitStudy: () => Promise<void>;

  isLinkingStudy: boolean;
  linkStudyError: string | null;
  linkRunToStudy: (studyId: string) => Promise<void>;
};

export function useResearchArtifacts(
  selectedRun: RunDetail | null,
  onRunUpdated?: (run: RunDetail) => void,
): UseResearchArtifactsReturn {
  const [studies, setStudies] = useState<StudyRecord[]>([]);
  const [studiesLoading, setStudiesLoading] = useState(false);
  const [studiesError, setStudiesError] = useState<string | null>(null);

  const [notes, setNotes] = useState<DecisionNoteRecord[]>([]);
  const [notesLoading, setNotesLoading] = useState(false);
  const [notesError, setNotesError] = useState<string | null>(null);

  const [bundles, setBundles] = useState<EvidenceBundleRecord[]>([]);
  const [bundlesLoading, setBundlesLoading] = useState(false);

  const [noteForm, setNoteForm] = useState<{ kind: DecisionNoteKind; body: string }>({
    kind: "observation",
    body: "",
  });
  const [isSubmittingNote, setIsSubmittingNote] = useState(false);
  const [noteSubmitError, setNoteSubmitError] = useState<string | null>(null);

  const [studyForm, setStudyForm] = useState({ title: "", question: "" });
  const [isSubmittingStudy, setIsSubmittingStudy] = useState(false);
  const [studySubmitError, setStudySubmitError] = useState<string | null>(null);

  const [isLinkingStudy, setIsLinkingStudy] = useState(false);
  const [linkStudyError, setLinkStudyError] = useState<string | null>(null);

  // Derived: linked study based on run's research_metadata.study_id
  const linkedStudy = useMemo(
    () => studies.find((s) => s.study_id === selectedRun?.research_metadata?.study_id) ?? null,
    [studies, selectedRun?.research_metadata?.study_id],
  );

  // Load studies on mount
  useEffect(() => {
    let cancelled = false;
    setStudiesLoading(true);
    listStudies()
      .then((data) => {
        if (!cancelled) {
          setStudies(data);
          setStudiesError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setStudiesError(toErrorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setStudiesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Load notes when selected run changes
  useEffect(() => {
    if (!selectedRun) {
      setNotes([]);
      return;
    }
    let cancelled = false;
    setNotes([]);
    setNotesLoading(true);
    listDecisionNotes({ source_kind: "run", source_id: selectedRun.run_id })
      .then((data) => {
        if (!cancelled) {
          setNotes(data);
          setNotesError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setNotesError(toErrorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setNotesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedRun?.run_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Load evidence bundles when linked study changes
  useEffect(() => {
    if (!linkedStudy) {
      setBundles([]);
      return;
    }
    let cancelled = false;
    setBundlesLoading(true);
    listEvidenceBundles({ study_id: linkedStudy.study_id })
      .then((data) => {
        if (!cancelled) setBundles(data);
      })
      .catch(() => {
        if (!cancelled) setBundles([]);
      })
      .finally(() => {
        if (!cancelled) setBundlesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [linkedStudy?.study_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const submitNote = async () => {
    if (!selectedRun || !linkedStudy || !noteForm.body.trim()) return;
    setIsSubmittingNote(true);
    setNoteSubmitError(null);
    try {
      const note = await createDecisionNote({
        study_id: linkedStudy.study_id,
        source_kind: "run",
        source_id: selectedRun.run_id,
        note_kind: noteForm.kind,
        body: noteForm.body.trim(),
      });
      setNotes((prev) => [note, ...prev]);
      setNoteForm((prev) => ({ ...prev, body: "" }));
    } catch (err) {
      setNoteSubmitError(toErrorMessage(err));
    } finally {
      setIsSubmittingNote(false);
    }
  };

  const submitStudy = async () => {
    if (!studyForm.title.trim() || !studyForm.question.trim()) return;
    setIsSubmittingStudy(true);
    setStudySubmitError(null);
    try {
      const study = await createStudy({
        title: studyForm.title.trim(),
        question: studyForm.question.trim(),
        status: "active",
      });
      setStudies((prev) => [study, ...prev]);
      setStudyForm({ title: "", question: "" });
    } catch (err) {
      setStudySubmitError(toErrorMessage(err));
    } finally {
      setIsSubmittingStudy(false);
    }
  };

  const linkRunToStudy = async (studyId: string) => {
    if (!selectedRun) return;
    setIsLinkingStudy(true);
    setLinkStudyError(null);
    try {
      const updated = await patchRunMetadata(selectedRun.run_id, { study_id: studyId });
      onRunUpdated?.(updated);
    } catch (err) {
      setLinkStudyError(toErrorMessage(err));
    } finally {
      setIsLinkingStudy(false);
    }
  };

  return {
    studies,
    studiesLoading,
    studiesError,
    linkedStudy,
    notes,
    notesLoading,
    notesError,
    bundles,
    bundlesLoading,
    noteForm,
    setNoteForm,
    isSubmittingNote,
    noteSubmitError,
    submitNote,
    studyForm,
    setStudyForm,
    isSubmittingStudy,
    studySubmitError,
    submitStudy,
    isLinkingStudy,
    linkStudyError,
    linkRunToStudy,
  };
}
