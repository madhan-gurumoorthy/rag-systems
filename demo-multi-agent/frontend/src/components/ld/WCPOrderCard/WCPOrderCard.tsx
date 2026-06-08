// @refresh reset

/**
 * @module WCPOrderCard
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
import { useState } from "react";
import { Button } from '../Button';
import { ProgressTracker, ProgressTrackerItem } from '../ProgressTracker';
import { Alert } from '../Alert';
import { Divider } from '../Divider';
import { Link } from '../Link';
import './WCPOrderCard.css';

export type OrderType = "curbside" | "delivery" | "shipping" | "store" | "auto";
export type TimelineStep = "placed" | "preparing" | "on-the-way" | "delivered";

export interface OrderProduct {
  src: string;
  alt: string;
}

export interface OrderAction {
  label: string;
  variant: "primary" | "secondary";
  onClick?: () => void;
}

export interface ServiceDetails {
  vehicle: string;
  services: string[];
  appointmentContact?: string;
  storePhone?: string;
  storeHours?: string;
  serviceInstructions?: string;
  appointmentStep?: number; // 0=Scheduled, 1=Ready to service, 2=Serviced
}

export interface WCPOrderCardProps {
  orderType: OrderType;
  location?: string;
  seller?: string;
  fulfilledBy?: string;
  statusHeading: string;
  timelineStep?: TimelineStep;
  timelineVariant?: "delivery" | "pickup";
  isDelayed?: boolean;
  products: OrderProduct[];
  actions?: OrderAction[];
  orderTotal?: string;
  showStartReturn?: boolean;
  returnNotice?: string;
  returnDeadline?: string;
  addItemsBanner?: string;
  serviceDetails?: ServiceDetails;
}

const ORDER_TYPE_LABELS: Record<OrderType, string> = {
  curbside: "Curbside pickup",
  delivery: "Delivery from store",
  shipping: "Shipping",
  store: "Store purchase",
  auto: "Auto Care Center",
};

const EXPERIENCE_LABELS: Record<OrderType, string> = {
  curbside: "pickup",
  delivery: "delivery",
  shipping: "shipping",
  store: "in-store",
  auto: "Auto Care",
};

const FULFILLMENT_ICONS: Record<OrderType, string> = {
  curbside:
    "https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Feb8e854b1c2441668631c59d482af3f2",
  delivery:
    "https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F06ac09fed4534c02b62a8d43e759a824",
  store:
    "https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F4ed8486e018848678a23689dc195dcd8",
  shipping:
    "https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2Fae074f13699f44c0a142fc357711a02e",
  auto:
    "https://cdn.builder.io/api/v1/image/assets%2F02297b1ff48d4a2f8e4d9ed415c47ecf%2F26a934c359774221bf674b2fb62d93da",
};

const DELIVERY_STEPS = ["Placed", "Preparing", "On the way", "Delivered"];
const PICKUP_STEPS = ["Placed", "Preparing", "Ready", "Picked up"];
const AUTO_STEPS = ["Scheduled", "Ready to service", "Serviced"];

const STEP_INDEX: Record<TimelineStep, number> = {
  placed: 0,
  preparing: 1,
  "on-the-way": 2,
  delivered: 3,
};

function RatingWidget({ orderType }: { orderType: OrderType }) {
  const [selected, setSelected] = useState(0);

  const stars = [1, 2, 3, 4, 5];

  if (selected > 0) {
    return (
      <div className="ld-wcp-order-card-rating-wrap">
        <div className="ld-wcp-order-card-rating-stars">
          {stars.map((s) => (
            <svg key={s} width="20" height="20" viewBox="0 0 24 24" fill={s <= selected ? "#F5A623" : "none"} stroke="#F5A623" strokeWidth="2">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
            </svg>
          ))}
        </div>
        <p className="ld-wcp-order-card-rating-thanks">
          Thanks for your feedback!
        </p>
      </div>
    );
  }

  return (
    <div className="ld-wcp-order-card-rating-wrap">
      <p className="ld-wcp-order-card-rating-prompt">
        How was your {EXPERIENCE_LABELS[orderType]} experience?
      </p>
      <p className="ld-wcp-order-card-rating-subtitle">
        Select a rating to begin quick survey.
      </p>
      <div className="ld-wcp-order-card-rating-stars-interactive">
        {stars.map((s) => (
          <button
            key={s}
            onClick={() => setSelected(s)}
            aria-label={`${s} star${s > 1 ? "s" : ""}`}
            className="ld-wcp-order-card-star-btn"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F5A623" strokeWidth="2">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
            </svg>
          </button>
        ))}
      </div>
    </div>
  );
}

export function WCPOrderCard({
  orderType,
  location,
  seller,
  fulfilledBy,
  statusHeading,
  timelineStep,
  timelineVariant = "delivery",
  isDelayed = false,
  products,
  actions = [],
  orderTotal,
  showStartReturn = false,
  returnNotice,
  returnDeadline,
  addItemsBanner,
  serviceDetails,
}: WCPOrderCardProps) {
  const primaryActions = actions.filter((a) => a.variant === "primary");
  const secondaryActions = actions.filter((a) => a.variant === "secondary");

  const steps = timelineVariant === "pickup" ? PICKUP_STEPS : DELIVERY_STEPS;
  const activeStep = timelineStep ? STEP_INDEX[timelineStep] : undefined;
  const trackerVariant = isDelayed
    ? "warning"
    : timelineStep === "delivered"
      ? "success"
      : "info";

  return (
    <article className="ld-wcp-order-card-root">
      {/* Amends Banner */}
      {addItemsBanner && (
        <div className="ld-wcp-order-card-amends-banner">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="ld-wcp-order-card-amends-icon">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 6v6l4 2" />
          </svg>
          {addItemsBanner}
        </div>
      )}

      <div className="ld-wcp-order-card-body">
        {/* Left column */}
        <div className="ld-wcp-order-card-left">
          {/* Fulfillment type + location + status */}
          <div className="ld-wcp-order-card-fulfillment-wrap">
            <div className="ld-wcp-order-card-fulfillment-row">
              <img
                src={FULFILLMENT_ICONS[orderType]}
                alt=""
                aria-hidden="true"
                width={64}
                height={64}
                className="ld-wcp-order-card-fulfillment-icon"
              />
              <div className="ld-wcp-order-card-fulfillment-text">
                <span className="ld-wcp-order-card-type-label">
                  {ORDER_TYPE_LABELS[orderType]}
                </span>
                {location && (
                  <span className="ld-wcp-order-card-location">
                    {location}
                  </span>
                )}
                <h3 className="ld-wcp-order-card-status-heading">
                  {statusHeading}
                </h3>
              </div>
            </div>
            {seller && (
              <span className="ld-wcp-order-card-seller">
                Sold by{" "}
                <Link href="#">{seller}</Link>
                {fulfilledBy && <> | Fulfilled by {fulfilledBy}</>}
              </span>
            )}
          </div>

          {/* LD ProgressTracker -- delivery/pickup */}
          {timelineStep && activeStep !== undefined && (
            <div className="ld-wcp-order-card-timeline">
              <ProgressTracker activeIndex={activeStep} variant={trackerVariant}>
                {steps.map((label) => (
                  <ProgressTrackerItem key={label}>{label}</ProgressTrackerItem>
                ))}
              </ProgressTracker>
            </div>
          )}

          {/* Auto Care appointment tracker */}
          {orderType === "auto" && serviceDetails?.appointmentStep !== undefined && (
            <div className="ld-wcp-order-card-timeline">
              <ProgressTracker activeIndex={serviceDetails.appointmentStep} variant="info">
                {AUTO_STEPS.map((label) => (
                  <ProgressTrackerItem key={label}>{label}</ProgressTrackerItem>
                ))}
              </ProgressTracker>
            </div>
          )}

          {/* Return notices */}
          {returnNotice && (
            <div className="ld-wcp-order-card-notice">
              <Alert variant="info">{returnNotice}</Alert>
            </div>
          )}
          {returnDeadline && (
            <div className="ld-wcp-order-card-notice">
              <Alert variant="info">Return by {returnDeadline}</Alert>
            </div>
          )}

          {/* Service details (auto appointments) */}
          {serviceDetails && (
            <div className="ld-wcp-order-card-service-details">
              <span className="ld-wcp-order-card-vehicle-name">
                {serviceDetails.vehicle}
              </span>
              <ul className="ld-wcp-order-card-services-list">
                {serviceDetails.services.map((s, i) => (
                  <li
                    key={i}
                    className="ld-wcp-order-card-service-item"
                  >
                    <span className="ld-wcp-order-card-service-bullet" />
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Product images (up to 8) */}
          {products.length > 0 && (
            <div className="ld-wcp-order-card-products">
              {products.slice(0, 8).map((p, i) => (
                <img
                  key={i}
                  src={p.src}
                  alt={p.alt}
                  className="ld-wcp-order-card-product-img"
                />
              ))}
            </div>
          )}
        </div>

        {/* Right column: action buttons */}
        {actions.length > 0 && (
          <div className="ld-wcp-order-card-actions">
            {primaryActions.map((a) => (
              <Button
                key={a.label}
                variant="primary"
                size="small"
                isFullWidth
                onClick={a.onClick}
              >
                {a.label}
              </Button>
            ))}
            {secondaryActions.map((a) => (
              <Button
                key={a.label}
                variant="secondary"
                size="small"
                isFullWidth
                onClick={a.onClick}
              >
                {a.label}
              </Button>
            ))}
          </div>
        )}
      </div>

      {/* Rating -- shown for delivered orders */}
      {timelineStep === "delivered" && (
        <>
          <Divider />
          <RatingWidget orderType={orderType} />
        </>
      )}

      {/* Footer */}
      <Divider />
      <div className="ld-wcp-order-card-footer">
        {showStartReturn && (
          <Link href="#">Start a return</Link>
        )}
        <span className="ld-wcp-order-card-footer-spacer" />
        {orderTotal && (
          <span className="ld-wcp-order-card-order-total">
            Order total {orderTotal}
          </span>
        )}
      </div>
    </article>
  );
}
WCPOrderCard.displayName = 'WCPOrderCard';
