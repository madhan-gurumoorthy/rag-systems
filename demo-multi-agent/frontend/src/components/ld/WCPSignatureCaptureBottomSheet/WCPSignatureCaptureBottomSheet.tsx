// @refresh reset

/**
 * @module WCPSignatureCaptureBottomSheet
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
import {BottomSheet} from '../BottomSheet';
import {Button} from '../Button';
import {SignatureBase, SignatureBaseProps} from '../WCPSignatureCapture';
import './WCPSignatureCaptureBottomSheet.css';

export interface WCPSignatureCaptureBottomSheetProps extends SignatureBaseProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  onSubmit?: () => void;
  submitLabel?: string;
  submitDisabled?: boolean;
}

export const WCPSignatureCaptureBottomSheet: React.FunctionComponent<WCPSignatureCaptureBottomSheetProps> = ({
  isOpen,
  onClose,
  title = 'Subscription agreement',
  onSubmit,
  submitLabel = 'Agree & sign',
  submitDisabled = false,
  ...signatureBaseProps
}) => (
  <BottomSheet
    isOpen={isOpen}
    onClose={onClose}
    title={title}
    actions={
      <Button variant="primary" size="medium" isFullWidth onClick={onSubmit} disabled={submitDisabled}>
        {submitLabel}
      </Button>
    }
  >
    <SignatureBase {...signatureBaseProps} />
  </BottomSheet>
);
WCPSignatureCaptureBottomSheet.displayName = 'WCPSignatureCaptureBottomSheet';
