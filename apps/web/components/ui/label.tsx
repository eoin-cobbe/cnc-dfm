import type { LabelHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Label({ className, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={cn("text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--panel-muted)]", className)}
      {...props}
    />
  );
}
