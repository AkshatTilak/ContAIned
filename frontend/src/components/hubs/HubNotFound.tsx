/**
 * HubNotFound — rendered when the hub id in the URL resolves to a 404.
 *
 * Per hubs.md §5.2 the API returns 404 for both non-existent and non-member
 * hubs, so the copy must never imply the hub exists; it must not leak hub
 * existence to unauthorised callers.
 */

import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { routes } from "../../routes";

export function HubNotFound() {
  const navigate = useNavigate();

  return (
    <motion.div
      className="hub-not-found"
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
    >
      <div className="hub-not-found__icon" aria-hidden="true">
        <svg
          width="64"
          height="64"
          viewBox="0 0 64 64"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle cx="32" cy="32" r="31" stroke="var(--border-subtle)" strokeWidth="1.5" />
          <path
            d="M20 32h24M32 20v24"
            stroke="var(--text-muted)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray="4 4"
          />
          <circle cx="32" cy="32" r="6" fill="var(--bg-elevated)" stroke="var(--border-subtle)" strokeWidth="1.5" />
        </svg>
      </div>

      <h1 className="hub-not-found__title">Hub not found</h1>
      <p className="hub-not-found__body">
        This hub doesn't exist or you don't have access to it. If you believe
        this is an error, ask a hub owner to check your membership.
      </p>

      <button
        id="hub-not-found-back-btn"
        className="btn btn--primary"
        onClick={() => navigate(routes.hubs.directory())}
      >
        Back to Hub Directory
      </button>
    </motion.div>
  );
}
