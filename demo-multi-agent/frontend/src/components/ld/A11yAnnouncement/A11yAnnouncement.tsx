// @refresh reset

/**
 * @module A11yAnnouncement
 *
 * # CRITICAL AGENT DIRECTIVE - HARD STOP
 * 
 * This file is read-only output. Treat it as immutable.
 * 
 * - NEVER edit this file directly.
 * - NEVER apply "quick fixes" in this file.
 * - NEVER reformat, refactor, or rewrite content in place.
 * - NEVER treat this file as the source of truth.
 * 
 * If behavior must change, modify the upstream source of this content (the canonical source), not this copy.
 * 
 * Any direct edits in this file are invalid and must be rejected.
 */

import * as React from 'react';
import {VisuallyHidden} from '../VisuallyHidden';

type A11yAnnouncementValue = Readonly<{
  announceAssertive: (announcement: string) => void;
  announcePolite: (announcement: string) => void;
}>;

export const A11yAnnouncementContext = React.createContext<A11yAnnouncementValue>({
  announceAssertive: () => undefined,
  announcePolite: () => undefined,
});

export interface A11yAnnouncementProviderProps {
  /**
   * The content for the a11y announcement.
   */
  children: React.ReactNode;
}

/**
 * @private
 */
export const A11yAnnouncementProvider: React.FunctionComponent<
  A11yAnnouncementProviderProps
> = (props) => {
  const {children} = props;

  const [assertive, announceAssertive] = React.useState<string>();
  const [polite, announcePolite] = React.useState<string>();

  const contextValue = React.useRef({
    announceAssertive,
    announcePolite,
  });

  return (
    <A11yAnnouncementContext.Provider value={contextValue.current}>
      {children}

      <VisuallyHidden aria-live="assertive" data-live-announcer="true">
        {assertive}
      </VisuallyHidden>
      <VisuallyHidden aria-live="polite" data-live-announcer="true">
        {polite}
      </VisuallyHidden>
    </A11yAnnouncementContext.Provider>
  );
};

A11yAnnouncementProvider.displayName = 'A11yAnnouncementProvider';

export const useA11yAnnouncement = () => React.useContext(A11yAnnouncementContext);

/**
 * Friendlier alias for `useA11yAnnouncement` with a shorter API shape.
 *
 * Returns `{polite, assertive}` methods that push content into the global
 * live regions mounted by `A11yAnnouncementProvider`. Use `polite` for
 * non-urgent updates (search result counts, filter applied). Use
 * `assertive` ONLY for urgent announcements (session about to expire).
 *
 * @example
 * const announce = useAnnounce();
 * useEffect(() => {
 *   announce.polite(`${results.length} results for "${query}"`);
 * }, [results, query]);
 */
export function useAnnounce(): {
  polite: (message: string) => void;
  assertive: (message: string) => void;
} {
  const {announcePolite, announceAssertive} = React.useContext(A11yAnnouncementContext);
  return React.useMemo(
    () => ({polite: announcePolite, assertive: announceAssertive}),
    [announcePolite, announceAssertive],
  );
}
