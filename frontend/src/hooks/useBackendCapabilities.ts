import { useEffect, useState } from "react";
import { getBackendCapabilities, getDefaultBackendCapabilities, type BackendCapabilities } from "../api/client";
import { toErrorMessage } from "../lib/helpers";

type BackendCapabilitiesState = {
  capabilities: BackendCapabilities;
  loading: boolean;
  error: string | null;
};

export function useBackendCapabilities() {
  const [state, setState] = useState<BackendCapabilitiesState>({
    capabilities: getDefaultBackendCapabilities(),
    loading: true,
    error: null,
  });

  useEffect(() => {
    let active = true;
    getBackendCapabilities()
      .then((capabilities) => {
        if (!active) return;
        setState({
          capabilities,
          loading: false,
          error: null,
        });
      })
      .catch((error) => {
        if (!active) return;
        setState({
          capabilities: getDefaultBackendCapabilities(),
          loading: false,
          error: toErrorMessage(error),
        });
      });

    return () => {
      active = false;
    };
  }, []);

  return state;
}

