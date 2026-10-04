import { render } from "@testing-library/react";
import { InputSessionProvider } from "@/lib/input/InputSessionProvider";
import { initialInputSession, type InputSessionState } from "@/lib/input/session";

export function renderWithSession(ui: React.ReactElement, state: Partial<InputSessionState> = {}) {
  return render(
    <InputSessionProvider initialState={{ ...initialInputSession, ...state }}>{ui}</InputSessionProvider>,
  );
}
