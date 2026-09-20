// Karta pracy agenta (ui-kit, rozdz. 12.1): plan kroków, krok bieżący, zegar,
// dziennik i zatrzymanie. Obrys Aurora i poświata wyłącznie w trakcie pracy.

import { useEffect, useId, useState, type ReactNode } from "react";
import { Badge } from "./Badge";
import { Button, IconButton } from "./Button";
import { ChevronDownIcon, CircleDashedIcon, ErrorIcon, InfoIcon, StopIcon, SuccessIcon, WarningIcon } from "./Icons";
import { Progress, Spinner } from "./Progress";
import { cx, type BaseProps } from "./types";

export type AgentStepState = "queued" | "running" | "done" | "error" | "skipped";

export interface AgentStepData {
  id: string;
  label: string;
  tool?: string;
  detail?: string;
  state: AgentStepState;
  progress?: number;
  durationMs?: number;
  error?: { message: string; actions?: { label: string; onSelect: () => void; primary?: boolean }[] };
  log?: { at: string; text: string }[];
}

export interface AgentRun {
  id: string;
  state: "queued" | "running" | "done" | "error" | "stopped" | "awaiting-input";
  queuePosition?: number;
  steps: AgentStepData[];
  /** Znacznik ISO początku pracy — źródło zegara. */
  startedAt?: string;
  durationMs?: number;
  question?: { text: string; options: { label: string; value: string }[] };
}

export interface AgentStatusProps extends BaseProps {
  run: AgentRun;
  expanded?: boolean;
  onExpandedChange?: (expanded: boolean) => void;
  onStop: () => void;
  onResume?: () => void;
  onCancel?: () => void;
  onRetryStep?: (stepId: string) => void;
  onSkipStep?: (stepId: string) => void;
  onAnswer?: (value: string) => void;
}

/** mm:ss z cyframi tabelarycznymi. */
export function czasZegara(ms: number): string {
  const sekundy = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(sekundy / 60)).padStart(2, "0")}:${String(sekundy % 60).padStart(2, "0")}`;
}

function useZegar(run: AgentRun): number {
  const [teraz, setTeraz] = useState(() => Date.now());
  useEffect(() => {
    if (run.state !== "running" || !run.startedAt) return;
    const odliczanie = setInterval(() => setTeraz(Date.now()), 1000);
    return () => clearInterval(odliczanie);
  }, [run.startedAt, run.state]);

  if (run.state === "running" && run.startedAt) return teraz - new Date(run.startedAt).getTime();
  return run.durationMs ?? 0;
}

const IKONA_KROKU: Record<AgentStepState, ReactNode> = {
  queued: <CircleDashedIcon size={20} className="text-subtle" />,
  running: <Spinner size="md" tone="ai" />,
  done: <SuccessIcon size={20} className="text-success" />,
  error: <ErrorIcon size={20} className="text-danger" />,
  skipped: <CircleDashedIcon size={20} className="text-subtle" />,
};

export function AgentStatus({
  run,
  expanded,
  onExpandedChange,
  onStop,
  onResume,
  onCancel,
  onRetryStep,
  onSkipStep,
  onAnswer,
  className,
  ...reszta
}: AgentStatusProps) {
  const id = useId();
  const domyslnieRozwiniete = run.state === "running" || run.state === "error" || run.state === "awaiting-input";
  const [wlasne, setWlasne] = useState(domyslnieRozwiniete);
  const rozwiniete = expanded ?? wlasne;
  const ustawRozwiniete = (stan: boolean) => {
    setWlasne(stan);
    onExpandedChange?.(stan);
  };

  const uplyw = useZegar(run);
  const pracuje = run.state === "running";
  const biezacy = run.steps.find((krok) => krok.state === "running");
  const numer = biezacy ? run.steps.indexOf(biezacy) + 1 : run.steps.filter((krok) => krok.state === "done").length;

  const naglowek =
    run.state === "queued"
      ? `W kolejce${run.queuePosition ? ` · przed tym zadaniem ${run.queuePosition} inne` : ""}`
      : run.state === "running"
        ? `${biezacy?.label ?? "Pracuję…"}  krok ${numer} z ${run.steps.length}`
        : run.state === "done"
          ? `Zakończono ${run.steps.length} kroków`
          : run.state === "error"
            ? "Krok nie powiódł się"
            : run.state === "stopped"
              ? `Zatrzymano na kroku ${numer} z ${run.steps.length} · wykonane kroki zachowano`
              : (run.question?.text ?? "Czekam na decyzję");

  const ikonaStanu =
    run.state === "done" ? (
      <SuccessIcon size={20} className="text-success" />
    ) : run.state === "error" ? (
      <ErrorIcon size={20} className="text-danger" />
    ) : run.state === "stopped" ? (
      <WarningIcon size={20} className="text-warning" />
    ) : run.state === "awaiting-input" ? (
      <InfoIcon size={20} className="text-info" />
    ) : pracuje ? (
      <span className="ui-oddech aurora-tlo block rounded-full" style={{ inlineSize: "var(--space-2)", blockSize: "var(--space-2)" }} />
    ) : (
      <span className="block rounded-full bg-subtle" style={{ inlineSize: "var(--space-2)", blockSize: "var(--space-2)" }} />
    );

  return (
    <section
      role={run.state === "error" ? "alert" : "status"}
      aria-live={run.state === "error" ? "assertive" : "polite"}
      className={cx(
        "rounded-lg border bg-raised",
        pracuje ? "aurora-obrys glow-ai border-transparent" : run.state === "error" ? "border-danger" : run.state === "awaiting-input" ? "border-info" : "border-line",
        className,
      )}
      {...reszta}
    >
      <div className="flex items-center" style={{ padding: "var(--space-3) var(--space-4)", gap: "var(--space-3)" }}>
        <span className="grid shrink-0 place-items-center" style={{ inlineSize: "var(--icon-size-md)" }}>
          {ikonaStanu}
        </span>
        <p className="min-w-0 flex-1 truncate text-fg" style={{ font: "var(--text-style-label)" }}>
          {naglowek}
        </p>
        <span className="text-muted" style={{ font: "var(--text-style-caption)", fontVariantNumeric: "var(--font-numeric-tabular)" }}>
          {czasZegara(uplyw)}
        </span>
        {pracuje ? (
          <Button variant="secondary" size="xs" iconStart={<StopIcon size={14} />} onClick={onStop} shortcut={["Esc"]}>
            Zatrzymaj
          </Button>
        ) : null}
        {run.state === "queued" && onCancel ? (
          <Button variant="ghost" size="xs" onClick={onCancel}>
            Anuluj
          </Button>
        ) : null}
        {run.state === "stopped" && onResume ? (
          <Button variant="secondary" size="xs" onClick={onResume}>
            Wznów
          </Button>
        ) : null}
        <IconButton
          icon={<ChevronDownIcon className={rozwiniete ? "rotate-180" : undefined} />}
          label={rozwiniete ? "Zwiń kroki" : "Rozwiń kroki"}
          size="xs"
          onClick={() => ustawRozwiniete(!rozwiniete)}
          aria-expanded={rozwiniete}
          aria-controls={`${id}-kroki`}
        />
      </div>

      {run.state === "awaiting-input" && run.question ? (
        <div className="flex flex-wrap items-center border-t border-line" style={{ padding: "var(--space-3) var(--space-4)", gap: "var(--space-2)" }}>
          {run.question.options.map((opcja, index) => (
            <Button key={opcja.value} variant={index === 0 ? "primary" : "secondary"} size="sm" onClick={() => onAnswer?.(opcja.value)}>
              {opcja.label}
            </Button>
          ))}
        </div>
      ) : null}

      {rozwiniete ? (
        <ol id={`${id}-kroki`} className="border-t border-line" style={{ padding: "var(--space-3) var(--space-4)", display: "grid", gap: "var(--space-3)" }}>
          {run.steps.map((krok) => (
            <li key={krok.id} className="flex" style={{ gap: "var(--space-3)" }}>
              <span className="grid shrink-0 place-items-start" style={{ inlineSize: "var(--icon-size-md)" }}>
                {IKONA_KROKU[krok.state]}
              </span>
              <div className="flex min-w-0 flex-1 flex-col" style={{ gap: "var(--space-1)" }}>
                <div className="flex items-baseline" style={{ gap: "var(--space-2)" }}>
                  <span
                    className={cx(
                      "min-w-0 flex-1 truncate",
                      krok.state === "running" ? "font-medium text-fg" : krok.state === "error" ? "text-fg" : "text-muted",
                      krok.state === "skipped" && "line-through",
                    )}
                    style={{ font: "var(--text-style-body)" }}
                  >
                    {krok.label}
                  </span>
                  {krok.tool ? <Badge tone="ai">{krok.tool}</Badge> : null}
                  {typeof krok.durationMs === "number" ? (
                    <span className="text-subtle" style={{ font: "var(--text-style-caption)", fontVariantNumeric: "var(--font-numeric-tabular)" }}>
                      {(krok.durationMs / 1000).toFixed(1)} s
                    </span>
                  ) : null}
                </div>
                {krok.detail ? (
                  <span className="truncate text-muted" style={{ font: "var(--text-style-caption)" }}>
                    {krok.detail}
                  </span>
                ) : null}
                {krok.state === "queued" ? (
                  <span className="text-subtle" style={{ font: "var(--text-style-caption)" }}>
                    w kolejce
                  </span>
                ) : null}
                {krok.state === "running" && typeof krok.progress === "number" ? (
                  <Progress value={krok.progress} tone="ai" valueText={krok.detail} />
                ) : null}
                {krok.error ? (
                  <div className="flex flex-col" style={{ gap: "var(--space-2)" }}>
                    <span className="text-danger" style={{ font: "var(--text-style-caption)" }}>
                      {krok.error.message}
                    </span>
                    <div className="flex flex-wrap" style={{ gap: "var(--space-2)" }}>
                      {krok.error.actions?.map((dzialanie) => (
                        <Button key={dzialanie.label} variant={dzialanie.primary ? "secondary" : "ghost"} size="xs" onClick={dzialanie.onSelect}>
                          {dzialanie.label}
                        </Button>
                      ))}
                      {onRetryStep ? (
                        <Button variant="secondary" size="xs" onClick={() => onRetryStep(krok.id)}>
                          Ponów krok
                        </Button>
                      ) : null}
                      {onSkipStep ? (
                        <Button variant="ghost" size="xs" onClick={() => onSkipStep(krok.id)}>
                          Pomiń krok
                        </Button>
                      ) : null}
                    </div>
                  </div>
                ) : null}
                {(krok.log?.length ?? 0) > 0 && (krok.state === "running" || krok.state === "error") ? (
                  <pre
                    className="overflow-x-auto rounded-md border border-line bg-code text-muted"
                    style={{ padding: "var(--space-2)", font: "var(--text-style-code)", fontSize: "var(--font-size-xs)" }}
                  >
                    {(krok.log ?? []).map((wpis) => `${wpis.at}  ${wpis.text}`).join("\n")}
                  </pre>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
