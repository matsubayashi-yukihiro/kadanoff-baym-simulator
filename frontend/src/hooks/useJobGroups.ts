import { useCallback, useEffect, useRef, useState } from "react";
import { getJobGroup, launchJobGroup, listJobGroups } from "../api/client";
import type { JobGroupLaunchRequest, JobGroupRecord } from "../api/types";

type JobGroupsState = {
  groups: JobGroupRecord[];
  loading: boolean;
  error: string | null;
  selectedGroupId: string | null;
  selectedGroup: JobGroupRecord | null;
  groupLoading: boolean;
  groupError: string | null;
  isLaunching: boolean;
  launchError: string | null;
};

const TERMINAL_STATES = new Set(["succeeded", "failed", "cancelled"]);
const POLL_INTERVAL_MS = 2000;

export function useJobGroups(studyId?: string | null) {
  const [state, setState] = useState<JobGroupsState>({
    groups: [],
    loading: false,
    error: null,
    selectedGroupId: null,
    selectedGroup: null,
    groupLoading: false,
    groupError: null,
    isLaunching: false,
    launchError: null,
  });

  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (pollTimerRef.current !== null) {
        clearTimeout(pollTimerRef.current);
      }
    };
  }, []);

  const fetchGroups = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const groups = await listJobGroups(studyId ? { study_id: studyId } : {});
      if (!mountedRef.current) return;
      setState((prev) => ({ ...prev, groups, loading: false }));
    } catch (err) {
      if (!mountedRef.current) return;
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : "failed to load job groups",
      }));
    }
  }, [studyId]);

  const pollGroup = useCallback(async (groupId: string) => {
    if (!mountedRef.current) return;
    try {
      const group = await getJobGroup(groupId);
      if (!mountedRef.current) return;
      setState((prev) => ({
        ...prev,
        selectedGroup: group,
        groupLoading: false,
        groups: prev.groups.map((g) => (g.group_id === groupId ? group : g)),
      }));
      if (!TERMINAL_STATES.has(group.state)) {
        pollTimerRef.current = setTimeout(() => pollGroup(groupId), POLL_INTERVAL_MS);
      }
    } catch (err) {
      if (!mountedRef.current) return;
      setState((prev) => ({
        ...prev,
        groupLoading: false,
        groupError: err instanceof Error ? err.message : "failed to fetch group",
      }));
    }
  }, []);

  const selectGroup = useCallback(
    (groupId: string) => {
      if (pollTimerRef.current !== null) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      setState((prev) => ({
        ...prev,
        selectedGroupId: groupId,
        selectedGroup: prev.groups.find((g) => g.group_id === groupId) ?? null,
        groupLoading: true,
        groupError: null,
      }));
      pollGroup(groupId);
    },
    [pollGroup],
  );

  const launchGroup = useCallback(
    async (req: JobGroupLaunchRequest) => {
      setState((prev) => ({ ...prev, isLaunching: true, launchError: null }));
      try {
        const group = await launchJobGroup(req);
        if (!mountedRef.current) return;
        setState((prev) => ({
          ...prev,
          isLaunching: false,
          groups: [group, ...prev.groups],
          selectedGroupId: group.group_id,
          selectedGroup: group,
        }));
        // Start polling the new group
        pollGroup(group.group_id);
      } catch (err) {
        if (!mountedRef.current) return;
        setState((prev) => ({
          ...prev,
          isLaunching: false,
          launchError: err instanceof Error ? err.message : "launch failed",
        }));
      }
    },
    [pollGroup],
  );

  // Load groups on mount
  useEffect(() => {
    fetchGroups();
  }, [fetchGroups]);

  return {
    ...state,
    fetchGroups,
    selectGroup,
    launchGroup,
  };
}
