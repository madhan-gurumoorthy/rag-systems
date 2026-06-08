// @refresh reset

/**
 * @module WCPUploadImage
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
import {cx, applyCommonProps} from '../common';
import {CloseIcon, ExclamationCircleIcon} from '../Icons';
import './WCPUploadImage.css';

const MAX_IMAGES = 5;

export interface UploadedImage {
  id: string;
  src: string;
  file: File;
}

export interface WCPUploadImageProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style' | 'onChange'> {
  images?: UploadedImage[];
  onChange?: (images: UploadedImage[]) => void;
  /** @default 5 */
  maxImages?: number;
  invalid?: boolean;
  errorMessage?: string;
  photoTip?: string;
  label?: string;
  subLabel?: string;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

export const WCPUploadImage: React.FunctionComponent<WCPUploadImageProps> = (props) => {
  const {
    images = [],
    onChange,
    maxImages = MAX_IMAGES,
    invalid = false,
    errorMessage = "Invalid file type. Choose a file that's a PNG, GIF, JPG, JPEG, HEIC or TIFF.",
    photoTip = 'show us a clear photo of the item, highlighting any notable details.',
    label = 'Show us what it looks like',
    subLabel = 'Add up to 5 photos, 5MB max each.',
    className,
    ...rest
  } = applyCommonProps(props);

  const inputRef = React.useRef<HTMLInputElement>(null);
  const isEmpty = images.length === 0;
  const canAddMore = images.length < maxImages;
  const remainingSlots = Math.max(0, maxImages - images.length);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    const newImages: UploadedImage[] = [];
    for (const file of files) {
      if (images.length + newImages.length >= maxImages) break;
      const src = URL.createObjectURL(file);
      newImages.push({id: `${Date.now()}-${file.name}`, src, file});
    }
    onChange?.([...images, ...newImages]);
    e.target.value = '';
  }

  function handleRemove(id: string) {
    onChange?.(images.filter((img) => img.id !== id));
  }

  function openFilePicker() {
    inputRef.current?.click();
  }

  return (
    <div className={cx('ld-wcp-uploadimage-root', className)} {...rest}>
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/gif,image/jpg,image/jpeg,image/heic,image/tiff,.heic,.tiff"
        multiple
        className="ld-wcp-uploadimage-hiddenInput"
        onChange={handleFileChange}
        aria-hidden="true"
        tabIndex={-1}
      />

      <div className="ld-wcp-uploadimage-header">
        <span className="ld-wcp-uploadimage-labelBold">{label}</span>{' '}
        <span className="ld-wcp-uploadimage-labelNormal">{subLabel}</span>
      </div>

      {invalid && (
        <div className="ld-wcp-uploadimage-errorAlert" role="alert">
          <div className="ld-wcp-uploadimage-errorTab" aria-hidden="true" />
          <div className="ld-wcp-uploadimage-errorContent">
            <ExclamationCircleIcon size="small" className="ld-wcp-uploadimage-errorIcon" />
            <span className="ld-wcp-uploadimage-errorMessage">{errorMessage}</span>
          </div>
        </div>
      )}

      {isEmpty ? (
        <button type="button" className="ld-wcp-uploadimage-wideTile" onClick={openFilePicker} aria-label="Add photos">
          <i className="ld ld-Plus" aria-hidden="true" style={{fontSize: '32px'}} />
        </button>
      ) : (
        <div className="ld-wcp-uploadimage-tilesRow">
          {images.map((img, idx) => {
            const imgLabel = img.file?.name || `Uploaded photo ${idx + 1} of ${images.length}`;
            return (
              <div key={img.id} className="ld-wcp-uploadimage-uploadedTile">
                <img src={img.src} alt={imgLabel} className="ld-wcp-uploadimage-uploadedImg" />
                <button type="button" className="ld-wcp-uploadimage-removeBtn" onClick={() => handleRemove(img.id)} aria-label={`Remove ${imgLabel}`}>
                  <CloseIcon size="small" />
                </button>
              </div>
            );
          })}
          {canAddMore &&
            Array.from({length: remainingSlots}).map((_, i) => (
              <button
                key={`empty-${i}`}
                type="button"
                className={cx('ld-wcp-uploadimage-squareTile', i > 0 && 'ld-wcp-uploadimage-squareTileGhost')}
                onClick={openFilePicker}
                aria-label="Add photo"
                disabled={i > 0}
                tabIndex={i === 0 ? 0 : -1}
              >
                <i className="ld ld-Plus" aria-hidden="true" style={{fontSize: '32px'}} />
              </button>
            ))}
        </div>
      )}

      <p className="ld-wcp-uploadimage-photoTip">
        <strong className="ld-wcp-uploadimage-photoTipBold">Photo tip:</strong>{' '}
        {photoTip}
      </p>
    </div>
  );
};

WCPUploadImage.displayName = 'WCPUploadImage';
