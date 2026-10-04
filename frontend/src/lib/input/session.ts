/** Pure reducer for the in-memory input session (drafts, claim review, confirmation). */
import type { ConfirmationResult, ReviewClaim, ReviewSession } from "@/lib/claims/types";
import type { PreparedSubmission } from "./types";

export interface InputSessionState {
  quickCheckText: string;
  contentText: string;
  /** Quick Check only: claim prepared for the later confirmation step. */
  prepared: PreparedSubmission | null;
  /** Full Content: extracted claims under user review (session only). */
  review: ReviewSession | null;
  /** Result of the explicit confirmation gate — ready for the future pipeline. */
  confirmation: ConfirmationResult | null;
}

export const initialInputSession: InputSessionState = {
  quickCheckText: "",
  contentText: "",
  prepared: null,
  review: null,
  confirmation: null,
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
  | { type: "confirmation/clear" };

function mapClaims(
  state: InputSessionState,
  fn: (claims: ReviewClaim[]) => ReviewClaim[],
): InputSessionState {
  if (!state.review) return state;
  // Any change to the review invalidates a previous confirmation.
  return { ...state, review: { ...state.review, claims: fn(state.review.claims) }, confirmation: null };
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
      return { ...state, confirmation: null };
  }
}
