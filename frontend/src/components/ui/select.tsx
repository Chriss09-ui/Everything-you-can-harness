import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";

interface Option {
  value: string;
  label: string;
}

interface SelectProps {
  value: string;
  onValueChange: (v: string) => void;
  options: Option[];
  className?: string;
  id?: string;
}

export function Select({ value, onValueChange, options, className, id }: SelectProps) {
  return (
    <div className={cn("relative", className)}>
      <select
        id={id}
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        className={cn(
          "w-full appearance-none cursor-pointer bg-canvas border border-line-strong rounded-md",
          "px-3.5 py-2.5 pr-10 text-[14.5px] text-ink",
          "transition-[background,border-color,box-shadow] duration-150",
          "focus:outline-none focus:bg-surface focus:border-ink-faint focus:shadow-[0_0_0_3px_rgba(0,0,0,0.03)]",
        )}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown
        size={16}
        className="absolute right-3.5 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none"
      />
    </div>
  );
}
