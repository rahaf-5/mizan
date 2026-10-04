/** Pure reducer for the in-memory input session (drafts + prepared submission). */
import type { ContentMode, ImageSelection, PreparedSubmission } from "./types";

export interface InputSessionState {
  quickCheckText: string;
  contentText: string;
  contentMode: ContentMode;
  image: ImageSelection | null;
  /** Latest prepared submission, waiting for a later stage (Task 3/4). */
  prepared: PreparedSubmission | null;
}

export const initialInputSession: InputSessionState = {
  quickCheckText: "",
  contentText: "",
  contentMode: "text",
  image: null,
  prepared: null,
};

export type InputSessionAction =
  | { type: "quickCheck/setText"; text: string }
  | { type: "content/setText"; text: string }
  | { type: "content/setMode"; mode: ContentMode }
  | { type: "content/setImage"; image: ImageSelection | null }
  | { type: "prepared/set"; submission: PreparedSubmission }
  | { type: "prepared/clear" }
  /** Quick Check input looked like several claims: carry it into Full Content (text). */
  | { type: "quickCheck/moveToFullContent" };

export function inputSessionReducer(
  state: InputSessionState,
  action: InputSessionAction,
): InputSessionState {
  switch (action.type) {
    case "quickCheck/setText":
      return { ...state, quickCheckText: action.text };
    case "content/setText":
      return { ...state, contentText: action.text };
    case "content/setMode":
      return { ...state, contentMode: action.mode };
    case "content/setImage":
      return { ...state, image: action.image };
    case "prepared/set":
      return { ...state, prepared: action.submission };
    case "prepared/clear":
      return { ...state, prepared: null };
    case "quickCheck/moveToFullContent":
      return {
        ...state,
        contentText: state.quickCheckText,
        contentMode: "text",
        prepared: null,
      };
  }
}
