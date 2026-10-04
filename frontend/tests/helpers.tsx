import { render } from "@testing-library/react";
import { InputSessionProvider } from "@/lib/input/InputSessionProvider";
import { initialInputSession, type InputSessionState } from "@/lib/input/session";

export function renderWithSession(ui: React.ReactElement, state: Partial<InputSessionState> = {}) {
  return render(
    <InputSessionProvider initialState={{ ...initialInputSession, ...state }}>{ui}</InputSessionProvider>,
  );
}

const PNG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0];
const JPEG = [0xff, 0xd8, 0xff, 0xe0, 0, 0, 0, 0];

export const pngFile = (name = "page.png") => new File([new Uint8Array(PNG)], name, { type: "image/png" });
export const jpegFile = (name = "page.jpg") => new File([new Uint8Array(JPEG)], name, { type: "image/jpeg" });
