import * as React from 'react';


// ---------------------------------------------------------------------------
// cx
// ---------------------------------------------------------------------------

type CxArg = string | number | boolean | null | undefined;

export function cx(...args: CxArg[]): string {
  return args.filter(Boolean).join(' ');
}


// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type PolymorphicElementWithoutRef<E extends React.ElementType, P> =
  P & Omit<React.ComponentPropsWithoutRef<E>, keyof P> & { as?: E };

export type WithIconProps = React.SVGProps<SVGSVGElement> & {
  a11yLabel?: string;
  size?: 'small' | 'medium' | 'large';
};


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let _idCounter = 0;
export function useStableId(providedId?: string): string {
  const [id] = React.useState(() => providedId || `ld-id-${++_idCounter}`);
  return providedId || id;
}

export function invariant(condition: boolean, message: string): void {
  if (condition) return;
  const error = `LD: ${message}`;
  if (import.meta.env.MODE === 'production') {
    console.error(error);
  } else {
    throw new Error(error);
  }
}

export function getTarget(target?: string): { rel?: string; target?: string } {
  if (target === '') return {};
  if (target === '_blank') return { target, rel: 'noopener noreferrer' };
  return { target };
}

export function onAnchorKeyDown(anchorProps: {
  href?: string;
  onClick?: React.MouseEventHandler<HTMLAnchorElement>;
  onKeyDown?: React.KeyboardEventHandler<HTMLAnchorElement>;
}) {
  const { href, onClick, onKeyDown } = anchorProps;
  return (event: React.KeyboardEvent<HTMLAnchorElement>) => {
    onKeyDown?.(event);
    if (event.defaultPrevented || event.key !== ' ') return;
    onClick?.(event as unknown as React.MouseEvent<HTMLAnchorElement>);
    if (event.defaultPrevented || !href) return;
    location.assign(href);
  };
}

export type MergeRefsItem<T> = React.MutableRefObject<T> | React.ForwardedRef<T> | null;
export function mergeRefs<T extends HTMLElement>(...refs: Array<MergeRefsItem<T>>): React.RefCallback<T> {
  return (instance: T | null) =>
    refs.forEach((ref) => {
      if (typeof ref === 'function') ref(instance);
      else if (typeof ref === 'object' && ref) ref.current = instance;
    });
}

export function remToPxValue(remValue: string): number {
  const defaultFontSize =
    (typeof window !== 'undefined' &&
      parseFloat(window.getComputedStyle(document.documentElement).fontSize)) ||
    16;
  return parseFloat(remValue) * defaultFontSize;
}

export function debounce<T extends unknown[]>(
  fn: (...args: T) => void,
  timeout: number
) {
  let timerID: ReturnType<typeof setTimeout>;
  const cancel = () => { clearTimeout(timerID); };
  const debounced = (...args: T) => {
    clearTimeout(timerID);
    timerID = setTimeout(() => { fn(...args); }, timeout);
  };
  debounced.cancel = cancel;
  return debounced;
}

export function setStyleProperty(node: HTMLElement, property: string, value: string) {
  node.style.setProperty(property, value);
}

/* eslint-disable @typescript-eslint/no-explicit-any */
export function applyCommonProps<T>(props: T): T & { className?: string; style?: React.CSSProperties } {
  const result: any = {};
  for (const [key, value] of Object.entries(props as any)) {
    if (key === 'UNSAFE_className') result.className = value;
    else if (key === 'UNSAFE_style') result.style = value;
    else if (key !== 'className' && key !== 'style') result[key] = value;
  }
  return result;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

/** @deprecated Use applyCommonProps instead */
export const _applyCommonProps = applyCommonProps;

export type CalculatePositionFn = (dimensions: {
  referrerHeight: number;
  referrerWidth: number;
  targetHeight: number;
  targetWidth: number;
}) => { left: number; top: number };

export function getPositionStyle(opts: {
  calculatePosition: CalculatePositionFn;
  referrerRef: React.RefObject<HTMLElement>;
  targetRef: React.RefObject<HTMLElement>;
}) {
  const referrerDOMRect = opts.referrerRef.current?.getBoundingClientRect() || { height: 0, width: 0 };
  const targetDOMRect = opts.targetRef.current?.getBoundingClientRect() || { height: 0, width: 0 };
  const { left, top } = opts.calculatePosition({
    referrerHeight: referrerDOMRect.height,
    referrerWidth: referrerDOMRect.width,
    targetHeight: targetDOMRect.height,
    targetWidth: targetDOMRect.width,
  });
  return { transform: `translate3d(${left}px, ${top}px, 0)` };
}

// --- CommonProps type used by some LD components ---
export interface CommonProps {
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

// --- Portable overlay hooks ---

/* eslint-disable @typescript-eslint/no-explicit-any */

export function useLockBodyScroll(): [(el: HTMLElement | null) => void] {
  React.useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, []);
  return [() => {}];
}

export function usePointerOutside(
  ref: React.RefObject<HTMLElement | null> | React.RefObject<HTMLElement | null>[],
  callback: (...args: any[]) => void
): void {
  React.useEffect(() => {
    const handler = (event: MouseEvent) => {
      const refs = Array.isArray(ref) ? ref : [ref];
      const isOutside = refs.every(r => r.current && !r.current.contains(event.target as Node));
      if (isOutside) callback(event);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [ref, callback]);
}

export function useOnKeyDown(
  keys: string[],
  callback: (...args: any[]) => void
): void {
  React.useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (keys.includes(event.key)) callback(event);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [keys, callback]);
}

export function ariaHideOutside(
  _elements: HTMLElement[],
  _container: HTMLElement
): () => void {
  return () => {};
}

/* eslint-enable @typescript-eslint/no-explicit-any */

// CSSTransition is in ../common/CSSTransition.tsx — import from there directly

// ── DevTools event emitter ────────────────────────────────────────
// Lightweight emit that dispatches a CustomEvent for the DevToolsPanel.
// The full Store.tsx emit also calls internal subscribers; this is the
// portable subset that just broadcasts on the window so generated
// components can participate without importing helpers/Store.

const GENLD_EVENT = 'ld-kit-event';

export function emit(topic: string, payload?: unknown): void {
  window.dispatchEvent(
    new CustomEvent(GENLD_EVENT, {detail: {topic, payload}}),
  );
}


// ---------------------------------------------------------------------------
// useCSSTransition
// ---------------------------------------------------------------------------

type TransitionState =
  | 'unmounted'
  | 'exited'
  | 'entering'
  | 'entered'
  | 'exiting';

export interface UseCSSTransitionOptions {
  in: boolean;
  timeout: number | {enter: number; exit: number};
  classNames: {
    enter?: string;
    enterActive?: string;
    exit?: string;
    exitActive?: string;
  };
  nodeRef: React.RefObject<Element>;
  mountOnEnter?: boolean;
  unmountOnExit?: boolean;
  onEnter?: () => void;
  onEntering?: () => void;
  onEntered?: () => void;
  onExit?: () => void;
  onExiting?: () => void;
  onExited?: () => void;
}

const isDomEnvironment =
  typeof window !== 'undefined' &&
  typeof window.document !== 'undefined' &&
  typeof window.document.createElement !== 'undefined';

const useIsomorphicLayoutEffect = isDomEnvironment
  ? React.useLayoutEffect
  : React.useEffect;

export function useCSSTransition(options: UseCSSTransitionOptions): {
  shouldMount: boolean;
} {
  const {
    in: inProp,
    timeout,
    classNames,
    nodeRef,
    mountOnEnter = false,
    unmountOnExit = false,
  } = options;

  const enterTimeout = typeof timeout === 'number' ? timeout : timeout.enter;
  const exitTimeout = typeof timeout === 'number' ? timeout : timeout.exit;

  const callbacksRef = React.useRef(options);
  callbacksRef.current = options;

  const getInitialState = (): TransitionState => {
    if (inProp) return 'entered';
    if (mountOnEnter || unmountOnExit) return 'unmounted';
    return 'exited';
  };

  const [state, setState] = React.useState<TransitionState>(getInitialState);
  const prevInRef = React.useRef(inProp);
  const timerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = () => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const rafRef = React.useRef<number | null>(null);

  const clearRaf = () => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  };

  const pendingEnterRef = React.useRef(false);

  function performEnter() {
    const node = nodeRef.current;
    if (!node) return;

    callbacksRef.current.onEnter?.();

    if (classNames.enter) {
      node.classList.add(classNames.enter);
    }

    // Force reflow before activating enter transition class.
    (node as HTMLElement).scrollTop;

    setState('entering');
    callbacksRef.current.onEntering?.();

    if (classNames.enterActive) {
      node.classList.add(classNames.enterActive);
    }

    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      if (classNames.enter) node.classList.remove(classNames.enter);
      if (classNames.enterActive) node.classList.remove(classNames.enterActive);
      setState('entered');
      callbacksRef.current.onEntered?.();
    }, enterTimeout);
  }

  function performExit() {
    const node = nodeRef.current;
    if (!node) return;

    callbacksRef.current.onExit?.();

    if (classNames.exit) {
      node.classList.add(classNames.exit);
    }

    // Force reflow before activating exit transition class.
    (node as HTMLElement).scrollTop;

    setState('exiting');
    callbacksRef.current.onExiting?.();

    if (classNames.exitActive) {
      node.classList.add(classNames.exitActive);
    }

    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      if (classNames.exit) node.classList.remove(classNames.exit);
      if (classNames.exitActive) node.classList.remove(classNames.exitActive);
      setState('exited');
      callbacksRef.current.onExited?.();
      if (unmountOnExit) {
        setState('unmounted');
      }
    }, exitTimeout);
  }

  if (inProp && !prevInRef.current && state === 'unmounted') {
    pendingEnterRef.current = true;
    setState('exited');
  }

  useIsomorphicLayoutEffect(() => {
    const prevIn = prevInRef.current;
    prevInRef.current = inProp;

    if (inProp && !prevIn) {
      clearTimer();
      clearRaf();

      if (pendingEnterRef.current) {
        pendingEnterRef.current = false;
        const node = nodeRef.current;
        if (node && !node.isConnected) {
          rafRef.current = requestAnimationFrame(() => {
            rafRef.current = null;
            performEnter();
          });
          return;
        }
        performEnter();
        return;
      }

      if (state !== 'unmounted') {
        performEnter();
      }
    } else if (!inProp && prevIn) {
      clearTimer();
      clearRaf();
      performExit();
    }
  });

  useIsomorphicLayoutEffect(() => {
    return () => {
      clearTimer();
      clearRaf();
    };
  }, []);

  return {shouldMount: state !== 'unmounted'};
}


// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

type IconProps = {
  size?: 'small' | 'medium' | 'large';
  a11yLabel?: string;
  className?: string;
  style?: React.CSSProperties;
} & React.SVGProps<SVGSVGElement>;

const SIZES: Record<string, string> = {small: '1rem', medium: '1.5rem', large: '2rem'};
const ALIGNS: Record<string, string> = {small: '-0.175em', medium: '-0.25em', large: '-0.325em'};

function makeIcon(paths: React.ReactNode, displayName: string): React.FC<IconProps> {
  const Icon: React.FC<IconProps> = ({size = 'small', a11yLabel, className, style, ...rest}) => {
    const a11y = a11yLabel
      ? {'aria-label': a11yLabel, role: 'img' as const}
      : {'aria-hidden': true as const, role: 'presentation' as const};
    return (
      <svg
        className={className}
        fill="currentColor"
        height="1em"
        style={{fontSize: SIZES[size], verticalAlign: ALIGNS[size], ...style}}
        viewBox="0 0 16 16"
        width="1em"
        xmlns="http://www.w3.org/2000/svg"
        {...a11y}
        {...rest}
      >
        {paths}
      </svg>
    );
  };
  Icon.displayName = displayName;
  return Icon;
}

function makeIcon32(paths: React.ReactNode, displayName: string): React.FC<IconProps> {
  const Icon: React.FC<IconProps> = ({size = 'small', a11yLabel, className, style, ...rest}) => {
    const a11y = a11yLabel
      ? {'aria-label': a11yLabel, role: 'img' as const}
      : {'aria-hidden': true as const, role: 'presentation' as const};
    return (
      <svg
        className={className}
        fill="currentColor"
        height="1em"
        style={{fontSize: SIZES[size], verticalAlign: ALIGNS[size], ...style}}
        viewBox="0 0 32 32"
        width="1em"
        xmlns="http://www.w3.org/2000/svg"
        {...a11y}
        {...rest}
      >
        {paths}
      </svg>
    );
  };
  Icon.displayName = displayName;
  return Icon;
}

// SVG-only icons with no font equivalent

export const HourglassIcon = makeIcon32(
  <path fillRule="evenodd" d="M6 3.014C6 2.454 6.454 2 7.014 2h17.948a1.014 1.014 0 0 1 0 2.029h-.983v4.979L17.173 16l6.806 6.992v4.979h1.006a1.014 1.014 0 1 1 0 2.029H7.038a1.014 1.014 0 1 1 0-2.029h.96v-4.979L14.804 16 7.998 9.008V4.029h-.984C6.454 4.029 6 3.575 6 3.014ZM21.982 8V4.052H9.996V8h11.986Zm-10.193 2 4.2 4.315 4.2-4.315h-8.4Zm4.223 13.913 3.972 4.035h1.998v-4.105l-5.993-6.158-5.993 6.158v4.105h2.043l3.973-4.035Z" clipRule="evenodd" />,
  'HourglassIcon'
);

export const ShieldCheckIcon = makeIcon32(
  <>
    <path d="m23.848 12.341-10 10a1.198 1.198 0 0 1-1.696 0l-4-4 1.696-1.695L13 19.796l9.152-9.15 1.696 1.695Z" />
    <path fillRule="evenodd" d="M15.293 3.294a1.003 1.003 0 0 1 1.414 0l.006.006.035.033.152.143c.138.125.347.308.62.53a19.467 19.467 0 0 0 2.363 1.632c2.03 1.195 4.854 2.363 8.117 2.363a1 1 0 0 1 1 1c0 6.037-1.512 12.978-6.36 17.018a13.783 13.783 0 0 1-4.449 2.492c-.61.203-1.121.325-1.488.395a7.827 7.827 0 0 1-.562.086l-.037.003-.012.002h-.184l-.011-.002-.038-.003a7.827 7.827 0 0 1-.563-.086c-.366-.07-.878-.192-1.487-.395a13.784 13.784 0 0 1-4.45-2.492C6.095 23.299 3 18.247 3 9.001a1 1 0 0 1 1-1c3.263 0 6.086-1.168 8.117-2.363a19.467 19.467 0 0 0 2.363-1.633c.273-.22.482-.404.62-.529.068-.062.12-.111.152-.143l.035-.033.006-.006Zm.445 2.264a21.36 21.36 0 0 1-2.605 1.805c-2.016 1.186-4.823 2.39-8.121 2.601.205 8.12 2.995 12.323 5.629 14.518a11.789 11.789 0 0 0 3.8 2.133c.516.171.941.27 1.23.326.145.027.257.043.327.053h.004c.07-.01.182-.026.326-.053.29-.055.715-.155 1.23-.326a11.789 11.789 0 0 0 3.801-2.133c3.927-3.273 5.468-8.97 5.625-14.518-3.296-.212-6.102-1.416-8.117-2.601a21.384 21.384 0 0 1-2.605-1.805c-.095-.077-.18-.156-.262-.225-.082.07-.167.148-.262.225Z" clipRule="evenodd" />
  </>,
  'ShieldCheckIcon'
);

export const SparkIcon = makeIcon32(
  <path d="M10.887.645A2.2 2.2 0 0 1 14.643 2.2c0 .532-.534 6.187-.72 6.752a1.553 1.553 0 0 1-2.96 0c-.187-.565-.72-6.22-.72-6.752a2.2 2.2 0 0 1 .644-1.555ZM3.323 6.196a2.2 2.2 0 1 0-2.2 3.81c.46.266 5.624 2.632 6.207 2.753a1.552 1.552 0 0 0 1.48-2.562c-.396-.447-5.026-3.735-5.487-4.001Zm20.437 3.807c-.459.267-5.622 2.633-6.206 2.753a1.556 1.556 0 0 1-1.876-1.684c.035-.328.174-.636.396-.88.396-.444 5.026-3.733 5.487-3.999a2.2 2.2 0 0 1 2.2 3.81Zm-6.206 5.24c.583.121 5.746 2.487 6.207 2.754A2.202 2.202 0 0 1 24.567 21a2.2 2.2 0 0 1-3.004.805c-.461-.266-5.092-3.554-5.487-4a1.552 1.552 0 0 1 1.478-2.563Zm-5.111 2.722a1.561 1.561 0 0 0-1.48 1.081c-.186.565-.72 6.22-.72 6.752a2.2 2.2 0 1 0 4.4 0c0-.532-.533-6.187-.72-6.752a1.56 1.56 0 0 0-1.48-1.081Zm-11.318.03c.46-.268 5.623-2.634 6.207-2.754a1.556 1.556 0 0 1 1.876 1.685 1.553 1.553 0 0 1-.396.879c-.396.445-5.026 3.734-5.487 4a2.2 2.2 0 1 1-2.2-3.81Z" />,
  'SparkIcon'
);

export const WPlusIcon: React.FC<IconProps> = ({size = 'small', a11yLabel, className, style, ...rest}) => {
  const a11y = a11yLabel
    ? {'aria-label': a11yLabel, role: 'img' as const}
    : {'aria-hidden': true as const, role: 'presentation' as const};
  return (
    <svg
      className={className}
      fill="none"
      height="1em"
      style={{fontSize: SIZES[size], verticalAlign: ALIGNS[size], ...style}}
      viewBox="0 0 32 32"
      width="1em"
      xmlns="http://www.w3.org/2000/svg"
      {...a11y}
      {...rest}
    >
      <g transform="scale(2)">
        <path fillRule="evenodd" clipRule="evenodd" d="M0 3.62329H1.30939L1.88821 6.5773L2.1601 8.13549L2.25468 7.6536L2.59745 6.1194L3.18414 3.62329H4.48287L5.02956 6.18341C5.12556 6.65809 5.20735 7.06048 5.27806 7.47196L5.37624 8.10616L5.49723 7.4601L5.76293 6.1354L6.28828 3.62329H7.53367L5.99227 9.43155C5.01089 9.64489 4.63487 9.25288 4.49887 8.62885L4.10152 6.81543C4.01085 6.37986 3.9344 6.03081 3.87217 5.64817L3.7895 5.03402C3.70594 5.47671 3.6295 5.8305 3.53883 6.20997L2.74412 9.43155C1.84168 9.61156 1.46847 9.38979 1.26287 8.76041L0 3.62329Z" fill="#0071DC" />
        <path fillRule="evenodd" clipRule="evenodd" d="M10.0473 4.36638C10.2883 4.36638 10.4902 4.4978 10.5653 4.65823L10.5966 4.7824L10.6473 6.05979L11.9273 6.10779C12.138 6.11579 12.3434 6.35314 12.3434 6.65182C12.3434 6.89289 12.2119 7.09301 12.0515 7.16751L11.9273 7.19851L10.642 7.24651L10.5939 8.5239C10.5886 8.73191 10.3486 8.93992 10.0499 8.93992C9.80885 8.93992 9.60702 8.80679 9.53184 8.64704L9.50057 8.5239L9.45256 7.24384L8.16984 7.19851C7.95916 7.19051 7.75382 6.95316 7.75382 6.65448C7.75382 6.4134 7.88524 6.21329 8.04567 6.13879L8.16984 6.10779L9.45523 6.05712L9.50057 4.7824C9.50857 4.57172 9.74858 4.36638 10.0473 4.36638Z" fill="#0071DC" />
        <path fillRule="evenodd" clipRule="evenodd" d="M10.0454 9.95183C10.2352 9.95183 10.4046 10.0286 10.4716 10.1413L10.5014 10.2318L10.7361 12.8613C10.7601 13.12 10.4321 13.336 10.0454 13.336C9.72536 13.336 9.44794 13.1786 9.37516 12.9826L9.35734 12.8613L9.58935 10.2318C9.60535 10.0745 9.81069 9.95183 10.0454 9.95183Z" fill="#FFC220" />
        <path fillRule="evenodd" clipRule="evenodd" d="M13.3052 8.0036L13.4004 8.01821L15.8031 9.13026C16.0378 9.24227 16.0618 9.63162 15.8698 9.9623C15.7098 10.2379 15.4424 10.4042 15.2311 10.3671L15.1124 10.3197L12.9443 8.80492C12.8217 8.70358 12.811 8.47424 12.9283 8.27156C13.0222 8.10942 13.1724 8.00872 13.3052 8.0036Z" fill="#FFC220" />
        <path fillRule="evenodd" clipRule="evenodd" d="M15.0597 2.92299C15.2784 2.77898 15.6224 2.94966 15.8171 3.28301C15.9749 3.55857 15.9864 3.87303 15.8484 4.03656L15.7478 4.11504L13.345 5.22709C13.2036 5.29643 12.9903 5.17642 12.873 4.97375C12.777 4.80947 12.7578 4.62813 12.8235 4.51301L12.889 4.44039L15.0597 2.92299Z" fill="#FFC220" />
        <path fillRule="evenodd" clipRule="evenodd" d="M10.045 0C10.3672 0 10.6487 0.150007 10.7197 0.349707L10.7357 0.474688L10.501 3.10414C10.493 3.26948 10.2824 3.38415 10.045 3.38415C9.85727 3.38415 9.68659 3.30393 9.61901 3.19266L9.58899 3.10414L9.35698 0.474688C9.33031 0.210676 9.66099 0 10.045 0Z" fill="#FFC220" />
      </g>
    </svg>
  );
};
WPlusIcon.displayName = 'WPlusIcon';


// ---------------------------------------------------------------------------
// CSSTransition
// ---------------------------------------------------------------------------

type TransitionPhase = 'idle' | 'enter' | 'enterActive' | 'exit' | 'exitActive';

export interface CSSTransitionProps {
  children: React.ReactElement;
  classNames: {
    enter: string;
    enterActive: string;
    exit: string;
    exitActive: string;
  };
  in?: boolean;
  mountOnEnter?: boolean;
  nodeRef: React.RefObject<HTMLElement | null>;
  onEntered?: () => void;
  onEntering?: () => void;
  onExit?: () => void;
  onExited?: () => void;
  onExiting?: () => void;
  timeout: number | { enter: number; exit: number };
  unmountOnExit?: boolean;
}

export function CSSTransition({
  children,
  classNames,
  in: isOpen = false,
  mountOnEnter = false,
  nodeRef,
  onEntered,
  onEntering,
  onExit,
  onExited,
  onExiting,
  timeout,
  unmountOnExit = false,
}: CSSTransitionProps) {
  const enterMs = typeof timeout === 'number' ? timeout : timeout.enter;
  const exitMs = typeof timeout === 'number' ? timeout : timeout.exit;
  const [isMounted, setIsMounted] = React.useState(isOpen);
  const [phase, setPhase] = React.useState<TransitionPhase>('idle');

  React.useEffect(() => {
    if (isOpen) {
      if (!isMounted) {
        setIsMounted(true);
        setPhase('enter');
      }
      return;
    }
    if (isMounted) {
      setPhase('exit');
    }
  }, [isOpen, isMounted]);

  React.useEffect(() => {
    if (!isMounted) return;
    let frameId: number | undefined;
    let timerId: ReturnType<typeof setTimeout> | undefined;

    if (phase === 'enter') {
      frameId = requestAnimationFrame(() => setPhase('enterActive'));
    } else if (phase === 'enterActive') {
      onEntering?.();
      timerId = setTimeout(() => { onEntered?.(); setPhase('idle'); }, enterMs);
    } else if (phase === 'exit') {
      onExit?.();
      frameId = requestAnimationFrame(() => setPhase('exitActive'));
    } else if (phase === 'exitActive') {
      onExiting?.();
      timerId = setTimeout(() => {
        setPhase('idle');
        if (unmountOnExit) setIsMounted(false);
        onExited?.();
      }, exitMs);
    }

    return () => {
      if (frameId !== undefined) cancelAnimationFrame(frameId);
      if (timerId !== undefined) clearTimeout(timerId);
    };
  }, [isMounted, onEntered, onEntering, onExit, onExited, onExiting, phase, enterMs, exitMs, unmountOnExit]);

  if (!isMounted && (mountOnEnter || unmountOnExit)) return null;

  let transitionClassName = '';
  if (phase === 'enter') transitionClassName = classNames.enter;
  else if (phase === 'enterActive') transitionClassName = classNames.enterActive;
  else if (phase === 'exit') transitionClassName = classNames.exit;
  else if (phase === 'exitActive') transitionClassName = classNames.exitActive;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return React.cloneElement(children, {
    className: [(children.props as any).className, transitionClassName].filter(Boolean).join(' '),
    ref: nodeRef,
  } as any);
}


// ---------------------------------------------------------------------------
// FocusLock
// ---------------------------------------------------------------------------

export interface FocusLockProps {
  children: React.ReactNode;
  disabled?: boolean;
  returnFocus?: boolean;
  onDeactivation?: () => void;
  [key: string]: unknown;
}

export const FocusLock: React.FC<FocusLockProps> = ({
  children,
  disabled = false,
  returnFocus = false,
  onDeactivation,
  ...rest
}) => {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const previouslyFocused = React.useRef<Element | null>(null);

  React.useEffect(() => {
    if (disabled) return;
    previouslyFocused.current = document.activeElement;
    const el = containerRef.current;
    if (!el) return;

    const focusables = el.querySelectorAll<HTMLElement>(
      'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])'
    );
    if (focusables.length > 0) focusables[0].focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    el.addEventListener('keydown', handleKeyDown);

    return () => {
      el.removeEventListener('keydown', handleKeyDown);
      onDeactivation?.();
      if (returnFocus && previouslyFocused.current instanceof HTMLElement) {
        previouslyFocused.current.focus();
      }
    };
  }, [disabled, returnFocus, onDeactivation]);

  return <div ref={containerRef} {...rest}>{children}</div>;
};

FocusLock.displayName = 'FocusLock';


// ---------------------------------------------------------------------------
// Date utilities
// ---------------------------------------------------------------------------

export function formatDate(date: Date, formatStr: string): string {
  const y = date.getFullYear();
  const M = date.getMonth() + 1;
  const d = date.getDate();
  return formatStr
    .replace('yyyy', String(y).padStart(4, '0'))
    .replace('MM', String(M).padStart(2, '0'))
    .replace('dd', String(d).padStart(2, '0'));
}

export function parseDate(value: string, formatStr: string): Date {
  const yearIdx = formatStr.indexOf('yyyy');
  const monthIdx = formatStr.indexOf('MM');
  const dayIdx = formatStr.indexOf('dd');
  const y = yearIdx >= 0 ? parseInt(value.substring(yearIdx, yearIdx + 4), 10) : NaN;
  const m = monthIdx >= 0 ? parseInt(value.substring(monthIdx, monthIdx + 2), 10) : NaN;
  const d = dayIdx >= 0 ? parseInt(value.substring(dayIdx, dayIdx + 2), 10) : NaN;
  if (isNaN(y) || isNaN(m) || isNaN(d) || m < 1 || m > 12 || d < 1 || d > 31) return new Date(NaN);
  const date = new Date(y, m - 1, d);
  date.setFullYear(y);
  if (date.getMonth() !== m - 1 || date.getDate() !== d) return new Date(NaN);
  return date;
}

export function isValid(date: unknown): date is Date {
  return date instanceof Date && !isNaN(date.getTime());
}

export function differenceInCalendarDays(a: Date, b: Date): number {
  const utcA = Date.UTC(a.getFullYear(), a.getMonth(), a.getDate());
  const utcB = Date.UTC(b.getFullYear(), b.getMonth(), b.getDate());
  return Math.floor((utcA - utcB) / 86400000);
}

export function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export function isToday(date: Date): boolean {
  return isSameDay(date, new Date());
}

export function lastDayOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0);
}

function addDaysImpl(date: Date, n: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + n);
  return d;
}

export function addDays(date: Date, n: number): Date {
  return addDaysImpl(date, n);
}

export function subDays(date: Date, n: number): Date {
  return addDaysImpl(date, -n);
}

export function addWeeks(date: Date, n: number): Date {
  return addDaysImpl(date, n * 7);
}

export function subWeeks(date: Date, n: number): Date {
  return addDaysImpl(date, -n * 7);
}

function addMonthsImpl(date: Date, n: number): Date {
  const d = new Date(date);
  const day = d.getDate();
  d.setMonth(d.getMonth() + n, 1);
  d.setDate(Math.min(day, lastDayOfMonth(d).getDate()));
  return d;
}

export function addMonths(date: Date, n: number): Date {
  return addMonthsImpl(date, n);
}

export function subMonths(date: Date, n: number): Date {
  return addMonthsImpl(date, -n);
}

export function startOfWeek(date: Date): Date {
  const d = new Date(date);
  d.setDate(d.getDate() - d.getDay());
  return d;
}

export function endOfWeek(date: Date): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + (6 - d.getDay()));
  return d;
}


// ---------------------------------------------------------------------------
// Product Images
// ---------------------------------------------------------------------------

/**
 * Product image CDN URLs used across WCP pattern demos.
 */
export const PRODUCT_IMAGES = {
  airFryer:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Ff453f584eedd4e529289af6e389c88f8?format=webp&width=400',
  digitalCamera:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Fc77a8a2194f044f083d462529790fade?format=webp&width=400',
  tablet:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F0ba6171a7ddc4fa8882a508257c2f450?format=webp&width=400',
  headphones:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Fd12a13bd5b9f4f6a8aeb6c36b1670513?format=webp&width=400',
  blackCardigan:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Fb9e98086fb724b9bba6cb6e35d84d81f?format=webp&width=400',
  leatherHandbag:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F5909f37338d84f129a39089788932eaf?format=webp&width=400',
  rattanCabinet:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F27eb35b2afea4485ba9d20aa745ccf53?format=webp&width=400',
  hoboBagGreen:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F1ab87b8c961148eba3758ee80601ceee?format=webp&width=400',
  hoboBagBrown:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F9f231ed362dd43248ea4aed7618a2b3a?format=webp&width=400',
  brownTote:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F9f231ed362dd43248ea4aed7618a2b3a?format=webp&width=400',
  ivoryToteSet:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F8181bc0378fc4d3088c9da866ab225e8?format=webp&width=400',
  mkMonogramSet:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F248d089cd4d74a20a2a4c9c506db3bbf?format=webp&width=400',
  cordlessVacuum:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F379731330bb940eda8207457fa0843f6?format=webp&width=400',
  comforterSet:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Fb76644a968b4459a9b818c73fac555cb?format=webp&width=400',
  cookwareSet:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Fdff23a61c3bb45d1bcaed4c8bd36bfbe?format=webp&width=400',
  mugSet:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F05a837e12c93403fa0ef20a3f1a1bffe?format=webp&width=400',
  boucleArmchair:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F3b2eb5963d0e4ac59a9d7e1aa8d5a214?format=webp&width=400',
  pinkSofaBed:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F09953c0ff5f84a5e8fb11576c26ee11c?format=webp&width=400',
  leatherArmchairDetail:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F274f4ff2e6604cdeb950166fd782b99f?format=webp&width=400',
  leatherArmchair:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F250f1a9f3f154c0985288398cc0902b7?format=webp&width=400',
  countertopBlender:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Fcac71e56229e48498251db800593caaf?format=webp&width=400',
  handBlenderSet:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F4dc1b475cbc74199b27cfbb96b56f2e2?format=webp&width=400',
  blenderSystem:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Ff3efbc2a8da24ef0a5061e45658a7bcb?format=webp&width=400',
  personalBlender:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F0613e780cd224b2dbc4bc8cab3af9618?format=webp&width=400',
  roomba1:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Fcac6d3b33da74f008e7189846ce4a29c?format=webp&width=400',
  roomba2:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F395f5a69955c45c7b7c294ed96f4ee30?format=webp&width=400',
  roomba3:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F9496a8e7bb424b84b7017d47030ea046?format=webp&width=400',
  roomba4:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Fec092fc1f1c04133a2d576221cabeb66?format=webp&width=400',
  laptop1:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Fb2958dd952ce42b6bddc9c13b91fed5a?format=webp&width=400',
  laptop2:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F282111a6dce74ad98d66fd74387a597b?format=webp&width=400',
  laptop3:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F546652e80853422fb199a2a23650acc4?format=webp&width=400',
  laptop4:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Fea3f3c92e92e4b8e8b788740957e2374?format=webp&width=400',
  starbucksDoubleshot:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F0df5f2566ed745199caba22cd2550580?format=webp&width=400',
  bettergooodsFruitSnacks:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F0fb02ee43822448c9fefc27edb406268?format=webp&width=400',
  eggs6Count:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F7205b144e57e44eda68c0978f46b4ae1?format=webp&width=400',
  oatlyOatMilk:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Faca303496b8e4fbebda3b698b6f71b74?format=webp&width=400',
  bettergoodsCarrotJuice:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Fbee8e19031fa4558ac46003f633b4d3a?format=webp&width=400',
  skinnyPopPopcorn:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Fcec333ca519841fda21dba1f99e06296?format=webp&width=400',
  kikkomanSoySauce:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F488da5f4c78145f982f09761420ab8a5?format=webp&width=400',
  goodCultureCottageCheese:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F51d895e46664467f973c60bc34b032b1?format=webp&width=400',
  bettergoodsFrozenMeal:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F84ec9962ed7f416ba60c9eb18f965158?format=webp&width=400',
  freshStrawberries:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F69a12d76a7aa4d1797ea8c5081cc95f4?format=webp&width=400',
  bettergoodsSalsa:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Fcb649a50618f49ca918bf515c9662749?format=webp&width=400',
  redApple:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F58b6ed866290432196fcfee0794c8c48?format=webp&width=400',
  flashEarrings:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Fd02a9e520e5040aab3e4cc7a15442318?format=webp&width=400',
  flashShampoo:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F05643d24b1534517bba50e26a1a75178?format=webp&width=400',
  flashHumidifier:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F207f43bc2e614f0fac075e2d6c9a2d1f?format=webp&width=400',
  flashTankTops:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F3351e086d41b41b8a457ea95b7ebde21?format=webp&width=400',
  flashLaptop:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Febac1d29c0c243c58bf6b0f4f724dd65?format=webp&width=400',
  flashExerciseBike:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F8327129ce60a4a7c8fcef5aa641d9611?format=webp&width=400',
  cheerios:
    'https://i5.walmartimages.com/seo/Cheerios-Cereal-Gluten-Free-Breakfast-Cereal-Original-Flavor-18-oz_8c5e2039-9c67-4c6a-92d4-f7e2e5d5e8e8.jpg?odnHeight=640&odnWidth=640&odnBg=FFFFFF',
  honeyNutCheerios:
    'https://i5.walmartimages.com/seo/Honey-Nut-Cheerios-Gluten-Free-Cereal-with-Oats-Heart-Healthy-Cereal-10-8-oz_a6f65b9e-6315-4a64-8c8e-f6e3b5b5e5e5.jpg?odnHeight=640&odnWidth=640&odnBg=FFFFFF',
  // Grocery product images (used by order card patterns)
  milk:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F4275c57e09134f118110d61ffaed7f3e?format=webp&width=400',
  eggs:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F78ef20205e3c4c4d89a0402b3651cfaf?format=webp&width=400',
  bananas:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F3722ac211f454e0e981b44c68bd71f32?format=webp&width=400',
  avocado:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F5d243d5fa5384060878d8e665e30b97a?format=webp&width=400',
  blueberries:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F23fbfba8c5334a6e97499ee2bcbdeeed?format=webp&width=400',
  strawberries:
    'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F182fe6cfc6cc4e94935dbbe85d069c17?format=webp&width=400',
  // Walmart no-image placeholder (spark on gray background)
  walmartPlaceholder:
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400'%3E%3Crect width='400' height='400' fill='%23f5f5f5'/%3E%3Cg transform='translate(200,175)'%3E%3Ccircle r='4' fill='%23FFC220'/%3E%3Cg fill='%23FFC220'%3E%3Crect x='-3.5' y='-24' width='7' height='19' rx='3.5'/%3E%3Crect x='-3.5' y='5' width='7' height='19' rx='3.5'/%3E%3Crect x='-3.5' y='-24' width='7' height='19' rx='3.5' transform='rotate(60)'/%3E%3Crect x='-3.5' y='5' width='7' height='19' rx='3.5' transform='rotate(60)'/%3E%3Crect x='-3.5' y='-24' width='7' height='19' rx='3.5' transform='rotate(-60)'/%3E%3Crect x='-3.5' y='5' width='7' height='19' rx='3.5' transform='rotate(-60)'/%3E%3C/g%3E%3C/g%3E%3Ctext x='200' y='225' text-anchor='middle' font-family='system-ui,sans-serif' font-size='13' fill='%2374767c'%3EImage not available%3C/text%3E%3C/svg%3E",
} as const;
