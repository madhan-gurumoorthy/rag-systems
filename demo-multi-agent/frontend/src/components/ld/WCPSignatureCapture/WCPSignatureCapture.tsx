// @refresh reset

/**
 * @module WCPSignatureCapture
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
import {Button} from '../Button';
import {Alert} from '../Alert';
import {Checkbox} from '../Checkbox';
import {TextField} from '../TextField';
import './WCPSignatureCapture.css';

export type WCPSignatureCaptureVariant = 'trigger' | 'terms' | 'base' | 'reauth';

const PencilIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M12.146.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1 0 .708l-9.5 9.5a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168l9.5-9.5zM11.207 2.5 13.5 4.793 14.793 3.5 12.5 1.207 11.207 2.5zm1.586 3L10.5 3.207 4 9.707V10h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.293l6.5-6.5zM3.032 11.032l-.178.178a.5.5 0 0 0-.11.168l-1.5 3.75 3.75-1.5a.5.5 0 0 0 .168-.11l.178-.178H5a.5.5 0 0 1-.5-.5V12.5h-.5A.5.5 0 0 1 3.5 12v-.5h-.468z" fill="currentColor"/>
  </svg>
);

// ── Internal sub-components ──

interface AlertRowProps {
  variant: 'error' | 'warning';
  message: string;
  action?: React.ReactNode;
}

const AlertRow: React.FC<AlertRowProps> = ({variant, message, action}) => (
  <Alert variant={variant}>
    <span>{message}</span>
    {action && <span className="ld-wcp-signaturecapture-alertAction">{action}</span>}
  </Alert>
);

interface SignatureBoxProps {
  label?: string;
  signatureState?: 'unsigned' | 'signed' | 'signed-as';
  signedName?: string;
  size?: 'normal' | 'short';
}

const SignatureBox: React.FC<SignatureBoxProps> = ({label, signatureState = 'unsigned', signedName, size = 'normal'}) => (
  <div className={cx('ld-wcp-signaturecapture-signatureBox', size === 'short' && 'ld-wcp-signaturecapture-signatureBoxShort')}>
    {label && <span className="ld-wcp-signaturecapture-signatureBoxLabel">{label}</span>}
    <div className="ld-wcp-signaturecapture-signatureBoxInner">
      {signatureState === 'signed' && signedName && (
        <>
          <span className="ld-wcp-signaturecapture-signatureName">{signedName}</span>
          <div className="ld-wcp-signaturecapture-signatureDivider" />
        </>
      )}
      {signatureState === 'signed-as' && signedName && (
        <span className="ld-wcp-signaturecapture-signedAsText">Signed as {signedName}</span>
      )}
    </div>
  </div>
);

// ── Trigger variant ──

export interface SignatureTriggerProps {
  subText?: string;
  onAgreeAndSign?: () => void;
}

export const SignatureTrigger: React.FC<SignatureTriggerProps> = ({subText, onAgreeAndSign}) => (
  <div className="ld-wcp-signaturecapture-triggerWrapper">
    <div className="ld-wcp-signaturecapture-ctaSubtext">
      <Button variant="secondary" size="small" isFullWidth onClick={onAgreeAndSign}><PencilIcon /> Agree &amp; sign</Button>
      {subText && <span className="ld-wcp-signaturecapture-subText">{subText}</span>}
    </div>
  </div>
);

// ── Terms variant ──

export interface SignatureTermsProps {
  title?: string;
  signatureState?: 'unsigned' | 'signed' | 'signed-as';
  signedName?: string;
  showPreviewWarning?: boolean;
  onChangeSignature?: () => void;
  onRefreshPage?: () => void;
  subText?: string;
}

export const SignatureTerms: React.FC<SignatureTermsProps> = ({
  title = 'Subscription agreement',
  signatureState = 'unsigned',
  signedName,
  showPreviewWarning,
  onChangeSignature,
  onRefreshPage,
  subText,
}) => (
  <div className="ld-wcp-signaturecapture-termsWrapper">
    <div className="ld-wcp-signaturecapture-titleRow">
      <span className="ld-wcp-signaturecapture-signatureTitle">{title}</span>
      {signatureState !== 'unsigned' && onChangeSignature && (
        <button type="button" className="ld-wcp-signaturecapture-changeSigBtn" onClick={onChangeSignature}>
          Change signature
        </button>
      )}
    </div>
    {showPreviewWarning && onRefreshPage && (
      <AlertRow
        variant="warning"
        message="We couldn't load your signature preview. Please try again."
        action={<button type="button" className="ld-wcp-signaturecapture-alertAction" onClick={onRefreshPage}>Refresh page</button>}
      />
    )}
    <SignatureBox signatureState={signatureState} signedName={signedName} />
    {subText && <span className="ld-wcp-signaturecapture-subText">{subText}</span>}
  </div>
);

// ── Base variant ──

export interface SignatureBaseProps {
  userName?: string;
  showTechError?: boolean;
  showPetNameWarning?: boolean;
  showSignBeforeSubmitError?: boolean;
  showPreviewBeforeSignError?: boolean;
  showCheckboxError?: boolean;
  signatureState?: 'unsigned' | 'signed' | 'signed-as';
  signedName?: string;
  fullName?: string;
  onFullNameChange?: (name: string) => void;
  onPreviewSignature?: () => void;
  isSignChecked?: boolean;
  onSignCheckedChange?: (checked: boolean) => void;
  onRefreshPage?: () => void;
  termsText?: string;
}

export const SignatureBase: React.FC<SignatureBaseProps> = ({
  userName,
  showTechError,
  showPetNameWarning,
  showSignBeforeSubmitError,
  showPreviewBeforeSignError,
  showCheckboxError,
  signatureState = 'unsigned',
  signedName,
  fullName = '',
  onFullNameChange,
  onPreviewSignature,
  isSignChecked = false,
  onSignCheckedChange,
  onRefreshPage,
  termsText = 'By checking this box, I agree to the terms and conditions.',
}) => (
  <div className="ld-wcp-signaturecapture-baseWrapper">
    {showTechError && onRefreshPage && (
      <AlertRow
        variant="error"
        message="Something went wrong. Please refresh the page and try again."
        action={<button type="button" className="ld-wcp-signaturecapture-alertAction" onClick={onRefreshPage}>Refresh page</button>}
      />
    )}
    {showPetNameWarning && (
      <AlertRow variant="warning" message="The name you entered doesn't match your account name. Please use your legal name." />
    )}
    {showSignBeforeSubmitError && (
      <AlertRow variant="error" message="Please sign before submitting." />
    )}
    {showPreviewBeforeSignError && (
      <AlertRow variant="error" message="Please preview your signature before signing." />
    )}

    <div className="ld-wcp-signaturecapture-termsText">
      <span className="ld-wcp-signaturecapture-legalText">{termsText}</span>
    </div>

    <div className="ld-wcp-signaturecapture-signatureSection">
      <span className="ld-wcp-signaturecapture-signatureSectionTitle">Your signature</span>
      {userName && <span className="ld-wcp-signaturecapture-requiredLabel">Account name: {userName}</span>}
      <div className="ld-wcp-signaturecapture-requiredFields">
        <TextField
          label="Full name"
          value={fullName}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => onFullNameChange?.(e.target.value)}
          helperText="Enter your name to preview your signature."
        />
      </div>
      <Button variant="secondary" size="small" onClick={onPreviewSignature}>Preview signature</Button>
      <SignatureBox label="Signature preview" signatureState={signatureState} signedName={signedName} size="short" />
    </div>

    <div className="ld-wcp-signaturecapture-checkboxSection">
      <Checkbox
        label="I agree to sign"
        checked={isSignChecked}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => onSignCheckedChange?.(e.target.checked)}
      />
      {showCheckboxError && (
        <AlertRow variant="error" message="You must agree before signing." />
      )}
    </div>
  </div>
);

// ── Reauth variant ──

export interface SignatureReauthProps {
  subVariant?: 'agree-sign' | 'signed' | 'signed-as';
  signatureState?: 'unsigned' | 'signed' | 'signed-as';
  signedName?: string;
  showReauthError?: boolean;
  showPreviewWarning?: boolean;
  signatureRequired?: string;
  tempHoldText?: string;
  subText?: string;
  onAgreeAndSign?: () => void;
  onConfirm?: () => void;
  onChangeSignature?: () => void;
  onRefreshPage?: () => void;
}

export const SignatureReauth: React.FC<SignatureReauthProps> = ({
  subVariant = 'agree-sign',
  signatureState = 'unsigned',
  signedName,
  showReauthError,
  showPreviewWarning,
  signatureRequired = 'Signature is required for this order.',
  tempHoldText = 'A temporary hold will be placed on your card.',
  subText,
  onAgreeAndSign,
  onConfirm,
  onChangeSignature,
  onRefreshPage,
}) => (
  <div className="ld-wcp-signaturecapture-reauthWrapper">
    {showReauthError && subVariant === 'agree-sign' && (
      <AlertRow
        variant="error"
        message="To place your order, you'll need to agree to and sign the subscription terms."
      />
    )}
    {(subVariant === 'signed' || subVariant === 'signed-as') && showPreviewWarning && (
      <AlertRow
        variant="warning"
        message="We couldn't show your signature preview."
        action={<button type="button" className="ld-wcp-signaturecapture-alertAction" onClick={onRefreshPage}>Refresh page</button>}
      />
    )}

    {(subVariant === 'signed' || subVariant === 'signed-as') ? (
      <>
        <div className="ld-wcp-signaturecapture-titleRow">
          <span className="ld-wcp-signaturecapture-signatureTitle">Your signature</span>
          <button type="button" className="ld-wcp-signaturecapture-changeSigBtn" onClick={onChangeSignature}>
            Change signature
          </button>
        </div>
        <SignatureBox signatureState={subVariant === 'signed-as' ? 'signed-as' : 'signed'} signedName={signedName} size="short" />
        <span className="ld-wcp-signaturecapture-subText">{signatureRequired}</span>
      </>
    ) : (
      <div className="ld-wcp-signaturecapture-ctaSubtext">
        <Button variant="secondary" size="small" isFullWidth onClick={onAgreeAndSign}><PencilIcon /> Agree &amp; sign</Button>
        <span className="ld-wcp-signaturecapture-subText">{signatureRequired}</span>
      </div>
    )}

    <div className="ld-wcp-signaturecapture-holdAndConfirm">
      <span className="ld-wcp-signaturecapture-subText">{tempHoldText}</span>
      <Button variant="primary" size="medium" isFullWidth onClick={onConfirm}>Confirm</Button>
    </div>
  </div>
);

// ── Main component ──

export interface WCPSignatureCaptureProps
  extends Omit<React.ComponentPropsWithoutRef<'div'>, 'className' | 'style'> {
  variant: WCPSignatureCaptureVariant;
  userName?: string;
  signatureState?: 'unsigned' | 'signed' | 'signed-as';
  signedName?: string;
  onAgreeAndSign?: () => void;
  onChangeSignature?: () => void;
  onRefreshPage?: () => void;
  onConfirm?: () => void;
  subText?: string;
  title?: string;
  showPreviewWarning?: boolean;
  showTechError?: boolean;
  showPetNameWarning?: boolean;
  showSignBeforeSubmitError?: boolean;
  showPreviewBeforeSignError?: boolean;
  showCheckboxError?: boolean;
  fullName?: string;
  onFullNameChange?: (name: string) => void;
  onPreviewSignature?: () => void;
  isSignChecked?: boolean;
  onSignCheckedChange?: (checked: boolean) => void;
  reauthSubVariant?: 'agree-sign' | 'signed' | 'signed-as';
  showReauthError?: boolean;
  UNSAFE_className?: string;
  UNSAFE_style?: React.CSSProperties;
}

export const WCPSignatureCapture: React.FunctionComponent<WCPSignatureCaptureProps> = (props) => {
  const {
    variant, userName, signatureState, signedName,
    onAgreeAndSign, onChangeSignature, onRefreshPage, onConfirm,
    subText, title, showPreviewWarning, showTechError,
    showPetNameWarning, showSignBeforeSubmitError, showPreviewBeforeSignError,
    showCheckboxError, fullName, onFullNameChange, onPreviewSignature,
    isSignChecked, onSignCheckedChange, reauthSubVariant, showReauthError,
    className, ...rest
  } = applyCommonProps(props);

  return (
    <div className={cx('ld-wcp-signaturecapture-capture', className)} {...rest}>
      {variant === 'trigger' && (
        <SignatureTrigger subText={subText} onAgreeAndSign={onAgreeAndSign} />
      )}
      {variant === 'terms' && (
        <SignatureTerms
          title={title}
          signatureState={signatureState}
          signedName={signedName}
          showPreviewWarning={showPreviewWarning}
          onChangeSignature={onChangeSignature}
          onRefreshPage={onRefreshPage}
          subText={subText}
        />
      )}
      {variant === 'base' && (
        <SignatureBase
          userName={userName}
          showTechError={showTechError}
          showPetNameWarning={showPetNameWarning}
          showSignBeforeSubmitError={showSignBeforeSubmitError}
          showPreviewBeforeSignError={showPreviewBeforeSignError}
          showCheckboxError={showCheckboxError}
          signatureState={signatureState}
          signedName={signedName}
          fullName={fullName}
          onFullNameChange={onFullNameChange}
          onPreviewSignature={onPreviewSignature}
          isSignChecked={isSignChecked}
          onSignCheckedChange={onSignCheckedChange}
          onRefreshPage={onRefreshPage}
        />
      )}
      {variant === 'reauth' && (
        <SignatureReauth
          subVariant={reauthSubVariant}
          signatureState={signatureState}
          signedName={signedName}
          showReauthError={showReauthError}
          showPreviewWarning={showPreviewWarning}
          onAgreeAndSign={onAgreeAndSign}
          onConfirm={onConfirm}
          onChangeSignature={onChangeSignature}
          onRefreshPage={onRefreshPage}
          subText={subText}
        />
      )}
    </div>
  );
};
WCPSignatureCapture.displayName = 'WCPSignatureCapture';
