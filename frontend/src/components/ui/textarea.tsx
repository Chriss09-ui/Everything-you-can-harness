import * as React from "react";
import { cn } from "@/lib/cn";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "w-full resize-none border-none bg-transparent text-ink placeholder:text-ink-faint focus:outline-none",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
