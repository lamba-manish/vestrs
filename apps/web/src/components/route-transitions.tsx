import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import * as React from "react";
import { useLocation } from "react-router-dom";

/**
 * Wraps the route outlet with a subtle fade + 4px translate on path change.
 * Respects `prefers-reduced-motion` — when set, transitions collapse to an
 * instant swap (no animation).
 */
export function RouteTransitions({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const reduce = useReducedMotion();

  const variants = reduce
    ? { initial: {}, animate: {}, exit: {} }
    : {
        initial: { opacity: 0, y: 4 },
        animate: { opacity: 1, y: 0 },
        exit: { opacity: 0, y: -4 },
      };

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={location.pathname}
        initial="initial"
        animate="animate"
        exit="exit"
        variants={variants}
        transition={{ duration: reduce ? 0 : 0.2, ease: "easeOut" }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
