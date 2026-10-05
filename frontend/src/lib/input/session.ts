/** Pure reducer for the in-memory input session (drafts, claim review, confirmation). */
import type { ConfirmationResult, ReviewClaim, ReviewSession } from "@/lib/claims/types";
import type { ClaimRun } from "@/lib/verify/types";
import type { PreparedSubmission } from "./types";

export interface InputSessionState {
  quickCheckText: string;
  contentText: string;
  /** Quick Check only: claim prepared for the later confirmation step. */
  prepared: PreparedSubmission | null;
  /** Full Content: extracted claims under user review (session only). */
  review: ReviewSession | null;
  /** Result of the explicit confirmation gate (Full Content). */
  confirmation: ConfirmationResult | null;
  /** Verification report runs (in memory). `key` ties them to the confirmed claims. */
  verification: { key: string; runs: ClaimRun[] } | null;
}

export const initialInputSession: InputSessionState = {
  quickCheckText: "",
  contentText: "",
  prepared: null,
  review: null,
  confirmation: null,
  verification: null,
};

export type InputSessionAction =
  | { type: "quickCheck/setText"; text: string }
  | { type: "content/setText"; text: string }
  | { type: "prepared/set"; submission: PreparedSubmission }
  | { type: "prepared/clear" }
  /** Quick Check input looked like several claims: carry it into Full Content. */
  | { type: "quickCheck/moveToFullContent" }
  | { type: "review/start"; sourceText: string; claims: ReviewClaim[] }
  | { type: "review/toggle"; id: string }
  | { type: "review/setAll"; selected: boolean }
  | { type: "review/edit"; id: string; text: string }
  | { type: "review/delete"; id: string }
  | { type: "review/add"; claim: ReviewClaim }
  | { type: "confirmation/set"; result: ConfirmationResult }
  | { type: "confirmation/clear" }
  | { type: "verification/set"; key: string; runs: ClaimRun[] }
  | { type: "verification/updateAt"; key: string; index: number; run: ClaimRun }
  | { type: "verification/clear" };

function mapClaims(
  state: InputSessionState,
  fn: (claims: ReviewClaim[]) => ReviewClaim[],
): InputSessionState {
  if (!state.review) return state;
  // Any change to the review invalidates a previous confirmation.
  return {
    ...state,
    review: { ...state.review, claims: fn(state.review.claims) },
    confirmation: null,
    verification: null,
  };
}

export function inputSessionReducer(
  state: InputSessionState,
  action: InputSessionAction,
): InputSessionState {
  switch (action.type) {
    case "quickCheck/setText":
      return { ...state, quickCheckText: action.text };
    case "content/setText":
      return { ...state, contentText: action.text };
    case "prepared/set":
      return { ...state, prepared: action.submission };
    case "prepared/clear":
      return { ...state, prepared: null };
    case "quickCheck/moveToFullContent":
      return { ...state, contentText: state.quickCheckText, prepared: null };
    case "review/start":
      return {
        ...state,
        review: { sourceText: action.sourceText, claims: action.claims },
        confirmation: null,
        verification: null,
      };
    case "review/toggle":
      return mapClaims(state, (cs) => cs.map((c) => (c.id === action.id ? { ...c, selected: !c.selected } : c)));
    case "review/setAll":
      return mapClaims(state, (cs) => cs.map((c) => ({ ...c, selected: action.selected })));
    case "review/edit":
      return mapClaims(state, (cs) => cs.map((c) => (c.id === action.id ? { ...c, text: action.text } : c)));
    case "review/delete":
      return mapClaims(state, (cs) => cs.filter((c) => c.id !== action.id));
    case "review/add":
      return mapClaims(state, (cs) => [...cs, action.claim]);
    case "confirmation/set":
      return { ...state, confirmation: action.result };
    case "confirmation/clear":
      return { ...state, confirmation: null, verification: null };
    case "verification/set":
      return { ...state, verification: { key: action.key, runs: action.runs } };
    case "verification/updateAt": {
      const v = state.verification;
      if (!v || v.key !== action.key || !v.runs[action.index]) return state;
      const runs = v.runs.map((r, i) => (i === action.index ? action.run : r));
      return { ...state, verification: { key: v.key, runs } };
    }
    case "verification/clear":
      return { ...state, verification: null };
  }
}
