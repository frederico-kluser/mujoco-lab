"use client"

import { Toggle as TogglePrimitive } from "@base-ui/react/toggle"
import { ToggleGroup as ToggleGroupPrimitive } from "@base-ui/react/toggle-group"
import { motion } from "motion/react"
import {
  createContext,
  useContext,
  useId,
  useMemo,
  type ReactNode,
} from "react"
import { useMotionUITheme, useMotionUITransition } from "@/components/motion-ui/ui-theme"
import type { UITransition } from "@/components/motion-ui/ui-theme"

const FOCUS_RING =
  "outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"

interface SegmentedToggleContextValue {
  /** Currently selected value. */
  value: string
  /** Shared `layoutId` for the sliding pill. */
  layoutId: string
  /** Theme transition for the pill slide (`snap`). */
  indicatorTransition: UITransition
  /** Whether the pill should slide (false under reduced motion). */
  animateIndicator: boolean
}

const SegmentedToggleContext =
  createContext<SegmentedToggleContextValue | null>(null)

function useSegmentedToggleContext(who: string): SegmentedToggleContextValue {
  const ctx = useContext(SegmentedToggleContext)
  if (!ctx) throw new Error(`${who} must be rendered inside <SegmentedToggle>.`)
  return ctx
}

export interface SegmentedToggleProps<T extends string = string> {
  /** Currently selected option value (controlled). */
  value: T
  /** Called when a new option is selected. */
  onChange: (value: T) => void
  /** Accessible name for the `role="group"` container. */
  ariaLabel?: string
  /** Override the shared pill's `layoutId`. */
  layoutId?: string
  /** Merged onto the segmented shell. */
  className?: string
  /** `SegmentedToggleOption` children. */
  children?: ReactNode
}

/** Segmented toggle root with a shared sliding pill. */
export function SegmentedToggle<T extends string = string>({
  value,
  onChange,
  ariaLabel,
  layoutId,
  className,
  children,
}: SegmentedToggleProps<T>) {
  const generatedId = useId()
  const snap = useMotionUITransition("snap")
  const { motionMode } = useMotionUITheme()
  const motionAllowed = motionMode === "full"

  const ctx = useMemo<SegmentedToggleContextValue>(
    () => ({
      value,
      layoutId: layoutId ?? `segmented-toggle-${generatedId}`,
      indicatorTransition: snap,
      animateIndicator: motionAllowed,
    }),
    [value, layoutId, generatedId, snap, motionAllowed]
  )

  return (
    <SegmentedToggleContext.Provider value={ctx}>
      <ToggleGroupPrimitive
        value={[value]}
        onValueChange={(next: string[]) => {
          // Ignore deselect: pressing the active option keeps it pressed.
          if (next[0] && next[0] !== value) onChange(next[0] as T)
        }}
        aria-label={ariaLabel}
        className={`relative inline-flex items-center gap-1 rounded-full border border-border/70 bg-card p-1 shadow-sm${className ? ` ${className}` : ""}`}
      >
        {children}
      </ToggleGroupPrimitive>
    </SegmentedToggleContext.Provider>
  )
}

export interface SegmentedToggleOptionProps {
  /** This option's value. */
  value: string
  /** Option label and extra content. */
  children?: ReactNode
  /** Merged onto the option `<button>`. */
  className?: string
}

/** One option of a `SegmentedToggle`. */
export function SegmentedToggleOption({
  value,
  children,
  className,
}: SegmentedToggleOptionProps) {
  const ctx = useSegmentedToggleContext("SegmentedToggleOption")
  const selected = ctx.value === value

  return (
    <TogglePrimitive
      value={value}
      render={
        <motion.button
          whileTap={ctx.animateIndicator ? { scale: PRESS_SCALE } : undefined}
          transition={ctx.indicatorTransition}
        />
      }
      className={`relative z-10 flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium ${FOCUS_RING} ${
        selected
          ? "text-primary-foreground"
          : "text-muted-foreground hover:text-foreground"
      } transition-colors duration-[var(--motion-ui-transition-snap-duration)] ease-[var(--motion-ui-transition-snap)]${className ? ` ${className}` : ""}`}
    >
      <span className="relative z-10 flex items-center gap-2 leading-none">
        {children}
      </span>
      {selected && (
        <motion.span
          layoutId={ctx.layoutId}
          className="absolute inset-0 rounded-full bg-primary shadow-sm"
          initial={ctx.animateIndicator ? { scaleX: 1 } : false}
          animate={ctx.animateIndicator ? { scaleX: THUMB_STRETCH } : undefined}
          transition={
            ctx.animateIndicator
              ? {
                  ...ctx.indicatorTransition,
                  scaleX: { duration: STRETCH_DURATION, times: [0, 0.35, 1], ease: "easeOut" },
                }
              : { duration: 0 }
          }
          aria-hidden="true"
        />
      )}
    </TogglePrimitive>
  )
}

/* The only motion beyond a plain toggle group: the thumb stretches a little
 * as it arrives, and an option gives under the pointer. Both stay small
 * enough to read as feel, not decoration. */
const PRESS_SCALE = 0.96
const THUMB_STRETCH = [1, 1.08, 1]
const STRETCH_DURATION = 0.32
