/** Pure reducer for the in-memory input session (drafts + prepared submission). */
import type { OcrExtraction } from "@/lib/ocr/types";
import type { ContentMode, ImageSelection, OcrSession, PreparedSubmission } from "./types";

export interface InputSessionState {
  quickCheckText: string;
  contentText: string;
  contentMode: ContentMode;
  image: ImageSelection | null;
  /** Image flow: raw OCR result + user-reviewed text (separate). */
  ocr: OcrSession | null;
  /** Latest prepared submission, waiting for a later stage (Task 3/4). */
  prepared: PreparedSubmission | null;
}

export const initialInputSession: InputSessionState = {
  quickCheckText: "",
  contentText: "",
  contentMode: "text",
  image: null,
  ocr: null,
  prepared: null,
};

export type InputSessionAction =
  | { type: "quickCheck/setText"; text: string }
  | { type: "content/setText"; text: string }
  | { type: "content/setMode"; mode: ContentMode }
  | { type: "content/setImage"; image: ImageSelection | null }
  | { type: "ocr/received"; image: ImageSelection; extraction: OcrExtraction }
  | { type: "ocr/editReviewed"; text: string }
  | { type: "ocr/restoreRaw" }
  | { type: "ocr/clear" }
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
      return { ...state, image: action.image, ocr: null };
    case "ocr/received":
      // Reviewed text starts as a copy; the raw extraction object is never mutated.
      return {
        ...state,
        image: action.image,
        ocr: { image: action.image, extraction: action.extraction, reviewedText: action.extraction.raw_text },
        prepared: null,
      };
    case "ocr/editReviewed":
      return state.ocr ? { ...state, ocr: { ...state.ocr, reviewedText: action.text } } : state;
    case "ocr/restoreRaw":
      return state.ocr
        ? { ...state, ocr: { ...state.ocr, reviewedText: state.ocr.extraction.raw_text } }
        : state;
    case "ocr/clear":
      return { ...state, ocr: null, prepared: null };
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
