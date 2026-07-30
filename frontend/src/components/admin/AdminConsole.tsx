/** Admin console placeholder — full implementation in S6-10e. */
import { motion } from "framer-motion";

export function AdminConsole() {
  return (
    <motion.div
      className="admin-console"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <h1 className="admin-console__title">Admin Console</h1>
      <p className="admin-console__placeholder">
        Admin Console — full implementation coming in S6-10e.
      </p>
    </motion.div>
  );
}
