"use client";

import { InputSessionProvider } from "@/lib/input/InputSessionProvider";

export function Providers({ children }: { children: React.ReactNode }) {
  return <InputSessionProvider>{children}</InputSessionProvider>;
}
