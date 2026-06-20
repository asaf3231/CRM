import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  Users,
  Pencil,
  Copy,
  Trash2,
  SlidersHorizontal,
  FileText,
  Sparkles,
  ChevronDown,
} from "lucide-react";
import { api } from "@/lib/api";
import { useGtmStore } from "@/store/useGtmStore";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { TagChip } from "@/components/tags/TagChip";
import { TagInput } from "@/components/tags/TagInput";
import { TagGroup } from "@/components/tags/TagGroup";

/* ─── Local types ─────────────────────────────────────────────── */
type SourceMode = "Companies" | "Leads";
type CriterionCategory = "Demographic" | "Behavioral" | "Firmographic" | "Technographic";
type CriterionType = "Requirement" | "Disqualifier" | "Bonus";
type CriterionWeight = "High" | "Medium" | "Low";

interface CriterionRow {
  criterion: string;
  category: CriterionCategory;
  type: CriterionType;
  weight: CriterionWeight;
}

function importanceToWeight(imp: "High" | "Medium" | "Low"): CriterionWeight {
  return imp; // same enum values
}

/* ─── Left configuration panel ───────────────────────────────── */
interface ConfigPanelProps {
  source: SourceMode;
  onSourceChange: (s: SourceMode) => void;
  description: string;
  onDescriptionChange: (v: string) => void;
  preferredSegments: string[];
  onAddSegment: (t: string) => void;
  onRemoveSegment: (t: string) => void;
  preferredCerts: string[];
  onAddCert: (t: string) => void;
  onRemoveCert: (t: string) => void;
}

function ConfigPanel({
  source,
  onSourceChange,
  description,
  onDescriptionChange,
  preferredSegments,
  onAddSegment,
  onRemoveSegment,
  preferredCerts,
  onAddCert,
  onRemoveCert,
}: ConfigPanelProps) {
  const charMax = 600;

  return (
    <aside className="flex w-[300px] shrink-0 flex-col gap-5 overflow-auto border-r border-border bg-card/40 p-4">
      <h2 className="text-sm font-semibold">Configuration</h2>

      {/* Source toggle */}
      <div className="flex flex-col gap-1.5">
        <SectionLabel>Source</SectionLabel>
        <div className="inline-flex rounded-md border border-border bg-muted p-0.5">
          <SourceBtn
            icon={<Building2 className="h-3.5 w-3.5" />}
            label="Companies"
            active={source === "Companies"}
            onClick={() => onSourceChange("Companies")}
          />
          <SourceBtn
            icon={<Users className="h-3.5 w-3.5" />}
            label="Leads"
            active={source === "Leads"}
            onClick={() => onSourceChange("Leads")}
          />
        </div>
      </div>

      {/* Select Companies */}
      <div className="flex flex-col gap-1.5">
        <SectionLabel>Select Companies (Optional)</SectionLabel>
        <Select disabled className="opacity-60">
          <option value="">Select companies…</option>
        </Select>
        <p className="text-[11px] text-muted-foreground">0/10 companies selected</p>
      </div>

      {/* Description */}
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <SectionLabel>Description</SectionLabel>
          <span className="text-[11px] text-muted-foreground">
            {description.length}/{charMax}
          </span>
        </div>
        <Textarea
          value={description}
          maxLength={charMax}
          onChange={(e) => onDescriptionChange(e.target.value)}
          placeholder="Full service digital marketing company"
        />
        <p className="text-[11px] leading-snug text-muted-foreground">
          Be specific about capabilities, industry verticals, and service types you're looking for
        </p>
      </div>

      {/* Qualification criteria */}
      <SectionLabel>Qualification Criteria</SectionLabel>

      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-2 gap-2">
          <div className="flex flex-col gap-1">
            <FieldLabel>Geography</FieldLabel>
            <Select defaultValue="nationwide">
              <option value="nationwide">Nationwide</option>
              <option value="regional">Regional</option>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <FieldLabel>State match type</FieldLabel>
            <Select defaultValue="any">
              <option value="any">Any office</option>
              <option value="hq">HQ only</option>
            </Select>
          </div>
        </div>

        <label className="flex cursor-pointer items-center gap-2">
          <Checkbox defaultChecked />
          <span className="text-sm">Require US office</span>
        </label>

        <div className="grid grid-cols-2 gap-2">
          <div className="flex flex-col gap-1">
            <FieldLabel>Government experience</FieldLabel>
            <Select defaultValue="any">
              <option value="any">Any</option>
              <option value="required">Required</option>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <FieldLabel>Offering type</FieldLabel>
            <Select defaultValue="any">
              <option value="any">Any</option>
              <option value="services">Services</option>
              <option value="products">Products</option>
            </Select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="flex flex-col gap-1">
            <FieldLabel>Min team size</FieldLabel>
            <Input type="number" defaultValue={30} min={0} className="h-9" />
          </div>
          <div className="flex flex-col gap-1">
            <FieldLabel>Max team size</FieldLabel>
            <Input type="text" placeholder="No max" className="h-9" />
          </div>
        </div>
      </div>

      {/* Preferred customer segments */}
      <div className="flex flex-col gap-1.5">
        <FieldLabel>Preferred customer segments</FieldLabel>
        <TagInput
          tags={preferredSegments}
          onAdd={onAddSegment}
          onRemove={onRemoveSegment}
          placeholder="e.g. Enterprise, Mid-market, Public sector"
        />
        <p className="text-[11px] text-muted-foreground">Press Enter or comma to add</p>
      </div>

      {/* Preferred certifications */}
      <div className="flex flex-col gap-1.5">
        <FieldLabel>Preferred certifications</FieldLabel>
        <TagInput
          tags={preferredCerts}
          onAdd={onAddCert}
          onRemove={onRemoveCert}
          placeholder="e.g. SOC 2, ISO 27001, FedRAMP"
        />
        <p className="text-[11px] text-muted-foreground">Press Enter or comma to add</p>
      </div>
    </aside>
  );
}

/* ─── Center main panel ───────────────────────────────────────── */
interface CenterPanelProps {
  title: string;
  onTitleChange: (v: string) => void;
  // Keywords backed by Zustand
  keywords: string[];
  onAddKeyword: (t: string) => void;
  onRemoveKeyword: (t: string) => void;
  // Local state groups
  industryVerticals: string[];
  onAddVertical: (t: string) => void;
  onRemoveVertical: (t: string) => void;
  geographicFocus: string[];
  onAddGeo: (t: string) => void;
  onRemoveGeo: (t: string) => void;
  criteria: CriterionRow[];
  onCriterionChange: (idx: number, field: keyof CriterionRow, value: string) => void;
}

function CenterPanel({
  title,
  onTitleChange,
  keywords,
  onAddKeyword,
  onRemoveKeyword,
  industryVerticals,
  onAddVertical,
  onRemoveVertical,
  geographicFocus,
  onAddGeo,
  onRemoveGeo,
  criteria,
  onCriterionChange,
}: CenterPanelProps) {
  const [editingTitle, setEditingTitle] = useState(false);

  return (
    <div className="flex min-w-0 flex-1 flex-col overflow-auto p-5">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-5">
        {/* Header row */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-1 items-center gap-2">
            {editingTitle ? (
              <input
                autoFocus
                value={title}
                onChange={(e) => onTitleChange(e.target.value)}
                onBlur={() => setEditingTitle(false)}
                onKeyDown={(e) => e.key === "Enter" && setEditingTitle(false)}
                className="flex-1 rounded border border-ring bg-transparent px-1 text-lg font-bold outline-none"
              />
            ) : (
              <h1 className="text-lg font-bold">{title}</h1>
            )}
            <button
              type="button"
              onClick={() => setEditingTitle(true)}
              className="rounded p-1 text-muted-foreground hover:text-foreground"
              aria-label="Edit title"
            >
              <Pencil className="h-4 w-4" />
            </button>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button variant="outline" size="sm">
              <Copy className="h-4 w-4" /> Copy
            </Button>
            <Button variant="destructive" size="sm">
              <Trash2 className="h-4 w-4" /> Delete
            </Button>
          </div>
        </div>

        {/* Short description placeholder */}
        <div className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm text-muted-foreground">
          <span>No short description</span>
          <button
            type="button"
            className="rounded p-1 text-muted-foreground hover:text-foreground"
            aria-label="Edit description"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="editor">
          <TabsList>
            <TabsTrigger value="editor" className="gap-1.5">
              <SlidersHorizontal className="h-3.5 w-3.5" /> Editor
            </TabsTrigger>
            <TabsTrigger value="markdown" className="gap-1.5">
              <FileText className="h-3.5 w-3.5" /> Markdown
            </TabsTrigger>
            <TabsTrigger value="examples" className="gap-1.5">
              <Sparkles className="h-3.5 w-3.5" /> Examples
            </TabsTrigger>
          </TabsList>

          <TabsContent value="editor" className="mt-4">
            <div className="flex flex-col gap-5">
              {/* Search Criteria section */}
              <div>
                <button
                  type="button"
                  className="mb-3 flex w-full items-center justify-between text-sm font-semibold"
                >
                  Search Criteria
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                </button>

                <div className="flex flex-col gap-4">
                  <TagGroup
                    label="Keywords"
                    tags={keywords}
                    onAdd={onAddKeyword}
                    onRemove={onRemoveKeyword}
                    placeholder="e.g., IT modernization, cloud migration"
                    helper="Press Enter or comma to add"
                  />
                  <TagGroup
                    label="Industry Verticals"
                    tags={industryVerticals}
                    onAdd={onAddVertical}
                    onRemove={onRemoveVertical}
                    placeholder="e.g. Healthcare, Defense, Financial Services"
                    helper="Press Enter or comma to add"
                  />
                  <TagGroup
                    label="Geographic Focus"
                    tags={geographicFocus}
                    onAdd={onAddGeo}
                    onRemove={onRemoveGeo}
                    placeholder="e.g. Washington DC, Texas, California"
                    helper="Press Enter or comma to add"
                  />
                </div>
              </div>

              {/* Company Size Range */}
              <div className="flex flex-col gap-3">
                <div className="text-sm font-semibold">Company Size Range</div>
                <div className="flex items-center gap-3">
                  <div className="flex flex-col gap-1">
                    <FieldLabel>Min Employees</FieldLabel>
                    <Input type="number" defaultValue={30} className="w-28" />
                  </div>
                  <div className="flex flex-col gap-1">
                    <FieldLabel>Max Employees</FieldLabel>
                    <Input type="number" placeholder="No max" className="w-28" />
                  </div>
                  <label className="ml-2 flex cursor-pointer items-center gap-2 self-end pb-1">
                    <Checkbox defaultChecked />
                    <span className="text-sm">No size constraint</span>
                  </label>
                </div>
              </div>

              {/* Qualification Criteria */}
              <div className="flex flex-col gap-3">
                <div className="text-sm font-semibold">Qualification Criteria</div>
                <p className="text-[11px] leading-snug text-muted-foreground">
                  Define requirements a lead must meet and flags that disqualify them.
                </p>

                <div className="flex flex-col gap-2">
                  {criteria.map((row, i) => (
                    <CriterionRow
                      key={i}
                      row={row}
                      onChange={(field, val) => onCriterionChange(i, field, val)}
                    />
                  ))}
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="markdown" className="mt-4">
            <div className="rounded-md border border-border bg-muted/40 px-4 py-8 text-center text-sm text-muted-foreground">
              Markdown view coming soon
            </div>
          </TabsContent>

          <TabsContent value="examples" className="mt-4">
            <div className="rounded-md border border-border bg-muted/40 px-4 py-8 text-center text-sm text-muted-foreground">
              Example companies coming soon
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

function CriterionRow({
  row,
  onChange,
}: {
  row: CriterionRow;
  onChange: (field: keyof CriterionRow, val: string) => void;
}) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-border bg-card p-2">
      <span className="flex-1 text-sm">{row.criterion}</span>
      <Select
        value={row.category}
        onChange={(e) => onChange("category", e.target.value)}
        className="h-7 w-32 py-0 text-xs"
      >
        <option value="Demographic">Demographic</option>
        <option value="Behavioral">Behavioral</option>
        <option value="Firmographic">Firmographic</option>
        <option value="Technographic">Technographic</option>
      </Select>
      <Select
        value={row.type}
        onChange={(e) => onChange("type", e.target.value)}
        className="h-7 w-28 py-0 text-xs"
      >
        <option value="Requirement">Requirement</option>
        <option value="Disqualifier">Disqualifier</option>
        <option value="Bonus">Bonus</option>
      </Select>
      <Select
        value={row.weight}
        onChange={(e) => onChange("weight", e.target.value)}
        className="h-7 w-20 py-0 text-xs"
      >
        <option value="High">High</option>
        <option value="Medium">Medium</option>
        <option value="Low">Low</option>
      </Select>
    </div>
  );
}

/* ─── Right AI Suggestions rail ──────────────────────────────── */
interface SuggestionsRailProps {
  onAccept: (tag: string) => void;
}

function SuggestionsRail({ onAccept }: SuggestionsRailProps) {
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[] | null>(null);

  async function handleGetSuggestions() {
    setLoading(true);
    try {
      const result = await api.getIcpSuggestions();
      setSuggestions(result);
    } finally {
      setLoading(false);
    }
  }

  function handleAccept(tag: string) {
    onAccept(tag);
    setSuggestions((prev) => prev?.filter((s) => s !== tag) ?? null);
  }

  return (
    <aside className="flex w-[260px] shrink-0 flex-col gap-3 overflow-auto border-l border-border bg-card/40 p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">AI Suggestions</span>
        <Button
          variant="outline"
          size="sm"
          onClick={handleGetSuggestions}
          disabled={loading}
          className="h-7 gap-1 px-2 text-xs"
        >
          <Sparkles className="h-3.5 w-3.5" />
          {loading ? "Generating…" : "Get Suggestions"}
        </Button>
      </div>

      {loading && (
        <p className="text-center text-xs text-muted-foreground">Generating…</p>
      )}

      {!loading && suggestions === null && (
        <p className="mt-4 text-center text-xs text-muted-foreground">
          Click to get AI-powered suggestions
        </p>
      )}

      {!loading && suggestions !== null && suggestions.length === 0 && (
        <p className="mt-4 text-center text-xs text-muted-foreground">
          All suggestions accepted
        </p>
      )}

      {!loading && suggestions !== null && suggestions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <TagChip key={s} label={s} action="add" onAction={() => handleAccept(s)} />
          ))}
        </div>
      )}
    </aside>
  );
}

/* ─── Small helpers ───────────────────────────────────────────── */
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
      {children}
    </div>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <div className="text-xs text-muted-foreground">{children}</div>;
}

function SourceBtn({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex flex-1 items-center justify-center gap-1.5 rounded px-3 py-1.5 text-sm font-medium transition-colors",
        active
          ? "bg-card text-foreground shadow-sm"
          : "text-muted-foreground hover:text-foreground"
      )}
    >
      {icon}
      {label}
    </button>
  );
}

/* ─── Root page ───────────────────────────────────────────────── */
export function IcpBuilder() {
  const { tagVocabulary, addTag, removeTag, setTagVocabulary } = useGtmStore();

  const icpQuery = useQuery({ queryKey: ["icpDocument"], queryFn: api.getIcpDocument });

  // Seed the store once the ICP document loads
  useEffect(() => {
    if (icpQuery.data) {
      setTagVocabulary(icpQuery.data.keywords);
    }
  }, [icpQuery.data, setTagVocabulary]);

  // Local state (not cross-screen)
  const [source, setSource] = useState<SourceMode>("Companies");
  const [description, setDescription] = useState(
    icpQuery.data?.description ?? "Full service digital marketing company"
  );
  const [title, setTitle] = useState(
    icpQuery.data?.title ?? "Compliant B2G Digital Agency"
  );
  const [industryVerticals, setIndustryVerticals] = useState<string[]>([]);
  const [geographicFocus, setGeographicFocus] = useState<string[]>([]);
  const [preferredSegments, setPreferredSegments] = useState<string[]>([]);
  const [preferredCerts, setPreferredCerts] = useState<string[]>([]);
  const [criteria, setCriteria] = useState<CriterionRow[]>([]);

  // Once doc loads, seed local state
  useEffect(() => {
    if (icpQuery.data) {
      setTitle(icpQuery.data.title);
      setDescription(icpQuery.data.description);
      setIndustryVerticals(icpQuery.data.industryVerticals);
      setGeographicFocus(icpQuery.data.geographicFocus);
      setCriteria(
        icpQuery.data.qualificationCriteria.map((c) => ({
          criterion: c.criterion,
          category: "Demographic" as CriterionCategory,
          type: "Requirement" as CriterionType,
          weight: importanceToWeight(c.importance),
        }))
      );
    }
  }, [icpQuery.data]);

  function handleCriterionChange(idx: number, field: keyof CriterionRow, value: string) {
    setCriteria((prev) =>
      prev.map((r, i) => (i === idx ? { ...r, [field]: value } : r))
    );
  }

  if (icpQuery.isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Loading ICP…
      </div>
    );
  }

  if (icpQuery.isError) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="rounded-lg border border-border bg-card px-6 py-8 text-center">
          <p className="text-sm text-muted-foreground">
            Couldn't load ICP document —{" "}
            <button
              onClick={() => icpQuery.refetch()}
              className="text-info underline-offset-2 hover:underline"
            >
              retry
            </button>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0">
      <ConfigPanel
        source={source}
        onSourceChange={setSource}
        description={description}
        onDescriptionChange={setDescription}
        preferredSegments={preferredSegments}
        onAddSegment={(t) => setPreferredSegments((p) => [...p, t])}
        onRemoveSegment={(t) => setPreferredSegments((p) => p.filter((x) => x !== t))}
        preferredCerts={preferredCerts}
        onAddCert={(t) => setPreferredCerts((p) => [...p, t])}
        onRemoveCert={(t) => setPreferredCerts((p) => p.filter((x) => x !== t))}
      />

      <CenterPanel
        title={title}
        onTitleChange={setTitle}
        keywords={tagVocabulary}
        onAddKeyword={addTag}
        onRemoveKeyword={removeTag}
        industryVerticals={industryVerticals}
        onAddVertical={(t) => setIndustryVerticals((p) => [...p, t])}
        onRemoveVertical={(t) => setIndustryVerticals((p) => p.filter((x) => x !== t))}
        geographicFocus={geographicFocus}
        onAddGeo={(t) => setGeographicFocus((p) => [...p, t])}
        onRemoveGeo={(t) => setGeographicFocus((p) => p.filter((x) => x !== t))}
        criteria={criteria}
        onCriterionChange={handleCriterionChange}
      />

      <SuggestionsRail onAccept={addTag} />
    </div>
  );
}
