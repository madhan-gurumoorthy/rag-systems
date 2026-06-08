'use client';
// @refresh reset

/**
 * @module LivingDesignIconsFont
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
import {useEffect} from 'react';
import type {CSSProperties} from 'react';

export const LD_ICON_CODEPOINTS: Record<string, string> = {
  ArrowDown: '\uf188',
  ArrowLeft: '\uf187',
  ArrowRight: '\uf186',
  ArrowUp: '\uf185',
  Article: '\uf184',
  Ban: '\uf183',
  Barcode: '\uf182',
  Bell: '\uf181',
  Bluetooth: '\uf180',
  Bookmark: '\uf17f',
  BookmarkFill: '\uf17e',
  Box: '\uf17d',
  Calendar: '\uf17c',
  Camera: '\uf17b',
  Car: '\uf17a',
  Card: '\uf179',
  CaretDown: '\uf178',
  CaretUp: '\uf177',
  Chat: '\uf176',
  Check: '\uf175',
  CheckCircle: '\uf174',
  CheckCircleFill: '\uf173',
  ChevronDown: '\uf172',
  ChevronLeft: '\uf171',
  ChevronRight: '\uf170',
  ChevronUp: '\uf16f',
  Clock: '\uf16e',
  Close: '\uf16d',
  CloseCircleFill: '\uf16c',
  CloudDownload: '\uf16b',
  CloudUpload: '\uf16a',
  Copy: '\uf169',
  CurrentLocation: '\uf168',
  Dollar: '\uf167',
  DollarCircle: '\uf166',
  DollarCircleFill: '\uf165',
  Download: '\uf164',
  Email: '\uf163',
  ExclamationCircle: '\uf162',
  ExclamationCircleFill: '\uf161',
  Eye: '\uf160',
  EyeSlash: '\uf15f',
  Facility: '\uf15e',
  FacilityFill: '\uf15d',
  Filter: '\uf15c',
  Flag: '\uf15b',
  FlagFill: '\uf15a',
  Flash: '\uf159',
  FlashFill: '\uf158',
  FlashSlash: '\uf157',
  Gear: '\uf156',
  Gift: '\uf155',
  GiftFill: '\uf154',
  Globe: '\uf153',
  Grid: '\uf152',
  GridFill: '\uf151',
  Heart: '\uf150',
  HeartFill: '\uf14f',
  History: '\uf14e',
  Home: '\uf14d',
  IdCard: '\uf14c',
  Image: '\uf14b',
  InfoCircle: '\uf14a',
  InfoCircleFill: '\uf149',
  Keyboard: '\uf148',
  Link: '\uf147',
  LinkExternal: '\uf146',
  List: '\uf145',
  Location: '\uf144',
  Lock: '\uf143',
  LockOpen: '\uf142',
  Magic: '\uf141',
  MagicFill: '\uf140',
  Map: '\uf13f',
  MapFill: '\uf13e',
  Maximize: '\uf13d',
  Menu: '\uf13c',
  Microphone: '\uf13b',
  MicrophoneSlash: '\uf13a',
  Minimize: '\uf139',
  Minus: '\uf138',
  Mobile: '\uf137',
  More: '\uf136',
  MoreAlt: '\uf135',
  Note: '\uf134',
  Notebook: '\uf133',
  Pause: '\uf132',
  Pencil: '\uf131',
  Phone: '\uf130',
  Play: '\uf12f',
  PlayFill: '\uf12e',
  Plus: '\uf12d',
  Printer: '\uf12c',
  QrCode: '\uf12b',
  QuestionCircle: '\uf12a',
  Receipt: '\uf129',
  Refresh: '\uf128',
  Returns: '\uf127',
  Search: '\uf126',
  Services: '\uf125',
  ServicesFill: '\uf124',
  Share: '\uf123',
  ShareAndroid: '\uf122',
  SignIn: '\uf121',
  SignOut: '\uf120',
  Sliders: '\uf11f',
  Speaker: '\uf11e',
  SpeakerSlash: '\uf11d',
  Star: '\uf11c',
  StarFill: '\uf11b',
  StarHalf: '\uf11a',
  Tag: '\uf119',
  TagFill: '\uf118',
  ThumbDown: '\uf117',
  ThumbDownFill: '\uf116',
  ThumbUp: '\uf115',
  ThumbUpFill: '\uf114',
  Trash: '\uf113',
  Truck: '\uf112',
  Undo: '\uf111',
  User: '\uf110',
  UserCircle: '\uf10f',
  UserCircleFill: '\uf10e',
  UserPlus: '\uf10d',
  Users: '\uf10c',
  Video: '\uf10b',
  Voice: '\uf10a',
  Wallet: '\uf109',
  Warning: '\uf108',
  WarningFill: '\uf107',
  WiFi: '\uf106',
  WifiSlash: '\uf105',
  Wrench: '\uf104',
  Write: '\uf103',
  ZoomIn: '\uf102',
  ZoomOut: '\uf101',
};

let _useLivingDesignIconsFontInjected = false;

export const useLivingDesignIconsFont = () => {
  useEffect(() => {
    if (_useLivingDesignIconsFontInjected || typeof document === 'undefined') {
      return;
    }

    _useLivingDesignIconsFontInjected = true;
    const LD_ICONS_WOFF2_BASE64 = "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";

    const style = document.createElement('style');
    style.setAttribute('data-ld-portable-font', 'living-design-icons');
    style.textContent = `
      @font-face {
        font-display: swap;
        font-family: 'LivingDesign';
        font-style: normal;
        src: url('data:font/woff2;base64,${LD_ICONS_WOFF2_BASE64}') format('woff2');
      }
      .ld {
        -moz-osx-font-smoothing: grayscale;
        -webkit-font-smoothing: antialiased;
        display: inline-block;
        font: normal normal normal 16px/1 LivingDesign;
        font-size: inherit;
      }
      .ld.ld-ArrowDown:before{content:"\\f188"}.ld.ld-ArrowLeft:before{content:"\\f187"}.ld.ld-ArrowRight:before{content:"\\f186"}.ld.ld-ArrowUp:before{content:"\\f185"}.ld.ld-Article:before{content:"\\f184"}.ld.ld-Ban:before{content:"\\f183"}.ld.ld-Barcode:before{content:"\\f182"}.ld.ld-Bell:before{content:"\\f181"}.ld.ld-Bluetooth:before{content:"\\f180"}.ld.ld-Bookmark:before{content:"\\f17f"}.ld.ld-BookmarkFill:before{content:"\\f17e"}.ld.ld-Box:before{content:"\\f17d"}.ld.ld-Calendar:before{content:"\\f17c"}.ld.ld-Camera:before{content:"\\f17b"}.ld.ld-Car:before{content:"\\f17a"}.ld.ld-Card:before{content:"\\f179"}.ld.ld-CaretDown:before{content:"\\f178"}.ld.ld-CaretUp:before{content:"\\f177"}.ld.ld-Chat:before{content:"\\f176"}.ld.ld-Check:before{content:"\\f175"}.ld.ld-CheckCircle:before{content:"\\f174"}.ld.ld-CheckCircleFill:before{content:"\\f173"}.ld.ld-ChevronDown:before{content:"\\f172"}.ld.ld-ChevronLeft:before{content:"\\f171"}.ld.ld-ChevronRight:before{content:"\\f170"}.ld.ld-ChevronUp:before{content:"\\f16f"}.ld.ld-Clock:before{content:"\\f16e"}.ld.ld-Close:before{content:"\\f16d"}.ld.ld-CloseCircleFill:before{content:"\\f16c"}.ld.ld-CloudDownload:before{content:"\\f16b"}.ld.ld-CloudUpload:before{content:"\\f16a"}.ld.ld-Copy:before{content:"\\f169"}.ld.ld-CurrentLocation:before{content:"\\f168"}.ld.ld-Dollar:before{content:"\\f167"}.ld.ld-DollarCircle:before{content:"\\f166"}.ld.ld-DollarCircleFill:before{content:"\\f165"}.ld.ld-Download:before{content:"\\f164"}.ld.ld-Email:before{content:"\\f163"}.ld.ld-ExclamationCircle:before{content:"\\f162"}.ld.ld-ExclamationCircleFill:before{content:"\\f161"}.ld.ld-Eye:before{content:"\\f160"}.ld.ld-EyeSlash:before{content:"\\f15f"}.ld.ld-Facility:before{content:"\\f15e"}.ld.ld-FacilityFill:before{content:"\\f15d"}.ld.ld-Filter:before{content:"\\f15c"}.ld.ld-Flag:before{content:"\\f15b"}.ld.ld-FlagFill:before{content:"\\f15a"}.ld.ld-Flash:before{content:"\\f159"}.ld.ld-FlashFill:before{content:"\\f158"}.ld.ld-FlashSlash:before{content:"\\f157"}.ld.ld-Gear:before{content:"\\f156"}.ld.ld-Gift:before{content:"\\f155"}.ld.ld-GiftFill:before{content:"\\f154"}.ld.ld-Globe:before{content:"\\f153"}.ld.ld-Grid:before{content:"\\f152"}.ld.ld-GridFill:before{content:"\\f151"}.ld.ld-Heart:before{content:"\\f150"}.ld.ld-HeartFill:before{content:"\\f14f"}.ld.ld-History:before{content:"\\f14e"}.ld.ld-Home:before{content:"\\f14d"}.ld.ld-IdCard:before{content:"\\f14c"}.ld.ld-Image:before{content:"\\f14b"}.ld.ld-InfoCircle:before{content:"\\f14a"}.ld.ld-InfoCircleFill:before{content:"\\f149"}.ld.ld-Keyboard:before{content:"\\f148"}.ld.ld-Link:before{content:"\\f147"}.ld.ld-LinkExternal:before{content:"\\f146"}.ld.ld-List:before{content:"\\f145"}.ld.ld-Location:before{content:"\\f144"}.ld.ld-Lock:before{content:"\\f143"}.ld.ld-LockOpen:before{content:"\\f142"}.ld.ld-Magic:before{content:"\\f141"}.ld.ld-MagicFill:before{content:"\\f140"}.ld.ld-Map:before{content:"\\f13f"}.ld.ld-MapFill:before{content:"\\f13e"}.ld.ld-Maximize:before{content:"\\f13d"}.ld.ld-Menu:before{content:"\\f13c"}.ld.ld-Microphone:before{content:"\\f13b"}.ld.ld-MicrophoneSlash:before{content:"\\f13a"}.ld.ld-Minimize:before{content:"\\f139"}.ld.ld-Minus:before{content:"\\f138"}.ld.ld-Mobile:before{content:"\\f137"}.ld.ld-More:before{content:"\\f136"}.ld.ld-MoreAlt:before{content:"\\f135"}.ld.ld-Note:before{content:"\\f134"}.ld.ld-Notebook:before{content:"\\f133"}.ld.ld-Pause:before{content:"\\f132"}.ld.ld-Pencil:before{content:"\\f131"}.ld.ld-Phone:before{content:"\\f130"}.ld.ld-Play:before{content:"\\f12f"}.ld.ld-PlayFill:before{content:"\\f12e"}.ld.ld-Plus:before{content:"\\f12d"}.ld.ld-Printer:before{content:"\\f12c"}.ld.ld-QrCode:before{content:"\\f12b"}.ld.ld-QuestionCircle:before{content:"\\f12a"}.ld.ld-Receipt:before{content:"\\f129"}.ld.ld-Refresh:before{content:"\\f128"}.ld.ld-Returns:before{content:"\\f127"}.ld.ld-Search:before{content:"\\f126"}.ld.ld-Services:before{content:"\\f125"}.ld.ld-ServicesFill:before{content:"\\f124"}.ld.ld-Share:before{content:"\\f123"}.ld.ld-ShareAndroid:before{content:"\\f122"}.ld.ld-SignIn:before{content:"\\f121"}.ld.ld-SignOut:before{content:"\\f120"}.ld.ld-Sliders:before{content:"\\f11f"}.ld.ld-Speaker:before{content:"\\f11e"}.ld.ld-SpeakerSlash:before{content:"\\f11d"}.ld.ld-Star:before{content:"\\f11c"}.ld.ld-StarFill:before{content:"\\f11b"}.ld.ld-StarHalf:before{content:"\\f11a"}.ld.ld-Tag:before{content:"\\f119"}.ld.ld-TagFill:before{content:"\\f118"}.ld.ld-ThumbDown:before{content:"\\f117"}.ld.ld-ThumbDownFill:before{content:"\\f116"}.ld.ld-ThumbUp:before{content:"\\f115"}.ld.ld-ThumbUpFill:before{content:"\\f114"}.ld.ld-Trash:before{content:"\\f113"}.ld.ld-Truck:before{content:"\\f112"}.ld.ld-Undo:before{content:"\\f111"}.ld.ld-User:before{content:"\\f110"}.ld.ld-UserCircle:before{content:"\\f10f"}.ld.ld-UserCircleFill:before{content:"\\f10e"}.ld.ld-UserPlus:before{content:"\\f10d"}.ld.ld-Users:before{content:"\\f10c"}.ld.ld-Video:before{content:"\\f10b"}.ld.ld-Voice:before{content:"\\f10a"}.ld.ld-Wallet:before{content:"\\f109"}.ld.ld-Warning:before{content:"\\f108"}.ld.ld-WarningFill:before{content:"\\f107"}.ld.ld-WiFi:before{content:"\\f106"}.ld.ld-WifiSlash:before{content:"\\f105"}.ld.ld-Wrench:before{content:"\\f104"}.ld.ld-Write:before{content:"\\f103"}.ld.ld-ZoomIn:before{content:"\\f102"}.ld.ld-ZoomOut:before{content:"\\f101"}
    `;

    document.head.appendChild(style);
  }, []);
};

type LivingDesignFontIconProps = {
  style?: CSSProperties;
  className?: string;
  title?: string;
};

export function LivingDesignFontIcon({name, style, className, title}: LivingDesignFontIconProps & {name: string}) {
  const iconSize = style?.fontSize ?? style?.width ?? style?.height;
  const fontSize = typeof iconSize === 'number' ? `${iconSize}px` : iconSize ?? '1em';

  return (
    <i
      aria-hidden="true"
      className={`ld ld-${name}${className ? ` ${className}` : ''}`}
      title={title}
      style={{
        fontSize,
        ...style,
      }}
    />
  );
}

export const SearchIcon = (props: LivingDesignFontIconProps) => <LivingDesignFontIcon name="Search" {...props} />;
export const ChevronUpIcon = (props: LivingDesignFontIconProps) => <LivingDesignFontIcon name="ChevronUp" {...props} />;
export const SettingsIcon = (props: LivingDesignFontIconProps) => <LivingDesignFontIcon name="Gear" {...props} />;
export const StarIcon = (props: LivingDesignFontIconProps) => <LivingDesignFontIcon name="Star" {...props} />;
export const CheckIcon = (props: LivingDesignFontIconProps) => <LivingDesignFontIcon name="Check" {...props} />;
export const PlusIcon = (props: LivingDesignFontIconProps) => <LivingDesignFontIcon name="Plus" {...props} />;
export const InfoIcon = (props: LivingDesignFontIconProps) => <LivingDesignFontIcon name="InfoCircle" {...props} />;
export const AlertTriangleIcon = (props: LivingDesignFontIconProps) => <LivingDesignFontIcon name="Warning" {...props} />;
export const XIcon = (props: LivingDesignFontIconProps) => <LivingDesignFontIcon name="Close" {...props} />;
