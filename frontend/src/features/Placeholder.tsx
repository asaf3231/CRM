import { NAV_LAYERS } from "@/components/shell/nav";

export function Placeholder({ path, stage }: { path: string; stage: string }) {
  const layer = NAV_LAYERS.find((l) => l.path === path)!;
  const Icon = layer.icon;
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-muted text-muted-foreground">
        <Icon className="h-6 w-6" />
      </div>
      <div>
        <h1 className="text-lg font-semibold">{layer.label}</h1>
        <p className="text-sm text-muted-foreground">
          Layer {layer.index} · {layer.caption}
        </p>
      </div>
      <p className="rounded-full bg-secondary px-3 py-1 text-xs text-secondary-foreground">
        Planned for {stage}
      </p>
    </div>
  );
}
