import * as React from "react";
import { cn } from "@/lib/cn";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "w-full bg-canvas border border-line-strong rounded-md px-3.5 py-2.5 text-[14.5px] text-ink",
      "placeholder:text-ink-faint",
      "transition-[background,border-color,box-shadow] duration-150",
      "focus:outline-none focus:bg-surface focus:border-ink-faint focus:shadow-[0_0_0_3px_rgba(0,0,0,0.03)]",
      "disabled:opacity-60",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";
