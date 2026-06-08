import * as React from 'react';
import { useInitializeTheming } from "./utils/Theming";
import { useInitializeStore } from "./utils/Store";
import { A11yAnnouncementProvider } from "./components/ld/A11yAnnouncement";
import { A11yDevAssertions } from "./components/ld/A11yDevAssertions";
import { Page } from "./components/ld/Page";
import { MatbotHomePage } from "./pages/MatbotHomePage";

export default function App() {

  // ── Theme ─────────────────────────────────────────────────────
  // matbot-multi-agents is an internal Walmart Item Operations tool.
  // Sparky (dark navy + cyan) is the Living Design theme for internal
  // products; it owns the brand identity while `data-color-mode` flips
  // surface/text/border tokens for light/dark via dark-overrides.css.
  useInitializeTheming('Sparky', ['Sparky'] as const);

  useInitializeStore();

  // ── Accessibility ─────────────────────────────────────────────
  // A11yAnnouncementProvider mounts the global live regions used by
  // `useAnnounce()` for polite/assertive screen reader announcements.
  // A11yDevAssertions runs a dev-only DOM scanner that throws into the
  // Vite error overlay when it finds an a11y violation (missing alt,
  // clickable non-interactive, unlabeled input, multiple h1, etc.).
  // In production both are no-ops / tree-shaken.
  //
  // Every page MUST be wrapped in <Page title="…"> — it renders the
  // single h1, the <main> landmark, and the skip-to-content link.
  // Do NOT write <main>, <h1>, or a skip link by hand.
  //
  // See the a11y rules file for the full directive.

  // ── Store Bindings (REQUIRED for headers & product interactions) ──
  // Every page with a header MUST use useHeaderCartBindings() so cart
  // count and price update live as items are added/removed:
  //
  //   import { useHeaderCartBindings, useStoreConnectedItemBindings } from "./utils/Store";
  //
  //   const { cartCount, cartPrice } = useHeaderCartBindings();
  //   <WCPHeader cartCount={cartCount} cartPrice={cartPrice} />
  //
  // Every product card/tile MUST use useStoreConnectedItemBindings() so
  // cart qty, heart state, and header totals stay in sync across all
  // components that reference the same SKU:
  //
  //   const bindItem = useStoreConnectedItemBindings();
  //   const product = bindItem({ sku: "ABC", name: "Item", priceCents: 1999 });
  //
  //   <WCPHeartView activated={product.hearted} onChange={product.onHeartChange} />
  //   {product.cartQty === 0
  //     ? <Button variant="primary" onClick={product.onAddToCart}>Add to cart</Button>
  //     : <QuantityStepper count={product.cartQty} onChange={product.onCartQtyChange} />}
  //
  // NEVER use local useState for cart/heart state. NEVER use addToCart()
  // with QuantityStepper — it increments; use onCartQtyChange (sets exact qty).
  // See .cursor/rules/component-communication.mdc for full API reference.

  // The Page wrapper renders the single h1 (visually hidden) plus
  // the <main> landmark and skip-link. MatbotHomePage owns the
  // visible page heading as an <h2> wordmark.
  return (
    <A11yAnnouncementProvider>
      <A11yDevAssertions />
      <Page title="matbot multi-agents" titleVisuallyHidden>
        <MatbotHomePage />
      </Page>
    </A11yAnnouncementProvider>
  );
}
