"use client";

import { useInputSession } from "@/lib/input/InputSessionProvider";
import type { ContentMode } from "@/lib/input/types";
import { ImageUploadPanel } from "./ImageUploadPanel";
import { MODES, ModeTabs, panelId, tabId } from "./ModeTabs";
import { TextContentPanel } from "./TextContentPanel";

/** Full Content Check input: text or image. Each mode keeps its own draft. */
export function FullContentInput() {
  const { state, dispatch } = useInputSession();
  const setMode = (mode: ContentMode) => {
    if (mode === state.contentMode) return;
    dispatch({ type: "content/setMode", mode });
    if (state.prepared?.kind === "full_content_text" || state.prepared?.kind === "full_content_image") {
      dispatch({ type: "prepared/clear" });
    }
  };

  return (
    <div className="space-y-5">
      <ModeTabs value={state.contentMode} onChange={setMode} />
      {MODES.map(({ mode }) =>
        mode === state.contentMode ? (
          <div key={mode} role="tabpanel" id={panelId(mode)} aria-labelledby={tabId(mode)} tabIndex={0}>
            {mode === "text" ? <TextContentPanel /> : <ImageUploadPanel />}
          </div>
        ) : null,
      )}
    </div>
  );
}
