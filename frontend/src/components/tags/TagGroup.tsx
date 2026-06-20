import { TagInput } from "./TagInput";

interface TagGroupProps {
  label: string;
  tags: string[];
  onAdd: (tag: string) => void;
  onRemove: (tag: string) => void;
  placeholder?: string;
  helper?: string;
}

/**
 * A labelled TagInput wrapper: small muted label above + the tag input below.
 */
export function TagGroup({ label, tags, onAdd, onRemove, placeholder, helper }: TagGroupProps) {
  return (
    <div className="flex flex-col gap-1">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <TagInput
        tags={tags}
        onAdd={onAdd}
        onRemove={onRemove}
        placeholder={placeholder}
        helper={helper}
      />
    </div>
  );
}
