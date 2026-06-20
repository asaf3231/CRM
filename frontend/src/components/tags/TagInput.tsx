import { useRef, useState, KeyboardEvent } from "react";
import { TagChip } from "./TagChip";
import { cn } from "@/lib/utils";

interface TagInputProps {
  tags: string[];
  onAdd: (tag: string) => void;
  onRemove: (tag: string) => void;
  placeholder?: string;
  helper?: string;
  className?: string;
}

/**
 * Controlled tag input: renders chips (flex-wrap) followed by a borderless inline input.
 * Enter or comma adds; Backspace on empty removes last chip.
 */
export function TagInput({ tags, onAdd, onRemove, placeholder, helper, className }: TagInputProps) {
  const [inputVal, setInputVal] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  function commit(raw: string) {
    const trimmed = raw.trim().replace(/,$/, "").trim();
    if (trimmed && !tags.includes(trimmed)) {
      onAdd(trimmed);
    }
    setInputVal("");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      commit(inputVal);
    } else if (e.key === "Backspace" && inputVal === "" && tags.length > 0) {
      onRemove(tags[tags.length - 1]);
    }
  }

  function handleChange(val: string) {
    // Commit on comma
    if (val.endsWith(",")) {
      commit(val.slice(0, -1));
    } else {
      setInputVal(val);
    }
  }

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <div
        className="flex min-h-[2.5rem] w-full flex-wrap gap-1 rounded-md border border-input bg-card px-2 py-1.5 focus-within:ring-2 focus-within:ring-ring"
        onClick={() => inputRef.current?.focus()}
      >
        {tags.map((tag) => (
          <TagChip key={tag} label={tag} action="remove" onAction={() => onRemove(tag)} />
        ))}
        <input
          ref={inputRef}
          value={inputVal}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={tags.length === 0 ? placeholder : ""}
          className="min-w-[8rem] flex-1 border-none bg-transparent py-0.5 text-sm outline-none placeholder:text-muted-foreground"
        />
      </div>
      {helper && (
        <p className="text-[11px] text-muted-foreground">
          {helper} ({tags.length})
        </p>
      )}
    </div>
  );
}
