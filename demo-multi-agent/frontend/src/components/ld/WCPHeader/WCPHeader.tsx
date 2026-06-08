// @refresh reset

/**
 * @module WCPHeader
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
import {cx, emit} from '../common';
import { useState, useRef, useEffect, useCallback } from 'react';
import {Icon} from '../Icons';
import {CategoryNav} from '../CategoryNav';
import './WCPHeader.css';

/**
 * DesktopHeader - WCP pattern helper (demo only).
 *
 * Faithful visual replica of the Walmart desktop top-nav bar
 * with interactive GIC, Reorder, and Account dropdown menus.
 */

/* ---------- CDN assets ---------- */

const GIC_ICON = 'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Fe96ba70bf20a4d59aede84cfd5b0636c';
const PICKUP_ICON = 'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Ff91b889ffddd4a669bd5f5ed913c38df';
const DELIVERY_ICON = 'https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Ff8af2f0cfbbf459b862fcbd867dac70d';

const SEARCH_SUGGESTIONS = [
  'tv',
  'tvs on sale',
  'smart tv 65',
  'television stand',
  'toilet paper',
  'paper towels',
  'laundry detergent',
  'sunscreen travel size',
  'kids socks toddler',
  'coffee pods',
  'dog food',
  'wireless headphones',
  'gaming laptop',
  'blender',
  'toys for toddlers',
  'protein powder',
];

const DEFAULT_RECENT_SEARCHES = [
  'towel papers big rolls',
  'sunscreen travel size',
  'kids socks toddler',
  'milk low fat',
  'smart tv 65',
];

const KEEP_SHOPPING_CATEGORY = 'Flowers';

type KeepShoppingItem = {
  label: string;
  image: string | null;
  isFilter?: boolean;
};

const KEEP_SHOPPING_FOR: KeepShoppingItem[] = [
  { label: 'Pickup today', image: null, isFilter: true },
  { label: 'Flowers Shop', image: 'https://images.pexels.com/photos/5410133/pexels-photo-5410133.jpeg?auto=compress&cs=tinysrgb&w=300' },
  { label: 'Flowers Bouquet', image: 'https://images.pexels.com/photos/35062137/pexels-photo-35062137.jpeg?auto=compress&cs=tinysrgb&w=300' },
  { label: 'Roses', image: 'https://images.pexels.com/photos/19867740/pexels-photo-19867740.jpeg?auto=compress&cs=tinysrgb&w=300' },
  { label: 'Artificial Flowers', image: 'https://images.pexels.com/photos/8754695/pexels-photo-8754695.jpeg?auto=compress&cs=tinysrgb&w=300' },
  { label: 'Sunflowers', image: 'https://images.pexels.com/photos/4622893/pexels-photo-4622893.jpeg?auto=compress&cs=tinysrgb&w=300' },
];

const GRAB_YOUR_USUALS = [
  'white socks',
  'coffee pods',
  'paper towels',
  'laundry detergent',
  'dog food',
  'bread',
  'cheese',
];

const TRENDING_SEARCHES = [
  'sprite+tea',
  'slashing legends tin',
  'toothpicks',
  'abu garcia',
  'quilted northern bath tissue',
  'pencils',
  'protein powder',
];

const FREQUENT_SEARCHES = [
  'paper plates',
  'laundry detergent',
  'eggs',
  'green tea',
  'cereal',
  'colgate',
  'flour',
  'listerine',
];

function filterSearchSuggestions(query: string): string[] {
  if (!query.trim()) {
    return [];
  }
  const lowerQuery = query.toLowerCase();
  return SEARCH_SUGGESTIONS.filter((suggestion) => suggestion.toLowerCase().includes(lowerQuery));
}

function highlightSuggestionParts(text: string, query: string): { before: string; match: string; after: string } {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return { before: '', match: text, after: '' };
  }

  const lowerText = text.toLowerCase();
  const matchIndex = lowerText.indexOf(normalizedQuery);
  if (matchIndex === -1) {
    return { before: text, match: '', after: '' };
  }

  return {
    before: text.slice(0, matchIndex),
    match: text.slice(matchIndex, matchIndex + normalizedQuery.length),
    after: text.slice(matchIndex + normalizedQuery.length),
  };
}

/* ---------- Inline CartIcon ---------- */

function CartIcon({ count = 0, price = '$0.00', textColor = 'white' }: { count?: number; price?: string; textColor?: string }) {
  return (
    <div className="ld-wcp-responsive-header-desktop-cart-wrap">
      <div className="ld-wcp-responsive-header-desktop-cart-icon-wrap">
        <Icon name="Cart" style={{ fontSize: 24, color: textColor }} />
        <div className="ld-wcp-responsive-header-desktop-cart-badge">
          {count > 99 ? '99+' : count}
        </div>
      </div>
      <div className="ld-wcp-responsive-header-desktop-cart-price" style={{ color: textColor }}>
        {price}
      </div>
    </div>
  );
}

/* ---------- Inline icon helpers ---------- */

const HeartSvg = () => (
  <Icon name="Heart" style={{ fontSize: 20 }} />
);

const UserSvg = () => (
  <Icon name="User" style={{ fontSize: 20 }} />
);

/* ---------- Inline SVG icons for dropdowns ---------- */

const FulfillmentShippingSvg = () => (
  <svg width="50" height="50" viewBox="0 0 50 50" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <g clipPath="url(#clip_ship)">
      <path d="M24.9826 49.9651C38.78 49.9651 49.9651 38.78 49.9651 24.9826C49.9651 11.1851 38.78 0 24.9826 0C11.1851 0 0 11.1851 0 24.9826C0 38.78 11.1851 49.9651 24.9826 49.9651Z" fill="#D3EFF8"/>
      <path d="M44.7307 27.1235H5.08203V31.4516H44.7307V27.1235Z" fill="#001F60"/>
      <path d="M12.7227 27.1235H44.9196V32.2796C44.9196 32.529 44.7174 32.7312 44.468 32.7312H12.7227V27.1235Z" fill="#001F60"/>
      <path d="M33.0274 36.0807C34.9605 36.0807 36.5275 34.5137 36.5275 32.5806C36.5275 30.6476 34.9605 29.0806 33.0274 29.0806C31.0944 29.0806 29.5273 30.6476 29.5273 32.5806C29.5273 34.5137 31.0944 36.0807 33.0274 36.0807Z" fill="#0047BA"/>
      <path d="M33.0247 34.4996C34.0847 34.4996 34.9439 33.6403 34.9439 32.5804C34.9439 31.5204 34.0847 30.6611 33.0247 30.6611C31.9647 30.6611 31.1055 31.5204 31.1055 32.5804C31.1055 33.6403 31.9647 34.4996 33.0247 34.4996Z" fill="#BFDFEC"/>
      <path d="M33.0259 33.1378C33.3337 33.1378 33.5831 32.8884 33.5831 32.5806C33.5831 32.2729 33.3337 32.0234 33.0259 32.0234C32.7182 32.0234 32.4688 32.2729 32.4688 32.5806C32.4688 32.8884 32.7182 33.1378 33.0259 33.1378Z" fill="#041E42"/>
      <path d="M13.7579 36.0807C15.6909 36.0807 17.258 34.5137 17.258 32.5806C17.258 30.6476 15.6909 29.0806 13.7579 29.0806C11.8248 29.0806 10.2578 30.6476 10.2578 32.5806C10.2578 34.5137 11.8248 36.0807 13.7579 36.0807Z" fill="#0047BA"/>
      <path d="M13.7552 34.4996C14.8151 34.4996 15.6744 33.6403 15.6744 32.5804C15.6744 31.5204 14.8151 30.6611 13.7552 30.6611C12.6952 30.6611 11.8359 31.5204 11.8359 32.5804C11.8359 33.6403 12.6952 34.4996 13.7552 34.4996Z" fill="#BFDFEC"/>
      <path d="M13.7564 33.1378C14.0641 33.1378 14.3136 32.8884 14.3136 32.5806C14.3136 32.2729 14.0641 32.0234 13.7564 32.0234C13.4487 32.0234 13.1992 32.2729 13.1992 32.5806C13.1992 32.8884 13.4487 33.1378 13.7564 33.1378Z" fill="#041E42"/>
      <path d="M29.6211 13.8384H33.1212C33.8694 13.8384 34.476 14.445 34.476 15.1932V27.1236H29.6211V13.8384Z" fill="#001F60"/>
      <path d="M5.08203 15.1932C5.08203 14.445 5.68862 13.8384 6.43692 13.8384H29.6202V27.8386H5.08203V15.1932Z" fill="#0047BA"/>
      <path d="M20.0921 20.488C20.3275 20.4396 22.4095 19.4856 22.5948 19.3777C22.6957 19.3195 22.7842 19.242 22.8551 19.1496C22.926 19.0572 22.978 18.9517 23.0081 18.8392C23.0382 18.7267 23.046 18.6093 23.0308 18.4939C23.0156 18.3784 22.9778 18.267 22.9196 18.1661C22.8613 18.0652 22.7838 17.9768 22.6914 17.906C22.599 17.8351 22.4935 17.783 22.381 17.7529C22.2685 17.7227 22.1512 17.7151 22.0357 17.7302C21.9202 17.7454 21.8088 17.7832 21.708 17.8415C21.5221 17.9487 19.655 19.2748 19.4954 19.4543C19.4059 19.5524 19.35 19.6765 19.3357 19.8086C19.3214 19.9407 19.3494 20.0738 19.4158 20.1889C19.4822 20.304 19.5835 20.3949 19.7051 20.4485C19.8265 20.5022 19.962 20.5158 20.0918 20.4874L20.0921 20.488Z" fill="#FFC220"/>
      <path d="M22.5949 22.5999C22.4092 22.4927 20.3272 21.5386 20.0921 21.4896C19.9623 21.4612 19.8268 21.4747 19.7051 21.5284C19.5835 21.5821 19.4822 21.6731 19.4157 21.7883C19.3493 21.9034 19.3213 22.0368 19.3357 22.1689C19.3502 22.3011 19.4063 22.4252 19.496 22.5233C19.6556 22.7028 21.5227 24.0287 21.7086 24.1362C21.9123 24.2538 22.1544 24.2856 22.3816 24.2248C22.6088 24.1639 22.8025 24.0152 22.9202 23.8115C23.0377 23.6078 23.0696 23.3657 23.0088 23.1385C22.9478 22.9112 22.7992 22.7175 22.5955 22.5999H22.5949Z" fill="#FFC220"/>
      <path d="M18.0277 22.5884C17.895 22.5889 17.7658 22.6314 17.6587 22.7096C17.5516 22.7879 17.4719 22.8981 17.4312 23.0244C17.3559 23.2522 17.1406 25.5324 17.1406 25.7469C17.1406 25.9822 17.2341 26.2078 17.4004 26.3741C17.5668 26.5405 17.7924 26.634 18.0277 26.634C18.263 26.634 18.4886 26.5405 18.6549 26.3741C18.8213 26.2078 18.9147 25.9822 18.9147 25.7469C18.9147 25.5324 18.6998 23.2522 18.6242 23.0244C18.5834 22.8981 18.5038 22.7879 18.3966 22.7096C18.2895 22.6314 18.1604 22.5889 18.0277 22.5884Z" fill="#FFC220"/>
      <path d="M15.9678 21.4904C15.7324 21.5387 13.6504 22.4928 13.465 22.6007C13.3626 22.6581 13.2726 22.7352 13.2002 22.8278C13.1278 22.9202 13.0745 23.0262 13.0434 23.1394C13.0123 23.2527 13.004 23.371 13.0189 23.4874C13.0339 23.6039 13.0718 23.7163 13.1306 23.818C13.1893 23.9197 13.2676 24.0088 13.361 24.08C13.4544 24.1511 13.5611 24.2031 13.6747 24.2327C13.7883 24.2624 13.9067 24.2692 14.023 24.2527C14.1393 24.2363 14.2512 24.1969 14.3521 24.1369C14.5378 24.0297 16.4049 22.7036 16.5647 22.5241C16.6541 22.4258 16.7099 22.3018 16.7241 22.1697C16.7384 22.0377 16.7103 21.9046 16.6439 21.7896C16.5775 21.6746 16.4762 21.5837 16.3548 21.53C16.2333 21.4763 16.0979 21.4627 15.9682 21.4909L15.9678 21.4904Z" fill="#FFC220"/>
      <path d="M14.3521 17.8418C14.2512 17.7819 14.1393 17.7425 14.023 17.726C13.9067 17.7096 13.7883 17.7164 13.6747 17.746C13.5611 17.7757 13.4544 17.8277 13.361 17.8989C13.2676 17.97 13.1893 18.0591 13.1306 18.1608C13.0718 18.2625 13.0339 18.3748 13.0189 18.4913C13.004 18.6078 13.0123 18.7261 13.0434 18.8393C13.0745 18.9526 13.1278 19.0585 13.2002 19.151C13.2726 19.2435 13.3626 19.3207 13.465 19.3782C13.6508 19.4854 15.7327 20.4395 15.9678 20.4884C16.0975 20.5167 16.2329 20.503 16.3544 20.4494C16.4758 20.3957 16.5771 20.3048 16.6435 20.1898C16.7099 20.0748 16.738 19.9416 16.7238 19.8096C16.7095 19.6776 16.6537 19.5535 16.5643 19.4553C16.4049 19.2752 14.5378 17.9491 14.3521 17.8418Z" fill="#FFC220"/>
      <path d="M18.0275 15.3438C17.7923 15.3438 17.5667 15.4373 17.4003 15.6037C17.234 15.77 17.1406 15.9956 17.1406 16.2308C17.1406 16.4453 17.3555 18.7255 17.4312 18.9533C17.4715 19.0799 17.551 19.1904 17.6583 19.2687C17.7655 19.3471 17.8948 19.3894 18.0277 19.3894C18.1605 19.3894 18.2899 19.3471 18.3971 19.2687C18.5044 19.1904 18.5839 19.0799 18.6242 18.9533C18.6995 18.7255 18.9147 16.4453 18.9147 16.2308C18.9148 16.1143 18.8918 15.999 18.8473 15.8913C18.8027 15.7836 18.7373 15.6858 18.6549 15.6035C18.5725 15.5211 18.4747 15.4557 18.367 15.4112C18.2594 15.3666 18.144 15.3437 18.0275 15.3438Z" fill="#FFC220"/>
      <path d="M34.7188 20.1423C34.7188 19.4772 35.258 18.938 35.9231 18.938H41.9779C42.4972 18.938 42.9582 19.271 43.1213 19.7641L44.9179 25.1949V31.4517H40.7592L39.8311 28.7448C39.6433 28.1971 39.1284 27.8293 38.5495 27.8293H34.7188V20.1423Z" fill="#6BC4E8"/>
      <path d="M43.1282 19.7847L44.918 25.1948V25.2042H37.2969V19.7847H43.1282Z" fill="#001F60"/>
      <path d="M31.5938 20.1423C31.5938 19.4772 32.1329 18.938 32.7981 18.938H38.8528C39.3722 18.938 39.8331 19.271 39.9962 19.7641L41.7929 25.1949V31.4517H37.6342L36.7061 28.7448C36.5183 28.1971 36.0033 27.8293 35.4244 27.8293H31.5938V20.1423Z" fill="white"/>
      <path d="M32.7422 20.3869C32.7422 20.0543 33.0118 19.7847 33.3444 19.7847H38.1098C38.3662 19.7847 38.5944 19.947 38.6786 20.1892L40.2316 24.6584V26.1263H38.0488L36.878 25.026C36.6268 24.7899 36.2949 24.6584 35.9502 24.6584H33.3444C33.0118 24.6584 32.7422 24.3889 32.7422 24.0563V20.3869Z" fill="#001F60"/>
      <path d="M34.6699 24.9404H33.0433C32.877 24.9404 32.7422 25.0752 32.7422 25.2415V25.3823C32.7422 25.5486 32.877 25.6834 33.0433 25.6834H34.6699C34.8362 25.6834 34.971 25.5486 34.971 25.3823V25.2415C34.971 25.0752 34.8362 24.9404 34.6699 24.9404Z" fill="#002042"/>
      <path d="M44.9167 28.5537H41.793V31.4516H44.9167V28.5537Z" fill="#001F60"/>
      <path d="M42.5399 31.1882C42.7841 31.1882 42.9821 30.6532 42.9821 29.9933C42.9821 29.3333 42.7841 28.7983 42.5399 28.7983C42.2956 28.7983 42.0977 29.3333 42.0977 29.9933C42.0977 30.6532 42.2956 31.1882 42.5399 31.1882Z" fill="white"/>
      <path d="M44.2313 31.1882C44.4755 31.1882 44.6735 30.6532 44.6735 29.9933C44.6735 29.3333 44.4755 28.7983 44.2313 28.7983C43.987 28.7983 43.7891 29.3333 43.7891 29.9933C43.7891 30.6532 43.987 31.1882 44.2313 31.1882Z" fill="white"/>
      <path d="M41.1437 31.7339H40.0628C39.8965 31.7339 39.7617 31.8687 39.7617 32.035V32.0628C39.7617 32.2291 39.8965 32.3639 40.0628 32.3639H41.1437C41.31 32.3639 41.4448 32.2291 41.4448 32.0628V32.035C41.4448 31.8687 41.31 31.7339 41.1437 31.7339Z" fill="#F58220"/>
      <path d="M6.89761 30.3413H5.81671C5.65042 30.3413 5.51562 30.4761 5.51562 30.6424V30.6703C5.51562 30.8365 5.65042 30.9713 5.81671 30.9713H6.89761C7.06389 30.9713 7.19869 30.8365 7.19869 30.6703V30.6424C7.19869 30.4761 7.06389 30.3413 6.89761 30.3413Z" fill="#F58220"/>
      <path d="M40.3664 23.7178H40.1019C39.9356 23.7178 39.8008 23.8526 39.8008 24.0189V26.3884C39.8008 26.5547 39.9356 26.6895 40.1019 26.6895H40.3664C40.5327 26.6895 40.6675 26.5547 40.6675 26.3884V24.0189C40.6675 23.8526 40.5327 23.7178 40.3664 23.7178Z" fill="#6BC4E8"/>
    </g>
    <defs>
      <clipPath id="clip_ship">
        <rect width="50" height="50" fill="white"/>
      </clipPath>
    </defs>
  </svg>
);

const LocationSvg = () => (
  <svg width="16" height="16" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path fill="currentColor" d="M16 2.001a11.84 11.84 0 0 1 12 11.66c0 6.34-7 12.34-10.54 15.5l-.58.52a1.4 1.4 0 0 1-.88.32 1.4 1.4 0 0 1-.88-.32l-.58-.52C11 26.081 4 20.021 4 13.661a11.84 11.84 0 0 1 12-11.66Zm0 2a9.84 9.84 0 0 0-10 9.66 13.521 13.521 0 0 0 3.86 8.16 55.158 55.158 0 0 0 6 5.84l.14.12.14-.12a55.153 55.153 0 0 0 6-5.84 13.52 13.52 0 0 0 3.86-8.16 9.84 9.84 0 0 0-10-9.66Zm0 7a3 3 0 1 0 3 3h2a5.002 5.002 0 0 1-5 5 5 5 0 1 1 0-10v2Z"/>
  </svg>
);

const StoreSvg = () => (
  <svg width="16" height="16" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path fill="currentColor" d="M14.662 3.515a1.997 1.997 0 0 1 2.676 0l6.046 5.45H26c2.209 0 4 1.794 4 4.007v12.021A4.003 4.003 0 0 1 26 29h-8v-8.014h-4V29H6c-2.21 0-4-1.794-4-4.007V12.972a4.004 4.004 0 0 1 4-4.007h2.616l6.046-5.45Zm-5.278 7.454H6c-1.104 0-2 .896-2 2.003v12.021c0 1.107.895 2.004 2 2.004h6v-8.015h8v8.015h6c1.105 0 2-.897 2-2.004V12.972a2.002 2.002 0 0 0-2-2.003h-3.384L16 5.004l-6.616 5.965Z"/>
  </svg>
);

const ChevronRightSvg = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path fill="currentColor" d="M9.29 6.71a1 1 0 0 0 0 1.42L13.17 12l-3.88 3.88a1 1 0 1 0 1.42 1.41l4.59-4.59a1 1 0 0 0 0-1.41L10.71 6.7a1 1 0 0 0-1.42 0Z"/>
  </svg>
);

const ReorderSvg = () => (
  <svg width="18" height="18" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path fill="currentColor" d="M27.793 17.707c.63-.63 1.707-.184 1.707.707V21.5a1 1 0 0 1-1 1h-3.086c-.89 0-1.337-1.077-.707-1.707l.77-.77a4 4 0 1 0 1.63 5.208l1.803.866a6 6 0 1 1-1.984-7.523l.867-.866ZM11.688 2.672a2.001 2.001 0 0 1 1.624 0l8 3.556A2 2 0 0 1 22.5 8.055V15.5h-2V8.945l-7 3.11V18.5h-2v-6.443l-7-3.112v8.81l8 3.556 2.969-1.32.812 1.828-2.968 1.32c-.518.23-1.108.23-1.626 0l-8-3.556A2 2 0 0 1 2.5 17.755v-9.7a2 2 0 0 1 1.188-1.827l8-3.556ZM10.402 9.38l2.097.931 6.54-2.906-2.284-1.014-6.353 2.989ZM5.961 7.406l2.027.9 6.352-2.989L12.5 4.5 5.96 7.406Z"/>
  </svg>
);

const ListsSvg = () => (
  <svg width="18" height="18" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path fill="currentColor" d="M23 2a3 3 0 0 1 3 3v22a3 3 0 0 1-3 3H9a3 3 0 0 1-3-3V5a3 3 0 0 1 3-3h14ZM9 4a1 1 0 0 0-1 1v22a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1H9Zm9 18h-8v-2h8v2Zm4-6v2H10v-2h12Zm0-2H10v-2h12v2Zm0-4H10V8h12v2Z"/>
  </svg>
);

const GiftSvg = () => (
  <svg width="18" height="18" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path fill="currentColor" d="M20.538 2c2.9 0 4.994 2.776 4.197 5.564l-.049.172c-.13.459-.33.883-.584 1.264H27a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2H17v9h8a1 1 0 0 0 1-1v-6h2v6a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3v-6h2v6a1 1 0 0 0 1 1h8v-9H5a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h2.898a4.495 4.495 0 0 1-.585-1.264l-.048-.172C6.468 4.776 8.562 2 11.462 2a4.366 4.366 0 0 1 4.197 3.166L16 6.359l.34-1.193A4.366 4.366 0 0 1 20.539 2ZM5 16h10v-5H5v5Zm12 0h10v-5H17v5ZM11.462 4a2.366 2.366 0 0 0-2.274 3.016l.048.17A2.5 2.5 0 0 0 11.64 9h3.035l-.939-3.284A2.366 2.366 0 0 0 11.462 4Zm9.076 0c-1.056 0-1.984.7-2.274 1.716L17.325 9h3.035a2.5 2.5 0 0 0 2.404-1.813l.049-.171A2.366 2.366 0 0 0 20.538 4Z"/>
  </svg>
);

const PurchaseHistorySvg = () => (
  <svg width="18" height="18" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path fill="currentColor" d="M30 4h-1a3 3 0 0 0-3 3v18a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5v-2.5A1.5 1.5 0 0 1 3.5 21h13a1.5 1.5 0 0 1 1.5 1.5V25a3 3 0 1 0 6 0V7c0-1.126.372-2.164 1-3H12a3 3 0 0 0-3 3v11H7V7a5 5 0 0 1 5-5h18v2ZM4 25a3 3 0 0 0 3 3h10a4.978 4.978 0 0 1-1-3v-2H4v2Zm14-7h-6v-2h6v2Zm3-4h-9v-2h9v2Zm0-4h-9V8h9v2Z"/>
  </svg>
);

const WalmartPlusLogoSvg = () => (
  <svg width="18" height="18" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <g transform="scale(2)">
      <path fillRule="evenodd" clipRule="evenodd" d="M0 3.62329H1.30939L1.88821 6.5773L2.1601 8.13549L2.25468 7.6536L2.59745 6.1194L3.18414 3.62329H4.48287L5.02956 6.18341C5.12556 6.65809 5.20735 7.06048 5.27806 7.47196L5.37624 8.10616L5.49723 7.4601L5.76293 6.1354L6.28828 3.62329H7.53367L5.99227 9.43155C5.01089 9.64489 4.63487 9.25288 4.49887 8.62885L4.10152 6.81543C4.01085 6.37986 3.9344 6.03081 3.87217 5.64817L3.7895 5.03402C3.70594 5.47671 3.6295 5.8305 3.53883 6.20997L2.74412 9.43155C1.84168 9.61156 1.46847 9.38979 1.26287 8.76041L0 3.62329Z" fill="#0071DC"/>
      <path fillRule="evenodd" clipRule="evenodd" d="M10.0473 4.36638C10.2883 4.36638 10.4902 4.4978 10.5653 4.65823L10.5966 4.7824L10.6473 6.05979L11.9273 6.10779C12.138 6.11579 12.3434 6.35314 12.3434 6.65182C12.3434 6.89289 12.2119 7.09301 12.0515 7.16751L11.9273 7.19851L10.642 7.24651L10.5939 8.5239C10.5886 8.73191 10.3486 8.93992 10.0499 8.93992C9.80885 8.93992 9.60702 8.80679 9.53184 8.64704L9.50057 8.5239L9.45256 7.24384L8.16984 7.19851C7.95916 7.19051 7.75382 6.95316 7.75382 6.65448C7.75382 6.4134 7.88524 6.21329 8.04567 6.13879L8.16984 6.10779L9.45523 6.05712L9.50057 4.7824C9.50857 4.57172 9.74858 4.36638 10.0473 4.36638Z" fill="#0071DC"/>
      <path fillRule="evenodd" clipRule="evenodd" d="M10.0454 9.95183C10.2352 9.95183 10.4046 10.0286 10.4716 10.1413L10.5014 10.2318L10.7361 12.8613C10.7601 13.12 10.4321 13.336 10.0454 13.336C9.72536 13.336 9.44794 13.1786 9.37516 12.9826L9.35734 12.8613L9.58935 10.2318C9.60535 10.0745 9.81069 9.95183 10.0454 9.95183Z" fill="#FFC220"/>
      <path fillRule="evenodd" clipRule="evenodd" d="M13.3052 8.0036L13.4004 8.01821L15.8031 9.13026C16.0378 9.24227 16.0618 9.63162 15.8698 9.9623C15.7098 10.2379 15.4424 10.4042 15.2311 10.3671L15.1124 10.3197L12.9443 8.80492C12.8217 8.70358 12.811 8.47424 12.9283 8.27156C13.0222 8.10942 13.1724 8.00872 13.3052 8.0036Z" fill="#FFC220"/>
      <path fillRule="evenodd" clipRule="evenodd" d="M15.0597 2.92299C15.2784 2.77898 15.6224 2.94966 15.8171 3.28301C15.9749 3.55857 15.9864 3.87303 15.8484 4.03656L15.7478 4.11504L13.345 5.22709C13.2036 5.29643 12.9903 5.17642 12.873 4.97375C12.777 4.80947 12.7578 4.62813 12.8235 4.51301L12.889 4.44039L15.0597 2.92299Z" fill="#FFC220"/>
      <path fillRule="evenodd" clipRule="evenodd" d="M10.045 0C10.3672 0 10.6487 0.150007 10.7197 0.349707L10.7357 0.474688L10.501 3.10414C10.493 3.26948 10.2824 3.38415 10.045 3.38415C9.85727 3.38415 9.68659 3.30393 9.61901 3.19266L9.58899 3.10414L9.35698 0.474688C9.33031 0.210676 9.66099 0 10.045 0Z" fill="#FFC220"/>
    </g>
  </svg>
);

const SubscriptionSvg = () => (
  <svg width="18" height="18" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <g transform="scale(2)">
      <path fillRule="evenodd" clipRule="evenodd" d="M14.9824 8.5C14.726 12.1326 11.6979 15 8 15C5.45365 15 3.22486 13.6403 2 11.6074V14H1V10C1 9.72386 1.22386 9.5 1.5 9.5H5V10.5H2.54395C3.49267 12.567 5.58007 14 8 14C11.1453 14 13.7254 11.5798 13.9795 8.5H14.9824ZM8 1C10.5464 1 12.7751 2.35971 14 4.39258V2H15V6C15 6.27614 14.7761 6.5 14.5 6.5H11V5.5H13.4561C12.5074 3.43321 10.42 2 8 2C4.85472 2.00006 2.27458 4.42027 2.02051 7.5H1.01758C1.27395 3.8674 4.30218 1.00006 8 1Z" fill="#2E2F32"/>
    </g>
  </svg>
);

const WalmartCashSvg = () => (
  <svg width="18" height="18" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <g transform="scale(2)">
      <g clipPath="url(#clip_cash)">
        <path d="M8 16C12.4183 16 16 12.4183 16 8C16 3.58172 12.4183 0 8 0C3.58172 0 0 3.58172 0 8C0 12.4183 3.58172 16 8 16Z" fill="#FFC220"/>
        <path d="M8.0007 2.12988C9.57068 2.1299 11.0411 2.73962 12.1511 3.84961L12.1804 3.87988C13.2904 4.98988 13.9011 6.46027 13.9011 8.03027C13.9009 11.27 11.2707 13.91 8.03098 13.9102C4.80101 13.9102 2.16091 11.28 2.16086 8.04004C2.16086 6.88004 2.49082 5.75957 3.12082 4.80957L2.53098 4.91016C2.35114 4.94013 2.19107 4.82014 2.16086 4.65039C2.13086 4.47042 2.25066 4.31031 2.42063 4.28027L3.80051 4.04004C3.8905 4.02004 3.99027 4.05036 4.06027 4.11035C4.07028 4.12035 4.09032 4.1304 4.10031 4.15039C4.11035 4.17024 4.13059 4.18027 4.13059 4.2002C4.14055 4.21023 4.15109 4.23007 4.15109 4.25V4.26953L4.40109 5.65039C4.43076 5.82022 4.31018 5.98956 4.14035 6.01953H4.08078C3.93078 6.01953 3.80024 5.90977 3.77024 5.75977L3.65109 5.08984C3.08109 5.94984 2.77024 6.96 2.77024 8C2.77027 10.8799 5.12057 13.2294 8.01047 13.2295C10.8904 13.2295 13.2408 10.8801 13.2409 7.99023C13.2409 6.59032 12.6908 5.28002 11.7009 4.29004C10.7109 3.30005 9.40068 2.75978 8.0007 2.75977C7.0907 2.75977 6.20063 3.00043 5.42063 3.44043C5.27079 3.53015 5.08099 3.46994 4.99094 3.32031C4.90094 3.17031 4.96106 2.97965 5.11106 2.88965C5.99095 2.38981 6.99087 2.12988 8.0007 2.12988ZM7.9802 3.67969C8.22998 3.6697 8.4203 3.80969 8.42063 3.97949L8.34055 4.88965C9.07055 5.00965 9.61106 5.39004 9.86106 5.54004C9.96068 5.6002 9.95081 5.76038 9.91086 5.82031L9.4509 6.5C9.3809 6.6 9.23027 6.69031 9.06027 6.57031C8.85028 6.43033 8.34087 6.13005 7.86106 6.12988C7.52112 6.12988 7.36111 6.30987 7.36106 6.5498C7.36106 6.8498 7.68098 7.05961 8.28098 7.34961C9.06094 7.72958 10.071 8.12999 10.071 9.33984C10.071 10.1698 9.42068 10.9896 8.33078 11.1396L8.41086 12.0303C8.42051 12.1802 8.21024 12.3301 7.97043 12.3301C7.72071 12.33 7.53125 12.1901 7.53098 12.0303L7.61106 11.1396C6.69133 11.0497 6.17109 10.64 5.99094 10.46C5.91096 10.39 5.88096 10.3201 5.9509 10.2002L6.36106 9.47949C6.43115 9.36 6.57099 9.36001 6.66086 9.41992C6.91085 9.58991 7.37061 9.8798 7.93039 9.87988C8.26031 9.87988 8.50058 9.70003 8.5007 9.41016C8.5007 9.05018 8.18076 8.81979 7.62082 8.5498C6.76087 8.13983 5.90119 7.68999 5.90109 6.62012L5.91086 6.61035C5.91086 5.81035 6.47082 5.00988 7.62082 4.87988L7.54074 3.97949C7.53116 3.81977 7.7406 3.67986 7.9802 3.67969Z" fill="#0053E2"/>
      </g>
      <defs>
        <clipPath id="clip_cash">
          <rect width="16" height="16" fill="white"/>
        </clipPath>
      </defs>
    </g>
  </svg>
);

const GlobeSvg = () => (
  <svg width="18" height="18" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path fill="currentColor" d="M16 2.001c7.732 0 14 6.268 14 14s-6.268 14-14 14-14-6.268-14-14 6.268-14 14-14Zm-4.265 20c.298 1.13.673 2.143 1.104 3.005C13.999 27.326 15.233 28 16 28c.767 0 2-.674 3.161-2.995.431-.862.806-1.875 1.104-3.005h-8.53Zm-6.13 0a12.042 12.042 0 0 0 6.234 5.259c-.921-1.364-1.669-3.17-2.165-5.259H5.605Zm16.721 0c-.496 2.09-1.244 3.895-2.165 5.259A12.041 12.041 0 0 0 26.394 22h-4.068Zm-17.643-10a11.983 11.983 0 0 0-.683 4c0 1.402.24 2.749.683 4H9.29a27.252 27.252 0 0 1-.29-4c0-1.39.101-2.733.29-4H4.683Zm6.63 0a25.08 25.08 0 0 0-.313 4c0 1.41.112 2.755.313 4h9.373a25.08 25.08 0 0 0 .314-4c0-1.41-.112-2.755-.314-4h-9.373Zm11.397 0c.188 1.267.29 2.61.29 4 0 1.39-.102 2.733-.29 4h4.607c.442-1.251.683-2.598.683-4 0-1.402-.24-2.749-.683-4H22.71Zm-10.871-7.26a12.042 12.042 0 0 0-6.234 5.26h4.069c.496-2.09 1.244-3.896 2.165-5.26ZM16 4.001c-.767 0-2 .673-3.161 2.994-.431.862-.806 1.876-1.104 3.006h8.53c-.298-1.13-.673-2.144-1.104-3.006-1.16-2.32-2.394-2.994-3.161-2.994Zm4.161.74c.921 1.364 1.669 3.17 2.165 5.26h4.069a12.041 12.041 0 0 0-6.234-5.26Z"/>
  </svg>
);

const SignOutSvg = () => (
  <svg width="18" height="18" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path fill="currentColor" d="M13.5 2.5v2h-5a2 2 0 0 0-2 2v18a2 2 0 0 0 2 2h5v2h-5a4 4 0 0 1-4-4v-18a4 4 0 0 1 4-4h5Zm15.707 12.293a1 1 0 0 1 0 1.414l-5 5-1.414-1.414 3.293-3.293H13.5v-2h12.586l-3.293-3.293 1.414-1.414 5 5Z"/>
  </svg>
);

const HistorySvg = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M8 1.3335C4.3181 1.3335 1.33333 4.31826 1.33333 8.00016H0L2.04467 10.0448L4.08933 8.00016H2.66667C2.66667 5.05464 5.05448 2.66683 8 2.66683C10.9455 2.66683 13.3333 5.05464 13.3333 8.00016C13.3333 10.9457 10.9455 13.3335 8 13.3335C6.63924 13.3335 5.39905 12.8234 4.456 11.9842L3.56867 12.9802C4.74467 14.0275 6.30038 14.6668 8 14.6668C11.6819 14.6668 14.6667 11.6821 14.6667 8.00016C14.6667 4.31826 11.6819 1.3335 8 1.3335ZM7.33333 4.66683V8.27616L10.4 10.0955L11.0667 8.98616L8.66667 7.56016V4.66683H7.33333Z" fill="currentColor"/>
  </svg>
);

const ArrowUpLeftSvg = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M10.6667 3.3335H5.33334C4.96667 3.3335 4.66667 3.6335 4.66667 4.00016C4.66667 4.36683 4.96667 4.66683 5.33334 4.66683H9.06001L3.52667 10.2002C3.26667 10.4602 3.26667 10.8802 3.52667 11.1402C3.65334 11.2668 3.82001 11.3335 4.00001 11.3335C4.18001 11.3335 4.34667 11.2668 4.47334 11.1402L10 5.60683V9.3335C10 9.70016 10.3 10.0002 10.6667 10.0002C11.0333 10.0002 11.3333 9.70016 11.3333 9.3335V4.00016C11.3333 3.6335 11.0333 3.3335 10.6667 3.3335Z" fill="currentColor"/>
  </svg>
);

const CloseSvg = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M1 1L11 11M11 1L1 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const ScrollChevronLeftSvg = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M12.5 5L7.5 10L12.5 15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" strokeLinejoin="round" />
  </svg>
);

const ScrollChevronRightSvg = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M7.5 5L12.5 10L7.5 15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" strokeLinejoin="round" />
  </svg>
);

function TypeaheadSeparator() {
  return <div className="ld-wcp-responsive-header-desktop-typeahead-separator" />;
}

function TypeaheadHorizontalScrollSection({ children }: { children: React.ReactNode }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateScrollState = useCallback(() => {
    const element = scrollRef.current;
    if (!element) {
      return;
    }
    setCanScrollLeft(element.scrollLeft > 0);
    setCanScrollRight(element.scrollLeft + element.clientWidth < element.scrollWidth - 1);
  }, []);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) {
      return;
    }

    updateScrollState();
    element.addEventListener('scroll', updateScrollState);

    let resizeObserver: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(updateScrollState);
      resizeObserver.observe(element);
    }

    return () => {
      element.removeEventListener('scroll', updateScrollState);
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
    };
  }, [updateScrollState]);

  const scrollBy = (direction: 'left' | 'right') => {
    scrollRef.current?.scrollBy({ left: direction === 'left' ? -220 : 220, behavior: 'smooth' });
  };

  return (
    <div className="ld-wcp-responsive-header-desktop-typeahead-scroll-row">
      {canScrollLeft && (
        <button
          type="button"
          className="ld-wcp-responsive-header-desktop-typeahead-scroll-button"
          aria-label="Scroll left"
          onClick={() => scrollBy('left')}
        >
          <ScrollChevronLeftSvg />
        </button>
      )}

      <div ref={scrollRef} className="ld-wcp-responsive-header-desktop-typeahead-scroll-list">
        {children}
      </div>

      {canScrollRight && (
        <button
          type="button"
          className="ld-wcp-responsive-header-desktop-typeahead-scroll-button"
          aria-label="Scroll right"
          onClick={() => scrollBy('right')}
        >
          <ScrollChevronRightSvg />
        </button>
      )}
    </div>
  );
}

/* ---------- Component ---------- */

type FulfillmentOption = 'none' | 'shipping' | 'pickup' | 'delivery';

const GENLD_EVENT = 'ld-kit-event';

type HeaderCartSnapshot = {
  cartCount: number;
  cartPrice: string;
};

type LdKitCartStateItem = {
  qty?: number;
  priceCents?: number;
};

type LdKitWindowApi = {
  cart?: {
    getSummary?: () => { totalQty?: number; subtotalCents?: number };
    getState?: () => { items?: Record<string, LdKitCartStateItem> };
  };
};

function formatUsdFromCents(cents: number): string {
  const clamped = Number.isFinite(cents) ? Math.max(0, cents) : 0;
  return `$${(clamped / 100).toFixed(2)}`;
}

function normalizePropCartSnapshot(
  cartCountProp?: number,
  cartPriceProp?: string,
): HeaderCartSnapshot {
  return {
    cartCount:
      typeof cartCountProp === 'number' && Number.isFinite(cartCountProp)
        ? Math.max(0, Math.floor(cartCountProp))
        : 0,
    cartPrice: cartPriceProp?.trim() || '$0.00',
  };
}

function readStoreCartSnapshot(): HeaderCartSnapshot | null {
  if (typeof window === 'undefined') return null;

  const ldKit = (window as unknown as { ldKit?: LdKitWindowApi }).ldKit;
  if (!ldKit?.cart) return null;

  const summary = ldKit.cart.getSummary?.();
  if (
    summary &&
    typeof summary.totalQty === 'number' &&
    Number.isFinite(summary.totalQty) &&
    typeof summary.subtotalCents === 'number' &&
    Number.isFinite(summary.subtotalCents)
  ) {
    return {
      cartCount: Math.max(0, Math.floor(summary.totalQty)),
      cartPrice: formatUsdFromCents(summary.subtotalCents),
    };
  }

  const cartState = ldKit.cart.getState?.();
  const items = cartState?.items;
  if (!items) return null;

  let totalQty = 0;
  let subtotalCents = 0;
  for (const item of Object.values(items)) {
    const qty = typeof item.qty === 'number' && Number.isFinite(item.qty) ? item.qty : 0;
    const priceCents =
      typeof item.priceCents === 'number' && Number.isFinite(item.priceCents)
        ? item.priceCents
        : 0;
    totalQty += Math.max(0, qty);
    subtotalCents += Math.max(0, qty) * priceCents;
  }

  return {
    cartCount: Math.floor(totalQty),
    cartPrice: formatUsdFromCents(subtotalCents),
  };
}

function useHeaderCartSnapshot(
  cartCountProp?: number,
  cartPriceProp?: string,
): HeaderCartSnapshot {
  const [snapshot, setSnapshot] = useState<HeaderCartSnapshot>(() => {
    return readStoreCartSnapshot() ?? normalizePropCartSnapshot(cartCountProp, cartPriceProp);
  });

  const syncSnapshot = useCallback(() => {
    const next =
      readStoreCartSnapshot() ?? normalizePropCartSnapshot(cartCountProp, cartPriceProp);
    setSnapshot((prev) =>
      prev.cartCount === next.cartCount && prev.cartPrice === next.cartPrice ? prev : next,
    );
  }, [cartCountProp, cartPriceProp]);

  useEffect(() => {
    syncSnapshot();
  }, [syncSnapshot]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const onGenldEvent = () => syncSnapshot();
    window.addEventListener(GENLD_EVENT, onGenldEvent);
    return () => window.removeEventListener(GENLD_EVENT, onGenldEvent);
  }, [syncSnapshot]);

  return snapshot;
}

interface WCPResponsiveHeaderDesktopProps {
  cartCount?: number;
  cartPrice?: string;
}

function WCPResponsiveHeaderDesktop({ cartCount: cartCountProp, cartPrice: cartPriceProp }: WCPResponsiveHeaderDesktopProps = {}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [recentSearches, setRecentSearches] = useState<string[]>(DEFAULT_RECENT_SEARCHES);
  const [showHighlight, setShowHighlight] = useState(false);
  const [gicOpen, setGicOpen] = useState(false);
  const [selectedFulfillment, setSelectedFulfillment] = useState<FulfillmentOption>('none');
  const [reorderOpen, setReorderOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);

  const searchFormRef = useRef<HTMLDivElement>(null);
  const gicDropdownRef = useRef<HTMLDivElement>(null);
  const reorderDropdownRef = useRef<HTMLDivElement>(null);
  const accountDropdownRef = useRef<HTMLDivElement>(null);

  const { cartCount, cartPrice } = useHeaderCartSnapshot(cartCountProp, cartPriceProp);

  const openDropdown = useCallback((which: 'gic' | 'reorder' | 'account' | null) => {
    emit('ui:header:dropdown', {menu: which ?? 'close'});
    setGicOpen(which === 'gic');
    setReorderOpen(which === 'reorder');
    setAccountOpen(which === 'account');
    if (which === 'gic') setShowHighlight(false);
    if (which !== null) setSearchOpen(false);
  }, []);

  const closeSearchResults = useCallback(() => {
    setSearchOpen(false);
  }, []);

  // Click-outside handler
  useEffect(() => {
    function handleMouseDown(e: MouseEvent) {
      const target = e.target as Node;
      if (searchOpen && searchFormRef.current && !searchFormRef.current.contains(target)) {
        setSearchOpen(false);
      }
      if (gicOpen && gicDropdownRef.current && !gicDropdownRef.current.contains(target)) {
        setGicOpen(false);
      }
      if (reorderOpen && reorderDropdownRef.current && !reorderDropdownRef.current.contains(target)) {
        setReorderOpen(false);
      }
      if (accountOpen && accountDropdownRef.current && !accountDropdownRef.current.contains(target)) {
        setAccountOpen(false);
      }
    }
    document.addEventListener('mousedown', handleMouseDown);
    return () => document.removeEventListener('mousedown', handleMouseDown);
  }, [searchOpen, gicOpen, reorderOpen, accountOpen]);

  // Escape key handler
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        closeSearchResults();
        openDropdown(null);
      }
    }
    if (searchOpen || gicOpen || reorderOpen || accountOpen) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [searchOpen, gicOpen, reorderOpen, accountOpen, closeSearchResults, openDropdown]);

  const filteredSuggestions = filterSearchSuggestions(searchQuery).slice(0, 10);

  function saveRecentSearch(term: string) {
    const normalizedTerm = term.trim();
    if (!normalizedTerm) {
      return;
    }
    setRecentSearches((prev) => [
      normalizedTerm,
      ...prev.filter((search) => search.toLowerCase() !== normalizedTerm.toLowerCase()),
    ].slice(0, 5));
  }

  function handleSearchSubmit(nextQuery: string) {
    const normalizedQuery = nextQuery.trim();
    if (!normalizedQuery) {
      setSearchOpen(true);
      return;
    }
    emit('ui:header:search-submit', {query: normalizedQuery});
    saveRecentSearch(normalizedQuery);
    setSearchOpen(false);
  }

  function handleRecentClick(term: string) {
    setSearchQuery(term);
    saveRecentSearch(term);
    setSearchOpen(true);
  }

  function handleRemoveRecent(index: number) {
    setRecentSearches((prev) => prev.filter((_, rowIndex) => rowIndex !== index));
  }

  function handleChipClick(term: string) {
    setSearchQuery(term);
    saveRecentSearch(term);
    setSearchOpen(true);
  }

  /* GIC button dynamic content */
  const gicLabel = selectedFulfillment === 'none' ? 'Pickup or delivery?'
    : selectedFulfillment === 'shipping' ? 'Shipping'
    : selectedFulfillment === 'pickup' ? 'Pickup'
    : 'Delivery';

  const gicSubtext = selectedFulfillment === 'none' ? (
    <>
      <span>847 Maple Grove Dr</span>
      <span className="ld-wcp-responsive-header-desktop-gic-subtext-dot">&bull;</span>
      <span className="ld-wcp-responsive-header-desktop-gic-subtext-ellipsis">Sunnyvale Supercenter</span>
    </>
  ) : selectedFulfillment === 'pickup' ? (
    <span className="ld-wcp-responsive-header-desktop-gic-subtext-ellipsis">Carrollton Supercenter</span>
  ) : (
    <span>3471 Park Ln</span>
  );

  const gicIconContent = selectedFulfillment === 'none' ? (
    <img src={GIC_ICON} alt="Global Intent" width="40" height="40" className="ld-wcp-responsive-header-desktop-gic-icon-img" />
  ) : selectedFulfillment === 'shipping' ? (
    <FulfillmentShippingSvg />
  ) : selectedFulfillment === 'pickup' ? (
    <img src={PICKUP_ICON} alt="Pickup" width="40" height="40" className="ld-wcp-responsive-header-desktop-gic-icon-img" />
  ) : (
    <img src={DELIVERY_ICON} alt="Delivery" width="40" height="40" className="ld-wcp-responsive-header-desktop-gic-icon-img" />
  );

  /* GIC fulfillment options config */
  const fulfillmentOptions: Array<{ key: 'shipping' | 'pickup' | 'delivery'; label: string; icon: React.ReactNode }> = [
    { key: 'shipping', label: 'Shipping', icon: <FulfillmentShippingSvg /> },
    { key: 'pickup', label: 'Pickup', icon: <img src={PICKUP_ICON} alt="Pickup" width="50" height="50" /> },
    { key: 'delivery', label: 'Delivery', icon: <img src={DELIVERY_ICON} alt="Delivery" width="50" height="50" /> },
  ];

  return (
    <header className="ld-wcp-responsive-header-desktop-view">
      <div className="ld-wcp-responsive-header-desktop-content">
        {/* Brand logo — resolves via --wcp-semantic-media-topNav-logo-compact,
            which themeManager swaps by changing data-ld-theme on <html>. */}
        <a
          href="#"
          className="ld-wcp-responsive-header-desktop-logo"
          aria-label="Homepage"
        >
          <span className="ld-wcp-responsive-header-desktop-logo-img" aria-hidden="true" />
        </a>

        {/* GIC: Location / Delivery selector */}
        <div className="ld-wcp-responsive-header-desktop-gic-wrap" ref={gicDropdownRef}>
          <div className={`ld-wcp-responsive-header-desktop-gic-section${gicOpen ? ' ld-wcp-responsive-header-desktop-gic-section-active' : ''}`}>
            <button
              type="button"
              className="ld-wcp-responsive-header-desktop-gic-button"
              onClick={() => openDropdown(gicOpen ? null : 'gic')}
            >
              <div className="ld-wcp-responsive-header-desktop-gic-icon">
                {gicIconContent}
              </div>
              <div className="ld-wcp-responsive-header-desktop-gic-text">
                <div className="ld-wcp-responsive-header-desktop-gic-label">{gicLabel}</div>
                <div className="ld-wcp-responsive-header-desktop-gic-subtext">
                  {gicSubtext}
                </div>
              </div>
              <div className={`ld-wcp-responsive-header-desktop-gic-chevron${gicOpen ? ' ld-wcp-responsive-header-desktop-gic-chevron-open' : ''}`}>
                <Icon name="ChevronDown" className="ld-wcp-responsive-header-desktop-gic-chevron-icon" />
              </div>
            </button>
          </div>

          {/* Highlight Callout */}
          {showHighlight && !gicOpen && (
            <div
              role="status"
              aria-live="polite"
              className="ld-wcp-responsive-header-desktop-highlight"
            >
              <div className="ld-wcp-responsive-header-desktop-highlight-nubbin" />
              <div className="ld-wcp-responsive-header-desktop-highlight-icon">
                <svg width="28" height="28" viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                  <path d="M36 4.5C42.2657 4.5 48.2753 6.98864 52.7058 11.4192C57.1364 15.8497 59.625 21.8593 59.625 28.125C59.625 51.75 36 67.5 36 67.5C36 67.5 12.375 51.75 12.375 28.125C12.375 21.8593 14.8636 15.8497 19.2942 11.4192C23.7247 6.98864 29.7343 4.5 36 4.5ZM36 15.75C29.1655 15.75 23.625 21.2905 23.625 28.125C23.625 34.9595 29.1655 40.5 36 40.5C42.8345 40.5 48.375 34.9595 48.375 28.125C48.375 21.2905 42.8345 15.75 36 15.75Z" fill="#C7DBFF" />
                  <path d="M36 40.5C42.8345 40.5 48.375 34.9595 48.375 28.125C48.375 21.2905 42.8345 15.75 36 15.75C29.1655 15.75 23.625 21.2905 23.625 28.125C23.625 34.9595 29.1655 40.5 36 40.5Z" fill="#4DBDF5" />
                </svg>
              </div>
              <div className="ld-wcp-responsive-header-desktop-highlight-text">
                Is this the right location?
              </div>
              <button
                onClick={() => setShowHighlight(false)}
                className="ld-wcp-responsive-header-desktop-highlight-update-btn"
              >
                Update
              </button>
              <button
                type="button"
                onClick={() => setShowHighlight(false)}
                aria-label="Dismiss location prompt"
                className="ld-wcp-responsive-header-desktop-highlight-close-btn"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                  <path d="M1 1L11 11M11 1L1 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </button>
            </div>
          )}

          {/* GIC Dropdown */}
          {gicOpen && (
            <>
              <div className="ld-wcp-responsive-header-desktop-scrim" onClick={() => openDropdown(null)} />
              <div className="ld-wcp-responsive-header-desktop-gic-dropdown">
                {/* Fulfillment options section */}
                <div className="ld-wcp-responsive-header-desktop-gic-options-section">
                  <div className="ld-wcp-responsive-header-desktop-gic-options-list">
                    {fulfillmentOptions.map((opt) => (
                      <button
                        key={opt.key}
                        type="button"
                        className="ld-wcp-responsive-header-desktop-gic-option-btn"
                        onClick={() => { const next = selectedFulfillment === opt.key ? 'none' : opt.key; emit('ui:header:fulfillment', {selection: next}); setSelectedFulfillment(next); }}
                      >
                        <div className="ld-wcp-responsive-header-desktop-gic-option-icon-wrap">
                          {opt.icon}
                          {selectedFulfillment === opt.key && (
                            <>
                              <svg
                                className="ld-wcp-responsive-header-desktop-gic-selection-ring"
                                viewBox="0 0 64 64"
                                fill="none"
                                xmlns="http://www.w3.org/2000/svg"
                                aria-hidden="true"
                              >
                                <circle cx="32" cy="32" r="30" stroke="currentColor" strokeWidth="4" />
                              </svg>
                              <button
                                type="button"
                                onClick={(e) => { e.stopPropagation(); setSelectedFulfillment('none'); }}
                                className="ld-wcp-responsive-header-desktop-gic-deselect-btn"
                                aria-label={`Deselect ${opt.label}`}
                              >
                                <span className="ld-wcp-responsive-header-desktop-gic-deselect-badge">
                                  <svg className="ld-wcp-responsive-header-desktop-gic-deselect-circle" viewBox="0 0 21 21" fill="currentColor" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                                    <circle cx="10.5" cy="10.5" r="10.5" />
                                  </svg>
                                  <span className="ld-wcp-responsive-header-desktop-gic-deselect-x" aria-hidden="true">
                                    <svg width="9" height="9" viewBox="0 0 9 9" fill="none" xmlns="http://www.w3.org/2000/svg">
                                      <path fillRule="evenodd" clipRule="evenodd" d="M1.20967 0.157278C0.915456 -0.0714902 0.490033 -0.0506931 0.21967 0.21967C-0.0732233 0.512563 -0.0732233 0.987437 0.21967 1.28033L3.43934 4.5L0.21967 7.71967C-0.0732229 8.01256 -0.0732229 8.48744 0.21967 8.78033C0.490033 9.05069 0.915456 9.07149 1.20967 8.84272L1.28033 8.78033L4.5 5.56066L7.71967 8.78033L7.79033 8.84272C8.08454 9.07149 8.50997 9.05069 8.78033 8.78033C9.07322 8.48744 9.07322 8.01256 8.78033 7.71967L5.56066 4.5L8.78033 1.28033C9.07322 0.987437 9.07322 0.512563 8.78033 0.21967C8.50997 -0.0506931 8.08454 -0.0714902 7.79033 0.157278L7.71967 0.21967L4.5 3.43934L1.28033 0.21967L1.20967 0.157278Z" fill="currentColor" />
                                    </svg>
                                  </span>
                                </span>
                              </button>
                            </>
                          )}
                        </div>
                        <span className="ld-wcp-responsive-header-desktop-gic-option-label">{opt.label}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Address & store cards */}
                <div className="ld-wcp-responsive-header-desktop-gic-cards-section">
                  <div className="ld-wcp-responsive-header-desktop-gic-cards-list">
                    <button type="button" className="ld-wcp-responsive-header-desktop-gic-card">
                      <LocationSvg />
                      <span className="ld-wcp-responsive-header-desktop-gic-card-text-single">
                        1213 E Trinity Mills Rd, Dallas, TX 75220
                      </span>
                      <ChevronRightSvg />
                    </button>
                    <button type="button" className="ld-wcp-responsive-header-desktop-gic-card">
                      <StoreSvg />
                      <div className="ld-wcp-responsive-header-desktop-gic-card-text-stack">
                        <span className="ld-wcp-responsive-header-desktop-gic-card-store-name">Carrollton Supercenter</span>
                        <span className="ld-wcp-responsive-header-desktop-gic-card-store-addr">1213 E Trinity Mills Rd, Dallas, TX 75220</span>
                      </div>
                      <ChevronRightSvg />
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Search Form */}
        <div
          ref={searchFormRef}
          className={`ld-wcp-responsive-header-desktop-search-form-wrap${searchOpen ? ' ld-wcp-responsive-header-desktop-search-form-wrap-focused' : ''}`}
        >
          <form
            className="ld-wcp-responsive-header-desktop-search-form"
            role="search"
            aria-label="Walmart Site-Wide"
            onSubmit={(e) => {
              e.preventDefault();
              handleSearchSubmit(searchQuery);
            }}
          >
            <div className={`ld-wcp-responsive-header-desktop-search-input-wrap${searchOpen ? ' ld-wcp-responsive-header-desktop-search-input-wrap-active' : ''}`}>
              <input
                type="search"
                name="q"
                placeholder="Search everything at Walmart online and in store"
                aria-label="Search"
                autoComplete="off"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => {
                  openDropdown(null);
                  setSearchOpen(true);
                }}
                onClick={() => setSearchOpen(true)}
                className="ld-wcp-responsive-header-desktop-search-input"
              />
              <div className="ld-wcp-responsive-header-desktop-search-actions">
                {searchQuery.trim() ? (
                  <button
                    type="button"
                    className="ld-wcp-responsive-header-desktop-search-clear-button"
                    aria-label="Clear search"
                    onClick={() => {
                      setSearchQuery('');
                      setSearchOpen(true);
                    }}
                  >
                    <CloseSvg />
                  </button>
                ) : (
                  <button
                    type="button"
                    className="ld-wcp-responsive-header-desktop-search-button"
                    aria-label="Search"
                    onClick={() => {
                      setSearchOpen(true);
                    }}
                  >
                    <Icon name="Search" className="ld-wcp-responsive-header-desktop-search-icon" />
                  </button>
                )}
              </div>
            </div>
          </form>
          {searchOpen && (
            <>
              <div className="ld-wcp-responsive-header-desktop-search-scrim" onClick={closeSearchResults} />
              <div className="ld-wcp-responsive-header-desktop-search-results" role="listbox" aria-label="Search suggestions">
                {searchQuery.trim() ? (
                  filteredSuggestions.length > 0 ? (
                    filteredSuggestions.map((suggestion, index) => {
                      const parts = highlightSuggestionParts(suggestion, searchQuery);
                      return (
                        <button
                          key={`${suggestion}-${index}`}
                          type="button"
                          className="ld-wcp-responsive-header-desktop-search-result-row"
                          onClick={() => {
                            setSearchQuery(suggestion);
                            handleSearchSubmit(suggestion);
                          }}
                        >
                          <span className="ld-wcp-responsive-header-desktop-search-result-text">
                            {parts.before && <span className="ld-wcp-responsive-header-desktop-search-result-strong">{parts.before}</span>}
                            <span>{parts.match || suggestion}</span>
                            {parts.after && <span className="ld-wcp-responsive-header-desktop-search-result-strong">{parts.after}</span>}
                          </span>
                          <span className="ld-wcp-responsive-header-desktop-search-result-icon">
                            <ArrowUpLeftSvg />
                          </span>
                        </button>
                      );
                    })
                  ) : (
                    <div className="ld-wcp-responsive-header-desktop-search-empty-state">
                      No matching suggestions found.
                    </div>
                  )
                ) : (
                  <>
                    <section className="ld-wcp-responsive-header-desktop-typeahead-section">
                      <h3 className="ld-wcp-responsive-header-desktop-typeahead-section-heading">
                        Keep shopping for {KEEP_SHOPPING_CATEGORY}
                      </h3>
                      <TypeaheadHorizontalScrollSection>
                        {KEEP_SHOPPING_FOR.map((item) => (
                          <button
                            key={item.label}
                            type="button"
                            className="ld-wcp-responsive-header-desktop-typeahead-tile-button"
                            onClick={() => handleChipClick(item.label)}
                          >
                            {item.isFilter ? (
                              <div className="ld-wcp-responsive-header-desktop-typeahead-tile-filter">
                                <span className="ld-wcp-responsive-header-desktop-typeahead-tile-filter-label">{item.label}</span>
                              </div>
                            ) : (
                              <div className="ld-wcp-responsive-header-desktop-typeahead-tile-image">
                                <img src={item.image ?? ''} alt={item.label} className="ld-wcp-responsive-header-desktop-typeahead-tile-image-img" />
                              </div>
                            )}
                            <span className="ld-wcp-responsive-header-desktop-typeahead-tile-label">{item.label}</span>
                          </button>
                        ))}
                      </TypeaheadHorizontalScrollSection>
                    </section>

                    <TypeaheadSeparator />

                    <section className="ld-wcp-responsive-header-desktop-typeahead-section-padded">
                      <div className="ld-wcp-responsive-header-desktop-typeahead-section-heading-row">
                        <h3 className="ld-wcp-responsive-header-desktop-typeahead-section-heading" style={{ margin: 0 }}>
                          Grab your usuals
                        </h3>
                        <button type="button" className="ld-wcp-responsive-header-desktop-typeahead-my-items-link">
                          <span className="ld-wcp-responsive-header-desktop-typeahead-my-items-icon">
                            <HeartSvg />
                          </span>
                          My items
                        </button>
                      </div>
                      <TypeaheadHorizontalScrollSection>
                        {GRAB_YOUR_USUALS.map((term) => (
                          <button
                            key={term}
                            type="button"
                            className="ld-wcp-responsive-header-desktop-typeahead-chip-button"
                            onClick={() => handleChipClick(term)}
                          >
                            <span className="ld-wcp-responsive-header-desktop-typeahead-chip-label">{term}</span>
                          </button>
                        ))}
                      </TypeaheadHorizontalScrollSection>
                    </section>

                    <TypeaheadSeparator />

                    {recentSearches.length > 0 && (
                      <>
                        <section className="ld-wcp-responsive-header-desktop-typeahead-section-padded">
                          <h3 className="ld-wcp-responsive-header-desktop-typeahead-section-heading">Your recent searches</h3>
                          <div>
                            {recentSearches.map((search, index) => (
                              <React.Fragment key={`${search}-${index}`}>
                                <div className="ld-wcp-responsive-header-desktop-search-recent-row">
                                  <span className="ld-wcp-responsive-header-desktop-search-recent-icon">
                                    <HistorySvg />
                                  </span>
                                  <button
                                    type="button"
                                    className="ld-wcp-responsive-header-desktop-search-recent-term"
                                    onClick={() => handleRecentClick(search)}
                                  >
                                    {search}
                                  </button>
                                  <button
                                    type="button"
                                    className="ld-wcp-responsive-header-desktop-search-recent-remove"
                                    aria-label={`Remove ${search}`}
                                    onClick={() => handleRemoveRecent(index)}
                                  >
                                    <CloseSvg />
                                  </button>
                                </div>
                                {index < recentSearches.length - 1 && <TypeaheadSeparator />}
                              </React.Fragment>
                            ))}
                          </div>
                        </section>
                        <TypeaheadSeparator />
                      </>
                    )}

                    <section className="ld-wcp-responsive-header-desktop-typeahead-section-padded">
                      <h3 className="ld-wcp-responsive-header-desktop-typeahead-section-heading">Trending</h3>
                      <TypeaheadHorizontalScrollSection>
                        {TRENDING_SEARCHES.map((term) => (
                          <button
                            key={term}
                            type="button"
                            className="ld-wcp-responsive-header-desktop-typeahead-chip-button"
                            onClick={() => handleChipClick(term)}
                          >
                            <span className="ld-wcp-responsive-header-desktop-typeahead-chip-label">{term}</span>
                          </button>
                        ))}
                      </TypeaheadHorizontalScrollSection>
                    </section>

                    <TypeaheadSeparator />

                    <section className="ld-wcp-responsive-header-desktop-typeahead-section-padded">
                      <h3 className="ld-wcp-responsive-header-desktop-typeahead-section-heading">Your frequent searches</h3>
                      <TypeaheadHorizontalScrollSection>
                        {FREQUENT_SEARCHES.map((term) => (
                          <button
                            key={term}
                            type="button"
                            className="ld-wcp-responsive-header-desktop-typeahead-chip-button"
                            onClick={() => handleChipClick(term)}
                          >
                            <span className="ld-wcp-responsive-header-desktop-typeahead-chip-label">{term}</span>
                          </button>
                        ))}
                      </TypeaheadHorizontalScrollSection>
                    </section>
                  </>
                )}
              </div>
            </>
          )}
        </div>

        {/* Navigation */}
        <nav aria-label="Account and Cart" className="ld-wcp-responsive-header-desktop-nav">
          <ul className="ld-wcp-responsive-header-desktop-nav-list">
            {/* Reorder / My Items */}
            <li>
              <div className="ld-wcp-responsive-header-desktop-dropdown-root" ref={reorderDropdownRef}>
                <button
                  type="button"
                  className="ld-wcp-responsive-header-desktop-nav-button"
                  aria-haspopup="true"
                  aria-expanded={reorderOpen}
                  onClick={() => openDropdown(reorderOpen ? null : 'reorder')}
                >
                  <HeartSvg />
                  <div className="ld-wcp-responsive-header-desktop-nav-content">
                    <div className="ld-wcp-responsive-header-desktop-nav-subtext">Reorder</div>
                    <div className="ld-wcp-responsive-header-desktop-nav-label">My Items</div>
                  </div>
                </button>

                {reorderOpen && (
                  <div className="ld-wcp-responsive-header-desktop-dropdown-panel ld-wcp-responsive-header-desktop-dropdown-panel-left" role="menu" aria-label="Reorder and My Items">
                    <button type="button" role="menuitem" className="ld-wcp-responsive-header-desktop-dropdown-item" onClick={() => openDropdown(null)}>
                      <ReorderSvg />
                      <span className="ld-wcp-responsive-header-desktop-dropdown-item-label">Reorder</span>
                    </button>
                    <button type="button" role="menuitem" className="ld-wcp-responsive-header-desktop-dropdown-item" onClick={() => openDropdown(null)}>
                      <ListsSvg />
                      <span className="ld-wcp-responsive-header-desktop-dropdown-item-label">Lists</span>
                    </button>
                    <button type="button" role="menuitem" className="ld-wcp-responsive-header-desktop-dropdown-item" onClick={() => openDropdown(null)}>
                      <GiftSvg />
                      <span className="ld-wcp-responsive-header-desktop-dropdown-item-label">Registries</span>
                    </button>
                  </div>
                )}
              </div>
            </li>

            {/* Account */}
            <li>
              <div className="ld-wcp-responsive-header-desktop-dropdown-root" ref={accountDropdownRef}>
                <button
                  type="button"
                  className="ld-wcp-responsive-header-desktop-nav-button"
                  aria-haspopup="true"
                  aria-expanded={accountOpen}
                  onClick={() => openDropdown(accountOpen ? null : 'account')}
                >
                  <UserSvg />
                  <div className="ld-wcp-responsive-header-desktop-nav-content">
                    <div className="ld-wcp-responsive-header-desktop-nav-subtext">Hi, Emilia</div>
                    <div className="ld-wcp-responsive-header-desktop-nav-label">Account</div>
                  </div>
                </button>

                {accountOpen && (
                  <div className="ld-wcp-responsive-header-desktop-dropdown-panel ld-wcp-responsive-header-desktop-dropdown-panel-right" role="menu" aria-label="Account navigation">
                    <button type="button" role="menuitem" className="ld-wcp-responsive-header-desktop-dropdown-item" onClick={() => openDropdown(null)}>
                      <PurchaseHistorySvg />
                      <span className="ld-wcp-responsive-header-desktop-dropdown-item-label">Purchase History</span>
                    </button>
                    <button type="button" role="menuitem" className="ld-wcp-responsive-header-desktop-dropdown-item" onClick={() => openDropdown(null)}>
                      <WalmartPlusLogoSvg />
                      <span className="ld-wcp-responsive-header-desktop-dropdown-item-label">Walmart+</span>
                    </button>
                    <button type="button" role="menuitem" className="ld-wcp-responsive-header-desktop-dropdown-item" onClick={() => openDropdown(null)}>
                      <UserSvg />
                      <span className="ld-wcp-responsive-header-desktop-dropdown-item-label">Account</span>
                    </button>
                    <button type="button" role="menuitem" className="ld-wcp-responsive-header-desktop-dropdown-item" onClick={() => openDropdown(null)}>
                      <SubscriptionSvg />
                      <span className="ld-wcp-responsive-header-desktop-dropdown-item-label">Subscriptions</span>
                    </button>
                    <button type="button" role="menuitem" className="ld-wcp-responsive-header-desktop-dropdown-item" onClick={() => openDropdown(null)}>
                      <WalmartCashSvg />
                      <span className="ld-wcp-responsive-header-desktop-dropdown-item-label">Get Walmart Cash</span>
                    </button>
                    <div className="ld-wcp-responsive-header-desktop-dropdown-separator" role="separator" />
                    <button type="button" role="menuitem" className="ld-wcp-responsive-header-desktop-dropdown-item" onClick={() => openDropdown(null)}>
                      <GlobeSvg />
                      <span className="ld-wcp-responsive-header-desktop-dropdown-item-label">Language | English</span>
                    </button>
                    <div className="ld-wcp-responsive-header-desktop-dropdown-separator" role="separator" />
                    <button type="button" role="menuitem" className="ld-wcp-responsive-header-desktop-dropdown-item" onClick={() => openDropdown(null)}>
                      <SignOutSvg />
                      <span className="ld-wcp-responsive-header-desktop-dropdown-item-label">Sign Out</span>
                    </button>
                  </div>
                )}
              </div>
            </li>

            {/* Cart */}
            <li>
              <a href="#" className="ld-wcp-responsive-header-desktop-nav-button-cart" aria-label={`Cart contains ${cartCount} items`}>
                <CartIcon count={cartCount} price={cartPrice} textColor="var(--ld-semantic-color-topNav-text-onFill, white)" />
              </a>
            </li>
          </ul>
        </nav>
      </div>
    </header>
  );
}
WCPResponsiveHeaderDesktop.displayName = 'WCPHeaderDesktop';


/* ========================================================================= */
/*                              MOBILE VIEW                                  */
/* ========================================================================= */


/**
 * MobileHeader - WCP pattern helper (demo only).
 *
 * Faithful visual replica of the Walmart mobile header.
 * Two-row layout: logo + cart on row 1, search bar on row 2.
 */

/* ---------- Inline CartIcon matching original ---------- */

function MobileCartIcon({ count = 0, price = '$0.00', textColor = 'white' }: { count?: number; price?: string; textColor?: string }) {
  return (
    <div className="ld-wcp-responsive-header-mobile-cart-icon-wrap">
      <div className="ld-wcp-responsive-header-mobile-cart-icon-relative">
        <Icon name="Cart" style={{ fontSize: 24, color: textColor }} />
        <div className="ld-wcp-responsive-header-mobile-cart-badge">
          {count > 99 ? '99+' : count}
        </div>
      </div>
      <div className="ld-wcp-responsive-header-mobile-cart-price" style={{ color: textColor }}>
        {price}
      </div>
    </div>
  );
}

/* ---------- Component ---------- */

interface WCPResponsiveHeaderMobileProps {
  cartCount?: number;
  cartPrice?: string;
}

function WCPResponsiveHeaderMobile({ cartCount: cartCountProp, cartPrice: cartPriceProp }: WCPResponsiveHeaderMobileProps = {}) {
  const [searchQuery, setSearchQuery] = useState('');
  const { cartCount, cartPrice } = useHeaderCartSnapshot(cartCountProp, cartPriceProp);

  return (
    <header className="ld-wcp-responsive-header-mobile-view">
      {/* Row 1: Logo + Cart */}
      <div className="ld-wcp-responsive-header-mobile-row1">
        <a href="#" className="ld-wcp-responsive-header-mobile-logo-link" aria-label="Homepage">
          <span className="ld-wcp-responsive-header-mobile-logo-img" aria-hidden="true" />
        </a>
        <a
          href="#"
          className="ld-wcp-responsive-header-mobile-cart-link"
          aria-label={`Cart contains ${cartCount} items`}
        >
          <MobileCartIcon count={cartCount} price={cartPrice} textColor="var(--ld-semantic-color-text-inverse, white)" />
        </a>
      </div>

      {/* Row 2: Search bar (white pill, icon + input) matching source MobileHeader.module.css */}
      <form
        role="search"
        aria-label="Search Walmart"
        onSubmit={(e) => { e.preventDefault(); emit('ui:header:search-submit', {query: searchQuery}); }}
        className="ld-wcp-responsive-header-mobile-search-form"
      >
        <div className="ld-wcp-responsive-header-mobile-search-pill">
          <Icon name="Search" className="ld-wcp-responsive-header-mobile-search-icon" style={{ fontSize: 16 }} />
          <input
            type="search"
            placeholder="Search everything at Walmart online and in store"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search Walmart"
            className="ld-wcp-responsive-header-mobile-search-input"
          />
          {searchQuery.trim() && (
            <button
              type="button"
              className="ld-wcp-responsive-header-mobile-search-clear"
              aria-label="Clear search"
              onClick={() => setSearchQuery('')}
            >
              <CloseSvg />
            </button>
          )}
        </div>
      </form>
    </header>
  );
}
WCPResponsiveHeaderMobile.displayName = 'WCPHeaderMobile';


/* ========================================================================= */
/*                              MOBILE TOP NAV                               */
/* ========================================================================= */

/* ---------- CDN assets ---------- */



/* ---------- Sub-nav chip data ---------- */

const subNavLinks = [
  'Departments',
  'Services',
  'Get it Fast',
  'Rollbacks & More',
  'Easter',
  'Pharmacy',
  'New Arrivals',
  'Dinner Made Easy',
  'Walmart+',
];

/* ---------- Inline CartIcon matching original ---------- */

function TopNavCartIcon({ count = 0, price = '$0.00' }: { count?: number; price?: string }) {
  return (
    <div className="ld-wcp-responsive-header-mobile-topnav-cart-wrap">
      <div className="ld-wcp-responsive-header-mobile-topnav-cart-icon-wrap">
        <Icon name="Cart" style={{ fontSize: 24 }} />
        <div className="ld-wcp-responsive-header-mobile-topnav-cart-badge">
          {count}
        </div>
      </div>
      <div className="ld-wcp-responsive-header-mobile-topnav-cart-price">
        {price}
      </div>
    </div>
  );
}

/* ---------- Types ---------- */

export type WCPResponsiveHeaderMobileTopNavVariant = 'blue' | 'white';

interface WCPResponsiveHeaderMobileTopNavProps {
  variant?: WCPResponsiveHeaderMobileTopNavVariant;
  showDeliveryBanner?: boolean;
  cartCount?: number;
  cartPrice?: string;
}

/* ---------- Component ---------- */



function WCPResponsiveHeaderMobileTopNav({
  variant = 'blue',
  showDeliveryBanner = false,
  cartCount: cartCountProp,
  cartPrice: cartPriceProp,
}: WCPResponsiveHeaderMobileTopNavProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const { cartCount, cartPrice } = useHeaderCartSnapshot(cartCountProp, cartPriceProp);

  const variantClass = variant === 'blue'
    ? 'ld-wcp-responsive-header-mobile-topnav-blue'
    : 'ld-wcp-responsive-header-mobile-topnav-white';

  return (
    <div className={cx('ld-wcp-responsive-header-mobile-view ld-wcp-responsive-header-mobile-topnav', variantClass)}>
      {/* Top bar */}
      <div className="ld-wcp-responsive-header-mobile-topnav-topbar">
        {/* Left: hamburger + logo */}
        <div className="ld-wcp-responsive-header-mobile-topnav-left">
          <button
            type="button"
            className="ld-wcp-responsive-header-mobile-topnav-hamburger"
            aria-label="Menu"
            onClick={() => {}}
          >
            <Icon name="Menu" className="ld-wcp-responsive-header-mobile-topnav-hamburger-icon" style={{ fontSize: 32 }} />
          </button>
          <a href="#" aria-label="Homepage" className="ld-wcp-responsive-header-mobile-topnav-logo-link">
            <span className="ld-wcp-responsive-header-mobile-topnav-logo-img" aria-hidden="true" />
          </a>
        </div>

        {/* Center: search pill */}
        <form
          className="ld-wcp-responsive-header-mobile-topnav-search-pill"
          role="search"
          aria-label="Search Walmart"
          onSubmit={(e) => { e.preventDefault(); emit('ui:header:search-submit', {query: searchQuery}); }}
        >
          <input
            type="search"
            placeholder="Search Walmart"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search Walmart"
            className="ld-wcp-responsive-header-mobile-topnav-search-input"
          />
          {searchQuery.trim() && (
            <button
              type="button"
              className="ld-wcp-responsive-header-mobile-topnav-search-clear"
              aria-label="Clear search"
              onClick={() => setSearchQuery('')}
            >
              <CloseSvg />
            </button>
          )}
          <button type="submit" className="ld-wcp-responsive-header-mobile-topnav-search-btn" aria-label="Search">
            <Icon name="Search" className="ld-wcp-responsive-header-mobile-topnav-search-icon" style={{ fontSize: 14 }} />
          </button>
        </form>

        {/* Right: cart */}
        <TopNavCartIcon count={cartCount} price={cartPrice} />
      </div>

      {/* Delivery banner */}
      {showDeliveryBanner && (
        <div className="ld-wcp-responsive-header-mobile-topnav-delivery-wrap">
          <button className="ld-wcp-responsive-header-mobile-topnav-delivery-btn">
            <div className="ld-wcp-responsive-header-mobile-topnav-delivery-inner">
              <img
                src={GIC_ICON}
                alt="Global Intent"
                width="24"
                height="24"
                className="ld-wcp-responsive-header-mobile-topnav-gic-icon"
              />
              <span className="ld-wcp-responsive-header-mobile-topnav-delivery-text">
                How do you want your items?
              </span>
            </div>
            <Icon name="ChevronDown" className="ld-wcp-responsive-header-mobile-topnav-chevron-icon" style={{ fontSize: 20 }} />
          </button>
        </div>
      )}

    </div>
  );
}
WCPResponsiveHeaderMobileTopNav.displayName = 'WCPHeaderMobileTopNav';


/* ========================================================================= */
/*                              WRAPPER COMPONENT                            */
/* ========================================================================= */

export type MobileHeaderVariant = 'classic' | 'topnav-blue' | 'topnav-white';

export interface WCPHeaderProps {
  cartCount?: number;
  cartPrice?: string;
  mobileVariant?: MobileHeaderVariant;
  showMobileSubNav?: boolean;
  showMobileDeliveryBanner?: boolean;
}

export function WCPHeader({
  cartCount,
  cartPrice,
  mobileVariant = 'classic',
  showMobileSubNav = true,
  showMobileDeliveryBanner = false,
}: WCPHeaderProps) {
  const commonProps = { cartCount, cartPrice };
  return (
    <div className="ld-wcp-responsive-header-root">
      <WCPResponsiveHeaderDesktop {...commonProps} />
      {mobileVariant === 'classic' ? (
        <WCPResponsiveHeaderMobile {...commonProps} />
      ) : (
        <WCPResponsiveHeaderMobileTopNav
          {...commonProps}
          variant={mobileVariant === 'topnav-blue' ? 'blue' : 'white'} 
          showDeliveryBanner={showMobileDeliveryBanner}
        />
      )}
      {showMobileSubNav && mobileVariant !== 'classic' && (
        <div className="ld-wcp-responsive-header-mobile-category-nav">
          <CategoryNav />
        </div>
      )}
    </div>
  );
}
WCPHeader.displayName = 'WCPHeader';
