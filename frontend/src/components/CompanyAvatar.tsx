"use client";

import { useState } from "react";
import { companyDomain, companyInitials, faviconUrl } from "@/lib/ui";

interface CompanyAvatarProps {
  name: string;
  /** Tailwind size + radius classes for the outer chip (e.g. "w-9 h-9 rounded-md"). */
  className?: string;
  /** Initials font-size class for the fallback. */
  textClassName?: string;
}

/**
 * Company avatar: shows the brand's real favicon on a clean tile, falling back
 * to monochrome initials (bg-muted) when no logo resolves — so it sits naturally
 * in the neutral design system, with the favicon as the only spot of brand color.
 * The fallback renders underneath immediately, so there is never an empty frame
 * while the favicon loads.
 *
 * One source of truth for the "company chip" — shared by the browse card and the
 * detail pane instead of duplicated markup in each.
 */
export default function CompanyAvatar({
  name,
  className = "w-9 h-9 rounded-md",
  textClassName = "text-xs",
}: CompanyAvatarProps) {
  const domain = companyDomain(name);
  const [logoOk, setLogoOk] = useState(false);
  const [logoFailed, setLogoFailed] = useState(false);
  const showLogo = !!domain && !logoFailed;

  return (
    <div
      className={`relative flex items-center justify-center overflow-hidden shrink-0 border border-border ${
        logoOk ? "bg-white" : "bg-muted"
      } ${className}`}
    >
      {/* Fallback layer — initials. Hidden once a logo loads. */}
      {!logoOk && (
        <span className={`font-semibold text-foreground ${textClassName}`}>{companyInitials(name)}</span>
      )}
      {/* Real favicon. Fades in on load; on error we drop back to the initials. */}
      {showLogo && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={faviconUrl(domain, 64)}
          alt=""
          loading="lazy"
          onLoad={() => setLogoOk(true)}
          onError={() => setLogoFailed(true)}
          className={`absolute inset-0 w-full h-full object-contain p-1.5 transition-opacity duration-200 ${
            logoOk ? "opacity-100" : "opacity-0"
          }`}
        />
      )}
    </div>
  );
}
