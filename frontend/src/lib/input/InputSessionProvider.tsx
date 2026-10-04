"use client";

import { createContext, useContext, useMemo, useReducer, type Dispatch } from "react";
import {
  initialInputSession,
  inputSessionReducer,
  type InputSessionAction,
  type InputSessionState,
} from "./session";

interface InputSessionContextValue {
  state: InputSessionState;
  dispatch: Dispatch<InputSessionAction>;
}

const InputSessionContext = createContext<InputSessionContextValue | null>(null);

/**
 * In-memory input session shared across the input screens. Drafts survive
 * client-side navigation (e.g. Quick Check → Full Content). Nothing is sent
 * to the backend from here.
 */
export function InputSessionProvider({
  children,
  initialState = initialInputSession,
}: {
  children: React.ReactNode;
  initialState?: InputSessionState;
}) {
  const [state, dispatch] = useReducer(inputSessionReducer, initialState);
  const value = useMemo(() => ({ state, dispatch }), [state]);
  return <InputSessionContext.Provider value={value}>{children}</InputSessionContext.Provider>;
}

export function useInputSession(): InputSessionContextValue {
  const ctx = useContext(InputSessionContext);
  if (!ctx) throw new Error("useInputSession must be used inside <InputSessionProvider>");
  return ctx;
}
