import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

type ButtonVariant = "default" | "secondary" | "ghost" | "outline";

const variantClasses: Record<ButtonVariant, string> = {
  default:
    "bg-[var(--accent)] text-white shadow-[0_10px_24px_rgba(15,86,216,0.22)] hover:bg-[var(--accent-strong)]",
  secondary:
    "bg-[var(--panel-strong)] text-[var(--page-ink)] shadow-sm hover:bg-white",
  ghost:
    "bg-transparent text-[var(--page-ink)] hover:bg-white/70",
  outline:
    "border border-[color:var(--panel-border)] bg-white/70 text-[var(--page-ink)] hover:bg-white",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

export function Button({
  className,
  variant = "default",
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-60",
        variantClasses[variant],
        className,
      )}
      type={type}
      {...props}
    />
  );
}
