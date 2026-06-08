// @refresh reset

/**
 * @module WCPAccountSideNav
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
import {WPlusIcon, cx} from '../common';
const { useState } = React;
import { SideNavigation, SideNavigationItem } from '../SideNavigation';
import { Divider } from '../Divider';
import { Tag } from '../Tag';
import { ChevronDownIcon as CoreChevronDownIcon } from '../Icons';
import './WCPAccountSideNav.css';

/* ------------------------------------------------------------------ */
/*  Inline SVG icons (no core equivalent)                             */
/* ------------------------------------------------------------------ */

const UserIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <circle cx="12" cy="8" r="4" stroke="#0071dc" strokeWidth="1.5" />
    <path d="M5 20C5 17.2386 8.13401 15 12 15C15.866 15 19 17.2386 19 20" stroke="#0071dc" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const GearIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <circle cx="12" cy="12" r="3" stroke="#0071dc" strokeWidth="1.5" />
    <path d="M12 1V4M12 20V23M23 12H20M4 12H1M20.07 3.93L17.95 6.05M6.05 17.95L3.93 20.07M20.07 20.07L17.95 17.95M6.05 6.05L3.93 3.93" stroke="#0071dc" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const SignOutIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M9 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H9" stroke="#0071dc" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M16 17L21 12L16 7" stroke="#0071dc" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M21 12H9" stroke="#0071dc" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

/* ------------------------------------------------------------------ */
/*  Data                                                              */
/* ------------------------------------------------------------------ */

interface NavItem {
  label: string;
  path: string;
  tag?: string;
}

const accountItems: NavItem[] = [
  { label: 'Home', path: '/' },
  { label: 'Purchase history', path: '/purchase-history' },
  { label: 'Walmart+', path: '/walmart-plus' },
  { label: 'My savings', path: '/savings' },
  { label: 'Walmart Cash', path: '/walmart-cash' },
  { label: 'Messages', path: '/messages' },
];

const myItemsItems: NavItem[] = [
  { label: 'Reorder', path: '/reorder' },
  { label: 'Shop With Friends', path: '/shop-with-friends', tag: 'New' },
  { label: 'Lists', path: '/lists' },
  { label: 'Subscriptions', path: '/subscriptions' },
  { label: 'Registry', path: '/registry' },
  { label: 'Protection plans', path: '/protection-plans' },
];

const myProfileItems: NavItem[] = [
  { label: 'Reviews', path: '/reviews', tag: '6 items to review' },
  { label: 'Pets', path: '/pets' },
  { label: 'Vehicles', path: '/vehicles' },
  { label: 'Recipes', path: '/recipes' },
];

const otherAccountsItems: NavItem[] = [
  { label: 'Pharmacy', path: '/pharmacy' },
  { label: 'Photos', path: '/photos' },
  { label: 'eBooks', path: '/ebooks' },
];

const settingsPersonalInfo: NavItem[] = [
  { label: 'Contact info and password', path: '/settings/contact' },
  { label: 'Passkeys', path: '/settings/passkeys' },
  { label: 'Addresses', path: '/settings/addresses' },
  { label: 'Wallet', path: '/settings/wallet' },
];

const settingsComms: NavItem[] = [
  { label: 'Communication preferences', path: '/settings/communication' },
  { label: 'Privacy', path: '/settings/privacy' },
];

const settingsShopping: NavItem[] = [
  { label: 'Language settings', path: '/settings/language' },
];

/* ------------------------------------------------------------------ */
/*  Sub-components                                                    */
/* ------------------------------------------------------------------ */

function NavItemContent({ item }: { item: NavItem }) {
  return (
    <span className="ld-wcp-account-side-nav-nav-item-content">
      <span className="ld-wcp-account-side-nav-nav-item-label">{item.label}</span>
      {item.tag && (
        <Tag color="spark" variant="primary">{item.tag}</Tag>
      )}
    </span>
  );
}

interface NavGroupProps {
  title: string;
  items: NavItem[];
  currentPath: string;
}

function NavGroup({ title, items, currentPath }: NavGroupProps) {
  return (
    <>
      <div className="ld-wcp-account-side-nav-group-title">
        {title}
      </div>
      <SideNavigation aria-label={title}>
        {items.map((item) => (
          <SideNavigationItem
            key={item.path}
            href="#"
            isCurrent={currentPath === item.path}
            onClick={(e: React.MouseEvent<HTMLAnchorElement>) => e.preventDefault()}
          >
            <NavItemContent item={item} />
          </SideNavigationItem>
        ))}
      </SideNavigation>
    </>
  );
}

interface SectionHeaderProps {
  icon: React.ReactNode;
  label: string;
  isOpen: boolean;
  onClick: () => void;
}

function SectionHeader({ icon, label, isOpen, onClick }: SectionHeaderProps) {
  return (
    <button
      onClick={onClick}
      className="ld-wcp-account-side-nav-section-btn"
    >
      <span className="ld-wcp-account-side-nav-section-left">
        <span className="ld-wcp-account-side-nav-icon-circle">
          {icon}
        </span>
        <span>{label}</span>
      </span>
      <CoreChevronDownIcon
        className={cx('ld-wcp-account-side-nav-chevron', isOpen && 'ld-wcp-account-side-nav-chevron-open')}
      />
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  AccountSideNav                                                    */
/* ------------------------------------------------------------------ */

const hardcodedCurrentPath: string = '/purchase-history';

export function WCPAccountSideNav() {
  const [accountOpen, setAccountOpen] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <aside
      aria-label="Account navigation"
      className="ld-wcp-account-side-nav-root"
    >
      {/* User Header */}
      <div className="ld-wcp-account-side-nav-user-header">
        <div className="ld-wcp-account-side-nav-user-row">
          <WPlusIcon size="large" />
          <span className="ld-wcp-account-side-nav-user-name">Hi, Emilia</span>
        </div>
        <p className="ld-wcp-account-side-nav-member-since">Member since 2023</p>
      </div>

      {/* Account Section (collapsible) */}
      <SectionHeader
        icon={<UserIcon />}
        label="Account"
        isOpen={accountOpen}
        onClick={() => setAccountOpen((v) => !v)}
      />
      {accountOpen && (
        <div>
          <SideNavigation aria-label="Account">
            {accountItems.map((item) => (
              <SideNavigationItem
                key={item.path}
                href="#"
                isCurrent={hardcodedCurrentPath === item.path}
                onClick={(e: React.MouseEvent<HTMLAnchorElement>) => e.preventDefault()}
              >
                <NavItemContent item={item} />
              </SideNavigationItem>
            ))}
          </SideNavigation>
          <NavGroup title="My items" items={myItemsItems} currentPath={hardcodedCurrentPath} />
          <NavGroup title="My profile" items={myProfileItems} currentPath={hardcodedCurrentPath} />
          <NavGroup title="Other accounts" items={otherAccountsItems} currentPath={hardcodedCurrentPath} />
        </div>
      )}

      <Divider />

      {/* Settings Section (collapsible) */}
      <SectionHeader
        icon={<GearIcon />}
        label="Settings"
        isOpen={settingsOpen}
        onClick={() => setSettingsOpen((v) => !v)}
      />
      {settingsOpen && (
        <div>
          <SideNavigation aria-label="Settings">
            <SideNavigationItem
              href="#"
              isCurrent={hardcodedCurrentPath === '/'}
              onClick={(e: React.MouseEvent<HTMLAnchorElement>) => e.preventDefault()}
            >
              Home
            </SideNavigationItem>
          </SideNavigation>
          <NavGroup title="Personal information" items={settingsPersonalInfo} currentPath={hardcodedCurrentPath} />
          <NavGroup title="Communications and privacy" items={settingsComms} currentPath={hardcodedCurrentPath} />
          <NavGroup title="Shopping settings" items={settingsShopping} currentPath={hardcodedCurrentPath} />
        </div>
      )}

      <Divider />

      {/* Sign Out */}
      <button
        onClick={() => { /* no-op */ }}
        className="ld-wcp-account-side-nav-sign-out-btn"
      >
        <span className="ld-wcp-account-side-nav-icon-circle">
          <SignOutIcon />
        </span>
        <span>Sign Out</span>
      </button>
    </aside>
  );
}
WCPAccountSideNav.displayName = 'WCPAccountSideNav';
