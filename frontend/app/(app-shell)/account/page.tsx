"use client";

import { SectionCard } from "@/components/section-card";
import { useStoredShopDomain } from "@/lib/use-stored-shop-domain";

export default function AccountPage() {
  const { shopifyDomain } = useStoredShopDomain();

  return (
    <div className="page-stack">
      <div className="content-grid content-grid-2-1">
        <SectionCard>
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">Workspace</p>
              <h2 className="section-title">Store profile</h2>
            </div>
          </div>

          <div className="signal-list">
            <div className="signal-item">
              <div>
                <p className="signal-title">Connected store</p>
                <p className="signal-copy">
                  {shopifyDomain || "No Shopify domain saved yet"}
                </p>
              </div>
            </div>
            <div className="signal-item">
              <div>
                <p className="signal-title">Environment</p>
                <p className="signal-copy">Manual Shopify MVP</p>
              </div>
            </div>
          </div>
        </SectionCard>

        <SectionCard>
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">User</p>
              <h2 className="section-title section-title-small">Account details</h2>
            </div>
          </div>

          <div className="signal-list">
            <div className="signal-item">
              <div>
                <p className="signal-title">Name</p>
                <p className="signal-copy">Operations Lead</p>
              </div>
            </div>
            <div className="signal-item">
              <div>
                <p className="signal-title">Email</p>
                <p className="signal-copy">operator@store.com</p>
              </div>
            </div>
          </div>
        </SectionCard>
      </div>

      <SectionCard>
        <div className="section-heading">
          <div>
            <p className="section-eyebrow">Preferences</p>
            <h2 className="section-title section-title-small">Personal defaults</h2>
          </div>
        </div>

        <div className="step-list">
          <div className="step-item">
            <strong>Notifications</strong>
            <p>Placeholder area for future stockout, sync, and data quality alerts.</p>
          </div>
          <div className="step-item">
            <strong>Workspace defaults</strong>
            <p>Placeholder area for default landing page, view density, and export settings.</p>
          </div>
        </div>
      </SectionCard>
    </div>
  );
}
