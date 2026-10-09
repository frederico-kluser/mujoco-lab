import { Accordion as AccordionPrimitive } from "@base-ui/react/accordion"
import { AnimatePresence, motion } from "motion/react"
import type { HTMLMotionProps, Variants } from "motion/react"
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import {
  useMotionUITheme,
  useMotionUITransition,
} from "@/components/motion-ui/ui-theme"

/** Toggle one value in the open set; under single-open, opening one closes the rest. */
export function nextOpenIds(
  current: string[],
  value: string,
  singleOpen: boolean
): string[] {
  const isOpen = current.includes(value)
  if (singleOpen) return isOpen ? [] : [value]
  return isOpen ? current.filter((x) => x !== value) : [...current, value]
}

/** Ensure `value` is open (deep-link reveal, never closes). */
export function revealOpenIds(
  current: string[],
  value: string,
  singleOpen: boolean
): string[] {
  if (singleOpen) return [value]
  return current.includes(value) ? current : [...current, value]
}

const FOCUS_RING =
  "outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"

/** Inset focus ring for overflow-hidden card containers that clip offset rings. */
const FOCUS_RING_INSET =
  "outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"

/* Hover lifts the indicator rather than tinting the label: the accent is kept
 * for focus and selection. */
const INDICATOR_HOVER =
  "transition-colors duration-[var(--motion-ui-transition-snap-duration)] ease-[var(--motion-ui-transition-snap)] group-hover:text-foreground"

interface AccordionRootContextValue {
  openValues: string[]
  register: (value: string) => () => void
}

const AccordionRootContext = createContext<AccordionRootContextValue | null>(
  null
)

interface AccordionItemContextValue {
  open: boolean
  value: string
}

const AccordionItemContext = createContext<AccordionItemContextValue | null>(
  null
)

function useAccordionRoot(who: string): AccordionRootContextValue {
  const ctx = useContext(AccordionRootContext)
  if (!ctx) throw new Error(`${who} must be rendered inside <Accordion>.`)
  return ctx
}

function useAccordionItemContext(who: string): AccordionItemContextValue {
  const ctx = useContext(AccordionItemContext)
  if (!ctx) throw new Error(`${who} must be rendered inside <AccordionItem>.`)
  return ctx
}

export interface UseAccordionHashOptions {
  /** Called with the matched fragment id on mount and on every `hashchange`. */
  onMatch: (id: string) => void
  /** Restrict matches to these ids. Omit to honour any fragment on the page. */
  ids?: readonly string[]
  /** Turn the listener off. Defaults to true. */
  enabled?: boolean
}

/** Deep-link hook: opens row matching URL hash on mount and hashchange. */
export function useAccordionHash({
  onMatch,
  ids,
  enabled = true,
}: UseAccordionHashOptions): void {
  const { motionMode } = useMotionUITheme()
  const reduce = motionMode !== "full"

  useEffect(() => {
    if (!enabled) return

    const openFromHash = () => {
      const hash = window.location.hash.replace(/^#/, "")
      if (!hash) return
      if (ids && !ids.includes(hash)) return
      const el = document.getElementById(hash)
      if (!el) return
      onMatch(hash)
      el.scrollIntoView({
        block: "nearest",
        behavior: reduce ? "auto" : "smooth",
      })
    }

    openFromHash()
    window.addEventListener("hashchange", openFromHash)
    return () => window.removeEventListener("hashchange", openFromHash)
  }, [enabled, ids, onMatch, reduce])
}

export interface AccordionProps {
  /** Whether multiple rows can be open at once. Defaults to false. */
  multiple?: boolean
  /** Values open on first render (uncontrolled). */
  defaultValue?: string[]
  /** Controlled open values. */
  value?: string[]
  /** Called with the next open values whenever a row is toggled. */
  onValueChange?: (value: string[]) => void
  /** Open and scroll to the row matching the URL fragment. Defaults to false. */
  deepLink?: boolean
  /** Merged onto the container element. */
  className?: string
  /** The `AccordionItem` rows. */
  children?: ReactNode
}

/** Accordion root: Base UI open state plus optional deep-linking. */
export function Accordion({
  multiple = false,
  defaultValue,
  value: controlledValue,
  onValueChange,
  deepLink = false,
  className,
  children,
}: AccordionProps) {
  const [uncontrolledValue, setUncontrolledValue] = useState<string[]>(
    () => defaultValue ?? []
  )
  const openValues = controlledValue ?? uncontrolledValue

  const registered = useRef<Set<string>>(new Set())
  const [ids, setIds] = useState<string[]>([])
  const register = useCallback((value: string) => {
    registered.current.add(value)
    setIds([...registered.current])
    return () => {
      registered.current.delete(value)
      setIds([...registered.current])
    }
  }, [])

  const setValues = useCallback(
    (next: string[]) => {
      setUncontrolledValue(next)
      onValueChange?.(next)
    },
    [onValueChange]
  )

  const reveal = useCallback(
    (id: string) => setValues(revealOpenIds(openValues, id, !multiple)),
    [setValues, openValues, multiple]
  )

  useAccordionHash({ enabled: deepLink, ids, onMatch: reveal })

  const rootContext = useMemo<AccordionRootContextValue>(
    () => ({ openValues, register }),
    [openValues, register]
  )

  return (
    <AccordionRootContext.Provider value={rootContext}>
      <AccordionPrimitive.Root
        multiple={multiple}
        value={openValues}
        onValueChange={(next) => setValues(next as string[])}
        className={className}
      >
        {children}
      </AccordionPrimitive.Root>
    </AccordionRootContext.Provider>
  )
}

export interface AccordionItemProps extends Omit<HTMLMotionProps<"div">, "id"> {
  /** Stable value for this row and its deep-link anchor id. */
  value: string
  /** Merged onto the row element. */
  className?: string
  /** The row's `AccordionTrigger` and `AccordionPanel`. */
  children?: ReactNode
}

/** One disclosure row keyed by `value`. */
export function AccordionItem({
  value,
  className,
  children,
  ...rest
}: AccordionItemProps) {
  const root = useAccordionRoot("AccordionItem")

  useEffect(() => root.register(value), [root, value])

  const itemContext = useMemo<AccordionItemContextValue>(
    () => ({ open: root.openValues.includes(value), value }),
    [root, value]
  )

  return (
    <AccordionItemContext.Provider value={itemContext}>
      <AccordionPrimitive.Item
        value={value}
        render={
          <motion.div id={value} className={className} {...rest}>
            {children}
          </motion.div>
        }
      />
    </AccordionItemContext.Provider>
  )
}

export interface AccordionTriggerProps {
  /** The trigger label. */
  children?: ReactNode
  /** Open/closed indicator after the label. Defaults to `<AccordionChevron />`. */
  indicator?: ReactNode
  /** Merged onto the `<button>`. */
  className?: string
  /** Heading level wrapping the button. Defaults to 3. */
  headingLevel?: 2 | 3 | 4 | 5 | 6
  /** Use inset focus ring inside overflow-hidden containers. Defaults to false. */
  inset?: boolean
}

/** Accessible trigger with indicator slot. */
export function AccordionTrigger({
  children,
  indicator,
  className,
  headingLevel = 3,
  inset = false,
}: AccordionTriggerProps) {
  const ring = inset ? FOCUS_RING_INSET : FOCUS_RING
  const Heading = `h${headingLevel}` as "h2" | "h3" | "h4" | "h5" | "h6"

  return (
    <AccordionPrimitive.Header
      className="m-0"
      render={headingLevel === 3 ? undefined : <Heading />}
    >
      <AccordionPrimitive.Trigger
        className={`group flex w-full items-center justify-between gap-4 text-left text-foreground ${ring}${className ? ` ${className}` : ""}`}
      >
        {children}
        {indicator ?? <AccordionChevron />}
      </AccordionPrimitive.Trigger>
    </AccordionPrimitive.Header>
  )
}

const PANEL_VARIANTS: Variants = {
  open: {
    height: "auto",
    maskImage: "linear-gradient(to bottom, black 100%, transparent 100%)",
  },
  closed: {
    height: 0,
    maskImage: "linear-gradient(to bottom, black 50%, transparent 100%)",
  },
}

const CONTENT_VARIANTS: Variants = {
  open: { opacity: 1, filter: "blur(0px)" },
  closed: { opacity: 0, filter: "blur(3px)" },
}

const CONTENT_VARIANTS_REDUCED: Variants = {
  open: { opacity: 1 },
  closed: { opacity: 0 },
}

export interface AccordionPanelProps {
  /** The disclosed content. */
  children?: ReactNode
  /** Merged onto the inner content wrapper. */
  className?: string
}

/** Height-morph collapsible panel with fold mask and inner blur-in. */
export function AccordionPanel({ children, className }: AccordionPanelProps) {
  const item = useAccordionItemContext("AccordionPanel")
  const { motionMode } = useMotionUITheme()
  const motionAllowed = motionMode === "full"
  const reduced = !motionAllowed
  const uiTransition = useMotionUITransition("ui")

  return (
    <AccordionPrimitive.Panel
      keepMounted
      className="overflow-hidden [contain:layout] [&[hidden]]:block"
    >
      <AnimatePresence initial={false}>
        {item.open && (
          <motion.div
            initial="closed"
            animate="open"
            exit="closed"
            transition={reduced ? { duration: 0 } : { ...uiTransition }}
            variants={PANEL_VARIANTS}
          >
            <motion.div
              className={className}
              variants={reduced ? CONTENT_VARIANTS_REDUCED : CONTENT_VARIANTS}
            >
              {children}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </AccordionPrimitive.Panel>
  )
}

export interface AccordionIndicatorProps {
  /** Force open/closed state. Omit to read from the enclosing row. */
  open?: boolean
  /** Merged onto the indicator. */
  className?: string
}

function useIndicatorOpen(open: boolean | undefined): boolean {
  const item = useContext(AccordionItemContext)
  return open ?? item?.open ?? false
}

/** Chevron indicator that rotates with row open state. */
export function AccordionChevron({ open, className }: AccordionIndicatorProps) {
  const isOpen = useIndicatorOpen(open)
  const { motionMode } = useMotionUITheme()
  const motionAllowed = motionMode === "full"
  const snap = useMotionUITransition("snap")

  return (
    <motion.svg
      className={`shrink-0 text-muted-foreground ${INDICATOR_HOVER}${className ? ` ${className}` : ""}`}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      animate={{ rotate: isOpen ? 180 : 0 }}
      transition={motionAllowed ? { ...snap } : { duration: 0 }}
    >
      <path d="m6 9 6 6 6-6" />
    </motion.svg>
  )
}

/** Plus/minus indicator that morphs with row open state. */
export function AccordionPlusMinus({
  open,
  className,
}: AccordionIndicatorProps) {
  const isOpen = useIndicatorOpen(open)
  const { motionMode } = useMotionUITheme()
  const motionAllowed = motionMode === "full"
  const snap = useMotionUITransition("snap")
  const transition = motionAllowed ? { ...snap } : { duration: 0 }

  return (
    <span
      className={`relative inline-block size-[18px] shrink-0 text-muted-foreground ${INDICATOR_HOVER}${className ? ` ${className}` : ""}`}
    >
      <motion.span
        aria-hidden="true"
        className="absolute inset-0 m-auto h-[2px] w-[13px] rounded-full bg-current"
        animate={{ rotate: isOpen ? 180 : 0 }}
        transition={transition}
      />
      <motion.span
        aria-hidden="true"
        className="absolute inset-0 m-auto h-[2px] w-[13px] rounded-full bg-current"
        animate={{ rotate: isOpen ? 0 : 90 }}
        transition={transition}
      />
    </span>
  )
}
