import { Check, ChevronsUpDown } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface ComboboxOption {
  /** Stored value (e.g. ISO-2 code, currency code, dial code). */
  value: string;
  /** Visible label in the dropdown row. */
  label: React.ReactNode;
  /** Render in the trigger button when this option is selected (default = label). */
  triggerLabel?: React.ReactNode;
  /** Free-form text the search filters against. */
  searchTokens: string;
  /** Disabled rows. */
  disabled?: boolean;
}

export interface ComboboxProps {
  options: ComboboxOption[];
  value: string | undefined;
  onChange: (value: string) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyText?: string;
  ariaInvalid?: boolean;
  className?: string;
  /** Width of the popover content; defaults to the trigger width. */
  contentClassName?: string;
  id?: string;
  name?: string;
  disabled?: boolean;
}

export function Combobox({
  options,
  value,
  onChange,
  placeholder = "Select…",
  searchPlaceholder = "Search…",
  emptyText = "No matches.",
  ariaInvalid,
  className,
  contentClassName,
  id,
  disabled,
}: ComboboxProps) {
  const [open, setOpen] = React.useState(false);
  const [filter, setFilter] = React.useState("");

  const selected = React.useMemo(() => options.find((o) => o.value === value), [options, value]);

  // We pre-filter rather than relying on cmdk's built-in matcher so we
  // can match against a custom `searchTokens` string (e.g. the country
  // name + ISO-2 code + dial code together). cmdk's default scores by
  // label only, which would miss "+91" → "India".
  const filtered = React.useMemo(() => {
    if (!filter.trim()) return options;
    const needle = filter.trim().toLowerCase();
    return options.filter((o) => o.searchTokens.toLowerCase().includes(needle));
  }, [options, filter]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-invalid={ariaInvalid ? "true" : undefined}
          disabled={disabled}
          className={cn(
            "h-11 w-full justify-between font-normal text-foreground",
            !selected && "text-muted-foreground",
            className,
          )}
        >
          <span className="truncate">
            {selected ? (selected.triggerLabel ?? selected.label) : placeholder}
          </span>
          <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className={cn("w-[--radix-popover-trigger-width] p-0", contentClassName)}
      >
        <Command shouldFilter={false}>
          <CommandInput placeholder={searchPlaceholder} value={filter} onValueChange={setFilter} />
          <CommandList>
            <CommandEmpty>{emptyText}</CommandEmpty>
            <CommandGroup>
              {filtered.map((option) => (
                <CommandItem
                  key={option.value}
                  value={option.value}
                  disabled={option.disabled}
                  onSelect={(v) => {
                    onChange(v);
                    setOpen(false);
                    setFilter("");
                  }}
                >
                  <Check
                    className={cn(
                      "mr-2 size-4",
                      option.value === value ? "opacity-100" : "opacity-0",
                    )}
                  />
                  <span className="truncate">{option.label}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
